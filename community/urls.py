from django.urls import path

from . import chat_views, views

urlpatterns = [
    path('chat/', chat_views.global_chat, name='global_chat'),
    path('chat/api/', chat_views.chat_api, name='chat_api'),
    path('chat/api/rooms/', chat_views.chat_rooms_meta, name='chat_rooms_meta'),
    path('chat/api/upload/', chat_views.chat_upload, name='chat_upload'),
    path('chat/api/users/', chat_views.chat_users, name='chat_users'),
    path('chat/api/search/', chat_views.chat_search, name='chat_search'),
    path('chat/api/saved/', chat_views.chat_saved, name='chat_saved'),
    path('chat/api/saved/<int:pk>/delete/', chat_views.chat_unsave, name='chat_unsave'),
    path('chat/api/poll/', chat_views.chat_poll_create, name='chat_poll_create'),
    path('chat/api/poll/<int:option_id>/vote/', chat_views.chat_poll_vote, name='chat_poll_vote'),
    path('chat/file/<int:pk>/', chat_views.chat_file, name='chat_file'),
    path('chat/api/<int:pk>/edit/', chat_views.chat_edit, name='chat_edit'),
    path('chat/api/<int:pk>/delete/', chat_views.chat_delete, name='chat_delete'),
    path('chat/api/<int:pk>/react/', chat_views.chat_react, name='chat_react'),
    path('chat/api/<int:pk>/pin/', chat_views.chat_pin, name='chat_pin'),
    path('chat/api/<int:pk>/forward/', chat_views.chat_forward, name='chat_forward'),
    path('chat/api/<int:pk>/save/', chat_views.chat_save, name='chat_save'),
    path('study-groups/', views.thread_list, name='thread_list'),
    path('study-groups/new/', views.thread_create, name='thread_create'),
    path('study-groups/<int:pk>/', views.thread_detail, name='thread_detail'),
    path('study-groups/<int:pk>/delete/', views.thread_delete, name='thread_delete'),
    path('study-groups/buddies/', views.find_buddies, name='find_buddies'),
    path('study-groups/buddies/request/<int:user_id>/', views.send_buddy_request, name='send_buddy_request'),
    path('study-groups/buddies/respond/<int:request_id>/', views.respond_buddy_request, name='respond_buddy_request'),
    path('study-groups/<int:pk>/vote/', views.vote_thread, name='vote_thread'),
    # Phase 6 — Moderation
    path('posts/<int:pk>/report/', views.report_post, name='report_post'),
    path('users/<str:username>/mute/', views.mute_user, name='mute_user'),
    # Phase 7 — Feedback & Analytics
    path('feedback/', views.submit_feedback, name='submit_feedback'),
    path('analytics/', views.admin_dashboard, name='admin_dashboard'),
]

