import artsearch.views.views as views
from django.urls import path
from django.views.generic import RedirectView


urlpatterns = [
    path("", RedirectView.as_view(url="/all/", permanent=True)),
    path(
        "favicon.ico/", RedirectView.as_view(url="/static/favicon.ico", permanent=True)
    ),
    path("<str:museum>/", views.search, name="search"),
    path("<str:museum>/more-results/", views.more_results, name="more-results"),
]
