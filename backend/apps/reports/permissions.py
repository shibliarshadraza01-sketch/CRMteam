"""CP16: permissions for the reporting/dashboard domain.

No new comparison logic. `SavedReport`/`Dashboard` have a real `owner`
FK; `ReportExecution`/`DashboardWidget` each expose an `owner` PROPERTY
delegating to the record they belong to (`report.owner`/`dashboard.owner`
— see `models.py`). CP6's `IsOwnerOrSuperAdmin` — which discovers
ownership via a plain `hasattr(obj, "owner")` check — applies to all four
models unchanged, the same as every model in CP14's `apps.activities` and
CP15's `apps.communications`.
"""
from apps.accounts.permissions import IsOwnerOrSuperAdmin

__all__ = ["IsOwnerOrSuperAdmin"]
