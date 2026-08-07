"""CP7: creates database tables for the test-only models in ``models.py``
without a real migration.

These models exist purely to exercise the abstract base classes in
``apps/core/models.py`` end to end (save/filter/soft-delete/restore) and
are deliberately NOT covered by any migration (see ``models.py``'s module
docstring for why). ``schema_editor().create_model()`` issues the same DDL
a migration would, directly, for the duration of a single test — this is
the standard technique for testing abstract-model behavior without
polluting the real migration graph with tables that will never exist in
production.

Every test using this fixture requires a real database connection and is
therefore blocked in this environment along with every other DB-dependent
test since CP2 — see BACKEND_PROGRESS.md.
"""
import pytest
from django.db import connection

from .models import SampleRecord, SampleSoftDeleteOnly, SampleTimeStamped

_TEST_MODELS = [SampleTimeStamped, SampleSoftDeleteOnly, SampleRecord]


@pytest.fixture
def core_test_tables(db):
    with connection.schema_editor() as editor:
        for model in _TEST_MODELS:
            editor.create_model(model)
    yield
    with connection.schema_editor() as editor:
        for model in reversed(_TEST_MODELS):
            editor.delete_model(model)
