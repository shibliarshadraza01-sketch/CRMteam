"""CP15: django-filter ``FilterSet`` classes for the communications API."""
import django_filters

from .models import CommunicationLog, EmailMessage, EmailTemplate, Notification


class EmailTemplateFilterSet(django_filters.FilterSet):
    class Meta:
        model = EmailTemplate
        fields = ["is_active"]


class EmailMessageFilterSet(django_filters.FilterSet):
    class Meta:
        model = EmailMessage
        fields = ["status", "owner", "template", "content_type", "object_id"]


class NotificationFilterSet(django_filters.FilterSet):
    class Meta:
        model = Notification
        fields = ["notification_type", "is_read", "recipient", "content_type", "object_id"]


class CommunicationLogFilterSet(django_filters.FilterSet):
    class Meta:
        model = CommunicationLog
        fields = ["channel", "actor", "content_type", "object_id"]
