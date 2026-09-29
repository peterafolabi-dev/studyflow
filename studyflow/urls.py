from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from . import pwa

urlpatterns = [
    path('admin/', admin.site.urls),\n    path('accounts/', include('allauth.urls')),
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
