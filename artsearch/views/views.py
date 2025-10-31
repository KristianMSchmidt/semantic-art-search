from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from artsearch.views.context_builders import (
    build_search_context,
    build_home_context,
    build_filter_contexts,
    SearchParams,
)
from artsearch.views.log_utils import log_search_query


def home_view(request: HttpRequest) -> HttpResponse:
    """
    Render the main homepage with the search form and initial context.

    This view handles all non‐HTMX GET requests to “/”. It builds and returns
    the full `home.html` page including:
      - the search form
      - example queries
      - empty placeholder for search results

    It does _not_ process actual search submissions; those are handled by
    `get_artworks_view` via HTMX.
    """
    params = SearchParams(request=request)
    context = build_home_context(params)
    return render(request, "home.html", context)


def get_artworks_view(request: HttpRequest) -> HttpResponse:
    """
    HTMX endpoint for fetching artwork results (initial search or pagination).
    """
    params = SearchParams(request=request)
    if params.offset == 0:
        log_search_query(params)
    context = build_search_context(params)
    return render(request, "partials/artwork_response.html", context)


def update_work_types(request):
    """
    HTMX view that updates the work type dropdown based on selected museums.
    """
    params = SearchParams(request=request)
    filter_contexts = build_filter_contexts(params)
    context = {
        "filter_ctx": filter_contexts["work_type_filter_context"],
    }
    return render(request, "partials/dropdown.html", context)


def update_museums(request):
    """
    HTMX view that updates the museum dropdown based on selected work types.
    """
    params = SearchParams(request=request)
    filter_contexts = build_filter_contexts(params)
    context = {
        "filter_ctx": filter_contexts["museum_filter_context"],
    }
    return render(request, "partials/dropdown.html", context)
