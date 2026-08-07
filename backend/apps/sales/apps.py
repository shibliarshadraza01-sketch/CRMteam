"""App configuration for the sales app.

``apps.sales`` owns quoting and invoicing — the commercial-document layer
that sits downstream of ``apps.crm``'s ``Customer``/``Opportunity``: a
``Quote`` is drafted, submitted, approved, and (once approved) converted
into an ``Invoice``, which is tracked through to payment. A separate app
(rather than folding this into ``apps.crm``, the way CP11's `Opportunity`
was folded into `apps.crm.opportunities`) because quoting/invoicing is a
genuinely distinct commercial-document domain with its own numbering,
approval, and payment lifecycle — not another shape of CRM account data.
"""
from django.apps import AppConfig


class SalesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.sales"
    label = "sales"
    verbose_name = "Sales"
