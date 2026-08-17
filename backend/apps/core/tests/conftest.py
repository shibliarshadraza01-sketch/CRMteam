"""CP7: fixtures for the test-only models in ``models.py``.

The actual table-creation (``django_db_setup`` session override) now lives
in the project-root ``backend/conftest.py`` — NOT here — specifically so
it's visible to every test in the project regardless of which subset is
being run, not just tests collected under this directory. See that file's
own docstring for the full "why" (a sibling-directory conftest.py is
invisible to pytest's normal fixture resolution for tests outside its own
subtree, a real, reproducible bug this project hit).
"""
import pytest


@pytest.fixture
def core_test_tables(db):
    """Kept as an explicit, readable dependency marker in tests that
    persist ``SampleTimeStamped``/``SampleSoftDeleteOnly``/``SampleRecord``
    rows — actual table creation happens once per session, in the
    project-root conftest.py, not per test.
    """
    yield
