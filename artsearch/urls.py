import artsearch.views.views as views
from django.urls import path
from django.shortcuts import redirect
from django.views.generic import RedirectView


urlpatterns = [
    path("", views.home_page, name="home"),
    path(
        "favicon.ico/", RedirectView.as_view(url="/static/favicon.ico", permanent=True)
    ),
    path(
        "<str:museum>/",
        lambda request, museum: redirect(f"/{museum}/text-search/", permanent=False),
    ),
    path("<str:museum>/text-search/", views.text_search, name="text-search"),
    path("<str:museum>/find-similar/", views.find_similar, name="find-similar"),
    path("<str:museum>/more-results/", views.more_results, name="more-results"),
]
