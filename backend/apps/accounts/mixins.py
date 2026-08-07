"""CP6: RolePermissionMixin — a view-level convenience for role-gated views.

The permission classes in apps/accounts/permissions.py are the actual
authorization mechanism (DRF calls ``has_permission``/``has_object_permission``
on each configured permission class). This mixin does not replace that; it
gives a view a smaller declarative surface — ``required_role`` — for the
extremely common case of "this whole view needs at least role X", without
needing to import and list a specific permission class by hand.

See BACKEND_LEARNING_GUIDE.md CP6, "mixins vs permission classes", for why
both exist rather than picking one.
"""
from .models import User
from .permissions import IsEmployee, IsManager, IsSuperAdmin

# Maps a required-role declaration to the permission class that enforces it.
# Deliberately a plain dict, not a bigger registry class — CP6 has exactly
# three roles and no indication future checkpoints will need more than a
# lookup here.
_ROLE_PERMISSION_CLASSES = {
    User.Role.EMPLOYEE: IsEmployee,
    User.Role.MANAGER: IsManager,
    User.Role.SUPER_ADMIN: IsSuperAdmin,
}


class RolePermissionMixin:
    """Adds a ``required_role`` view attribute that gates the whole view.

    Usage::

        class SomeManagerOnlyView(RolePermissionMixin, generics.ListAPIView):
            required_role = User.Role.MANAGER
            ...

    ``required_role`` follows the same hierarchy as everywhere else in this
    module: MANAGER means "MANAGER or SUPER_ADMIN", EMPLOYEE means "any
    authenticated user". Leaving ``required_role`` unset makes this mixin a
    no-op (falls back to whatever ``permission_classes`` the view already
    declares) — it is opt-in, not a silent global gate.

    ``get_permissions()`` PREPENDS the derived permission class ahead of any
    ``permission_classes`` already declared on the view, rather than
    replacing them, so a view can still combine a role floor with, e.g., an
    object-level ``IsOwnerOrSuperAdmin`` check.
    """

    required_role = None

    def get_permissions(self):
        base_permissions = super().get_permissions()

        if self.required_role is None:
            return base_permissions

        permission_class = _ROLE_PERMISSION_CLASSES.get(self.required_role)
        if permission_class is None:
            raise ValueError(
                f"RolePermissionMixin.required_role={self.required_role!r} is not a "
                f"recognized User.Role value."
            )

        return [permission_class()] + list(base_permissions)


class ObjectOwnershipMixin:
    """Thin convenience mixin pairing a view with ``IsOwnerOrSuperAdmin``.

    Exists for the same reason as ``RolePermissionMixin``: lets a future
    view opt into object-level ownership checks by inheriting a mixin
    instead of remembering to list the permission class by hand. Like
    ``RolePermissionMixin``, it prepends rather than replaces.
    """

    def get_permissions(self):
        from .permissions import IsOwnerOrSuperAdmin

        base_permissions = super().get_permissions()
        return [IsOwnerOrSuperAdmin()] + list(base_permissions)


__all__ = [
    "RolePermissionMixin",
    "ObjectOwnershipMixin",
]
