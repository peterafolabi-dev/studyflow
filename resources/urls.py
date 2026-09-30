from django.urls import path

from . import views, cbt_views

urlpatterns = [
    # CBT Practice Mode
    path('cbt/', cbt_views.cbt_home, name='cbt_home'),
    path('cbt/bank/<int:bank_id>/', cbt_views.cbt_detail, name='cbt_detail'),
    path('cbt/bank/<int:bank_id>/take/', cbt_views.cbt_take, name='cbt_take'),
    path('cbt/bank/<int:bank_id>/submit/', cbt_views.cbt_submit, name='cbt_submit'),
    path('cbt/attempt/<int:attempt_id>/results/', cbt_views.cbt_result, name='cbt_result'),
    path('cbt/explain-answer/', cbt_views.cbt_explain_answer, name='cbt_explain_answer'),
    path('resources/<int:pk>/ai/generate-cbt/', cbt_views.resource_ai_generate_cbt, name='resource_ai_generate_cbt'),

    # Resources
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
    path('resources/<int:pk>/ai/summarize/', views.resource_ai_summarize, name='resource_ai_summarize'),
    path('resources/<int:pk>/ai/flashcards/', views.resource_ai_flashcards, name='resource_ai_flashcards'),
    path('resources/<int:pk>/ai/save-flashcards/', views.resource_ai_save_flashcards, name='resource_ai_save_flashcards'),
    path('resources/<int:pk>/ai/quiz/', views.resource_ai_quiz, name='resource_ai_quiz'),
    path('ibb-library/', views.ibb_library, name='ibb_library'),
    path('ibb-library/<int:pk>/reserve/', views.reserve_holding, name='reserve_holding'),
    path('ibb-library/<int:pk>/return/', views.return_holding, name='return_holding'),
    path('my-loans/', views.my_loans, name='my_loans'),
]
