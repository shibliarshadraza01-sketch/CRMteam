"""CP12: permission wiring for the sales domain.

No new role-comparison logic — per CP12's spec ("Reuse CP6 + CP10
ownership model... No duplicated logic") this module only re-exports
CP6's (``apps.accounts.permissions``) classes, exactly the precedent
CP7/CP8/CP9/CP11 already set for their own ``permissions.py`` modules.

``Quote``/``Invoice`` expose a plain ``owner`` FK (CP6's ``resolve_owner()``
finds it automatically) and their own ``manager_has_access()`` (reusing
CP10's ``managed_user_ids()`` — see ``models.py``). ``QuoteItem``/
``InvoiceItem`` have no owner of their own, so each gets an ``owner``
property delegating to its parent (``quote.owner``/``invoice.owner``) plus
a delegated ``manager_has_access()`` — the same pattern CP9 established for
``ContactPerson``/``Address`` and CP11 repeated for
``OpportunityActivity``/``OpportunityNote``.
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
