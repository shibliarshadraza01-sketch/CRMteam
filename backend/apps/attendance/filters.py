"""django-filter ``FilterSet`` for the attendance session list endpoint."""
import django_filters

from .models import AttendanceSession


class AttendanceSessionFilterSet(django_filters.FilterSet):
    login_from = django_filters.DateTimeFilter(field_name="login_at", lookup_expr="gte")
    login_to = django_filters.DateTimeFilter(field_name="login_at", lookup_expr="lte")

    class Meta:
        model = AttendanceSession
        fields = ["employee", "state"]
