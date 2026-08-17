"""Final-completion-pass: URL routing for the organization hierarchy API.

Mounted at ``/api/v1/organization/`` (see ``config/urls.py``), the same
one-router-per-app pattern every CP9+ domain app uses.
"""
from rest_framework.routers import DefaultRouter

from .views import DepartmentViewSet, MembershipViewSet, OrganizationViewSet, TeamViewSet

router = DefaultRouter()
router.register("organizations", OrganizationViewSet, basename="organization")
router.register("departments", DepartmentViewSet, basename="department")
router.register("teams", TeamViewSet, basename="team")
router.register("memberships", MembershipViewSet, basename="membership")

urlpatterns = router.urls
