"""Phase 4 transaction-safety audit: lead -> customer conversion leaves the
database either fully converted or completely untouched.

``test_lead_conversion_api.py`` already covers authorization and
idempotency for ``POST /api/v1/crm/leads/<id>/convert/``. What it could not
cover is the case this module exists for: what the DATABASE looks like when
a conversion fails PARTWAY THROUGH, after the ``Customer`` row has already
been written but before the ``Lead`` update that points at it.

That ordering is intrinsic to the operation (a lead cannot link to a
customer that does not exist yet), so the window is real, not hypothetical.
Un-transacted, a failure inside it committed the Customer and abandoned it:
a customer nobody asked for, in the lead owner's customer list, while the
lead still read as unconverted — and therefore still convertible, into a
SECOND duplicate customer. ``convert_lead()``'s own already-converted guard
cannot catch that, because the flag it reads is exactly the write that
never landed.

The tests below force that failure explicitly (patching the lead save, and
patching the audit stamping the view does after the service returns) rather
than hoping to observe it by chance, and then assert the only acceptable
outcome: zero customers created.
"""
import pytest

from apps.crm.models import Customer, Lead
from apps.crm.services import convert_lead

LEADS_URL = "/api/v1/crm/leads/"


def _convert_url(lead):
    return f"{LEADS_URL}{lead.pk}/convert/"


@pytest.fixture
def employee_lead(db, employee):
    return Lead.objects.create(
        company_name="Initech",
        contact_name="Peter Gibbons",
        email="peter@initech.test",
        owner=employee,
    )


class _Boom(Exception):
    """A downstream failure that is unmistakably ours, so a test can never
    pass by catching some unrelated error the ORM happened to raise.
    """


# --------------------------------------------------------------------------
# Service level: convert_lead() rolls back the Customer it just created
# --------------------------------------------------------------------------


def test_convert_lead_rolls_back_the_customer_when_the_lead_update_fails(
    db, employee_lead, organization, monkeypatch
):
    """The exact partial-write window: Customer written, Lead save explodes."""
    customers_before = Customer.objects.count()

    def exploding_save(self, *args, **kwargs):
        raise _Boom("simulated failure while marking the lead converted")

    monkeypatch.setattr(Lead, "save", exploding_save)

    with pytest.raises(_Boom):
        convert_lead(employee_lead, organization)

    # The Customer created moments before the failure must NOT survive it.
    assert Customer.objects.count() == customers_before


def test_convert_lead_leaves_the_lead_unconverted_after_a_rollback(
    db, employee_lead, organization, monkeypatch
):
    """The lead must stay genuinely convertible, not stranded half-way."""

    def exploding_save(self, *args, **kwargs):
        raise _Boom("simulated failure while marking the lead converted")

    monkeypatch.setattr(Lead, "save", exploding_save)
    with pytest.raises(_Boom):
        convert_lead(employee_lead, organization)
    monkeypatch.undo()

    employee_lead.refresh_from_db()
    assert employee_lead.status != Lead.Status.CONVERTED
    assert employee_lead.converted_customer_id is None

    # ...and a subsequent, non-failing conversion still works exactly once.
    customer = convert_lead(employee_lead, organization)
    employee_lead.refresh_from_db()
    assert employee_lead.converted_customer_id == customer.pk


def test_convert_lead_valid_request_creates_exactly_one_customer(db, employee_lead, organization):
    """Case (1) of the spec's transaction checklist: a valid request really
    does create the expected records — a rollback guarantee is worthless if
    the success path stopped working.
    """
    customers_before = Customer.objects.count()

    customer = convert_lead(employee_lead, organization)

    assert Customer.objects.count() == customers_before + 1
    employee_lead.refresh_from_db()
    assert employee_lead.status == Lead.Status.CONVERTED
    assert employee_lead.converted_customer_id == customer.pk


# --------------------------------------------------------------------------
# Endpoint level: the whole action, including the audit stamping the VIEW
# does after the service returns, is one transaction
# --------------------------------------------------------------------------


def test_convert_endpoint_rolls_back_when_audit_stamping_fails(
    api_client, employee, employee_lead, organization, monkeypatch
):
    """A custom ``@action`` is not covered by ``AuditStampedModelMixin``'s
    atomic ``create()``, and ``ATOMIC_REQUESTS`` is off — so the view's own
    post-service work needs the transaction to extend over it. If it does
    not, this failure commits both the Customer AND the converted Lead while
    answering 500.
    """
    from apps.crm import views as crm_views

    def exploding_stamp(*args, **kwargs):
        raise _Boom("simulated failure while stamping audit fields")

    monkeypatch.setattr(crm_views, "stamp_audit_fields", exploding_stamp)
    api_client.force_authenticate(employee)

    customers_before = Customer.objects.count()
    with pytest.raises(_Boom):
        api_client.post(_convert_url(employee_lead), {}, format="json")

    assert Customer.objects.count() == customers_before
    employee_lead.refresh_from_db()
    assert employee_lead.status != Lead.Status.CONVERTED
    assert employee_lead.converted_customer_id is None


def test_convert_endpoint_permission_failure_mutates_nothing(
    api_client, other_employee, employee_lead, organization
):
    """Case (4) of the spec's checklist: an unauthorized conversion must
    leave zero rows behind, not merely answer with an error code. The lead
    belongs to somebody else's scope, so the requester cannot even see it.
    """
    api_client.force_authenticate(other_employee)
    customers_before = Customer.objects.count()

    response = api_client.post(_convert_url(employee_lead), {}, format="json")

    assert response.status_code == 404
    assert Customer.objects.count() == customers_before
    employee_lead.refresh_from_db()
    assert employee_lead.status != Lead.Status.CONVERTED
    assert employee_lead.converted_customer_id is None


def test_convert_endpoint_rejects_a_second_conversion_without_creating_a_customer(
    api_client, employee, employee_lead, organization
):
    """Duplicate-conversion prevention, asserted at the ROW level rather
    than only on the status code: the refused second attempt must not leave
    a stray customer behind either.
    """
    api_client.force_authenticate(employee)
    first = api_client.post(_convert_url(employee_lead), {}, format="json")
    assert first.status_code == 201

    customers_after_first = Customer.objects.count()
    second = api_client.post(_convert_url(employee_lead), {}, format="json")

    assert second.status_code == 400
    assert "already been converted" in str(second.data)
    assert Customer.objects.count() == customers_after_first


def test_convert_endpoint_with_an_unknown_organization_creates_nothing(
    api_client, employee, employee_lead, organization
):
    """An invalid ``organization`` in the body is rejected BEFORE any write
    — case (2) of the spec's checklist.
    """
    api_client.force_authenticate(employee)
    customers_before = Customer.objects.count()

    response = api_client.post(
        _convert_url(employee_lead), {"organization": 99999999}, format="json"
    )

    assert response.status_code == 400
    assert Customer.objects.count() == customers_before
    employee_lead.refresh_from_db()
    assert employee_lead.converted_customer_id is None
