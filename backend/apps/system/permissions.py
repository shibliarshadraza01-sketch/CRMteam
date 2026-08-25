"""CP19: permissions for the system/platform domain.

Three different access shapes, each expressed with EXISTING CP6 classes
— zero new comparison logic:

- `AuditLog` has no per-row owner concept (an audit entry about a
  `Customer` isn't "owned" by anyone in the CP10 sense) and is
  compliance-sensitive — reuses CP6's `IsManagerOrSuperAdmin` directly:
  only a Manager-or-above may view it at all, no Employee access, no
  ownership scoping.
- `SystemSetting`/`FeatureFlag` are SYSTEM-WIDE configuration — a single
  global key/value namespace and a set of global on/off switches that
  apply to the whole deployment, not per-team operational records.
  Reuses CP6's `ReadOnlyOrSuperAdmin` unchanged: any authenticated user
  reads, ONLY a Super Admin writes.

  Phase 5 tightening: this used to be
  `ReadOnlyOrSuperAdmin | IsManagerOrSuperAdmin` (the CP13 catalog
  composition, borrowed here at CP19 for convenience because both
  models are ownerless reference data). That was wrong for this app:
  a `SystemSetting` row is not "reference data a Manager administers
  for their own team" the way a `Product` or a `Team` is — it changes
  behaviour for every user in the deployment, and a Manager flipping a
  `FeatureFlag` would alter what every other role sees. The frontend
  has always scoped "Settings / Configuration" (which maps exactly to
  `/api/v1/system/settings/`) to the Super Admin module list, so this
  makes the backend authoritative for the same boundary rather than
  relying on a hidden nav item. Managers KEEP read access — the system
  settings/feature-flag values are still needed to render the app.

  This is deliberately the same shape `apps.organization`'s
  `OrganizationWritePermission` and `apps.attendance`'s
  `ShiftConfigurationViewSet` already use for company-wide policy:
  everybody reads it, only a Super Admin edits it.
- `BackgroundJob` has a real `owner` FK — reuses CP6's
  `IsOwnerOrSuperAdmin` unchanged, the same as every owner-shaped model
  since CP9.
"""
from apps.accounts.permissions import IsManagerOrSuperAdmin, IsOwnerOrSuperAdmin, ReadOnlyOrSuperAdmin

#: Read: any authenticated user. Write (POST/PATCH/PUT/DELETE, and the
#: CP7 `restore`/`hard-delete` POST actions): Super Admin only.
SystemConfigWritePermission = ReadOnlyOrSuperAdmin

__all__ = ["IsManagerOrSuperAdmin", "IsOwnerOrSuperAdmin", "SystemConfigWritePermission"]
