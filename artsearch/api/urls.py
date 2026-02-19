from django.urls import path

from artsearch.api.views import artwork_detail_view

urlpatterns = [
    path("artworks/<str:museum_slug>/<str:object_number>/", artwork_detail_view),
]
