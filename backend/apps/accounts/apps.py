"""App configuration for the accounts app.

The accounts app owns the CRM's identity foundation: the custom User model
and its role field. Later checkpoints (CP3 auth, CP4 Super Admin access key,
CP5 device authorization, CP6 hierarchy/RBAC) all build on top of the model
defined here — they do not redefine identity.
"""
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    # Dotted path matches the app's location under backend/apps/accounts, not
    # a top-level "accounts" package — this must match INSTALLED_APPS exactly.
    name = "apps.accounts"
    label = "accounts"
    verbose_name = "Accounts"
