import artsearch.views.views as views
from django.urls import path
from django.views.generic import RedirectView


urlpatterns = [
    path(
        "favicon.ico/", RedirectView.as_view(url="/static/favicon.ico", permanent=True)
    ),
    path("", views.search, name="search"),
    path("more-results/", views.more_results, name="more-results"),
]
