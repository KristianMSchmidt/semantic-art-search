from django.shortcuts import render
from artsearch.src.services.search_service import search_service
from artsearch.src.services.smk_api_client import SMKAPIClientError
import artsearch.views.view_utils as view_utils


def similarity_search(request):
    """Handles similarity searches in the SMK collection."""

    object_number = request.GET.get('query')
    limit = view_utils.get_valid_limit(request.GET.get('limit'))

    results = []
    random_results = []
    error_message = None
    error_type = None

    if object_number is None:
        # Initial page load: Keep the query empty (don't prefill it)
        object_number = ""
        random_results = search_service.get_random_sample()

    elif object_number.strip() == "":
        # User submitted an empty query, show warning
        error_message = "Please enter an object number."
        error_type = "warning"
    else:
        # Normal case: Clean query and perform search
        object_number = object_number.strip()
        try:
            results = search_service.search_similar_images(object_number, limit=int(limit))
        except SMKAPIClientError as e:
            error_message = str(e)
            error_type = 'warning'
        except Exception as e:
            error_message = "An unexpected error occurred. Please try again."
            error_type = 'error'

    context = {
        'random_results': random_results,
        'search_action_url': 'similarity-search',
        'about_text': "Find similar paintings in the SMK collection.",
        'placeholder': "Enter the artwork's inventory number",
        'limit': limit,
        'query': object_number,
        'results': results,
        'error_message': error_message,
        'error_type': error_type,
        'example_queries': []
    }
    return render(request, 'search.html', context)
