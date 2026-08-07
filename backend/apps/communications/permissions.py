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

__all__ = ["IsOwnerOrSuperAdmin", "EmailTemplateWritePermission"]
