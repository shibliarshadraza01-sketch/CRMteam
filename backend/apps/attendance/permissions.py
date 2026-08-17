"""Permission wiring for the attendance domain — re-exports CP6's
(``apps.accounts.permissions``) classes only, no new role-comparison
logic, the same "reuse existing RBAC, compose don't reimplement" rule
``apps.crm.permissions``/``apps.organization.permissions`` already
follow.
"""
from apps.accounts.permissions import (
    IsManagerOrSuperAdmin,
    IsOwnerOrSuperAdmin,
    IsSuperAdmin,
    ReadOnlyOrSuperAdmin,
    assert_object_accessible,
)

__all__ = [
    "IsManagerOrSuperAdmin",
    "IsOwnerOrSuperAdmin",
    "IsSuperAdmin",
    "ReadOnlyOrSuperAdmin",
    "assert_object_accessible",
]
