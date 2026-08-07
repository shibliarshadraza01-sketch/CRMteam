"""CP17: permissions for the workflow automation domain.

No new comparison logic. `Workflow` has a real `owner` FK;
`WorkflowTrigger`/`WorkflowAction`/`WorkflowExecution` each expose an
`owner` PROPERTY delegating to the `Workflow` they belong to (see
`models.py`). CP6's `IsOwnerOrSuperAdmin` — which discovers ownership via
a plain `hasattr(obj, "owner")` check — applies to all four models
unchanged, the same as every model in CP16's `apps.reports`.
"""
from apps.accounts.permissions import IsOwnerOrSuperAdmin

__all__ = ["IsOwnerOrSuperAdmin"]
