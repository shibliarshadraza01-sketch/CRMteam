"""App configuration for the core app.

``apps.core`` owns no domain data of its own (no Lead, no Customer, nothing
CP7+ will eventually expose over HTTP as a business resource). It owns the
reusable *foundation* every future domain app builds on: abstract base
models (timestamps, soft delete, audit fields), the managers that make soft
delete usable, and the serializer/admin/permission building blocks that let
a future app add a concrete model without re-solving any of this.
"""
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"
    verbose_name = "Core"
