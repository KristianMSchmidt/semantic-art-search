import artsearch.views as views
from django.urls import path

urlpatterns = [
    path('', views.text_search_view, name='text-search'),
]
