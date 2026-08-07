"""App configuration for the catalog app.

``apps.catalog`` owns what a company sells and at what price: `Product`
(a tangible/stocked item, identified by `sku`), `Service` (a billable but
non-stocked offering, identified by `code`), `PriceBook` (a named,
currency-scoped collection of prices — "Standard Pricing 2026", "EU
Pricing"), and `PriceBookEntry` (one price, for one product or service, in
one price book). Deliberately its own app rather than folded into
`apps.sales` or `apps.crm`: catalog data is shared REFERENCE data (what
exists to be sold, and at what list price) with no per-user ownership the
way `Quote`/`Invoice`/`Customer` have — a genuinely different access shape
from every prior CRM/sales model, see `permissions.py`.
"""
from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.catalog"
    label = "catalog"
    verbose_name = "Catalog"
