from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from . import pwa

from django.http import HttpResponse

def setup_admin(request):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@studyflow.local', 'StudyFlowAdmin123!')
        return HttpResponse("Superuser 'admin' created! Password is: StudyFlowAdmin123!")
    return HttpResponse("Superuser 'admin' already exists. Try logging in.")

urlpatterns = [
    path('setup-admin-777/', setup_admin),
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('manifest.webmanifest', pwa.manifest, name='pwa_manifest'),
    path('sw.js', pwa.service_worker, name='pwa_service_worker'),
    path('', include('accounts.urls')),
    path('', include('planner.urls')),
    path('', include('library.urls')),
    path('', include('resources.urls')),
    path('', include('community.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
