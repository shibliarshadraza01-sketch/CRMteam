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

__all__ = [
    "IsEmployee",
    "IsManager",
    "IsManagerOrSuperAdmin",
    "IsOwnerOrSuperAdmin",
    "IsSuperAdmin",
    "ReadOnlyOrSuperAdmin",
]
