"""CP19: tests for apps/system/models.py."""
import pytest

from apps.system.models import AuditLog, BackgroundJob, FeatureFlag, SystemSetting

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_auditlog_has_no_soft_delete_fields():
    """AuditLog is the one model in this project that does NOT inherit
    SoftDeleteTimeStampedModel — see models.py's module docstring.
    """
    field_names = {f.name for f in AuditLog._meta.get_fields()}
    assert "is_deleted" not in field_names
    assert "deleted_at" not in field_names
    assert not hasattr(AuditLog, "soft_delete")


def test_auditlog_has_timestamps_and_audit_fields():
    field_names = {f.name for f in AuditLog._meta.get_fields()}
    assert {"created_at", "updated_at", "created_by", "updated_by"} <= field_names


def test_auditlog_has_generic_relation_fields_reused_from_activities():
    from apps.activities.models import RelatedToEntityModel

    assert issubclass(AuditLog, RelatedToEntityModel)


def test_auditlog_str_includes_action_and_actor():
    from django.contrib.auth import get_user_model
    from django.utils import timezone

    User = get_user_model()
    user = User(email="actor@example.com")
    log = AuditLog(action=AuditLog.Action.CREATE, actor=user, created_at=timezone.now())
    assert "Create" in str(log)


def test_auditlog_str_shows_system_when_no_actor():
    from django.utils import timezone

    log = AuditLog(action=AuditLog.Action.UPDATE, actor=None, created_at=timezone.now())
    assert "system" in str(log)


def test_systemsetting_inherits_soft_delete_and_timestamps_from_core():
    field_names = {f.name for f in SystemSetting._meta.get_fields()}
    assert {"created_at", "updated_at", "is_deleted", "deleted_at"} <= field_names


def test_systemsetting_key_is_unique():
    assert SystemSetting._meta.get_field("key").unique is True


def test_systemsetting_str_returns_key():
    assert str(SystemSetting(key="max_upload_size_mb")) == "max_upload_size_mb"


def test_featureflag_key_is_unique():
    assert FeatureFlag._meta.get_field("key").unique is True


def test_featureflag_is_enabled_defaults_false():
    assert FeatureFlag._meta.get_field("is_enabled").default is False


def test_featureflag_rollout_percentage_defaults_100():
    assert FeatureFlag._meta.get_field("rollout_percentage").default == 100


def test_featureflag_has_rollout_range_constraint():
    constraint_names = {c.name for c in FeatureFlag._meta.constraints}
    assert "system_flag_rollout_pct_range" in constraint_names


def test_backgroundjob_status_defaults_to_pending():
    assert BackgroundJob._meta.get_field("status").default == BackgroundJob.Status.PENDING


def test_backgroundjob_str_includes_name_and_status():
    assert str(BackgroundJob(name="Export", status=BackgroundJob.Status.RUNNING)) == "Export [RUNNING]"


def test_backgroundjob_owner_is_a_real_field_not_a_delegated_property():
    """Unlike every other model in this checkpoint, BackgroundJob owns its
    `owner` field directly — it has no parent record to delegate to.
    """
    assert "owner" in {f.name for f in BackgroundJob._meta.get_fields()}
    assert not isinstance(BackgroundJob.owner, property)


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_systemsetting_create_and_retrieve():
    setting = SystemSetting.objects.create(key="x", value={"a": 1})
    assert SystemSetting.objects.get(pk=setting.pk).is_active is True


@pytest.mark.django_db
def test_systemsetting_key_uniqueness_enforced():
    from django.db import IntegrityError

    SystemSetting.objects.create(key="dup", value=1)
    with pytest.raises(IntegrityError):
        SystemSetting.objects.create(key="dup", value=2)


@pytest.mark.django_db
def test_featureflag_rollout_constraint_rejects_out_of_range():
    from django.db import IntegrityError

    with pytest.raises(IntegrityError):
        FeatureFlag.objects.create(key="bad", name="Bad", rollout_percentage=101)


@pytest.mark.django_db
def test_auditlog_attaches_to_customer_via_generic_fk(customer):
    from django.contrib.contenttypes.models import ContentType

    log = AuditLog.objects.create(
        action=AuditLog.Action.CREATE, content_type=ContentType.objects.get_for_model(customer),
        object_id=customer.pk,
    )
    assert log.related_object == customer


@pytest.mark.django_db
def test_backgroundjob_manager_has_access_true_for_managed_owner(manager, employee, organization):
    from apps.organization.models import Department, Membership, Team

    department = Department.objects.create(organization=organization, name="Ops")
    team = Team.objects.create(department=department, name="Ops Team", manager=manager)
    Membership.objects.create(team=team, user=employee)

    job = BackgroundJob.objects.create(name="J", job_type="X", owner=employee)

    assert job.manager_has_access(manager) is True


# --------------------------------------------------------------------------
# Signal integration — the "integrate audit logging with existing apps"
# requirement, verified end-to-end
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_creating_a_customer_writes_an_auditlog_entry(organization, employee):
    from apps.crm.models import Customer

    customer = Customer.objects.create(
        organization=organization, name="Signal Co", slug="signal-co", owner=employee, created_by=employee
    )

    log = AuditLog.objects.for_entity(customer).get()
    assert log.action == AuditLog.Action.CREATE
    assert log.actor == employee


@pytest.mark.django_db
def test_updating_a_customer_writes_a_second_auditlog_entry(customer, employee):
    customer.updated_by = employee
    customer.name = "Renamed"
    customer.save()

    logs = AuditLog.objects.filter(
        content_type__model="customer", object_id=customer.pk
    ).order_by("created_at")
    assert [log.action for log in logs] == [AuditLog.Action.CREATE, AuditLog.Action.UPDATE]


@pytest.mark.django_db
def test_creating_an_opportunity_writes_an_auditlog_entry(customer, employee):
    from apps.crm.opportunities import Opportunity

    opportunity = Opportunity.objects.create(customer=customer, title="Big Deal", owner=employee, created_by=employee)

    assert AuditLog.objects.for_entity(opportunity).filter(action=AuditLog.Action.CREATE).exists()


@pytest.mark.django_db
def test_saving_an_unaudited_model_does_not_write_an_auditlog_entry(customer):
    """A sanity check that audit logging is CURATED, not blanket-applied —
    Address is not one of the five audited models.
    """
    from apps.crm.models import Address

    before = AuditLog.objects.count()
    Address.objects.create(customer=customer, address_type=Address.AddressType.BILLING, line1="1 Main St", city="X", country="US")

    after = AuditLog.objects.count()
    assert after == before


@pytest.mark.django_db
def test_audit_logging_failure_does_not_break_the_save_it_observes(organization, employee, monkeypatch):
    """The critical safety property: if apps.system's own logging code
    raises for any reason, the underlying Customer.save() must still
    succeed — see signals.py's own docstring.
    """
    from apps.crm.models import Customer

    def broken_log_audit_event(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("apps.system.services.log_audit_event", broken_log_audit_event)

    customer = Customer.objects.create(organization=organization, name="Still Works", slug="still-works", owner=employee)

    assert Customer.objects.filter(pk=customer.pk).exists()
