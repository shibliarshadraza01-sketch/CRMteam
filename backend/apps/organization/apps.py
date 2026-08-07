"""App configuration for the organization app.

``apps.organization`` owns the CRM's organizational hierarchy: which
company (``Organization``) a record belongs to, how that company is
structured internally (``Department`` -> ``Team``), and who belongs to
which team (``Membership``). This is the first CP8+ app to build a concrete
schema on top of CP7's abstract foundation (``apps.core.models
.TimeStampedModel``) — every model here inherits timestamps from it rather
than redeclaring ``created_at``/``updated_at`` by hand.
"""
from django.apps import AppConfig


class OrganizationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.organization"
    label = "organization"
    verbose_name = "Organization"
