"""CP15: tests for apps/communications/admin.py. Django's admin registry is
populated at import time — no database needed.
"""
from django.contrib import admin

from apps.communications.admin import (
    CommunicationLogAdmin,
    EmailMessageAdmin,
    EmailTemplateAdmin,
    NotificationAdmin,
)
from apps.communications.models import CommunicationLog, EmailMessage, EmailTemplate, Notification
from apps.core.admin import SoftDeleteTimeStampedAdminMixin


def test_all_four_models_are_registered():
    assert EmailTemplate in admin.site._registry
    assert EmailMessage in admin.site._registry
    assert Notification in admin.site._registry
    assert CommunicationLog in admin.site._registry


def test_registered_admins_are_the_expected_classes():
    assert isinstance(admin.site._registry[EmailTemplate], EmailTemplateAdmin)
    assert isinstance(admin.site._registry[EmailMessage], EmailMessageAdmin)
    assert isinstance(admin.site._registry[Notification], NotificationAdmin)
    assert isinstance(admin.site._registry[CommunicationLog], CommunicationLogAdmin)


def test_every_communications_admin_uses_soft_delete_timestamped_mixin():
    for admin_class in (EmailTemplateAdmin, EmailMessageAdmin, NotificationAdmin, CommunicationLogAdmin):
        assert issubclass(admin_class, SoftDeleteTimeStampedAdminMixin)


def test_admins_declare_search_fields():
    for model in (EmailTemplate, EmailMessage, Notification, CommunicationLog):
        admin_instance = admin.site._registry[model]
        assert admin_instance.search_fields
