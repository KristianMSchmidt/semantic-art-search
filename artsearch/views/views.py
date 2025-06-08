from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from artsearch.src.context_builders import (
    build_search_context,
    build_home_context,
    build_filter_contexts,
    SearchParams,
)
from artsearch.views.utils import log_search_query


def home_view(request: HttpRequest) -> HttpResponse:
    """Home page view that also handles search requests."""
    params = SearchParams(request=request)
    context = build_home_context(params)
    return render(request, "home.html", context)


def search_view(request: HttpRequest) -> HttpResponse:
    """
    HTMX view that produces error and search results section on the home page.
    """
    params = SearchParams(request=request)
    log_search_query(params)
    context = build_search_context(params)
    return render(request, "partials/search_results.html", context)


def more_results_view(request: HttpRequest) -> HttpResponse:
    """HTMX view to support infinite scroll."""
    context = build_search_context(SearchParams(request=request))
    return render(request, "partials/artwork_cards_and_trigger.html", context)


def update_work_types(request):
    """HTMX view that updates the work type dropdown based on selected museums."""
    filter_contexts = build_filter_contexts(SearchParams(request=request))
    context = {"filter_ctx": filter_contexts["work_type_filter_context"]}
    return render(request, "partials/dropdown.html", context)
