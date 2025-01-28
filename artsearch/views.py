import random
from django.shortcuts import render
from artsearch.src.utils.search_config import initialize_search_service


EXAMPLE_QUERIES = [
    "Paris",
    "Orientalism",
    "Rome",
    "Martin Luther",
    "War",
    "Cathedral",
    "Fauvism",
    "Cubism",
    "Old man with beard",
    "War",
    "Dance",
    "Death and horror",
    "Reading child",
    "Raw meat"
]

# Initialize the search service once
search_service = initialize_search_service()

# Create your views here.
def text_search_view(request):

    query = request.GET.get('query', random.choice(EXAMPLE_QUERIES))
    limit = request.GET.get('limit', '10')

    results = search_service.search_text(query, limit=int(limit))

    context = {
        'limit': limit,
        'query': query,
        'results': results
    }
    return render(request, 'text_search.html', context)
