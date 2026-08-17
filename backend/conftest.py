"""Project-root conftest.py — deliberately the ONLY place a session-scoped
pytest-django fixture override belongs.

CP7's ``django_db_setup`` override (creating apps/core/tests/models.py's
unmanaged test-only tables once, for the whole session — see that app's
own conftest.py for the full "why") used to live in
``apps/core/tests/conftest.py``. That works when the ENTIRE project's test
suite is collected via ``pytest`` with no path arguments (this project's
default — see pytest.ini's ``testpaths = .``), because pytest still ends
up resolving ``django_db_setup`` to that override for whichever test
happens to request it first, and caches it for the rest of the session.

It silently STOPS working the moment anyone runs a NARROWER, explicit
subset of tests that doesn't happen to include something under
``apps/core/tests/`` early enough in collection order — e.g.
``pytest apps/crm/tests/test_models.py`` alone. ``apps/core/tests/`` is a
SIBLING of ``apps/crm/tests/``, not an ancestor, so pytest's normal
fixture-resolution rule (walk up the directory tree from the test's own
location) never finds that override for a CRM test at all; the test then
runs against the DEFAULT (unmodified) ``django_db_setup``, and any test
that deletes a ``User`` — cascading into ``SampleTimeStamped``/etc.'s
``created_by``/``updated_by`` FKs — fails with "relation does not exist".

Living here instead makes the override visible from EVERY test in the
project, regardless of which subset is actually being run.
"""
import pytest
from django.db import connection

from apps.core.tests.models import SampleRecord, SampleSoftDeleteOnly, SampleTimeStamped

_TEST_MODELS = [SampleTimeStamped, SampleSoftDeleteOnly, SampleRecord]


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        with connection.schema_editor() as editor:
            for model in _TEST_MODELS:
                editor.create_model(model)
    yield
    with django_db_blocker.unblock():
        with connection.schema_editor() as editor:
            for model in reversed(_TEST_MODELS):
                editor.delete_model(model)
