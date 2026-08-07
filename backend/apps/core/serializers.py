"""CP7: reusable serializer mixins for the abstract models in models.py.

None of these are usable standalone (there is no concrete model to point a
``ModelSerializer`` at yet — CP7 is infrastructure only, same as CP6). They
are mixins a future domain serializer (``LeadSerializer``, ``CustomerSerializer``,
...) combines with its own ``serializers.ModelSerializer`` so every future
resource exposes timestamps/audit/soft-delete fields in the exact same
shape and with the exact same safety rules, instead of each domain app
reinventing "should ``created_by`` be writable" on its own.
"""
from rest_framework import serializers


class TimeStampedSerializerMixin(serializers.Serializer):
    """Adds read-only ``created_at``/``updated_at``.

    Always read-only: a client can never set or edit either timestamp
    directly — both are server-managed (``auto_now_add``/``auto_now`` on
    ``TimeStampedModel``). A future concrete serializer's ``Meta.fields``
    still has to list ``"created_at"``/``"updated_at"`` for them to actually
    appear in output (mixing this in only defines *how* those fields
    behave, not that they're included) — see the usage example in
    BACKEND_LEARNING_GUIDE.md CP7.
    """

    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class AuditSerializerMixin(serializers.Serializer):
    """Adds read-only ``created_by``/``updated_by`` (as plain user IDs).

    Read-only for the same reason as the timestamps above: which user
    created/last-updated a record is derived from the request, never
    supplied by the client — see ``apps/core/utils.py``'s
    ``stamp_audit_fields()``, the intended call site for actually setting
    these. Exposed as bare primary keys (not a nested user object) to keep
    this mixin dependency-free of any particular "safe user" serializer
    shape; a concrete serializer that wants the full nested user can add its
    own ``SerializerMethodField`` alongside this mixin.
    """

    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    updated_by = serializers.PrimaryKeyRelatedField(read_only=True)


class SoftDeleteSerializerMixin(serializers.Serializer):
    """Adds read-only ``is_deleted``/``deleted_at``.

    Read-only here too: soft-deleting/restoring a record is an *action*
    (``apps/core/utils.py``'s ``soft_delete()``/``restore()``, or a future
    dedicated endpoint calling them), never a plain field edit through a
    normal update payload — allowing ``is_deleted`` to be PATCHed directly
    would let any writer bypass whatever audit/permission rules a future
    "restore" endpoint enforces (e.g. CP7's own ``CanRestoreOrHardDelete``
    permission, see ``apps/core/permissions.py``).
    """

    is_deleted = serializers.BooleanField(read_only=True)
    deleted_at = serializers.DateTimeField(read_only=True, allow_null=True)


class SoftDeleteTimeStampedSerializerMixin(
    TimeStampedSerializerMixin, SoftDeleteSerializerMixin, AuditSerializerMixin
):
    """Combines all three mixins above — the base most future domain
    serializers are expected to mix in, mirroring ``SoftDeleteTimeStampedModel``
    on the model side.

    Example (illustrative only — no concrete model exists yet in CP7)::

        class LeadSerializer(SoftDeleteTimeStampedSerializerMixin, serializers.ModelSerializer):
            class Meta:
                model = Lead
                fields = [
                    "id", "name", "email",
                    "created_at", "updated_at",
                    "created_by", "updated_by",
                    "is_deleted", "deleted_at",
                ]
    """
