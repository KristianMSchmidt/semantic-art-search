from typing import Any
from artsearch.src.services.qdrant_service import (
    SearchFunctionArguments,
    get_qdrant_service,
)
from artsearch.src.services.museum_clients.base_client import MuseumAPIClientError


RESULTS_PER_PAGE = 20

# Create a global instance (initialized once and reused)
qdrant_service = get_qdrant_service()


def handle_search(
    query: str | None,
    offset: int,
    limit: int,
    museum_prefilter: list[str] | None,
    work_type_prefilter: list[str] | None,
) -> dict[Any, Any]:
    """
    Handle the search logic based on the provided query and filters.
    """
    text_above_results = ""
    results = []
    error_message = None
    error_type = None

    if query is None or query == "":
        # Query is None on initial page load
        query = ""
        results = qdrant_service.get_random_sample(
            limit=limit,
            work_types=work_type_prefilter,
            museums=museum_prefilter,
        )
        text_above_results = "A glimpse into the archive"

    else:
        # The user submitted a query.
        search_arguments = SearchFunctionArguments(
            query=query,
            limit=limit,
            offset=offset,
            work_type_prefilter=work_type_prefilter,
            museum_prefilter=museum_prefilter,
        )
        try:
            if qdrant_service.item_exists(query):
                results = qdrant_service.search_similar_images(search_arguments)
            else:
                results = qdrant_service.search_text(search_arguments)

            text_above_results = "Search results (best match first)"
        except MuseumAPIClientError as e:
            error_message = str(e)
            error_type = "warning"
        except Exception:
            error_message = "An unexpected error occurred. Please try again."
            error_type = "error"

    return {
        "results": results,
        "text_above_results": text_above_results,
        "error_message": error_message,
        "error_type": error_type,
    }
