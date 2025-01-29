from django.shortcuts import render
from artsearch.src.services.search_service import search_service
from artsearch.src.services.smk_api_client import SMKAPIClientError
import artsearch.views.view_utils as view_utils


def similarity_search(request):

    object_number = view_utils.get_object_number(request.GET.get('query'))
    limit = view_utils.get_valid_limit(request.GET.get('limit'))

    results = []
    error_message = None
    error_type = None

    try:
        results = search_service.search_similar_images(object_number, limit=int(limit))
    except SMKAPIClientError as e:
        error_message = str(e)
        error_type = 'warning'
    except Exception as e:
        error_message = "An unexpected error occurred. Please try again."
        error_type = 'error'

    context = {
        'search_action_url': 'similarity-search',
        'about_text': "Find similar paintings in the SMK collection.",
        'placeholder': "Enter the artwork's inventory number (e.g. KMS1)",
        'limit': limit,
        'query': object_number,
        'results': results,
        'error_message': error_message,
        'error_type': error_type
    }
    return render(request, 'search.html', context)
