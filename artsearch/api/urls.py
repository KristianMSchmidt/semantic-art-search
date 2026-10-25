from django.urls import path

from artsearch.api.views import (
    artwork_detail_view,
    museums_view,
    random_view,
    search_image_view,
    search_view,
    similar_view,
    work_types_view,
)

urlpatterns = [
    path("museums/", museums_view),
    path("work-types/", work_types_view),
    # Object numbers can contain "/" (e.g. SMK "KKS10208/5"), hence <path:>.
    # "similar/" must come first, or the detail route would swallow it.
    path(
        "artworks/<str:museum_slug>/<path:object_number>/similar/",
        similar_view,
    ),
    path("artworks/<str:museum_slug>/<path:object_number>/", artwork_detail_view),
    path("search/", search_view),
    path("search/image/", search_image_view),
    path("random/", random_view),
]
