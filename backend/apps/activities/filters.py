"""CP14: django-filter ``FilterSet`` classes for the activities API."""
import django_filters

from .models import ActivityLog, Event, Reminder, Task


class TaskFilterSet(django_filters.FilterSet):
    due_before = django_filters.DateTimeFilter(field_name="due_date", lookup_expr="lte")
    due_after = django_filters.DateTimeFilter(field_name="due_date", lookup_expr="gte")

    class Meta:
        model = Task
        fields = ["status", "priority", "owner", "assigned_to", "content_type", "object_id"]


class EventFilterSet(django_filters.FilterSet):
    starts_before = django_filters.DateTimeFilter(field_name="start_at", lookup_expr="lte")
    starts_after = django_filters.DateTimeFilter(field_name="start_at", lookup_expr="gte")

    class Meta:
        model = Event
        fields = ["owner", "recurrence_frequency", "content_type", "object_id"]


class ActivityLogFilterSet(django_filters.FilterSet):
    class Meta:
        model = ActivityLog
        fields = ["activity_type", "actor", "content_type", "object_id"]


class ReminderFilterSet(django_filters.FilterSet):
    class Meta:
        model = Reminder
        fields = ["task", "event", "is_sent"]
