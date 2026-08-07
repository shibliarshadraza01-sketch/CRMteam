from django.apps import AppConfig


class SystemConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.system"
    label = "system"
    verbose_name = "System"

    def ready(self):
        """Connects CP19's audit-logging signal receivers.

        This is the ONLY place this checkpoint touches app startup —
        `ready()` is the standard, non-invasive Django mechanism for
        observing an EXISTING model's lifecycle without editing that
        model's own file at all. See `signals.py`'s own docstring for
        why this satisfies "integrate audit logging with existing apps...
        without changing existing business behavior" by construction.
        """
        from . import signals

        signals.register_audit_signals()
