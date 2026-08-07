"""CP10: project-wide pagination.

A single, named pagination class (rather than the bare
``rest_framework.pagination.PageNumberPagination`` CP1 originally
configured) so every list endpoint's page size and override behavior is
defined in exactly one place, reusable by every future app the same way
``apps.core``'s other building blocks are.
"""
from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Page size 20 by default; a client may request up to 100 via
    ``?page_size=``.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
