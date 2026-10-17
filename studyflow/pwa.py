"""PWA plumbing; personalized pages are cached only after explicit user action."""
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
const USER_CACHE = 'studyflow-offline-v1';
const MAX_OFFLINE_BYTES = 15 * 1024 * 1024;

self.addEventListener('install', function (event) {
  event.waitUntil(self.skipWaiting());
});
self.addEventListener('activate', function (event) {
  event.waitUntil((async function () {
    const keys = await caches.keys();
    await Promise.all(keys.filter(function (key) {
      return key.startsWith('studyflow-offline-') && key !== USER_CACHE;
    }).map(function (key) { return caches.delete(key); }));
    await self.clients.claim();
  })());
});

self.addEventListener('message', function (event) {
  const data = event.data || {};
  if (data.type === 'CLEAR_OFFLINE') {
    event.waitUntil(caches.delete(USER_CACHE));
    if (event.ports[0]) event.ports[0].postMessage({ cleared: true });
    return;
  }
  if (data.type !== 'SAVE_OFFLINE') return;

  event.waitUntil((async function () {
    const cache = await caches.open(USER_CACHE);
    const saved = [];
    const failures = [];
    for (const rawUrl of (data.urls || []).slice(0, 25)) {
      try {
        const url = new URL(rawUrl, self.location.origin);
        if (url.origin !== self.location.origin) throw new Error('Only StudyFlow pages can be saved.');
        const request = new Request(url.href, { credentials: 'include', cache: 'reload' });
        const response = await fetch(request);
        const length = Number(response.headers.get('content-length') || 0);
        if (!response.ok || response.redirected || (length && length > MAX_OFFLINE_BYTES)) {
          throw new Error('Could not save this page. Sign in again or choose a smaller file.');
        }
        await cache.put(request, response.clone());
        saved.push(url.pathname);
      } catch (error) {
        failures.push(error.message || 'Save failed.');
      }
    }
    const keys = await cache.keys();
    for (const key of keys.slice(20)) await cache.delete(key);
    if (event.ports[0]) event.ports[0].postMessage({ saved: saved.length, failures: failures });
  })());
});

self.addEventListener('fetch', function (event) {
  const request = event.request;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.method === 'POST' && url.pathname === '/logout/') {
    event.respondWith(fetch(request));
    event.waitUntil(caches.delete(USER_CACHE));
    return;
  }
  if (request.method !== 'GET') return;

  event.respondWith((async function () {
    try {
      return await fetch(request);
    } catch (error) {
      const cache = await caches.open(USER_CACHE);
      const saved = await cache.match(request);
      if (saved) return saved;
      if (request.mode === 'navigate') {
        return new Response(
          '<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1">' +
          '<body style="font-family:system-ui;text-align:center;padding:3rem 1rem;">' +
          '<h1>You\\'re offline</h1><p>Open a timetable or note saved for offline use, or reconnect to StudyFlow.</p></body>',
          { headers: { 'Content-Type': 'text/html' } }
        );
      }
      throw error;
    }
  })());
});
"""


def service_worker(request):
    response = HttpResponse(SERVICE_WORKER_JS, content_type='application/javascript')
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache'
    return response
