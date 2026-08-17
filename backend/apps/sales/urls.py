"""CP12: URL routes for the sales API, mounted at /api/v1/sales/ by
config/urls.py.

    GET/POST          /api/v1/sales/quotes/
    GET/PATCH/DELETE  /api/v1/sales/quotes/<id>/
    POST              /api/v1/sales/quotes/<id>/submit/
    POST              /api/v1/sales/quotes/<id>/approve/
    POST              /api/v1/sales/quotes/<id>/reject/
    POST              /api/v1/sales/quotes/<id>/convert/
    POST              /api/v1/sales/quotes/<id>/restore/       (CP7 mixin)
    POST              /api/v1/sales/quotes/<id>/hard-delete/   (CP7 mixin)

...and the same CRUD+restore+hard-delete shape for /invoices/, with
``mark-paid``/``cancel`` in place of the four quote actions.

``/quote-items/`` and ``/invoice-items/`` are separate, ordinary CRUD
resources (CRUD+restore+hard-delete, same as CP10's ``ContactPerson``/
``Address``) rather than nested actions on their parent — CP12's own API
spec, unlike CP11's ("Support: ... notes, activities" bundled under one
endpoint), never bundles line items under the parent resource, so the
CP10 precedent (a separate top-level resource) is the better fit here.

    GET/POST          /api/v1/sales/payments/           (list/record a payment)
    GET               /api/v1/sales/payments/<id>/

``/payments/`` is create+list+retrieve only (see
``PaymentTransactionViewSet``'s own docstring) — a recorded payment is
never edited or soft-deleted through this API.

Built entirely from DRF's ``DefaultRouter`` — no hand-written URL
patterns.
"""
from rest_framework.routers import DefaultRouter

from .views import (
    InvoiceItemViewSet,
    InvoiceViewSet,
    PaymentTransactionViewSet,
    QuoteItemViewSet,
    QuoteViewSet,
)

app_name = "sales"

router = DefaultRouter()
router.register("quotes", QuoteViewSet, basename="quote")
router.register("quote-items", QuoteItemViewSet, basename="quote-item")
router.register("invoices", InvoiceViewSet, basename="invoice")
router.register("invoice-items", InvoiceItemViewSet, basename="invoice-item")
router.register("payments", PaymentTransactionViewSet, basename="payment-transaction")

urlpatterns = router.urls
