from dataclasses import dataclass
from django.http import HttpRequest

RESULTS_PER_PAGE = 20


@dataclass
class SearchParams:
    """Parameters for the handle_search view"""

    request: HttpRequest
    offset: int = 0
    limit: int = RESULTS_PER_PAGE
    example_queries: list[str] | None = None
