"""CP13: URL routes for the catalog API, mounted at /api/v1/catalog/ by
config/urls.py.

    GET/POST          /api/v1/catalog/products/
    GET/PATCH/DELETE  /api/v1/catalog/products/<id>/
    POST              /api/v1/catalog/products/<id>/restore/       (CP7 mixin)
    POST              /api/v1/catalog/products/<id>/hard-delete/   (CP7 mixin)

...and the same shape for /services/, /pricebooks/, /pricebook-entries/.
Built entirely from DRF's ``DefaultRouter`` — no hand-written URL
patterns, no non-standard routing needs.
"""
from rest_framework.routers import DefaultRouter

from .views import PriceBookEntryViewSet, PriceBookViewSet, ProductViewSet, ServiceViewSet

app_name = "catalog"

router = DefaultRouter()
router.register("products", ProductViewSet, basename="product")
router.register("services", ServiceViewSet, basename="service")
router.register("pricebooks", PriceBookViewSet, basename="pricebook")
router.register("pricebook-entries", PriceBookEntryViewSet, basename="pricebook-entry")

urlpatterns = router.urls
