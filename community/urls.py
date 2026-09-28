from django.urls import path

from . import views

urlpatterns = [
    path('study-groups/', views.thread_list, name='thread_list'),
    path('study-groups/new/', views.thread_create, name='thread_create'),
    path('study-groups/<int:pk>/', views.thread_detail, name='thread_detail'),
    path('study-groups/<int:pk>/delete/', views.thread_delete, name='thread_delete'),
]
