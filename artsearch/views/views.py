from typing import Callable
from dataclasses import dataclass
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from artsearch.src.services.smk_api_client import SMKAPIClientError
from artsearch.views.constants import EXAMPLE_QUERIES
from artsearch.src.services.qdrant_service import get_qdrant_service
from artsearch.views.view_utils import (
    retrieve_offset,
    retrieve_search_action_url,
    retrieve_search_function,
)

# Create a global instance (initialized once and reused)
qdrant_service = get_qdrant_service()

# Number of search results to fetch at a time
RESULTS_PER_PAGE = 20


@dataclass
class SearchParams:
    request: HttpRequest
    search_function: Callable[[str, int, int], list[dict]]
    search_action_url: str
    offset: int
    template_name: str
    about_text: str | None = None
    placeholder: str | None = None
    example_queries: list | None = None
    no_input_error_message: str | None = None


def handle_search(params: SearchParams, limit: int = RESULTS_PER_PAGE) -> HttpResponse:
    """Handles both text and similarity search in a generic way."""

    offset = params.offset

    # Initialize the context with the common parameters.
    query_param = params.request.GET.get("query")
    text_above_results = ""
    results = []
    error_message = None
    error_type = None

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
        "query": query_param,
        "results": results,
        "text_above_results": text_above_results,
        "error_message": error_message,
        "error_type": error_type,
        "offset": offset,
        "search_action_url": params.search_action_url,
        "about_text": params.about_text,
        "placeholder": params.placeholder,
        "example_queries": params.example_queries,
    }

    return render(params.request, params.template_name, context)


def text_search(request) -> HttpResponse:
    params = SearchParams(
        request=request,
        search_function=qdrant_service.search_text,
        no_input_error_message="Please enter a search query.",
        search_action_url="text-search",
        about_text="Explore the SMK collection through meaning-driven search!",
        placeholder="Search by theme, objects, style, or more...",
        example_queries=EXAMPLE_QUERIES,
        offset=0,
        template_name="search.html",
    )
    return handle_search(params)


def similarity_search(request: HttpRequest) -> HttpResponse:
    params = SearchParams(
        request=request,
        search_function=qdrant_service.search_similar_images,
        no_input_error_message="Please enter an inventory number.",
        search_action_url="similarity-search",
        about_text="Find similar artworks in the SMK collection.",
        placeholder="Enter the artwork's inventory number",
        example_queries=[],
        offset=0,
        template_name="search.html",
    )
    return handle_search(params)


def more_results(request: HttpRequest) -> HttpResponse:
    """
    HTMX view that fetches more search results for infinite scrolling.
    """
    offset = retrieve_offset(request)
    search_action_url = retrieve_search_action_url(request, qdrant_service)
    search_function = retrieve_search_function(search_action_url, qdrant_service)

    params = SearchParams(
        request=request,
        search_function=search_function,
        search_action_url=search_action_url,
        offset=offset,
        template_name="partials/artwork_cards_and_trigger.html",
    )
    return handle_search(params)
