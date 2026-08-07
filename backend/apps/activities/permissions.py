"""CP14: permissions for the activity layer.

No new permission class is needed here. `Task`/`Event` have a real ``owner``
FK; `ActivityLog` exposes an ``owner`` property delegating to ``actor``;
`Reminder` exposes an ``owner`` property delegating to whichever `Task`/
`Event` it belongs to (see ``models.py``) — every model in this app is
therefore directly compatible with CP6's ``IsOwnerOrSuperAdmin`` exactly as
it already exists (it discovers ownership via ``resolve_owner()``, which
checks for an ``owner`` attribute — a property satisfies that check exactly
like a real field) and with each model's own ``manager_has_access()`` hook,
reusing CP10's ``managed_user_ids()`` — the same pattern CP9's
`ContactPerson`/`Address` established for delegated ownership. Re-exported
here (rather than importing straight from ``apps.accounts.permissions`` in
``views.py``) purely so this app's permission dependency is visible in one
place, matching every other domain app's structure.
"""
from apps.accounts.permissions import IsOwnerOrSuperAdmin

__all__ = ["IsOwnerOrSuperAdmin"]
