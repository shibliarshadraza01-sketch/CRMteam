"""CP3: authentication API views.

Four endpoints, mounted at /api/v1/auth/ (see apps/accounts/urls.py):

- POST /login/    -> LoginView   (public)
- POST /refresh/  -> SimpleJWT's own TokenRefreshView (wired directly in
                      urls.py — see BACKEND_LEARNING_GUIDE.md CP3 for why we
                      did not wrap it)
- POST /logout/   -> LogoutView  (public; the refresh token itself is the
                      credential being acted on)
- GET  /me/       -> MeView      (requires a valid access token)

Views stay thin: validate via a serializer, issue/blacklist tokens via
SimpleJWT, return a response. No authentication logic is duplicated here —
password checking lives in Django's auth backend (via `authenticate()` in
LoginSerializer), token signing/verification lives in SimpleJWT.
"""
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import LoginSerializer, LogoutSerializer, UserSerializer


class LoginView(generics.GenericAPIView):
    """POST /api/v1/auth/login/ — email + password -> access + refresh + user."""

    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []  # logging in does not require being already authenticated

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class MeView(generics.RetrieveAPIView):
    """GET /api/v1/auth/me/ — the authenticated user's safe identity info.

    Requires a valid, non-expired access token. This is the endpoint the
    frontend will call on app load to restore "who is logged in" from a
    stored token, without ever needing the password again.
    """

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class LogoutView(generics.GenericAPIView):
    """POST /api/v1/auth/logout/ — blacklist a refresh token.

    Takes the refresh token (not the access token) in the body. Blacklisting
    it means it can never again be exchanged for a new access token via
    /refresh/, even though it hasn't reached its natural REFRESH_TOKEN_LIFETIME
    expiry yet. This is SimpleJWT's supported logout pattern; no custom
    server-side session table was introduced.
    """

    serializer_class = LogoutSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []  # possessing a valid refresh token is the credential here

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Successfully logged out."}, status=status.HTTP_200_OK)
