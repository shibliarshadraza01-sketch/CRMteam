"""CP14: tests for apps/activities/models.py."""
import pytest
from django.contrib.contenttypes.models import ContentType

from apps.activities.models import ActivityLog, Event, Reminder, Task

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_task_inherits_soft_delete_and_timestamps_from_core():
    field_names = {f.name for f in Task._meta.get_fields()}
    assert {"created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at"} <= field_names


def test_task_has_generic_relation_fields():
    field_names = {f.name for f in Task._meta.get_fields()}
    assert {"content_type", "object_id", "related_object"} <= field_names


def test_event_and_activitylog_also_have_generic_relation_fields():
    for model in (Event, ActivityLog):
        field_names = {f.name for f in model._meta.get_fields()}
        assert {"content_type", "object_id", "related_object"} <= field_names


def test_reminder_has_no_generic_relation_fields():
    """Reminder attaches to a Task/Event, not directly to a CRM entity —
    see models.py's module docstring for why.
    """
    field_names = {f.name for f in Reminder._meta.get_fields()}
    assert "content_type" not in field_names
    assert "object_id" not in field_names


def test_task_priority_and_status_defaults():
    assert Task._meta.get_field("priority").default == Task.Priority.MEDIUM
    assert Task._meta.get_field("status").default == Task.Status.PENDING


def test_task_str_returns_title():
    assert str(Task(title="Call back")) == "Call back"


def test_task_manager_has_access_false_without_owner():
    task = Task(title="No owner")
    assert task.owner_id is None


def test_event_recurrence_defaults_to_none():
    assert Event._meta.get_field("recurrence_frequency").default == Event.RecurrenceFrequency.NONE


def test_event_is_recurring_property():
    assert Event(recurrence_frequency=Event.RecurrenceFrequency.NONE).is_recurring is False
    assert Event(recurrence_frequency=Event.RecurrenceFrequency.WEEKLY).is_recurring is True


def test_event_end_after_start_constraint_declared():
    constraint_names = {c.name for c in Event._meta.constraints}
    assert "activities_event_end_after_start" in constraint_names


def test_activitylog_owner_property_delegates_to_actor():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User(email="actor@example.com")
    log = ActivityLog(actor=user)
    assert log.owner is user


def test_activitylog_description_is_required_not_blank():
    assert ActivityLog._meta.get_field("description").blank is False


def test_reminder_has_exactly_one_constraint():
    constraint_names = {c.name for c in Reminder._meta.constraints}
    assert "activities_reminder_exactly_one_of_task_or_event" in constraint_names


def test_reminder_subject_property_returns_task_when_set():
    task = Task(title="T")
    reminder = Reminder(task=task)
    assert reminder.subject is task


def test_reminder_subject_property_returns_event_when_set():
    event = Event(title="E")
    reminder = Reminder(event=event)
    assert reminder.subject is event


def test_reminder_owner_property_delegates_to_task_owner():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User(email="owner@example.com")
    task = Task(title="T", owner=user)
    reminder = Reminder(task=task)
    assert reminder.owner is user


def test_reminder_owner_property_none_without_subject():
    assert Reminder().owner is None


def test_related_entity_types_limits_to_five_crm_models():
    from apps.activities.models import RELATABLE_ENTITY_TYPES

    where_sql = str(RELATABLE_ENTITY_TYPES)
    for model_name in ("customer", "lead", "opportunity", "quote", "invoice"):
        assert model_name in where_sql


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_task_create_and_retrieve(employee):
    t = Task.objects.create(title="Draft proposal", owner=employee)
    assert Task.objects.get(pk=t.pk).status == Task.Status.PENDING


@pytest.mark.django_db
def test_task_attaches_to_customer_via_generic_fk(customer):
    content_type = ContentType.objects.get_for_model(customer)
    task = Task.objects.create(title="Renew contract", content_type=content_type, object_id=customer.pk)

    assert task.related_object == customer


@pytest.mark.django_db
def test_event_attaches_to_customer_via_generic_fk(customer):
    from django.utils import timezone

    content_type = ContentType.objects.get_for_model(customer)
    event = Event.objects.create(
        title="QBR", start_at=timezone.now(), content_type=content_type, object_id=customer.pk
    )

    assert event.related_object == customer


@pytest.mark.django_db
def test_event_end_before_start_rejected_by_constraint(employee):
    from datetime import timedelta

    from django.db import IntegrityError
    from django.utils import timezone

    start = timezone.now()
    with pytest.raises(IntegrityError):
        Event.objects.create(title="Bad", start_at=start, end_at=start - timedelta(hours=1))


@pytest.mark.django_db
def test_reminder_exactly_one_constraint_rejects_both(task, event):
    from django.db import IntegrityError
    from django.utils import timezone

    with pytest.raises(IntegrityError):
        Reminder.objects.create(task=task, event=event, remind_at=timezone.now())


@pytest.mark.django_db
def test_reminder_exactly_one_constraint_rejects_neither():
    from django.db import IntegrityError
    from django.utils import timezone

    with pytest.raises(IntegrityError):
        Reminder.objects.create(remind_at=timezone.now())


@pytest.mark.django_db
def test_deleting_task_cascades_to_reminders(task):
    from django.utils import timezone

    reminder = Reminder.objects.create(task=task, remind_at=timezone.now())
    task.delete()
    assert not Reminder.objects.filter(pk=reminder.pk).exists()


@pytest.mark.django_db
def test_activitylog_manager_has_access_true_for_managed_actor(manager, employee, organization):
    from apps.organization.models import Department, Membership, Team

    department = Department.objects.create(organization=organization, name="Sales")
    team = Team.objects.create(department=department, name="Sales Team", manager=manager)
    Membership.objects.create(team=team, user=employee)

    log = ActivityLog.objects.create(actor=employee, description="Called")

    assert log.manager_has_access(manager) is True
