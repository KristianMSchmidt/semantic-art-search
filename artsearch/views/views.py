from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from artsearch.models import SearchLog
from artsearch.src.context_builders import (
    build_main_context,
    build_search_context,
    build_filter_contexts,
    SearchParams,
)


def log_search_query(params: SearchParams) -> None:
    query = params.query
    if query:
        user = params.request.user
        username = user.username if user.is_authenticated else None
        try:
            SearchLog.objects.create(query=query, username=username)
        except Exception as e:
            print(f"Error logging search query: {e}")


def search(request: HttpRequest) -> HttpResponse:
    """Home page view that also handles search requests."""
    params = SearchParams(request=request)
    log_search_query(params)
    context = build_search_context(params)
    return render(request, "search.html", context)


def more_results(request: HttpRequest) -> HttpResponse:
    """HTMX view that fetches more search results for infinite scrolling."""
    context = build_main_context(SearchParams(request=request))
    return render(request, "partials/artwork_cards_and_trigger.html", context)


def update_work_types(request):
    """HTMX view that updates the work type dropdown based on selected museums."""
    filter_contexts = build_filter_contexts(SearchParams(request=request))
    context = {'filter_ctx': filter_contexts['work_type_filter_context']} 
    return render(request, "partials/dropdown.html", context)
