import artsearch.views.views as views
from django.urls import path
from django.shortcuts import redirect

urlpatterns = [
    path("", lambda request: redirect("text-search", permanent=False), name="home"),
    path("text-search/", views.text_search, name="text-search"),
    path("find-similar/", views.find_similar, name="find-similar"),
    path("more-results/", views.more_results, name="more-results"),
]
