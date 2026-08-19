"""CP15: permissions for the communications domain.

Two different access shapes, each expressed with EXISTING CP6 classes —
zero new comparison logic:

- `EmailTemplate` is shared reference data (like CP13's `Product`/
  `Service`/`PriceBook`) — no owner, so CP10's ownership-scoping model
  doesn't apply. Reuses CP13's exact composition: any authenticated user
  may read, only a Manager-or-above may write.
- `EmailMessage`/`Notification`/`CommunicationLog` all have an
  owner-shaped attribute (`owner` real field or delegating property — see
  `models.py`), so CP6's `IsOwnerOrSuperAdmin` applies unchanged, the same
  as every model in CP14's `apps.activities`.
"""
from apps.accounts.permissions import IsManagerOrSuperAdmin, IsOwnerOrSuperAdmin, ReadOnlyOrSuperAdmin

EmailTemplateWritePermission = ReadOnlyOrSuperAdmin | IsManagerOrSuperAdmin

#: Staff-management pass: notification RULES are a Super Admin concern.
#:
#: Every role RECEIVES notifications and manages their own read state, so
#: safe methods and the ``mark-read``/``mark-unread`` actions stay open to
#: everyone (still scoped to their own rows by ``owner_field="recipient"``);
#: creating, editing, or deleting a `Notification` through the API is
#: Super-Admin-only. Reuses CP6's existing ``ReadOnlyOrSuperAdmin``
#: unchanged rather than introducing a new comparison — the class already
#: means exactly "everyone reads, only Super Admin writes".
#:
#: This restricts the CLIENT-FACING endpoint only. System-generated
#: notifications are created by ``services.create_notification()`` from
#: internal code paths that never pass through DRF permissions, so
#: automatic CRM notifications are entirely unaffected.
NotificationWritePermission = ReadOnlyOrSuperAdmin

__all__ = ["IsOwnerOrSuperAdmin", "EmailTemplateWritePermission", "NotificationWritePermission"]
