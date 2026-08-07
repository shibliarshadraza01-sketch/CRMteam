"""CP7: URL routes for the core app.

Empty on purpose. ``apps.core`` defines no concrete model and therefore no
concrete endpoint — it is pure foundation for future domain apps (CP8+),
exactly like ``apps.accounts.permissions``/``mixins`` were pure foundation
in CP6 before anything used them. This module exists (rather than being
omitted) so the app has a stable ``apps.core.urls`` import path ready to be
``include()``-d from ``config/urls.py`` the moment a future checkpoint adds
a real resource here.
"""
app_name = "core"

urlpatterns = [
    # No routes yet — see module docstring.
]
