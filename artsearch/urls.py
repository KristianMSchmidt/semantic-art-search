import artsearch.views.views as views
from django.urls import path
from django.views.generic import RedirectView


urlpatterns = [
    path(
        "favicon.ico/", RedirectView.as_view(url="/static/favicon.ico", permanent=True)
    ),
    path("", views.home_view, name="home"),
    path("artworks/", views.get_artworks_view, name="get-artworks"),
    path("artworks/description/", views.get_artwork_description_view, name="get-artwork-description"),
    path("htmx/update-work-types/", views.update_work_types, name="update-work-types"),
    path("htmx/update-museums/", views.update_museums, name="update-museums"),
    path("map/", views.art_map_view, name="art-map"),
    path("map/data/", views.art_map_data_view, name="art-map-data"),
    path("clear-cache/", views.clear_cache, name="clear-cache"),
    path("sentry-test/", views.sentry_test, name="sentry-test"),
]
