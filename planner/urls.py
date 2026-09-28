from django.urls import path

from . import views

urlpatterns = [
    path('break-room/', views.break_room, name='break_room'),
    path('ai-chat/', views.ai_chat_api, name='ai_chat'),
    path('', views.dashboard, name='dashboard'),
    path('courses/', views.course_list, name='course_list'),
    path('courses/new/', views.course_create, name='course_create'),
    path('courses/<int:pk>/', views.course_detail, name='course_detail'),
    path('courses/<int:pk>/edit/', views.course_update, name='course_update'),
    path('courses/<int:pk>/delete/', views.course_delete, name='course_delete'),
    path('courses/<int:course_pk>/tasks/new/', views.task_create, name='task_create'),
    path('tasks/<int:pk>/edit/', views.task_update, name='task_update'),
    path('tasks/<int:pk>/delete/', views.task_delete, name='task_delete'),
    path('tasks/<int:pk>/toggle/', views.task_toggle, name='task_toggle'),
    path('search/', views.global_search, name='global_search'),
    path('gpa-calculator/', views.gpa_calculator, name='gpa_calculator'),
    path('timetable/', views.timetable, name='timetable'),
    path('study/', views.study_room, name='study_room'),
    path('study/log/', views.log_study, name='log_study'),
    path('flashcards/', views.flashcard_hubs, name='flashcards'),
    path('timetable/new/', views.timetable_create, name='timetable_create'),
    path('timetable/<int:pk>/delete/', views.timetable_delete, name='timetable_delete'),
    path('calendar.ics', views.export_calendar, name='export_calendar'),
]
