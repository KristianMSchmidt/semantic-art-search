import random
from django.shortcuts import render
from artsearch.src.utils.search_config import initialize_search_service


# Initialize the search service once
search_service = initialize_search_service()


def similarity_search(request):

    query = request.GET.get('query', search_service.get_random_point()['object_number'])

    limit = request.GET.get('limit', '10')

    results = search_service.search_similar_images(query, limit=int(limit))

    context = {
        'about_text': "Find similar paintings in the SMK collection.",
        'placeholder': "Enter the artwork's inventory number (e.g. KMS1)",
        'limit': limit,
        'query': query,
        'results': results
    }
    return render(request, 'search.html', context)
