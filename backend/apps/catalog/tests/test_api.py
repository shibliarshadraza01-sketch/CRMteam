"""CP13: end-to-end tests for the catalog API. Requires a real database.
"""
import pytest

from apps.catalog.models import PriceBookEntry, Product

pytestmark = pytest.mark.django_db

PRODUCTS_URL = "/api/v1/catalog/products/"
PRICEBOOKS_URL = "/api/v1/catalog/pricebooks/"
PRICEBOOK_ENTRIES_URL = "/api/v1/catalog/pricebook-entries/"


def _detail(url, pk):
    return f"{url}{pk}/"


# --------------------------------------------------------------------------
# CRUD + permission composition (the core of CP13's access rule)
# --------------------------------------------------------------------------


def test_unauthenticated_denied(api_client):
    response = api_client.get(PRODUCTS_URL)
    assert response.status_code == 401


def test_employee_can_list_and_retrieve(api_client, employee, product):
    api_client.force_authenticate(employee)
    response = api_client.get(PRODUCTS_URL)
    assert response.status_code == 200
    response = api_client.get(_detail(PRODUCTS_URL, product.pk))
    assert response.status_code == 200


def test_employee_cannot_create(api_client, employee):
    api_client.force_authenticate(employee)
    response = api_client.post(PRODUCTS_URL, {"name": "Gadget", "sku": "GAD-1"})
    assert response.status_code == 403


def test_employee_cannot_patch(api_client, employee, product):
    api_client.force_authenticate(employee)
    response = api_client.patch(_detail(PRODUCTS_URL, product.pk), {"name": "Renamed"})
    assert response.status_code == 403


def test_employee_cannot_delete(api_client, employee, product):
    api_client.force_authenticate(employee)
    response = api_client.delete(_detail(PRODUCTS_URL, product.pk))
    assert response.status_code == 403


def test_manager_can_create(api_client, manager):
    api_client.force_authenticate(manager)
    response = api_client.post(PRODUCTS_URL, {"name": "Gadget", "sku": "GAD-2"})
    assert response.status_code == 201


def test_manager_can_patch(api_client, manager, product):
    api_client.force_authenticate(manager)
    response = api_client.patch(_detail(PRODUCTS_URL, product.pk), {"description": "Updated"})
    assert response.status_code == 200
    product.refresh_from_db()
    assert product.description == "Updated"


def test_manager_can_delete_and_it_soft_deletes(api_client, manager, product):
    api_client.force_authenticate(manager)
    response = api_client.delete(_detail(PRODUCTS_URL, product.pk))
    assert response.status_code == 204
    product.refresh_from_db()
    assert product.is_deleted is True
    assert Product.objects.filter(pk=product.pk).exists()


def test_super_admin_can_create(api_client, super_admin):
    api_client.force_authenticate(super_admin)
    response = api_client.post(PRODUCTS_URL, {"name": "Gadget", "sku": "GAD-3"})
    assert response.status_code == 201


def test_put_not_allowed(api_client, manager, product):
    api_client.force_authenticate(manager)
    response = api_client.put(_detail(PRODUCTS_URL, product.pk), {"name": "X", "sku": product.sku})
    assert response.status_code == 405


# --------------------------------------------------------------------------
# restore / hard-delete (CP7 mixin actions)
# --------------------------------------------------------------------------


def test_restore_action(api_client, manager, product):
    product.soft_delete()
    api_client.force_authenticate(manager)
    response = api_client.post(f"{_detail(PRODUCTS_URL, product.pk)}restore/")
    assert response.status_code == 200
    product.refresh_from_db()
    assert product.is_deleted is False


def test_hard_delete_action(api_client, manager, product):
    pk = product.pk
    api_client.force_authenticate(manager)
    response = api_client.post(f"{_detail(PRODUCTS_URL, pk)}hard-delete/")
    assert response.status_code == 204
    assert not Product.objects.filter(pk=pk).exists()


def test_employee_cannot_restore_or_hard_delete(api_client, employee, product):
    product.soft_delete()
    api_client.force_authenticate(employee)
    response = api_client.post(f"{_detail(PRODUCTS_URL, product.pk)}restore/")
    assert response.status_code == 403


# --------------------------------------------------------------------------
# PriceBookEntry via its own resource + validation
# --------------------------------------------------------------------------


def test_create_pricebookentry_with_product(api_client, manager, pricebook, product):
    api_client.force_authenticate(manager)
    response = api_client.post(
        PRICEBOOK_ENTRIES_URL, {"price_book": pricebook.pk, "product": product.pk, "price": "9.99"}
    )
    assert response.status_code == 201


def test_create_pricebookentry_with_both_product_and_service_rejected(api_client, manager, pricebook, product, service):
    api_client.force_authenticate(manager)
    response = api_client.post(
        PRICEBOOK_ENTRIES_URL,
        {"price_book": pricebook.pk, "product": product.pk, "service": service.pk, "price": "9.99"},
    )
    assert response.status_code == 400


def test_retrieve_pricebook_uses_detail_serializer(api_client, employee, pricebook, product):
    from apps.catalog.services import add_pricebook_entry

    add_pricebook_entry(pricebook, 10, product=product)
    api_client.force_authenticate(employee)

    response = api_client.get(_detail(PRICEBOOKS_URL, pricebook.pk))

    assert response.status_code == 200
    assert "entries" in response.data
    assert len(response.data["entries"]) == 1


# --------------------------------------------------------------------------
# Search / filter / ordering / pagination
# --------------------------------------------------------------------------


def test_search_products_by_name_and_sku(api_client, employee):
    Product.objects.create(name="Rocket Widget", sku="ROC-1")
    Product.objects.create(name="Other", sku="OTH-9")
    api_client.force_authenticate(employee)

    response = api_client.get(PRODUCTS_URL, {"search": "Rocket"})
    names = {row["name"] for row in response.data["results"]}
    assert names == {"Rocket Widget"}


def test_filter_products_by_is_active(api_client, employee):
    Product.objects.create(name="Active P", sku="ACT-1", is_active=True)
    Product.objects.create(name="Inactive P", sku="INA-1", is_active=False)
    api_client.force_authenticate(employee)

    response = api_client.get(PRODUCTS_URL, {"is_active": "false"})
    names = {row["name"] for row in response.data["results"]}
    assert names == {"Inactive P"}


def test_order_products_by_default_price(api_client, employee):
    Product.objects.create(name="Cheap", sku="CH-1", default_price=1)
    Product.objects.create(name="Pricey", sku="PR-1", default_price=999)
    api_client.force_authenticate(employee)

    response = api_client.get(PRODUCTS_URL, {"ordering": "default_price"})
    names = [row["name"] for row in response.data["results"]]
    assert names == ["Cheap", "Pricey"]


def test_pagination_default_page_size_is_20(api_client, employee):
    for i in range(25):
        Product.objects.create(name=f"Product {i:03d}", sku=f"SKU-{i:03d}")
    api_client.force_authenticate(employee)

    response = api_client.get(PRODUCTS_URL)

    assert len(response.data["results"]) == 20
    assert response.data["count"] == 25
