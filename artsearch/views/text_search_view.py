from django.shortcuts import render
from artsearch.src.services.search_service import search_service
import artsearch.views.view_utils as view_utils


def text_search(request):

    query = view_utils.get_default_text_query(request.GET.get('query'))
    limit = view_utils.get_valid_limit(request.GET.get('limit'))

    results = []
    error_message = None
    error_type = None

    try:
        results = search_service.search_text(query, limit)

    except Exception as e:
        error_message = "An unexpected error occurred. Please try again."
        error_type = "error"  #

    context = {
        'search_action_url': 'text-search',
        'about_text': "Search for painting in the SMK collection by entering words, phrases or sentences.",
        'placeholder': "Woman by the window",
        'limit': limit,
        'query': query,
        'results': results,
        'error_message': error_message,
        'error_type': error_type
    }
    return render(request, 'search.html', context)
