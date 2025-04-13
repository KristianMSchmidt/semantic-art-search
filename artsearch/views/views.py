from typing import Callable
from dataclasses import dataclass
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from artsearch.src.services.museum_clients import MuseumAPIClientError, MuseumName
from artsearch.src.constants import EXAMPLE_QUERIES, SUPPORTED_MUSEUMS
from artsearch.src.services.qdrant_service import SearchFunctionArguments
from artsearch.src.services.service_factory import get_qdrant_service

from artsearch.src.services.museum_stats_service import (
    get_work_type_counts_for_museum,
)
from artsearch.views.view_utils import (
    retrieve_query,
    retrieve_offset,
    retrieve_search_action,
    retrieve_search_function,
    retrieve_selected_work_types,
    make_work_types_prefilter,
    make_urls,
)

# Create a global instance (initialized once and reused)
qdrant_service = get_qdrant_service()

# Number of search results to fetch at a time
RESULTS_PER_PAGE = 20


@dataclass
class SearchParams:
    """Parameters for the handle_search view"""

    request: HttpRequest
    search_function: Callable[[SearchFunctionArguments], list[dict]]
    search_action: str
    offset: int
    template_name: str
    museum: MuseumName
    about_text: str | None = None
    placeholder: str | None = None
    example_queries: list[str] | None = None
    no_input_error_message: str | None = None


def handle_search(params: SearchParams, limit: int = RESULTS_PER_PAGE) -> HttpResponse:
    """Handles both text and similarity search in a generic way."""
    offset = params.offset
    museum = params.museum
    work_type_counts_for_museum = get_work_type_counts_for_museum(museum)
    work_types_at_museum = list(work_type_counts_for_museum.work_types.keys())
    query = retrieve_query(params.request)

    selected_work_types = retrieve_selected_work_types(
        work_types_at_museum, params.request
    )
    work_types_prefilter = make_work_types_prefilter(
        work_types_at_museum, selected_work_types
    )

    # Set default context paramters
    text_above_results = ""
    results = []
    error_message = None
    error_type = None

    if query is None:
        # This is the initial page load.
        query = ""
        results = qdrant_service.get_random_sample(museum_filter=museum, limit=limit)
        text_above_results = "A glimpse into the archive"

    elif query == "":
        # The user submitted an empty query.
        error_message = params.no_input_error_message
        error_type = "warning"

    else:
        # The user submitted a query.
        try:
            results = params.search_function(
                SearchFunctionArguments(
                    query=query,
                    museum_filter=museum,
                    limit=limit,
                    offset=offset,
                    work_types_prefilter=work_types_prefilter,
                )
            )
            text_above_results = "Search results (best match first)"
        except MuseumAPIClientError as e:
            error_message = str(e)
            error_type = "warning"
        except Exception as e:
            error_message = "An unexpected error occurred. Please try again."
            error_type = "error"

    offset += limit
    urls = make_urls(
        offset, params.search_action, query, selected_work_types, museum=museum
    )
    context = {
        "work_count": work_type_counts_for_museum,
        "all_work_types": work_types_at_museum,
        "selected_work_types": selected_work_types,
        "query": query,
        "results": results,
        "text_above_results": text_above_results,
        "error_message": error_message,
        "error_type": error_type,
        "offset": offset,
        "about_text": params.about_text,
        "placeholder": params.placeholder,
        "example_queries": params.example_queries,
        "urls": urls,
    }
    return render(params.request, params.template_name, context)


def text_search(request, museum: MuseumName) -> HttpResponse:
    if museum == "all":
        about_text = "Explore all collections though meaning-driven search!"
    else:
        about_text = (
            f"Explore the {museum.upper()} collection through meaning-driven search!"
        )
    params = SearchParams(
        request=request,
        search_function=qdrant_service.search_text,
        no_input_error_message="Please enter a search query.",
        search_action="text-search",
        about_text=about_text,
        placeholder="Search by theme, objects, style, or more...",
        example_queries=EXAMPLE_QUERIES,
        offset=0,
        template_name="search.html",
        museum=museum,
    )
    return handle_search(params)


def find_similar(request: HttpRequest, museum: MuseumName) -> HttpResponse:
    params = SearchParams(
        request=request,
        search_function=qdrant_service.search_similar_images,
        no_input_error_message="Please enter an inventory number.",
        search_action="find-similar",
        about_text=f"Find similar artworks in the {museum.upper()} collection",
        placeholder="Enter an artwork inventory number",
        example_queries=[],
        offset=0,
        template_name="search.html",
        museum=museum,
    )
    return handle_search(params)


def more_results(request: HttpRequest, museum: MuseumName) -> HttpResponse:
    """
    HTMX view that fetches more search results for infinite scrolling.
    """
    offset = retrieve_offset(request)
    search_action = retrieve_search_action(request)
    search_function = retrieve_search_function(search_action, qdrant_service)

    params = SearchParams(
        request=request,
        search_function=search_function,
        search_action=search_action,
        offset=offset,
        template_name="partials/artwork_cards_and_trigger.html",
        museum=museum,
    )

    return handle_search(params)


def home_page(request):
    """Home page view"""
    context = {
        "museums": SUPPORTED_MUSEUMS,
    }
    return render(request, "home.html", context)
