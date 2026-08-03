"""ASGI config for Qualify Learn CRM backend.

Exposes the ASGI callable as a module-level variable named `application`.

For more on ASGI, see:
https://docs.djangoproject.com/en/stable/howto/deployment/asgi/
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

application = get_asgi_application()
