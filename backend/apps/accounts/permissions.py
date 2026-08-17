"""CP6: reusable role-based access control (RBAC) permission infrastructure.

This module is deliberately business-logic-free: it knows about the three
existing ``User.Role`` values (SUPER_ADMIN / MANAGER / EMPLOYEE) and the
hierarchy between them, and nothing about any future business module. Every
future checkpoint that needs "only a manager or above can do this" or "only
the owner of this object (or a super admin) can touch it" should reuse the
classes/functions here rather than hand-rolling role checks inside a view —
see BACKEND_LEARNING_GUIDE.md CP6 for the full design rationale and worked
examples.

Hierarchy (higher inherits every permission of everything below it)::

    SUPER_ADMIN
        |
    MANAGER
        |
    EMPLOYEE

"Inherits" is implemented as a numeric role level (see ``ROLE_LEVELS``): a
permission that requires "at least MANAGER" is satisfied by MANAGER or
SUPER_ADMIN, never by EMPLOYEE. This is why ``IsManager`` below allows
SUPER_ADMIN through too — a Super Admin is never blocked by a check written
for a lower role.
"""
from rest_framework import permissions

from .models import User

# --------------------------------------------------------------------------
# Role hierarchy utilities
# --------------------------------------------------------------------------

# Higher number = more privilege. Deliberately keyed by the SAME string
# values already defined on User.Role (CP2) — no new roles are introduced,
# per CP6's explicit requirement.
ROLE_LEVELS = {
    User.Role.EMPLOYEE: 0,
    User.Role.MANAGER: 1,
    User.Role.SUPER_ADMIN: 2,
}


def role_level(role):
    """Return the numeric hierarchy level for a role string, or None if the
    value is not a recognized role (e.g. an empty string, None, or a typo).
    """
    return ROLE_LEVELS.get(role)


def role_at_least(role, minimum_role):
    """True if ``role`` is at or above ``minimum_role`` in the hierarchy.

    Unrecognized roles never satisfy any minimum (fail closed).
    """
    level = role_level(role)
    minimum_level = role_level(minimum_role)
    if level is None or minimum_level is None:
        return False
    return level >= minimum_level


def user_has_role_at_least(user, minimum_role):
    """True if ``user`` is authenticated and holds at least ``minimum_role``.

    This is the single helper every role-checking permission class below
    delegates to — it is the one place "what does 'at least a role' mean"
    is decided, so future checkpoints extending the hierarchy (if ever)
    only need to change it here.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return role_at_least(getattr(user, "role", None), minimum_role)


def is_super_admin(user):
    """True if ``user`` is an authenticated SUPER_ADMIN.

    Not just ``user_has_role_at_least(user, SUPER_ADMIN)`` renamed — kept as
    its own function because "is this specifically a super admin, the one
    role with blanket override power" is a distinct question from "does this
    user meet a minimum role", and callers (e.g. ``IsOwnerOrSuperAdmin``)
    read more clearly asking it directly.
    """
    return user_has_role_at_least(user, User.Role.SUPER_ADMIN)


# --------------------------------------------------------------------------
# Role-based permission classes
# --------------------------------------------------------------------------


class IsSuperAdmin(permissions.BasePermission):
    """Allows access only to an authenticated SUPER_ADMIN.

    The one role-check class that does NOT widen via hierarchy (there is
    nothing above SUPER_ADMIN to inherit from) — using this class means
    "only the top of the hierarchy", e.g. for endpoints that must never be
    reachable by a Manager no matter how trusted.
    """

    message = "Only a Super Admin may perform this action."

    def has_permission(self, request, view):
        return is_super_admin(request.user)


class IsManager(permissions.BasePermission):
    """Allows access to an authenticated MANAGER or SUPER_ADMIN.

    "Manager inherits employee permissions [and is inherited by] Super
    Admin" (CP6 spec) is expressed here as "at least MANAGER" — an EMPLOYEE
    is rejected, MANAGER and SUPER_ADMIN both pass.
    """

    message = "Only a Manager or Super Admin may perform this action."

    def has_permission(self, request, view):
        return user_has_role_at_least(request.user, User.Role.MANAGER)


class IsEmployee(permissions.BasePermission):
    """Allows access to any authenticated user (EMPLOYEE, MANAGER, or
    SUPER_ADMIN).

    EMPLOYEE is the floor of the hierarchy, so "at least EMPLOYEE" is
    equivalent to "any authenticated user" — this class exists (rather than
    just using ``IsAuthenticated``) so a view's ``permission_classes`` can
    read as an explicit role statement, consistent with ``IsManager`` and
    ``IsSuperAdmin`` alongside it, and so a future change to the hierarchy's
    floor only has to be made in one place (``ROLE_LEVELS``).
    """

    message = "You must be signed in to perform this action."

    def has_permission(self, request, view):
        return user_has_role_at_least(request.user, User.Role.EMPLOYEE)


class IsManagerOrSuperAdmin(permissions.BasePermission):
    """Explicit union of MANAGER and SUPER_ADMIN, checked by exact role
    rather than by hierarchy level.

    Behaviorally identical to ``IsManager`` today (there are only three
    roles, and both allow exactly {MANAGER, SUPER_ADMIN}). It is kept as a
    separate, explicitly-named class — rather than a bare alias — for two
    reasons: (1) CP6's spec lists it as one of the required reusable
    classes, and (2) a view that means "specifically these two roles, an
    explicit list" reads more honestly with this class than with
    ``IsManager``, whose name implies "manager-level-or-above" hierarchy
    semantics that happen to produce the same set today but are conceptually
    different from an explicit enumeration. If the hierarchy ever grows a
    role between MANAGER and SUPER_ADMIN, ``IsManager`` would include it
    automatically while this class would not — that divergence is the
    entire reason to keep both.
    """

    message = "Only a Manager or Super Admin may perform this action."

    def has_permission(self, request, view):
        user = request.user
        if not user or not getattr(user, "is_authenticated", False):
            return False
        return getattr(user, "role", None) in (User.Role.MANAGER, User.Role.SUPER_ADMIN)


class ReadOnlyOrSuperAdmin(permissions.BasePermission):
    """Any authenticated user may read (safe methods); only a SUPER_ADMIN
    may write.

    Useful for future business-module endpoints where every role should be
    able to view shared data, but only a Super Admin can create/edit/delete
    it, without needing a separate view per role.
    """

    message = "Only a Super Admin may modify this resource."

    def has_permission(self, request, view):
        user = request.user
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return is_super_admin(user)


# --------------------------------------------------------------------------
# Object-level ownership permission
# --------------------------------------------------------------------------

# The attribute names checked, in order, to find "who owns this object".
# CP6 has no business models yet, so this stays a convention rather than a
# hard requirement on any base model class — a future model just needs to
# expose one of these attributes (or override the lookup, see
# `manager_has_access` below) to participate.
OWNER_ATTRS = ("owner", "user", "created_by")


def resolve_owner(obj):
    """Best-effort resolution of "the user who owns `obj`".

    Tries, in order: an ``owner``, ``user``, or ``created_by`` attribute (the
    first one present on the object, even if its value is None); the object
    itself if it IS a User instance (so this also works when the "resource"
    being protected is a User row, e.g. a future /users/<id>/ endpoint).
    Returns None if none of these apply — callers must treat "unknown owner"
    as "deny", never as "allow".
    """
    if isinstance(obj, User):
        return obj

    for attr in OWNER_ATTRS:
        if hasattr(obj, attr):
            return getattr(obj, attr)

    return None


def manager_has_access(user, obj):
    """Extension point: "a Manager has explicit access" to `obj`.

    CP6 introduces no team/hierarchy models, so there is nothing yet for a
    Manager's "explicit access" to be derived from — this always returns
    False for now. A future checkpoint that adds e.g. a Team or reporting-
    line model should override this behavior by monkey-patching is
    explicitly NOT the intended extension mechanism; instead, either:

    1. give the protected model a ``manager_has_access(self, user) -> bool``
       method, which ``IsOwnerOrSuperAdmin`` below will call automatically
       if present (see ``has_object_permission``), or
    2. subclass ``IsOwnerOrSuperAdmin`` and override this module-level
       function's call site for that specific view.

    Documented at length here because CP6's spec explicitly requires this
    hook to exist even though nothing populates it yet.
    """
    return False


class IsOwnerOrSuperAdmin(permissions.BasePermission):
    """Object-level permission: the object's owner, a Manager with explicit
    access to it, or a Super Admin.

    ``has_permission`` only requires the user be authenticated (there is no
    way to know ownership before an object is fetched); the real check is
    ``has_object_permission``, which DRF calls once a specific object has
    been retrieved (e.g. via ``get_object()`` in a ``Retrieve/Update/Destroy``
    view). Views using this class for a list endpoint are responsible for
    filtering their own queryset to the caller's own objects — this class
    cannot do that for you (DRF permissions never filter querysets).
    """

    message = "You do not have access to this resource."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and getattr(user, "is_authenticated", False))

    def has_object_permission(self, request, view, obj):
        user = request.user

        if is_super_admin(user):
            return True

        owner = resolve_owner(obj)
        if owner is not None and owner == user:
            return True

        if user_has_role_at_least(user, User.Role.MANAGER):
            # Prefer a per-object hook if the model defines one (see
            # manager_has_access() docstring), else fall back to the
            # module-level extension point.
            hook = getattr(obj, "manager_has_access", None)
            if callable(hook):
                return bool(hook(user))
            return manager_has_access(user, obj)

        return False


def assert_object_accessible(request, obj):
    """Raise ``Http404`` unless ``request.user`` can access ``obj`` under
    the exact same rule ``IsOwnerOrSuperAdmin.has_object_permission()``
    enforces for retrieve/update/destroy.

    Required for every ``perform_create()`` that attaches a new CHILD
    record to an EXISTING parent identified by a client-supplied ID in
    the request body (e.g. ``ContactPersonViewSet`` creating a contact
    for a given ``customer``, ``InvoiceItemViewSet``/``PaymentTransactionViewSet``
    for a given ``invoice``): DRF's permission classes only ever run
    ``has_object_permission()`` against an object ``get_object()`` has
    already fetched — for a plain ``POST`` to a list endpoint there IS no
    object yet, so a parent PK referenced inside the create payload is
    validated only by the serializer field's queryset (which, unscoped,
    accepts ANY existing parent), never by an ownership check. Without
    this call, any authenticated user could attach a fabricated child
    record (a contact, an invoice line item, a payment) to ANY other
    user's parent object just by guessing or enumerating its ID — call
    this immediately after popping the parent out of ``validated_data``,
    before doing anything with it.
    """
    from django.http import Http404

    if not IsOwnerOrSuperAdmin().has_object_permission(request, None, obj):
        raise Http404
