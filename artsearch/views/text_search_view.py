import random
from django.shortcuts import render
from artsearch.src.utils.search_config import initialize_search_service


EXAMPLE_QUERIES = [
    "Paris",
    "Orientalism",
    "Ancient Rome",
    "Martin Luther",
    "War",
    "Inside a cathedral",
    "Fauvism",
    "Cubism",
    "Old man with beard",
    "War",
    "Death and horror",
    "Reading child",
    "Raw meat"
]

# Initialize the search service once
search_service = initialize_search_service()

def text_search(request):

    query = request.GET.get('query', random.choice(EXAMPLE_QUERIES))
    limit = request.GET.get('limit', '10')

    results = search_service.search_text(query, limit=int(limit))

    context = {
        'about_text': "Search for painting in the SMK collection by entering words, phrases or sentences.",
        'placeholder': "Woman by the window",
        'limit': limit,
        'query': query,
        'results': results
    }
    return render(request, 'search.html', context)
