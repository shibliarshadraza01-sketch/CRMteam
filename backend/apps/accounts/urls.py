"""CP3: authentication routes, mounted at /api/v1/auth/ by config/urls.py.

    POST /api/v1/auth/login/
    POST /api/v1/auth/refresh/
    POST /api/v1/auth/logout/
    GET  /api/v1/auth/me/

/refresh/ uses SimpleJWT's own ``TokenRefreshView`` directly rather than a
custom wrapper — it already does exactly what STEP 5 requires (validate the
refresh token, honor rotation/blacklist settings, reject invalid/expired/
blacklisted tokens) and re-implementing it would just be a thinner, riskier
copy of already-reviewed library code.
"""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import LoginView, LogoutView, MeView

app_name = "accounts"

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
]
