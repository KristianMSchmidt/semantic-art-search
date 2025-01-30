from django.shortcuts import render
from artsearch.src.services.search_service import search_service
import artsearch.views.view_utils as view_utils
from artsearch.src.utils.constants import EXAMPLE_QUERIES
import logging

logger = logging.getLogger(__name__)

def text_search(request):
    """Handles text-based searches in the SMK collection."""

    query = request.GET.get('query')
    limit = view_utils.get_valid_limit(request.GET.get('limit'))

    results = []
    random_results = []
    error_message = None
    error_type = None

    if query is None:
        # Initial page load: Keep the query empty (don't prefill it)
        query = ""
        random_results = search_service.get_random_sample()

    elif query.strip() == "":
        # User submitted an empty query, show warning
        error_message = "Please enter a search query."
        error_type = "warning"

    else:
        # Normal case: Clean query and perform search
        query = query.strip()
        try:
            results = search_service.search_text(query, limit)
        except Exception as e:
            logger.error(f"Search error for query '{query}': {e}")
            error_message = "An unexpected error occurred. Please try again."
            error_type = "error"

    context = {
        'random_results': random_results,
        'search_action_url': 'text-search',
        'about_text': "Explore the SMK collection through meaning-driven search!",
        'placeholder': "Search by theme, objects, style, or more...",
        'limit': limit,
        'query': query,
        'results': results,
        'error_message': error_message,
        'error_type': error_type,
        'example_queries': EXAMPLE_QUERIES
    }

    return render(request, 'search.html', context)
