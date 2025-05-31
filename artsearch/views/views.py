from dataclasses import dataclass
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from artsearch.src.constants import EXAMPLE_QUERIES, SUPPORTED_MUSEUMS
from artsearch.src.services.qdrant_service import (
    get_qdrant_service,
)

from artsearch.views.view_utils import (
    get_work_type_names,
    get_museum_names,
    retrieve_query,
    retrieve_offset,
    retrieve_selected,
    make_prefilter,
    make_urls,
    build_filter_context,
    build_search_context,
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
    example_queries: list[str] | None = None


def handle_search(params: SearchParams, limit: int = RESULTS_PER_PAGE) -> HttpResponse:
    """Handles both text and similarity search"""
    request = params.request
    offset = params.offset
    query = retrieve_query(request)

    museum_names = get_museum_names()
    selected_museums = retrieve_selected(museum_names, request, "museums")

    work_type_names = get_work_type_names()
    selected_work_types = retrieve_selected(work_type_names, request, "work_types")

    search_ctx = build_search_context(
        query=query,
        offset=offset,
        limit=limit,
        museum_prefilter=make_prefilter(museum_names, selected_museums),
        work_type_prefilter=make_prefilter(work_type_names, selected_work_types),
    )

    urls = make_urls(
        offset=offset,
        query=query,
        selected_museums=selected_museums,
        selected_work_types=selected_work_types,
    )

    filter_ctx = build_filter_context(params.request)

    context = {
        **filter_ctx,
        **search_ctx,
        "query": query,
        "offset": offset + limit,
        "example_queries": params.example_queries,
        "museums": SUPPORTED_MUSEUMS,
        "urls": urls,
    }
    return render(params.request, params.template_name, context)


def search(request: HttpRequest) -> HttpResponse:
    params = SearchParams(
        request=request,
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


def update_work_types(request):
    """
    HTMX view that updates the work type dropdown based on selected museums.
    """
    context = build_filter_context(request)
    return render(request, "partials/work_type_dropdown.html", context)
