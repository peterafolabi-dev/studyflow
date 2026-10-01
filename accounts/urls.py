from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('login/', views.login_view, name='login'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('user/<str:username>/', views.public_profile, name='public_profile'),
    path('notifications/', views.notifications_view, name='notifications'),
    path('profile/export/', views.export_my_data, name='export_my_data'),
    # Logout only accepts POST, so the navbar uses a small form, not a link.
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]
