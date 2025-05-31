from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from artsearch.src.constants import EXAMPLE_QUERIES
from artsearch.views.view_utils import (
    retrieve_offset,
)
from artsearch.views.context_builders import (
    build_main_context,
    build_search_context,
    build_filter_context,
    SearchParams,
)


def search(request: HttpRequest) -> HttpResponse:
    params = SearchParams(
        request=request,
        example_queries=EXAMPLE_QUERIES["chosen"],
    )
    context = build_search_context(params)
    return render(request, "search.html", context)


def more_results(request: HttpRequest) -> HttpResponse:
    """
    HTMX view that fetches more search results for infinite scrolling.
    """
    params = SearchParams(
        request=request,
        offset=retrieve_offset(request),
    )
    context = build_main_context(params)
    return render(request, "partials/artwork_cards_and_trigger.html", context)


def update_work_types(request):
    """
    HTMX view that updates the work type dropdown based on selected museums.
    """
    context = build_filter_context(request)
    return render(request, "partials/work_type_dropdown.html", context)
