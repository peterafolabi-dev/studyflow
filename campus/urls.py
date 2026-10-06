from django.urls import path
from . import views

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
]

