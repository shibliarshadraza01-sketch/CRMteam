"""App configuration for the crm app.

``apps.crm`` owns the CRM's actual sales-facing domain data: ``Lead``
(a raw, pre-qualification inquiry), ``Customer`` (an organization's real
account, scoped under CP8's ``Organization``), and ``ContactPerson``/
``Address`` (details belonging to a ``Customer``). This is the first app
to combine CP7's soft-delete foundation with CP8's organizational
hierarchy — see BACKEND_LEARNING_GUIDE.md CP9 for the full design.
"""
from django.apps import AppConfig


class CrmConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.crm"
    label = "crm"
    verbose_name = "CRM"
