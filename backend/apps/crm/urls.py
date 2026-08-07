"""CP10/CP11: URL routes for the CRM API, mounted at /api/v1/crm/ by
config/urls.py.

    GET/POST      /api/v1/crm/customers/
    GET/PATCH/DELETE  /api/v1/crm/customers/<id>/
    POST          /api/v1/crm/customers/<id>/restore/       (CP7 mixin)
    POST          /api/v1/crm/customers/<id>/hard-delete/   (CP7 mixin)

...and the same shape for /leads/, /contacts/, /addresses/, /opportunities/.
``/opportunities/`` additionally exposes (CP11):

    POST  /api/v1/crm/opportunities/<id>/advance-stage/
    POST  /api/v1/crm/opportunities/<id>/mark-won/
    POST  /api/v1/crm/opportunities/<id>/mark-lost/
    POST  /api/v1/crm/opportunities/<id>/reopen/
    GET/POST  /api/v1/crm/opportunities/<id>/notes/
    GET/POST  /api/v1/crm/opportunities/<id>/activities/

Built entirely from DRF's ``DefaultRouter`` — no hand-written URL patterns,
since every resource here is a standard ``ModelViewSet``; the CP11 actions
above are picked up automatically from ``OpportunityViewSet``'s
``@action``-decorated methods, the same mechanism CP7's ``restore``/
``hard-delete`` actions already use.
"""
from rest_framework.routers import DefaultRouter

from .views import (
    AddressViewSet,
    ContactPersonViewSet,
    CustomerViewSet,
    LeadViewSet,
    OpportunityViewSet,
)

app_name = "crm"

router = DefaultRouter()
router.register("customers", CustomerViewSet, basename="customer")
router.register("leads", LeadViewSet, basename="lead")
router.register("contacts", ContactPersonViewSet, basename="contact")
router.register("addresses", AddressViewSet, basename="address")
router.register("opportunities", OpportunityViewSet, basename="opportunity")

urlpatterns = router.urls
