"""CP3/CP4/CP5: authentication routes, mounted at /api/v1/auth/ by config/urls.py.

    POST   /api/v1/auth/login/
    POST   /api/v1/auth/refresh/
    POST   /api/v1/auth/logout/
    GET    /api/v1/auth/me/
    POST   /api/v1/auth/super-admin/verify/     (CP4)
    GET    /api/v1/auth/sessions/                (CP5)
    DELETE /api/v1/auth/sessions/<id>/            (CP5)
    POST   /api/v1/auth/logout-all/               (CP5)

/refresh/ now uses SessionAwareTokenRefreshView (CP5) — a thin wrapper around
SimpleJWT's own TokenRefreshView, not a reimplementation; see views.py for
why. Still not reimplementing SimpleJWT's actual refresh logic itself — see
CP3's original reasoning for why re-implementing already-reviewed library
code would be a thinner, riskier copy.
"""
from django.urls import path

from .views import (
    LoginView,
    LogoutAllView,
    LogoutView,
    MeView,
    SessionAwareTokenRefreshView,
    SessionListView,
    SessionRevokeView,
    SuperAdminVerifyView,
)

app_name = "accounts"

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", SessionAwareTokenRefreshView.as_view(), name="refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
    path("super-admin/verify/", SuperAdminVerifyView.as_view(), name="super-admin-verify"),
    path("sessions/", SessionListView.as_view(), name="session-list"),
    path("sessions/<int:id>/", SessionRevokeView.as_view(), name="session-revoke"),
    path("logout-all/", LogoutAllView.as_view(), name="logout-all"),
]
