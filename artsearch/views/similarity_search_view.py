from django.shortcuts import render


def similarity_search(request):
    return render(request, 'similarity_search.html')
