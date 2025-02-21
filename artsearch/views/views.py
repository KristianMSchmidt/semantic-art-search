from typing import NamedTuple, Callable
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from artsearch.src.services.smk_api_client import SMKAPIClientError
from artsearch.views.constants import EXAMPLE_QUERIES
from artsearch.src.services.qdrant_service import get_qdrant_service

# Create a global instance (initialized once and reused)
qdrant_service = get_qdrant_service()

# Number of search results to fetch at a time
RESULTS_PER_PAGE = 20


class SearchParams(NamedTuple):
    search_function: Callable[[str, int, int], list[dict]]
    no_input_error_message: str
    search_action_url: str
    about_text: str
    placeholder: str
    example_queries: list


def handle_search(
    request: HttpRequest, params: SearchParams, limit: int = RESULTS_PER_PAGE
) -> HttpResponse:
    """Handles both text and similarity search in a generic way."""

    query_param = request.GET.get("query")
    text_above_results = ""
    results = []
    error_message = None
    error_type = None
    offset = 0

    if query_param is None:
        # This is the initial page load.
        query_param = ""
        results = qdrant_service.get_random_sample(limit=limit)
        text_above_results = "A glimpse into the archive"
    elif query_param.strip() == "":
        # The user submitted an empty query.
        error_message = params.no_input_error_message
        error_type = "warning"
    else:
        # The user submitted a query.
        query_param = query_param.strip()
        try:
            results = params.search_function(query_param, limit, offset)
            text_above_results = "Search results (best match first)"
        except SMKAPIClientError as e:
            error_message = str(e)
            error_type = "warning"
        except Exception as e:
            print(f"Search error for query '{query_param}': {e}")
            error_message = "An unexpected error occurred. Please try again."
            error_type = "error"

    offset += limit

    context = {
        "search_action_url": params.search_action_url,
        "about_text": params.about_text,
        "placeholder": params.placeholder,
        "query": query_param,
        "results": results,
        "error_message": error_message,
        "error_type": error_type,
        "example_queries": params.example_queries,
        "text_above_results": text_above_results,
        "offset": offset,
    }

    return render(request, "search.html", context)


def text_search(request) -> HttpResponse:
    params = SearchParams(
        search_function=qdrant_service.search_text,
        no_input_error_message="Please enter a search query.",
        search_action_url="text-search",
        about_text="Explore the SMK collection through meaning-driven search!",
        placeholder="Search by theme, objects, style, or more...",
        example_queries=EXAMPLE_QUERIES,
    )
    return handle_search(request, params)


def similarity_search(request: HttpRequest) -> HttpResponse:
    params = SearchParams(
        search_function=qdrant_service.search_similar_images,
        no_input_error_message="Please enter an inventory number.",
        search_action_url="similarity-search",
        about_text="Find similar artworks in the SMK collection.",
        placeholder="Enter the artwork's inventory number",
        example_queries=[],
    )
    return handle_search(request, params)


def more_results(request: HttpRequest, limit: int = RESULTS_PER_PAGE) -> HttpResponse:
    """
    HTMX view that fetches more search results for infinite scrolling.
    """
    query_param = request.GET.get("query")
    search_action_url = request.GET.get("search_action_url")
    offset = int(request.GET.get("offset", 1))

    if query_param is None:
        # This is the initial page load.
        query_param = ""
        results = qdrant_service.get_random_sample(limit=limit)
    else:
        # The user submitted a query.
        query_param = query_param.strip()
        if search_action_url == "text-search":
            search_function = qdrant_service.search_text
        else:
            search_function = qdrant_service.search_similar_images
        results = search_function(query_param, limit=limit, offset=offset)

    offset += limit

    context = {
        "query": query_param,
        "results": results,
        "search_action_url": search_action_url,
        "offset": offset,
    }

    return render(request, "partials/artwork_cards_and_trigger.html", context)
