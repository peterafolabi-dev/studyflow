from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('profile/', views.profile, name='profile'),
    path('profile/export/', views.export_my_data, name='export_my_data'),
    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='accounts/login.html',
            redirect_authenticated_user=True,
        ),
        name='login',
    ),
    # Logout only accepts POST, so the navbar uses a small form, not a link.
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]
