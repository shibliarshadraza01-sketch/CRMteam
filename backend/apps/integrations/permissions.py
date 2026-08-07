"""CP18: permissions for the integrations domain.

No new comparison logic. `Integration` has a real `owner` FK; `APIKey`/
`WebhookEndpoint` delegate `owner` to `integration.owner`, and
`WebhookDelivery` delegates two levels deep to `endpoint.integration.owner`
(see `models.py`). CP6's `IsOwnerOrSuperAdmin` applies to all four models
unchanged, the same as every model in CP17's `apps.workflows`.
"""
from apps.accounts.permissions import IsOwnerOrSuperAdmin

__all__ = ["IsOwnerOrSuperAdmin"]
