"""CP18: the integrations domain's REST API.

Every viewset reuses CP10's ``_CrmModelViewSet`` (``apps.crm.views``)
directly — all four models here have a real or delegating ``owner``, the
same cross-app reuse CP12/CP14/CP15/CP16/CP17 already established.
"""
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import assert_object_accessible
from apps.core.utils import stamp_audit_fields
from apps.crm.services import resolve_owner_for_create
from apps.crm.views import _CrmModelViewSet

from .filters import (
    APIKeyFilterSet,
    IntegrationFilterSet,
    WebhookDeliveryFilterSet,
    WebhookEndpointFilterSet,
)
from .models import APIKey, Integration, WebhookDelivery, WebhookEndpoint
from .serializers import (
    APIKeySerializer,
    APIKeyWithSecretSerializer,
    IntegrationSerializer,
    WebhookDeliverySerializer,
    WebhookEndpointSerializer,
)
from .services import (
    create_webhook_endpoint,
    deliver_webhook,
    generate_api_key,
    regenerate_webhook_secret,
    revoke_api_key,
    rotate_api_key,
)


class IntegrationViewSet(_CrmModelViewSet):
    base_manager = Integration.objects
    base_active_manager = Integration.active_objects
    serializer_class = IntegrationSerializer
    filterset_class = IntegrationFilterSet
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["name"]

    def get_queryset(self):
        return super().get_queryset().select_related("owner")

    def perform_create(self, serializer):
        """Defaults ``owner`` to the requesting user when not explicitly
        supplied — the same rule ``WorkflowViewSet``/``SavedReportViewSet``
        already apply.
        """
        super().perform_create(serializer)
        integration = serializer.instance
        resolved_owner = resolve_owner_for_create(self.request.user, integration.owner)
        if resolved_owner.pk != integration.owner_id:
            integration.owner = resolved_owner
            integration.save(update_fields=["owner", "updated_at"])


class _GenerateAPIKeySerializer(serializers.Serializer):
    """Write-only input shape for ``APIKeyViewSet.create()`` — an `APIKey`
    has no client-supplied secret (it's generated server-side), so
    ``name``/``integration``/``expires_at`` is the entire writable input,
    distinct from what `APIKeySerializer` reads back out.
    """

    integration = serializers.PrimaryKeyRelatedField(queryset=Integration.objects.all())
    name = serializers.CharField(max_length=200)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)


class APIKeyViewSet(_CrmModelViewSet):
    """``create()`` is overridden entirely: an `APIKey`'s secret is
    generated, never supplied by the client, so the input shape
    (``_GenerateAPIKeySerializer``) is deliberately different from the
    output shape (``APIKeySerializer``/``APIKeyWithSecretSerializer``) —
    the same "input union doesn't map onto the model's own fields"
    reasoning CP15's ``EmailMessageViewSet.create()``/CP17's
    ``WorkflowViewSet.execute`` both already apply.
    """

    base_manager = APIKey.objects
    base_active_manager = APIKey.active_objects
    serializer_class = APIKeySerializer
    filterset_class = APIKeyFilterSet
    owner_field = "integration__owner"
    search_fields = ["name", "key_prefix"]
    ordering_fields = ["created_at", "last_used_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return super().get_queryset().select_related("integration", "integration__owner")

    @extend_schema(request=_GenerateAPIKeySerializer, responses={201: APIKeyWithSecretSerializer})
    def create(self, request, *args, **kwargs):
        """``POST /api-keys/`` — generates a new key
        (``services.generate_api_key()``) and returns it WITH the raw
        secret, exactly once (see `serializers.py`'s
        `APIKeyWithSecretSerializer` docstring).
        """
        input_serializer = _GenerateAPIKeySerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        data = input_serializer.validated_data
        assert_object_accessible(request, data["integration"])

        api_key, raw_key = generate_api_key(
            data["integration"], data["name"], expires_at=data.get("expires_at")
        )
        stamp_audit_fields(api_key, request.user, creating=True)
        api_key.save()
        api_key.raw_key = raw_key

        output_serializer = APIKeyWithSecretSerializer(api_key)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={200: APIKeyWithSecretSerializer})
    @action(detail=True, methods=["post"])
    def rotate(self, request, *args, **kwargs):
        """``POST /api-keys/<id>/rotate/`` — replaces this key's secret
        (``services.rotate_api_key()``), returning the new raw key ONCE;
        rejects an already-revoked key.
        """
        api_key = self.get_object()
        try:
            _, raw_key = rotate_api_key(api_key)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        api_key.raw_key = raw_key
        serializer = APIKeyWithSecretSerializer(api_key)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(request=None, responses={200: APIKeySerializer})
    @action(detail=True, methods=["post"])
    def revoke(self, request, *args, **kwargs):
        """``POST /api-keys/<id>/revoke/`` — permanently disables this
        key (``services.revoke_api_key()``); rejects an already-revoked
        key.
        """
        api_key = self.get_object()
        try:
            revoke_api_key(api_key)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(api_key)
        return Response(serializer.data, status=status.HTTP_200_OK)


class WebhookEndpointViewSet(_CrmModelViewSet):
    base_manager = WebhookEndpoint.objects
    base_active_manager = WebhookEndpoint.active_objects
    serializer_class = WebhookEndpointSerializer
    filterset_class = WebhookEndpointFilterSet
    owner_field = "integration__owner"
    search_fields = ["url"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return super().get_queryset().select_related("integration", "integration__owner")

    def perform_create(self, serializer):
        """Routes creation through ``services.create_webhook_endpoint()``
        — real behavior: generates the signing ``secret`` server-side
        (``secret`` is read-only on the serializer — see
        `serializers.py` — so a bare ``serializer.save()`` would leave it
        blank).
        """
        data = dict(serializer.validated_data)
        integration = data.pop("integration")
        assert_object_accessible(self.request, integration)
        url = data.pop("url")
        event_types = data.pop("event_types", None)

        endpoint = create_webhook_endpoint(integration, url, event_types=event_types)
        stamp_audit_fields(endpoint, self.request.user, creating=True)
        endpoint.save()
        serializer.instance = endpoint

    @extend_schema(request=None, responses={200: WebhookEndpointSerializer})
    @action(detail=True, methods=["post"], url_path="regenerate-secret")
    def regenerate_secret(self, request, *args, **kwargs):
        """``POST /webhook-endpoints/<id>/regenerate-secret/`` — replaces
        this endpoint's signing secret (``services.regenerate_webhook_secret()``).
        """
        endpoint = self.get_object()
        regenerate_webhook_secret(endpoint)
        serializer = self.get_serializer(endpoint)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(request=None, responses={201: WebhookDeliverySerializer})
    @action(detail=True, methods=["post"])
    def deliver(self, request, *args, **kwargs):
        """``POST /webhook-endpoints/<id>/deliver/`` — ``{"event_type":
        ..., "payload": {...}}``. Attempts delivery now
        (``services.deliver_webhook()``), returning the resulting
        ``WebhookDelivery``, DELIVERED or FAILED.
        """
        endpoint = self.get_object()
        event_type = request.data.get("event_type")
        payload = request.data.get("payload", {})
        if not event_type:
            return Response({"detail": "event_type is required."}, status=status.HTTP_400_BAD_REQUEST)

        delivery = deliver_webhook(endpoint, event_type, payload)
        serializer = WebhookDeliverySerializer(delivery)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class WebhookDeliveryViewSet(_CrmModelViewSet):
    """Read-only — ``http_method_names`` excludes every write verb, so
    there is no create/update/delete/restore/hard-delete route (DRF
    returns 405 for any of them), matching this model's own "written
    automatically by ``deliver_webhook()``, never by a client" design —
    the same integrity-boundary pattern CP15's ``CommunicationLogViewSet``/
    CP16's ``ReportExecutionViewSet``/CP17's ``WorkflowExecutionViewSet``
    established.
    """

    base_manager = WebhookDelivery.objects
    base_active_manager = WebhookDelivery.active_objects
    serializer_class = WebhookDeliverySerializer
    filterset_class = WebhookDeliveryFilterSet
    owner_field = "endpoint__integration__owner"
    http_method_names = ["get", "head", "options"]
    search_fields = ["event_type"]
    ordering_fields = ["created_at", "delivered_at", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return super().get_queryset().select_related("endpoint", "endpoint__integration")
