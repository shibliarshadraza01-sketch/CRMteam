"""CP8: permission wiring for the organization hierarchy.

No new role-comparison logic is written here — per CP8's spec ("permissions
using CP6 RBAC") this module only composes CP6's (``apps.accounts
.permissions``) and CP7's (``apps.core.permissions``) existing classes
against this app's models. The two places CP8 needed *object-level*
ownership (a team's manager, a membership's own user) were solved by
giving ``Team``/``Membership`` an ``owner`` property and, for
``Membership``, a ``manager_has_access()`` hook — both are the exact
extension points CP6/CP7 documented and left unused until now (see
``models.py`` and BACKEND_LEARNING_GUIDE.md CP8, "exercising CP6's
extension points for real").

Access rules used across this app's tests/services:

- **Organization**: read — any authenticated user (``IsEmployee``);
  write — ``IsSuperAdmin`` only (creating/renaming a tenant-level
  organization is not a Manager-level decision).
- **Department / Team**: read — any authenticated user; write — Manager or
  above (``IsManagerOrSuperAdmin``).
- **Team** (object-level): a team's own ``manager``, or a Super Admin, may
  act on that specific team via ``IsOwnerOrSuperAdmin`` (``Team.owner``
  resolves to ``self.manager``).
- **Membership** (object-level): the member themselves, the team's
  manager (via ``Membership.manager_has_access()``), or a Super Admin, may
  act on that specific membership via ``IsOwnerOrSuperAdmin``.
"""
from apps.accounts.permissions import (
    IsEmployee,
    IsManager,
    IsManagerOrSuperAdmin,
    IsOwnerOrSuperAdmin,
    IsSuperAdmin,
    ReadOnlyOrSuperAdmin,
)

#: Organization: read — any authenticated user; write — Super Admin only.
#: ``ReadOnlyOrSuperAdmin`` alone already expresses exactly this rule.
OrganizationWritePermission = ReadOnlyOrSuperAdmin

#: Department / Team: read — any authenticated user; write — Manager or
#: above. Same composition CP13's ``CatalogWritePermission`` established —
#: see that module's docstring for the truth table.
#:
#: PHASE 5 AUDIT — DELIBERATELY UNCHANGED. Re-examined alongside the
#: Phase 5 tightening of ``apps.system``'s ``SystemConfigWritePermission``
#: and ``apps.attendance``'s ``ShiftConfigurationViewSet``. The
#: system-wide/Manager-scoped line in THIS app falls between
#: ``Organization`` and ``Department``/``Team``, and it is already drawn
#: correctly: ``Organization`` is the single tenant-level record and is
#: Super-Admin-only above (``test_api.py::test_manager_cannot_create_organization``),
#: while a ``Department``/``Team`` is one of many per-team structural rows
#: that a Manager legitimately administers — ``Team`` even carries a
#: ``manager`` FK naming the Manager responsible for it, and
#: ``test_manager_can_create_department``/``_team``/``_delete_team``
#: assert that capability today. Tightening this would remove real
#: Manager functionality rather than close a hole.
DepartmentTeamWritePermission = ReadOnlyOrSuperAdmin | IsManagerOrSuperAdmin

__all__ = [
    "IsEmployee",
    "IsManager",
    "IsManagerOrSuperAdmin",
    "IsOwnerOrSuperAdmin",
    "IsSuperAdmin",
    "ReadOnlyOrSuperAdmin",
    "OrganizationWritePermission",
    "DepartmentTeamWritePermission",
]
