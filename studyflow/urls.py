from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import include, path
from django.views.generic import TemplateView
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
    urls = ''.join(f'<url><loc>{base}{path}</loc></url>' for path in ('/about/', '/login/', '/signup/'))
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
    return HttpResponse(xml, content_type='application/xml')


ABOUT_SECTIONS = [
    {'icon': '📅', 'title': 'Plan your study', 'items': [
        'Courses, tasks and deadlines, with a weekly plan and a revision plan built around your exams',
        'Timetable with multi-day classes, attendance tracker, and calendar export (.ics)',
        'Pomodoro study room, study log, streaks and a progress page that shows weak topics',
        'GPA and CGPA calculators']},
    {'icon': '🤖', 'title': 'AI study coach', 'items': [
        'Ask anything about your courses or campus life; it remembers what you tell it and can add tasks for you',
        'Turns notes into flashcards and quizzes, and explains CBT answers']},
    {'icon': '📚', 'title': 'Resources and library', 'items': [
        'Past questions, notes, lecture slides, theses and research papers shared by students, with ratings and reports',
        'One-tap AI summaries, flashcards and quizzes from any uploaded PDF',
        'IBB library catalogue with reservations and loans']},
    {'icon': '📝', 'title': 'CBT practice', 'items': [
        'Practice exams from question banks, with timed attempts and explained results']},
    {'icon': '💬', 'title': 'Community', 'items': [
        'Campus chat rooms (Global, FUT Minna, Announcements) with replies, reactions, photos and files, polls, @mentions and search',
        'Study groups and study buddies']},
    {'icon': '🏫', 'title': 'Campus life', 'items': [
        'Power tracker, notices, events, lost and found, marketplace, opportunities and emergency contacts',
        'Lodges and roommates, and a SIWES logbook']},
    {'icon': '🎮', 'title': 'Game Zone', 'items': [
        'Study games with XP, badges, a daily challenge and a weekly leaderboard']},
    {'icon': '📱', 'title': 'Made for your phone', 'items': [
        'Installable on your home screen, dark mode, Google sign-in, email verification and a daily study digest',
        'Your data is yours: export it or delete your account at any time']},
]

ABOUT_COMING = [
    'A native Android and iPhone app (today StudyFlow is an installable web app)',
    'Push notifications for deadlines, messages and announcements',
    'Voice notes, calls and live (instant) chat; chat currently refreshes every few seconds',
    'Department and course rooms moderated by course reps',
    'Campus guides for other universities (the campus knowledge is FUT Minna for now)',
]


def about(request):
    return render(request, 'about.html', {'sections': ABOUT_SECTIONS, 'coming': ABOUT_COMING})


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
    path('about/', about, name='about'),
    path('privacy/', TemplateView.as_view(template_name='legal/privacy.html'), name='privacy'),
    path('terms/', TemplateView.as_view(template_name='legal/terms.html'), name='terms'),
    path('campus/', include('campus.urls')),
    path('campus-life/', include('campus_life.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
