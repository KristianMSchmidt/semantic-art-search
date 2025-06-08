import artsearch.views.views as views
from django.urls import path
from django.views.generic import RedirectView


urlpatterns = [
    path(
        "favicon.ico/", RedirectView.as_view(url="/static/favicon.ico", permanent=True)
    ),
    path("", views.home_view, name="home"),
    path("search/", views.search_view, name="search"),
    path("more-results/", views.more_results_view, name="more-results"),
    path("htmx/update-work-types/", views.update_work_types, name="update-work-types"),
]
