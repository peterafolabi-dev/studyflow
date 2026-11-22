from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
from django.views.decorators.cache import never_cache

from . import pwa


@never_cache
def healthz(request):
    """Cheap uptime check (no database, no login) used by the keep-awake GitHub Action."""
    return HttpResponse('ok', content_type='text/plain')


@never_cache
def healthz_db(request):
    """Deeper check: can we reach the database? 200 'ok' or 503 'db down'."""
    from django.db import connection
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        return HttpResponse('ok', content_type='text/plain')
    except Exception:  # noqa: BLE001 - any DB error means unhealthy
        return HttpResponse('db down', content_type='text/plain', status=503)


@never_cache
def robots_txt(request):
    """Search engines may index only the public entry pages, never logged-in or uploaded content."""
    base = f'{request.scheme}://{request.get_host()}'
    body = (
        'User-agent: *\n'
        'Allow: /login/\n'
        'Allow: /signup/\n'
        'Disallow: /\n'
        f'Sitemap: {base}/sitemap.xml\n'
    )
    return HttpResponse(body, content_type='text/plain')


def sitemap_xml(request):
    base = f'{request.scheme}://{request.get_host()}'
    urls = ''.join(f'<url><loc>{base}{path}</loc></url>' for path in ('/login/', '/signup/'))
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
    return HttpResponse(xml, content_type='application/xml')


urlpatterns = [
    path('robots.txt', robots_txt, name='robots_txt'),
    path('sitemap.xml', sitemap_xml, name='sitemap_xml'),
    path('healthz/', healthz, name='healthz'),
    path('healthz/db/', healthz_db, name='healthz_db'),
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('manifest.webmanifest', pwa.manifest, name='pwa_manifest'),
    path('sw.js', pwa.service_worker, name='pwa_service_worker'),
    path('', include('accounts.urls')),
    path('', include('planner.urls')),
    path('', include('library.urls')),
    path('', include('resources.urls')),
    path('', include('community.urls')),
    path('campus/', include('campus.urls')),
    path('campus-life/', include('campus_life.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
