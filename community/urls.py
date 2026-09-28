from django.urls import path

from . import views

urlpatterns = [
    path('chat/', views.global_chat, name='global_chat'),
    path('chat/api/', views.chat_api, name='chat_api'),
    path('study-groups/', views.thread_list, name='thread_list'),
    path('study-groups/new/', views.thread_create, name='thread_create'),
    path('study-groups/<int:pk>/', views.thread_detail, name='thread_detail'),
    path('study-groups/<int:pk>/delete/', views.thread_delete, name='thread_delete'),
    path('study-groups/buddies/', views.find_buddies, name='find_buddies'),
    path('study-groups/<int:pk>/vote/', views.vote_thread, name='vote_thread'),
]
