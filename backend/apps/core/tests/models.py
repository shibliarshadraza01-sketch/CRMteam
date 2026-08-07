"""CP7: test-only concrete models exercising the abstract bases in
``apps/core/models.py``.

Abstract models cannot be instantiated against a real table on their own —
something concrete has to inherit them for save/filter/update behavior to
be testable at all. These models exist ONLY for that purpose: they are not
part of the production schema, are not referenced by any migration, and are
not imported anywhere outside ``apps/core/tests/``. Registered under the
real ``core`` app label (``app_label = "core"``) so Django's app registry
resolves them without needing a dedicated fake test app.

Any test that persists one of these (``.save()``, ``.objects.filter()``,
etc.) requires a real database and is therefore blocked in this environment
for the same reason every other DB-backed test since CP2 is — see
BACKEND_PROGRESS.md. Tests that only inspect field/manager/method
definitions on these classes need no database at all.
"""
from django.db import models

from apps.core.models import SoftDeleteModel, SoftDeleteTimeStampedModel, TimeStampedModel


class SampleTimeStamped(TimeStampedModel):
    """Exercises ``TimeStampedModel`` (+ its inherited ``AuditModel``) in
    isolation, with no soft-delete behavior mixed in.
    """

    name = models.CharField(max_length=100)

    class Meta:
        app_label = "core"


class SampleSoftDeleteOnly(SoftDeleteModel):
    """Exercises ``SoftDeleteModel`` (+ its inherited ``AuditModel``) in
    isolation, with no timestamp fields mixed in.
    """

    name = models.CharField(max_length=100)

    class Meta:
        app_label = "core"


class SampleRecord(SoftDeleteTimeStampedModel):
    """The main test-only model: exercises the full
    ``SoftDeleteTimeStampedModel`` diamond (timestamps + soft delete +
    audit, all combined) end to end.
    """

    name = models.CharField(max_length=100)

    class Meta:
        app_label = "core"

    def __str__(self):
        return self.name
