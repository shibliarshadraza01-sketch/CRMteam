"""CP10: tests for apps/crm/filters.py.

``LeadFilterSet.filter_converted()`` reuses CP9's ``LeadQuerySet.converted()``/
``unconverted()`` — calling it just builds a filtered queryset (lazy,
never evaluated), so this needs no database.
"""
from apps.crm.filters import AddressFilterSet, ContactPersonFilterSet, CustomerFilterSet, LeadFilterSet
from apps.crm.models import Lead


def test_customer_filterset_declares_spec_fields():
    assert set(CustomerFilterSet.Meta.fields) == {"status", "owner", "organization", "industry", "is_active"}


def test_lead_filterset_declares_spec_fields_plus_converted():
    assert set(LeadFilterSet.Meta.fields) == {"status", "owner", "source"}
    assert "converted" in LeadFilterSet.declared_filters


def test_contact_filterset_has_customer_and_is_primary():
    assert set(ContactPersonFilterSet.Meta.fields) == {"customer", "is_primary"}


def test_address_filterset_has_customer_and_address_type():
    assert set(AddressFilterSet.Meta.fields) == {"customer", "address_type"}


def test_filter_converted_true_reuses_lead_queryset_converted_method():
    filterset = LeadFilterSet()
    base = Lead.objects.all()

    result = filterset.filter_converted(base, "converted", True)

    assert "converted_customer" in str(result.query.where)


def test_filter_converted_false_reuses_lead_queryset_unconverted_method():
    filterset = LeadFilterSet()
    base = Lead.objects.all()

    result = filterset.filter_converted(base, "converted", False)

    assert "converted_customer" in str(result.query.where)
