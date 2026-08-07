"""CP19: permissions for the system/platform domain.

Three different access shapes, each expressed with EXISTING CP6 classes
— zero new comparison logic:

- `AuditLog` has no per-row owner concept (an audit entry about a
  `Customer` isn't "owned" by anyone in the CP10 sense) and is
  compliance-sensitive — reuses CP6's `IsManagerOrSuperAdmin` directly:
  only a Manager-or-above may view it at all, no Employee access, no
  ownership scoping.
- `SystemSetting`/`FeatureFlag` are shared, global configuration (like
  CP13's catalog models) — reuses CP13's/CP15's/CP16's exact
  `ReadOnlyOrSuperAdmin | IsManagerOrSuperAdmin` composition: any
  authenticated user reads, only a Manager-or-above writes.
- `BackgroundJob` has a real `owner` FK — reuses CP6's
  `IsOwnerOrSuperAdmin` unchanged, the same as every owner-shaped model
  since CP9.
"""
from apps.accounts.permissions import IsManagerOrSuperAdmin, IsOwnerOrSuperAdmin, ReadOnlyOrSuperAdmin

SystemConfigWritePermission = ReadOnlyOrSuperAdmin | IsManagerOrSuperAdmin

__all__ = ["IsManagerOrSuperAdmin", "IsOwnerOrSuperAdmin", "SystemConfigWritePermission"]
