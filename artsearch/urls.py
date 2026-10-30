import artsearch.views.views as views
from django.contrib.sitemaps import views as sitemap_views
from django.urls import path
from django.views.decorators.cache import cache_page
from django.views.generic import RedirectView
from artsearch.sitemaps import SITEMAPS

# Sitemaps only change when the ETL loads new artworks; rendering a 10k-URL
# page takes about a second on the single prod worker, so cache for a day
SITEMAP_CACHE_SECONDS = 60 * 60 * 24


urlpatterns = [
    path(
        "favicon.ico/", RedirectView.as_view(url="/static/favicon.ico", permanent=True)
    ),
    path("", views.home_view, name="home"),
    # "similar/" must come first: object numbers can contain "/", so the page
    # route would otherwise swallow it
    path(
        "artwork/<str:museum_slug>/<path:object_number>/similar/",
        views.artwork_similar_view,
        name="artwork-similar",
    ),
    path(
        "artwork/<str:museum_slug>/<path:object_number>/",
        views.artwork_page_view,
        name="artwork-page",
    ),
    path("robots.txt", views.robots_txt_view, name="robots-txt"),
    path(
        "sitemap.xml",
        cache_page(SITEMAP_CACHE_SECONDS)(sitemap_views.index),
        {"sitemaps": SITEMAPS, "sitemap_url_name": "sitemap-section"},
        name="sitemap-index",
    ),
    path(
        "sitemap-<section>.xml",
        cache_page(SITEMAP_CACHE_SECONDS)(sitemap_views.sitemap),
        {"sitemaps": SITEMAPS},
        name="sitemap-section",
    ),
    path("artworks/", views.get_artworks_view, name="get-artworks"),
    path("artworks/image/", views.upload_image_view, name="upload-image"),
    path("artworks/description/", views.get_artwork_description_view, name="get-artwork-description"),
    path(
        "artworks/description/cached/",
        views.get_cached_artwork_description_view,
        name="get-cached-artwork-description",
    ),
    path(
        "artworks/large-image/",
        views.get_large_image_url_view,
        name="get-large-image-url",
    ),
    path("htmx/update-work-types/", views.update_work_types, name="update-work-types"),
    path("htmx/update-museums/", views.update_museums, name="update-museums"),
    path("map/", views.art_map_view, name="art-map"),
    path("map/data/", views.art_map_data_view, name="art-map-data"),
    path("map/data/geometry/", views.art_map_geometry_view, name="art-map-geometry"),
    path("clear-cache/", views.clear_cache, name="clear-cache"),
    path("sentry-test/", views.sentry_test, name="sentry-test"),
]
