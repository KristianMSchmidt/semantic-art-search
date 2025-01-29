import artsearch.views.text_search_view as text_search_view
import artsearch.views.similarity_search_view as similarity_search_view

from django.urls import path
from django.shortcuts import redirect

urlpatterns = [
    path('', lambda request: redirect('text-search', permanent=True), name='home'),
    path('text-search/', text_search_view.text_search, name='text-search'),
    path('similarity-search/', similarity_search_view.similarity_search, name='similarity-search'),
]
