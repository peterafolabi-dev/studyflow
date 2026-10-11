from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='campus_life_home'),
]