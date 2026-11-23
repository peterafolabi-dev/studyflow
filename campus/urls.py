from django.urls import path
from . import views, views_extra

urlpatterns = [
    path('', views.campus_hub, name='campus_hub'),
    path('power/', views.power_tracker, name='power_tracker'),
    path('power/<int:spot_id>/report/', views.report_power_status, name='report_power_status'),
    path('notices/', views.notice_board, name='notice_board'),
    path('notices/new/', views.create_notice, name='create_notice'),
    path('lodges-roommates/', views.lodge_and_roommate_hub, name='lodge_roommate_hub'),
    path('lodges/review/', views.add_lodge_review, name='add_lodge_review'),
    path('roommates/profile/', views.update_roommate_profile, name='update_roommate_profile'),
    path('siwes/', views.siwes_hub, name='siwes_hub'),
    path('siwes/log/', views.add_siwes_log, name='add_siwes_log'),
    path('marketplace/', views.marketplace, name='marketplace'),
    path('marketplace/new/', views.create_listing, name='create_listing'),
    path('marketplace/<int:item_id>/sold/', views.toggle_item_sold, name='toggle_item_sold'),
    path('emergency/', views.emergency_directory, name='emergency_directory'),
    path('lost-found/', views_extra.lost_found, name='lost_found'),
    path('lost-found/new/', views_extra.lost_found_create, name='lost_found_create'),
    path('lost-found/<int:pk>/resolve/', views_extra.lost_found_resolve, name='lost_found_resolve'),
    path('lost-found/<int:pk>/delete/', views_extra.lost_found_delete, name='lost_found_delete'),
    path('events/', views_extra.events, name='campus_events'),
    path('events/new/', views_extra.event_create, name='campus_event_create'),
    path('events/calendar.ics', views_extra.events_ics, name='campus_events_ics'),
    path('events/<int:pk>/calendar.ics', views_extra.event_ics, name='campus_event_ics'),
    path('events/<int:pk>/delete/', views_extra.event_delete, name='campus_event_delete'),
    path('opportunities/', views_extra.opportunities, name='campus_opportunities'),
    path('opportunities/new/', views_extra.opportunity_create, name='campus_opportunity_create'),
    path('opportunities/<int:pk>/delete/', views_extra.opportunity_delete, name='campus_opportunity_delete'),
]

