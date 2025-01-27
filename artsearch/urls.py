import artsearch.views as views
from django.urls import path

urlpatterns = [
    path('', views.home_view, name='home')
]
