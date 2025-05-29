import json
from dataclasses import dataclass
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from artsearch.src.services.museum_clients.base_client import MuseumAPIClientError
from artsearch.src.constants import EXAMPLE_QUERIES, SUPPORTED_MUSEUMS
from artsearch.src.utils.get_museums import get_museum_slugs
from artsearch.src.services.qdrant_service import (
    SearchFunctionArguments,
    get_qdrant_service,
)

from artsearch.src.services.museum_stats_service import (
    get_work_type_counts_for_museum,
)
from artsearch.views.view_utils import (
    retrieve_query,
    retrieve_offset,
    retrieve_selected,
    make_prefilter,
    make_urls,
    prepare_work_types_for_dropdown,
    prepare_initial_label,
)

# Create a global instance (initialized once and reused)
qdrant_service = get_qdrant_service()

# Number of search results to fetch at a time
RESULTS_PER_PAGE = 20


@dataclass
class SearchParams:
    """Parameters for the handle_search view"""

    request: HttpRequest
    offset: int
    template_name: str
    about_text: str | None = None
    example_queries: list[str] | None = None


def handle_search(params: SearchParams, limit: int = RESULTS_PER_PAGE) -> HttpResponse:
    """Handles both text and similarity search in a generic way."""
    offset = params.offset
    query = retrieve_query(params.request)

    museum_work_type_summary = get_work_type_counts_for_museum("all")
    work_types_at_museum = list(museum_work_type_summary.work_types.keys())
    selected_work_types = retrieve_selected(
        work_types_at_museum, params.request, "work_types"
    )
    work_types_prefilter = make_prefilter(work_types_at_museum, selected_work_types)

    museum_names = get_museum_slugs()
    selected_museums = retrieve_selected(museum_names, params.request, "museums")
    museum_prefilter = make_prefilter(museum_names, selected_museums)

    # Set default context parameters
    text_above_results = ""
    results = []
    error_message = None
    error_type = None

    if query is None:
        # This is the initial page load.
        query = ""
        results = qdrant_service.get_random_sample(limit=limit)
        text_above_results = "A glimpse into the archive"

    elif query == "":
        # The user submitted an empty query.
        error_message = "Please enter a search query."
        error_type = "warning"

    else:
        # The user submitted a query.
        search_arguments = SearchFunctionArguments(
            query=query,
            limit=limit,
            offset=offset,
            work_types_prefilter=work_types_prefilter,
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
        except Exception as e:
            error_message = "An unexpected error occurred. Please try again."
            error_type = "error"

    offset += limit
    urls = make_urls(offset, query, selected_work_types, selected_museums)
    prepared_work_types = prepare_work_types_for_dropdown(
        museum_work_type_summary.work_types
    )
    initial_work_types_label = prepare_initial_label(
        selected_work_types, work_types_at_museum, "work_types"
    )
    initial_museums_label = prepare_initial_label(
        selected_museums, museum_names, "museums"
    )

    context = {
        "initial_museums_label": initial_museums_label,
        "initial_work_types_label": initial_work_types_label,
        "total_work_count": museum_work_type_summary.total,
        "work_types": prepared_work_types,
        "all_work_types_json": json.dumps(work_types_at_museum),
        "selected_work_types_json": json.dumps(selected_work_types),
        "query": query,
        "results": results,
        "text_above_results": text_above_results,
        "error_message": error_message,
        "error_type": error_type,
        "offset": offset,
        "about_text": params.about_text,
        "example_queries": params.example_queries,
        "urls": urls,
        "museums": SUPPORTED_MUSEUMS,
        "selected_museums_json": json.dumps(selected_museums),
        "all_museums_json": json.dumps(museum_names),
    }
    return render(params.request, params.template_name, context)


def search(request: HttpRequest) -> HttpResponse:
    about_text = "Explore art through meaning-driven search!"
    params = SearchParams(
        request=request,
        about_text=about_text,
        example_queries=EXAMPLE_QUERIES["all"],
        offset=0,
        template_name="search.html",
    )
    return handle_search(params)


def more_results(request: HttpRequest) -> HttpResponse:
    """
    HTMX view that fetches more search results for infinite scrolling.
    """
    offset = retrieve_offset(request)

    params = SearchParams(
        request=request,
        offset=offset,
        template_name="partials/artwork_cards_and_trigger.html",
    )

    return handle_search(params)
