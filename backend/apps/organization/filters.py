"""Final-completion-pass: django-filter ``FilterSet`` classes for the
organization hierarchy API, following the exact plain-field-filter pattern
CP10's ``apps/crm/filters.py`` established.
"""
import django_filters

from .models import Department, Membership, Organization, Team


class OrganizationFilterSet(django_filters.FilterSet):
    class Meta:
        model = Organization
        fields = ["is_active"]


class DepartmentFilterSet(django_filters.FilterSet):
    class Meta:
        model = Department
        fields = ["organization"]


class TeamFilterSet(django_filters.FilterSet):
    class Meta:
        model = Team
        fields = ["department", "manager"]


class MembershipFilterSet(django_filters.FilterSet):
    class Meta:
        model = Membership
        fields = ["team", "user", "role"]
