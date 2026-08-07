"""CP9: permission wiring for the CRM domain.

No new role-comparison logic — per CP9's spec ("Reuse CP6 RBAC... Only
compose existing permission classes") this module only re-exports CP6's
(``apps.accounts.permissions``) classes for use under ``apps.crm``,
following the exact precedent CP7/CP8 already set for their own
``permissions.py`` modules.

``Customer``/``Lead`` already expose a plain ``owner`` FK — CP6's
``resolve_owner()`` finds this automatically, no property needed.
``ContactPerson``/``Address`` have no owner of their own, so ``models.py``
gives each an ``owner`` property delegating to ``self.customer.owner`` —
the same pattern CP8 established for ``ContactPerson``-shaped "belongs to
an owned parent" resources (see CP8's ``Team``/``Membership``).

Suggested access rules for a future view layer (no views exist yet in
CP9 — see "Deferred" in BACKEND_PROGRESS.md):

- **Customer / Lead**: read — any authenticated user (``IsEmployee``);
  write — Manager or above (``IsManagerOrSuperAdmin``); a specific object
  is additionally reachable by its own ``owner``, or a Super Admin, via
  ``IsOwnerOrSuperAdmin``.
- **ContactPerson / Address**: same shape, ownership resolved through the
  parent ``Customer``'s owner.
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
