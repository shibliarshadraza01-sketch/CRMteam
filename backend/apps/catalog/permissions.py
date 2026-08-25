"""CP13: permission wiring for the catalog domain.

Catalog data (`Product`/`Service`/`PriceBook`/`PriceBookEntry`) has no
`owner` — it's shared reference data, not a per-salesperson record — so
CP10's ownership-scoping model (`IsOwnerOrSuperAdmin`, `managed_user_ids()`)
doesn't apply here the way it does to `Customer`/`Lead`/`Opportunity`/
`Quote`/`Invoice`. The access rule this app actually needs is simpler:
**any authenticated user may read the catalog; only a Manager-or-above may
write to it** (creating/pricing a product is a managerial decision, not
something every Employee should be able to do unilaterally).

No new comparison logic was written to express this. CP6's
``ReadOnlyOrSuperAdmin`` (safe methods -> any authenticated; unsafe
methods -> Super Admin only) and ``IsManagerOrSuperAdmin`` (any method ->
Manager or above) are composed with DRF's own built-in permission ``|``
(OR) operator — a feature of `rest_framework.permissions.BasePermission`
since DRF 3.9, not something this app built:

    CatalogWritePermission = ReadOnlyOrSuperAdmin | IsManagerOrSuperAdmin

For a safe method (GET/HEAD/OPTIONS) by any authenticated user,
``ReadOnlyOrSuperAdmin`` already passes, so the OR short-circuits true.
For an unsafe method by a Manager-or-above, ``IsManagerOrSuperAdmin``
passes even though ``ReadOnlyOrSuperAdmin`` alone would have rejected it
(a non-Super-Admin write). For an unsafe method by a plain Employee, BOTH
sides fail, and access is correctly denied. See
BACKEND_LEARNING_GUIDE.md CP13, "composing permissions instead of writing
a new one", for the full truth table.

PHASE 5 AUDIT — DELIBERATELY UNCHANGED. Phase 5 tightened system-wide
CONFIGURATION writes to Super Admin only (`apps.system`'s
`SystemConfigWritePermission`, `apps.attendance`'s
`ShiftConfigurationViewSet`). This composition was re-examined and kept:
`Product`/`Service`/`PriceBook`/`PriceBookEntry` are MANY per-record rows
of operational sales reference data, not a single global policy row that
changes behaviour for every user in the deployment. Pricing a product is
the managerial decision this module's docstring already describes, and
`test_api.py`'s `test_manager_can_create`/`_patch`/`_delete` assert that
capability today. Tightening this to Super Admin would remove real
Manager functionality, not close a hole — the exact "do NOT simply change
every Manager permission to Super Admin" case. Contrast
`apps.organization`'s `OrganizationWritePermission`, which IS the
single-row-per-company shape and is correctly Super-Admin-only.
"""
from apps.accounts.permissions import (
    IsEmployee,
    IsManager,
    IsManagerOrSuperAdmin,
    IsOwnerOrSuperAdmin,
    IsSuperAdmin,
    ReadOnlyOrSuperAdmin,
)

#: Read: any authenticated user. Write: Manager or above. Composed
#: entirely from existing CP6 classes via DRF's `|` operator — see this
#: module's own docstring for the truth table.
CatalogWritePermission = ReadOnlyOrSuperAdmin | IsManagerOrSuperAdmin

__all__ = [
    "IsEmployee",
    "IsManager",
    "IsManagerOrSuperAdmin",
    "IsOwnerOrSuperAdmin",
    "IsSuperAdmin",
    "ReadOnlyOrSuperAdmin",
    "CatalogWritePermission",
]
