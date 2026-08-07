"""CP10: tests for apps/core/pagination.py (project-wide pagination)."""
from django.conf import settings

from apps.core.pagination import StandardPagination


def test_standard_pagination_page_size_is_20():
    assert StandardPagination.page_size == 20


def test_standard_pagination_allows_client_override_up_to_100():
    assert StandardPagination.page_size_query_param == "page_size"
    assert StandardPagination.max_page_size == 100


def test_standard_pagination_is_the_project_wide_default():
    assert settings.REST_FRAMEWORK["DEFAULT_PAGINATION_CLASS"] == "apps.core.pagination.StandardPagination"
    assert settings.REST_FRAMEWORK["PAGE_SIZE"] == 20
