"""CP15: django-filter ``FilterSet`` classes for the communications API.

Date-range filtering follows this project's established naming
convention — ``<field>_from``/``<field>_to`` `DateTimeFilter` pairs with
``gte``/``lte`` lookups, exactly as ``apps.attendance.filters``'s
``login_from``/``login_to`` already does — rather than inventing a new
``__gte``-style query-parameter shape for this app alone.

Every filter here is a *read* concern only: filtering narrows what a
caller already has permission to see (``scope_queryset_for_user()`` runs
first, in ``_CrmModelViewSet.get_queryset()``). A filter can therefore
never widen access — an Employee passing ``owner=<someone else>`` gets an
empty page, not another employee's rows.
"""
import django_filters

from .models import Call, CommunicationLog, EmailMessage, EmailTemplate, Notification, WhatsAppMessage


class EmailTemplateFilterSet(django_filters.FilterSet):
    class Meta:
        model = EmailTemplate
        fields = ["is_active"]


class EmailMessageFilterSet(django_filters.FilterSet):
    created_from = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_to = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    sent_from = django_filters.DateTimeFilter(field_name="sent_at", lookup_expr="gte")
    sent_to = django_filters.DateTimeFilter(field_name="sent_at", lookup_expr="lte")

    class Meta:
        model = EmailMessage
        fields = ["status", "direction", "owner", "template", "content_type", "object_id"]


class NotificationFilterSet(django_filters.FilterSet):
    class Meta:
        model = Notification
        fields = ["notification_type", "is_read", "recipient", "content_type", "object_id"]


class CommunicationLogFilterSet(django_filters.FilterSet):
    occurred_from = django_filters.DateTimeFilter(field_name="occurred_at", lookup_expr="gte")
    occurred_to = django_filters.DateTimeFilter(field_name="occurred_at", lookup_expr="lte")

    class Meta:
        model = CommunicationLog
        fields = ["channel", "actor", "content_type", "object_id"]


class CallFilterSet(django_filters.FilterSet):
    """Calls, filterable by the same axes the audit trail is queried on:
    who (``owner``), which contact (``content_type``+``object_id``, the
    generic entity link every `RelatedToEntityModel` shares), which
    direction, which outcome (``status``), and when.

    ``started_from``/``started_to`` filter on the moment the provider
    actually began the call; ``created_from``/``created_to`` on the moment
    the CRM recorded the attempt — a FAILED call that never reached the
    provider has no ``started_at`` at all, so both pairs exist and neither
    can be dropped without making one of those two questions unanswerable.
    """

    started_from = django_filters.DateTimeFilter(field_name="started_at", lookup_expr="gte")
    started_to = django_filters.DateTimeFilter(field_name="started_at", lookup_expr="lte")
    created_from = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_to = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = Call
        fields = ["status", "direction", "owner", "content_type", "object_id"]


class WhatsAppMessageFilterSet(django_filters.FilterSet):
    """`WhatsAppMessage` has no generic entity link (see ``models.py`` — it
    models a ``customer`` relation only), so ``customer`` is the
    per-contact filter here, in place of the ``content_type``/``object_id``
    pair the other channels use.
    """

    created_from = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_to = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = WhatsAppMessage
        fields = ["status", "direction", "owner", "customer"]
