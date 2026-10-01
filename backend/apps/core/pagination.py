from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """{ count, next, previous, results } with ?page= and ?page_size= (max 100)."""

    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100
