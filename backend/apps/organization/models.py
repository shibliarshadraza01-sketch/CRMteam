"""CP8: the CRM's organizational hierarchy.

``Organization`` -> ``Department`` -> ``Team`` -> ``Membership`` (users).
This is the first checkpoint to build a CONCRETE schema on top of CP7's
abstract foundation (``apps.core.models.TimeStampedModel``) — every model
below inherits ``created_at``/``updated_at`` from it rather than
redeclaring them, exactly as CP7's own docs anticipated future domain
models doing.

Soft delete (``apps.core.models.SoftDeleteModel``) was deliberately NOT
mixed in here — CP8's spec asks only for timestamps on these models, and
adding soft delete for a hierarchy this early would be speculative: what
"deleting" an ``Organization`` with active ``Department``s/``Team``s/
``Membership``s should mean (cascade-soft-delete children? block it?) is a
real product decision this checkpoint has no requirement to make. See
BACKEND_LEARNING_GUIDE.md CP8, "why no soft delete yet", for the full
reasoning.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class OrganizationQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)


class Organization(TimeStampedModel):
    """The top of the hierarchy — one row per company/tenant using the CRM.

    Nothing in this checkpoint enforces multi-tenant data isolation (e.g.
    scoping every other model's queries to "the caller's organization") —
    that is a deliberately separate, larger concern for a future checkpoint
    once there's an actual need for it. CP8 only builds the *shape* of the
    hierarchy.
    """

    name = models.CharField(_("name"), max_length=200, unique=True)
    slug = models.SlugField(_("slug"), max_length=220, unique=True)
    is_active = models.BooleanField(_("is active"), default=True, db_index=True)

    objects = models.Manager.from_queryset(OrganizationQuerySet)()

    class Meta:
        ordering = ["name"]
        verbose_name = _("organization")
        verbose_name_plural = _("organizations")

    def __str__(self):
        return self.name


class Department(TimeStampedModel):
    """A division within an ``Organization`` (e.g. "Sales", "Support")."""

    organization = models.ForeignKey(
        Organization,
        verbose_name=_("organization"),
        on_delete=models.CASCADE,
        related_name="departments",
    )
    name = models.CharField(_("name"), max_length=200)
    description = models.TextField(_("description"), blank=True, default="")

    class Meta:
        ordering = ["organization", "name"]
        verbose_name = _("department")
        verbose_name_plural = _("departments")
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                name="organization_department_unique_org_name",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "name"], name="org_department_org_name_idx"),
        ]

    def __str__(self):
        return f"{self.organization.name} / {self.name}"


class Team(TimeStampedModel):
    """A working group within a ``Department``, optionally led by a
    ``Manager``-or-above ``User`` (``manager``).
    """

    department = models.ForeignKey(
        Department,
        verbose_name=_("department"),
        on_delete=models.CASCADE,
        related_name="teams",
    )
    name = models.CharField(_("name"), max_length=200)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("manager"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="teams_managed",
        help_text=_("The user who manages this team, if assigned."),
    )

    class Meta:
        ordering = ["department", "name"]
        verbose_name = _("team")
        verbose_name_plural = _("teams")
        constraints = [
            models.UniqueConstraint(
                fields=["department", "name"],
                name="organization_team_unique_department_name",
            ),
        ]
        indexes = [
            models.Index(fields=["department", "name"], name="org_team_department_name_idx"),
        ]

    def __str__(self):
        return f"{self.department} / {self.name}"

    @property
    def owner(self):
        """Lets ``apps.core.permissions.IsOwnerOrSuperAdmin`` resolve this
        team's manager as its "owner" with zero new permission logic — see
        that class's ``resolve_owner()`` helper (CP6/CP7), which checks for
        exactly this attribute name. A team with no assigned manager simply
        has no owner (``None``), which ``resolve_owner()`` already treats
        as "deny unless Super Admin" — the same fail-closed default as
        everywhere else in this codebase.
        """
        return self.manager


class Membership(TimeStampedModel):
    """A ``User``'s membership on a ``Team``, with a role scoped to that
    team (distinct from ``accounts.User.role``, the CP2/CP6 *global* RBAC
    role — see BACKEND_LEARNING_GUIDE.md CP8, "two different kinds of
    role", for why these are deliberately separate concepts).
    """

    class Role(models.TextChoices):
        LEAD = "LEAD", _("Team Lead")
        MEMBER = "MEMBER", _("Member")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("user"),
        on_delete=models.CASCADE,
        related_name="team_memberships",
    )
    team = models.ForeignKey(
        Team,
        verbose_name=_("team"),
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(
        _("role"), max_length=20, choices=Role.choices, default=Role.MEMBER, db_index=True
    )
    joined_at = models.DateTimeField(_("joined at"), default=timezone.now)

    class Meta:
        ordering = ["team", "user"]
        verbose_name = _("membership")
        verbose_name_plural = _("memberships")
        constraints = [
            models.UniqueConstraint(fields=["user", "team"], name="organization_membership_unique_user_team"),
        ]
        indexes = [
            models.Index(fields=["team", "role"], name="org_membership_team_role_idx"),
        ]

    def __str__(self):
        return f"{self.user} @ {self.team} ({self.role})"

    @property
    def owner(self):
        """Lets ``IsOwnerOrSuperAdmin`` resolve the member themselves as the
        "owner" of their own membership row (e.g. a user viewing their own
        team memberships) — see ``resolve_owner()`` (CP6/CP7).
        """
        return self.user

    def manager_has_access(self, user):
        """CP6's documented per-object extension point (see
        ``apps.accounts.permissions.manager_has_access()``'s docstring),
        exercised here for real for the first time: a ``Manager``-or-above
        user who manages this membership's team has explicit access to it,
        even though they are not the membership's ``owner`` (the member
        themselves is). Falls back to ``False`` (never access) if the team
        has no assigned manager or the requester isn't that manager.
        """
        team_manager_id = self.team.manager_id
        return team_manager_id is not None and team_manager_id == getattr(user, "id", None)
