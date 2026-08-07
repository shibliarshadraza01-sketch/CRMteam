"""CP7: permission wiring for the core app's reusable base classes.

CP6 (``apps.accounts.permissions``) already built every role/ownership
primitive a domain endpoint needs (``IsSuperAdmin``, ``IsManager``,
``IsEmployee``, ``IsManagerOrSuperAdmin``, ``ReadOnlyOrSuperAdmin``,
``IsOwnerOrSuperAdmin``, plus the hierarchy utilities). CP7 does not
reimplement any of that — per its own spec, "No duplicate permission
logic." This module only re-exports those classes under `apps.core` (so a
future domain app can `from apps.core.permissions import IsManager` without
needing to know RBAC actually lives in `apps.accounts`) and adds ONE new
thing CP6 had no reason to know about: a permission gating soft-delete
`restore`/`hard_delete` actions, built by composing CP6 primitives rather
than checking `request.user.role` directly.
"""
from apps.accounts.permissions import (
    IsEmployee,
    IsManager,
    IsManagerOrSuperAdmin,
    IsOwnerOrSuperAdmin,
    IsSuperAdmin,
    ReadOnlyOrSuperAdmin,
    is_super_admin,
    manager_has_access,
    resolve_owner,
    role_at_least,
    role_level,
    user_has_role_at_least,
)


class CanRestoreOrHardDelete(IsManagerOrSuperAdmin):
    """Gates ``restore()``/``hard_delete()`` actions on a soft-deletable
    resource to Manager-or-above.

    Deliberately a subclass of CP6's ``IsManagerOrSuperAdmin`` — not a new
    role check — so this class contains zero role-comparison logic of its
    own; it exists purely to give the "who may undo/permanently remove a
    soft-deleted row" question its own name for readability at the call
    site (``permission_classes = [CanRestoreOrHardDelete]`` reads as intent,
    where reusing ``IsManagerOrSuperAdmin`` directly would work identically
    but not say why).
    """

    message = "Only a Manager or Super Admin may restore or permanently delete this resource."


__all__ = [
    "IsEmployee",
    "IsManager",
    "IsManagerOrSuperAdmin",
    "IsOwnerOrSuperAdmin",
    "IsSuperAdmin",
    "ReadOnlyOrSuperAdmin",
    "CanRestoreOrHardDelete",
    "is_super_admin",
    "manager_has_access",
    "resolve_owner",
    "role_at_least",
    "role_level",
    "user_has_role_at_least",
]
