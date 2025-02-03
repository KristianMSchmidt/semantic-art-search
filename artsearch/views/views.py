from typing import NamedTuple, Callable
from django.shortcuts import render
from artsearch.src.services.search_service import search_service
from artsearch.src.services.smk_api_client import SMKAPIClientError
import artsearch.views.utils as utils
from artsearch.src.utils.constants import EXAMPLE_QUERIES


class SearchParams(NamedTuple):
    search_function: Callable[[str, int], list]
    no_input_error_message: str
    search_action_url: str
    about_text: str
    placeholder: str
    example_queries: list


def handle_search(request, params: SearchParams):
    """Handles both text and similarity search in a generic way."""

    query_param = request.GET.get('query')
    limit = utils.get_valid_limit(request.GET.get('limit'))

    results = []
    random_results = []
    error_message = None
    error_type = None

    if query_param is None:
        # This is the initial page load.
        query_param = ""
        random_results = search_service.get_random_sample(10)
    elif query_param.strip() == "":
        # The user submitted an empty query.
        error_message = params.no_input_error_message
        error_type = "warning"
    else:
        # The user submitted a query.
        query_param = query_param.strip()
        try:
            results = params.search_function(query_param, limit)
        except SMKAPIClientError as e:
            error_message = str(e)
            error_type = "warning"
        except Exception as e:
            print(f"Search error for query '{query_param}': {e}")
            error_message = "An unexpected error occurred. Please try again."
            error_type = "error"

    context = {
        'random_results': random_results,
        'search_action_url': params.search_action_url,
        'about_text': params.about_text,
        'placeholder': params.placeholder,
        'limit': limit,
        'query': query_param,
        'results': results,
        'error_message': error_message,
        'error_type': error_type,
        'example_queries': params.example_queries,
    }

    return render(request, 'search.html', context)


def text_search(request):
    params = SearchParams(
        search_function=search_service.search_text,
        no_input_error_message="Please enter a search query.",
        search_action_url='text-search',
        about_text="Explore the SMK collection through meaning-driven search!",
        placeholder="Search by theme, objects, style, or more...",
        example_queries=EXAMPLE_QUERIES,
    )
    return handle_search(request, params)


def similarity_search(request):
    params = SearchParams(
        search_function=search_service.search_similar_images,
        no_input_error_message="Please enter an object number.",
        search_action_url='similarity-search',
        about_text="Find similar paintings in the SMK collection.",
        placeholder="Enter the artwork's inventory number",
        example_queries=[],
    )
    return handle_search(request, params)
