from django.urls import path

from artsearch.api.views import (
    artwork_detail_view,
    museums_view,
    random_view,
    search_view,
    similar_view,
    work_types_view,
)

urlpatterns = [
    path("museums/", museums_view),
    path("work-types/", work_types_view),
    path("artworks/<str:museum_slug>/<str:object_number>/", artwork_detail_view),
    path(
        "artworks/<str:museum_slug>/<str:object_number>/similar/",
        similar_view,
    ),
    path("search/", search_view),
    path("random/", random_view),
]
