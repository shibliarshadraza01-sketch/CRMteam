"""CP14: tests for apps/activities/admin.py. Django's admin registry is
populated at import time — no database needed.
"""
from django.contrib import admin

from apps.activities.admin import ActivityLogAdmin, EventAdmin, ReminderAdmin, TaskAdmin
from apps.activities.models import ActivityLog, Event, Reminder, Task
from apps.core.admin import SoftDeleteTimeStampedAdminMixin


def test_all_four_models_are_registered():
    assert Task in admin.site._registry
    assert Event in admin.site._registry
    assert ActivityLog in admin.site._registry
    assert Reminder in admin.site._registry


def test_registered_admins_are_the_expected_classes():
    assert isinstance(admin.site._registry[Task], TaskAdmin)
    assert isinstance(admin.site._registry[Event], EventAdmin)
    assert isinstance(admin.site._registry[ActivityLog], ActivityLogAdmin)
    assert isinstance(admin.site._registry[Reminder], ReminderAdmin)


def test_every_activities_admin_uses_soft_delete_timestamped_mixin():
    for admin_class in (TaskAdmin, EventAdmin, ActivityLogAdmin, ReminderAdmin):
        assert issubclass(admin_class, SoftDeleteTimeStampedAdminMixin)


def test_admins_declare_search_fields():
    for model in (Task, Event, ActivityLog, Reminder):
        admin_instance = admin.site._registry[model]
        assert admin_instance.search_fields


def test_reminder_admin_autocompletes_task_and_event():
    admin_instance = admin.site._registry[Reminder]
    assert set(admin_instance.autocomplete_fields) == {"task", "event"}
