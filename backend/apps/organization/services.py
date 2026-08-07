"""CP8: reusable service functions for team membership and management.

Following the CP5 (`apps.accounts.services`) pattern: narrow, single-purpose
functions, each doing one thing, callable from a future view/management
command/admin action alike, rather than duplicating this logic inline
wherever it's needed. Model-level CRUD that's already a single ORM call
(creating an ``Organization``, renaming a ``Department``) does NOT get a
wrapper here — a service function exists only where there's real behavior
beyond "call ``.objects.create()``" (idempotency, a business rule, a
multi-step operation).
"""
from .models import Membership, Team


def add_member(team, user, role=Membership.Role.MEMBER):
    """Add ``user`` to ``team`` with ``role``, idempotently.

    If the user is already a member, this does NOT change their existing
    role (adding someone who is already on the team is a no-op, not an
    implicit promotion/demotion) — use ``change_member_role()`` to change
    an existing membership's role explicitly. Returns
    ``(membership, created)`` mirroring ``get_or_create()``'s own return
    shape, since that's exactly what this wraps.
    """
    return Membership.objects.get_or_create(user=user, team=team, defaults={"role": role})


def remove_member(team, user):
    """Remove ``user`` from ``team`` if a membership exists.

    Returns ``True`` if a membership was actually deleted, ``False`` if the
    user was never a member — lets a caller distinguish "removed" from
    "there was nothing to remove" without needing a try/except.
    """
    deleted_count, _ = Membership.objects.filter(user=user, team=team).delete()
    return deleted_count > 0


def change_member_role(team, user, role):
    """Change an existing member's team-scoped role.

    Raises ``Membership.DoesNotExist`` if ``user`` is not currently a member
    of ``team`` — deliberately NOT falling back to creating one (that's
    ``add_member()``'s job); changing a role that doesn't exist yet is a
    caller error, not something to silently paper over.
    """
    membership = Membership.objects.get(user=user, team=team)
    membership.role = role
    membership.save(update_fields=["role", "updated_at"])
    return membership


def is_member(team, user):
    """True if ``user`` currently belongs to ``team``."""
    return Membership.objects.filter(user=user, team=team).exists()


def set_team_manager(team, user):
    """Assign (or clear, with ``user=None``) a team's manager.

    A thin wrapper rather than a bare ``team.manager = user; team.save()``
    at every call site — kept as a service function (rather than inlined)
    so a future rule (e.g. "the new manager must already be a team member")
    has exactly one place to be added.
    """
    team.manager = user
    team.save(update_fields=["manager", "updated_at"])
    return team


def get_user_teams(user):
    """All ``Team``s ``user`` currently belongs to, via their memberships."""
    return Team.objects.filter(memberships__user=user)


def get_team_members(team, role=None):
    """All ``User``s belonging to ``team``, optionally filtered to a single
    team-scoped ``role`` (e.g. ``Membership.Role.LEAD``).
    """
    memberships = team.memberships.all()
    if role is not None:
        memberships = memberships.filter(role=role)
    return memberships


__all__ = [
    "add_member",
    "remove_member",
    "change_member_role",
    "is_member",
    "set_team_manager",
    "get_user_teams",
    "get_team_members",
]
