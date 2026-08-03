"""WSGI config for Qualify Learn CRM backend.

Exposes the WSGI callable as a module-level variable named `application`.

For more on WSGI, see:
https://docs.djangoproject.com/en/stable/howto/deployment/wsgi/
"""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

application = get_wsgi_application()
