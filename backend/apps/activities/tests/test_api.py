"""CP14: end-to-end tests for the activities API. Requires a real database."""
import pytest

from apps.activities.models import Reminder, Task

pytestmark = pytest.mark.django_db

TASKS_URL = "/api/v1/activities/tasks/"
EVENTS_URL = "/api/v1/activities/events/"
LOGS_URL = "/api/v1/activities/activity-logs/"
REMINDERS_URL = "/api/v1/activities/reminders/"
TIMELINE_URL = "/api/v1/activities/timeline/"


def _detail(url, pk):
    return f"{url}{pk}/"


# --------------------------------------------------------------------------
# CRUD + ownership scoping (CP10's rule, reused unchanged)
# --------------------------------------------------------------------------


def test_unauthenticated_denied(api_client):
    response = api_client.get(TASKS_URL)
    assert response.status_code == 401


def test_employee_can_create_and_owns_it_by_default(api_client, employee):
    api_client.force_authenticate(employee)
    response = api_client.post(TASKS_URL, {"title": "Follow up"})
    assert response.status_code == 201
    assert response.data["owner"] == employee.id


def test_employee_cannot_see_another_employees_task(api_client, employee, other_employee):
    Task.objects.create(title="Not mine", owner=other_employee)
    api_client.force_authenticate(employee)

    response = api_client.get(TASKS_URL)

    assert response.data["count"] == 0


def test_employee_can_retrieve_own_task(api_client, employee, task):
    api_client.force_authenticate(employee)
    response = api_client.get(_detail(TASKS_URL, task.pk))
    assert response.status_code == 200


def test_employee_cannot_retrieve_others_task(api_client, other_employee, task):
    api_client.force_authenticate(other_employee)
    response = api_client.get(_detail(TASKS_URL, task.pk))
    assert response.status_code == 404


def test_super_admin_sees_every_task(api_client, super_admin, task):
    api_client.force_authenticate(super_admin)
    response = api_client.get(TASKS_URL)
    assert response.data["count"] == 1


def test_put_not_allowed(api_client, employee, task):
    api_client.force_authenticate(employee)
    response = api_client.put(_detail(TASKS_URL, task.pk), {"title": "X"})
    assert response.status_code == 405


def test_delete_soft_deletes(api_client, employee, task):
    api_client.force_authenticate(employee)
    response = api_client.delete(_detail(TASKS_URL, task.pk))
    assert response.status_code == 204
    task.refresh_from_db()
    assert task.is_deleted is True
    assert Task.objects.filter(pk=task.pk).exists()


# --------------------------------------------------------------------------
# Task lifecycle actions
# --------------------------------------------------------------------------


def test_complete_task_action(api_client, employee, task):
    api_client.force_authenticate(employee)
    response = api_client.post(f"{_detail(TASKS_URL, task.pk)}complete/")
    assert response.status_code == 200
    assert response.data["status"] == "COMPLETED"


def test_complete_already_completed_task_returns_400(api_client, employee, task):
    api_client.force_authenticate(employee)
    api_client.post(f"{_detail(TASKS_URL, task.pk)}complete/")
    response = api_client.post(f"{_detail(TASKS_URL, task.pk)}complete/")
    assert response.status_code == 400


def test_reassign_task_action(api_client, employee, other_employee, task):
    api_client.force_authenticate(employee)
    response = api_client.post(f"{_detail(TASKS_URL, task.pk)}reassign/", {"assigned_to": other_employee.pk})
    assert response.status_code == 200
    assert response.data["assigned_to"] == other_employee.pk


# --------------------------------------------------------------------------
# GenericForeignKey attachment via the API
# --------------------------------------------------------------------------


def test_create_task_attached_to_customer(api_client, employee, customer):
    from django.contrib.contenttypes.models import ContentType

    content_type = ContentType.objects.get_for_model(customer)
    api_client.force_authenticate(employee)

    response = api_client.post(
        TASKS_URL, {"title": "Renew contract", "content_type": content_type.pk, "object_id": customer.pk}
    )

    assert response.status_code == 201
    assert response.data["related_object"]["label"] == str(customer)


# --------------------------------------------------------------------------
# Event occurrences
# --------------------------------------------------------------------------


def test_event_occurrences_action(api_client, employee):
    from django.utils import timezone

    api_client.force_authenticate(employee)
    create_response = api_client.post(
        EVENTS_URL,
        {"title": "Standup", "start_at": timezone.now().isoformat(), "recurrence_frequency": "DAILY"},
    )
    assert create_response.status_code == 201

    response = api_client.get(f"{_detail(EVENTS_URL, create_response.data['id'])}occurrences/", {"limit": 3})

    assert response.status_code == 200
    assert len(response.data["occurrences"]) == 3


# --------------------------------------------------------------------------
# Reminder exactly-one-of validation + custom scoping
# --------------------------------------------------------------------------


def test_create_reminder_with_task(api_client, employee, task):
    from django.utils import timezone

    api_client.force_authenticate(employee)
    response = api_client.post(REMINDERS_URL, {"task": task.pk, "remind_at": timezone.now().isoformat()})
    assert response.status_code == 201


def test_create_reminder_with_both_rejected(api_client, employee, task, event):
    from django.utils import timezone

    api_client.force_authenticate(employee)
    response = api_client.post(
        REMINDERS_URL, {"task": task.pk, "event": event.pk, "remind_at": timezone.now().isoformat()}
    )
    assert response.status_code == 400


def test_employee_cannot_see_reminder_for_others_task(api_client, other_employee, task):
    from django.utils import timezone

    Reminder.objects.create(task=task, remind_at=timezone.now())
    api_client.force_authenticate(other_employee)

    response = api_client.get(REMINDERS_URL)

    assert response.data["count"] == 0


def test_mark_sent_action(api_client, employee, task):
    from django.utils import timezone

    reminder = Reminder.objects.create(task=task, remind_at=timezone.now())
    api_client.force_authenticate(employee)

    response = api_client.post(f"{_detail(REMINDERS_URL, reminder.pk)}mark-sent/")

    assert response.status_code == 200
    assert response.data["is_sent"] is True


# --------------------------------------------------------------------------
# Timeline endpoint
# --------------------------------------------------------------------------


def test_timeline_requires_query_params(api_client, employee):
    api_client.force_authenticate(employee)
    response = api_client.get(TIMELINE_URL)
    assert response.status_code == 400


def test_timeline_returns_merged_entries(api_client, employee, customer):
    from apps.activities.services import create_task, log_activity

    create_task("Renew", owner=employee, related_object=customer)
    log_activity(customer, "CALL", "Talked", actor=employee)
    api_client.force_authenticate(employee)

    response = api_client.get(TIMELINE_URL, {"content_type": "crm.customer", "object_id": customer.pk})

    assert response.status_code == 200
    kinds = {entry["kind"] for entry in response.data}
    assert kinds == {"task", "activity_log"}


# --------------------------------------------------------------------------
# Search / filter / ordering / pagination
# --------------------------------------------------------------------------


def test_search_tasks_by_title(api_client, employee):
    Task.objects.create(title="Renew Acme contract", owner=employee)
    Task.objects.create(title="Other", owner=employee)

    api_client.force_authenticate(employee)
    response = api_client.get(TASKS_URL, {"search": "Acme"})

    titles = {row["title"] for row in response.data["results"]}
    assert titles == {"Renew Acme contract"}


def test_filter_tasks_by_status(api_client, employee):
    Task.objects.create(title="Open", owner=employee)
    Task.objects.create(title="Done", owner=employee, status=Task.Status.COMPLETED)

    api_client.force_authenticate(employee)
    response = api_client.get(TASKS_URL, {"status": "COMPLETED"})

    titles = {row["title"] for row in response.data["results"]}
    assert titles == {"Done"}


def test_pagination_default_page_size_is_20(api_client, employee):
    for i in range(25):
        Task.objects.create(title=f"Task {i:03d}", owner=employee)
    api_client.force_authenticate(employee)

    response = api_client.get(TASKS_URL)

    assert len(response.data["results"]) == 20
    assert response.data["count"] == 25
