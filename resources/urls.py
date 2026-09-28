from django.urls import path

from . import views

urlpatterns = [
    path('resources/past-questions/', views.resource_list, {'rtype': 'past_question'}, name='past_questions'),
    path('resources/notes/', views.resource_list, {'rtype': 'notes'}, name='notes_list'),
    path('resources/theses-papers/', views.resource_list, {'rtype': 'thesis_paper'}, name='theses_papers'),
    path('resources/lecture-slides/', views.resource_list, {'rtype': 'lecture_slide'}, name='lecture_slides'),
    path('resources/research/', views.resource_list, {'rtype': 'research'}, name='research'),
    path('resources/<int:pk>/', views.resource_detail, name='resource_detail'),
    path('resources/upload/', views.resource_upload, name='resource_upload'),
    path('resources/<int:pk>/download/', views.resource_download, name='resource_download'),
    path('resources/<int:pk>/delete/', views.resource_delete, name='resource_delete'),
    path('resources/<int:pk>/rate/', views.rate_resource, name='rate_resource'),
    path('ibb-library/', views.ibb_library, name='ibb_library'),
    path('ibb-library/<int:pk>/reserve/', views.reserve_holding, name='reserve_holding'),
    path('ibb-library/<int:pk>/return/', views.return_holding, name='return_holding'),
    path('my-loans/', views.my_loans, name='my_loans'),
]
