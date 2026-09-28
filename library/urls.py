from django.urls import path

from . import views

urlpatterns = [
    path('catalogue/', views.catalogue, name='catalogue'),
    path('postgraduate/', views.postgraduate, name='postgraduate'),
    path('my-library/', views.my_library, name='my_library'),
    path('books/<int:pk>/', views.book_detail, name='book_detail'),
    path('books/<int:pk>/read/', views.read_online, name='read_online'),
    path('books/<int:pk>/download/', views.download_pdf, name='download_pdf'),
    path('books/<int:pk>/toggle-save/', views.toggle_save, name='toggle_save'),
    path('books/<int:pk>/status/', views.update_status, name='update_status'),
    path('books/<int:pk>/rate/', views.rate_book, name='rate_book'),
]
