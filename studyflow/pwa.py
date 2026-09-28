"""Progressive Web App plumbing: manifest + a deliberately minimal service worker.

The service worker is served from the site root (/sw.js) so its scope covers
the whole app. It does NOT cache pages: StudyFlow pages are per-user and
behind login, and caching them could show one student's data to another on a
shared device. It only provides a friendly offline message.
"""
from django.http import HttpResponse, JsonResponse
from django.templatetags.static import static


def manifest(request):
    return JsonResponse(
        {
            'name': 'StudyFlow',
            'short_name': 'StudyFlow',
            'description': 'Planner, reading hub and library for students.',
            'start_url': '/',
            'scope': '/',
            'display': 'standalone',
            'background_color': '#f5f3ff',
            'theme_color': '#7c3aed',
            'icons': [
                {'src': static('icons/icon-192.png'), 'sizes': '192x192', 'type': 'image/png'},
                {'src': static('icons/icon-512.png'), 'sizes': '512x512', 'type': 'image/png'},
                {'src': static('icons/icon-512.png'), 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'},
            ],
        },
        content_type='application/manifest+json',
    )


SERVICE_WORKER_JS = """
self.addEventListener('install', function () { self.skipWaiting(); });
self.addEventListener('activate', function (event) { event.waitUntil(self.clients.claim()); });

// Network-only, with a friendly message if the device is offline.
self.addEventListener('fetch', function (event) {
  if (event.request.mode !== 'navigate') return;
  event.respondWith(
    fetch(event.request).catch(function () {
      return new Response(
        '<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1">' +
        '<body style="font-family:system-ui;text-align:center;padding:3rem 1rem;">' +
        '<h1>You\\'re offline</h1><p>StudyFlow needs a connection. Try again once you\\'re back online.</p></body>',
        { headers: { 'Content-Type': 'text/html' } }
      );
    })
  );
});
"""


def service_worker(request):
    response = HttpResponse(SERVICE_WORKER_JS, content_type='application/javascript')
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache'
    return response
