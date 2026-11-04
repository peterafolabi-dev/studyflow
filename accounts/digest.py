"""The daily study email: each morning, a student's overdue and upcoming tasks,
flashcards due for review and a study tip.

Only sent to students who have something due, so it never becomes noise.
Triggered by .github/workflows/daily-digest.yml calling /cron/daily-digest/,
or manually with `python manage.py send_daily_digest`.
"""
import logging
import time
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .emails import _site_url
from .models import Profile

logger = logging.getLogger(__name__)

TIPS = [
    'Test yourself before you re-read. Recalling an answer strengthens memory far more than reading it again.',
    'Do the hardest task first, while your mind is fresh.',
    'Two 25-minute focus sessions beat two hours of half-attention. Try the Study Room timer.',
    'Explain today’s topic out loud as if teaching a classmate. Gaps show up fast.',
    'Space it out: a little every day beats one long night before the exam.',
    'Stuck on a derivation? Ask the AI coach to go one step at a time.',
    'Put your phone in another room for one focus session and see the difference.',
]


def build_digest_context(user, today=None):
    from planner.models import Flashcard, Task

    today = today or timezone.localdate()
    open_tasks = Task.objects.filter(course__user=user, is_done=False).select_related('course')
    overdue = list(open_tasks.filter(due_date__lt=today)[:5])
    upcoming = list(open_tasks.filter(due_date__gte=today, due_date__lte=today + timedelta(days=3))[:6])
    cards_due = Flashcard.objects.filter(deck__course__user=user, next_review_date__lte=today).count()
    return {
        'user': user,
        'name': (user.first_name or user.get_username()).strip(),
        'today': today,
        'overdue': overdue,
        'upcoming': upcoming,
        'cards_due': cards_due,
        'tip': TIPS[today.toordinal() % len(TIPS)],
    }


def has_something(ctx):
    return bool(ctx['overdue'] or ctx['upcoming'] or ctx['cards_due'])


def build_digest_message(profile, ctx, request=None):
    site = _site_url(request)
    unsubscribe = site + reverse('digest_unsubscribe', args=[profile.ensure_digest_token()])
    ctx = {
        **ctx,
        'site': site,
        'domain': site.split('://', 1)[-1],
        'dashboard_url': site + reverse('dashboard'),
        'tasks_url': site + reverse('task_list'),
        'flashcards_url': site + reverse('flashcards') + '?queue=due',
        'unsubscribe_url': unsubscribe,
    }
    n = len(ctx['overdue']) + len(ctx['upcoming'])
    bits = []
    if n:
        bits.append(f"{n} task{'s' if n != 1 else ''} due")
    if ctx['cards_due']:
        bits.append(f"{ctx['cards_due']} flashcard{'s' if ctx['cards_due'] != 1 else ''} to review")
    msg = EmailMultiAlternatives(
        subject=f"Today on StudyFlow: {' and '.join(bits)}",
        body=render_to_string('accounts/daily_digest.txt', ctx),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[profile.user.email],
        headers={'List-Unsubscribe': f'<{unsubscribe}>', 'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click'},
    )
    msg.attach_alternative(render_to_string('accounts/daily_digest.html', ctx), 'text/html')
    return msg


def send_daily_digest(now=None, time_budget=45.0, request=None):
    """Emails every opted-in student who has something due and hasn't had today's email.

    Safe to call repeatedly: stops before the time budget runs out and the next call carries on.
    """
    now = now or timezone.now()
    today = timezone.localdate(now)
    start_of_day = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
    profiles = (
        Profile.objects.filter(daily_digest=True, user__is_active=True)
        .exclude(user__email='')
        .exclude(last_digest_at__gte=start_of_day)
        .select_related('user')
        .order_by('id')
    )
    started = time.monotonic()
    sent = skipped = failed = 0
    stopped_early = False
    for profile in profiles:
        if time.monotonic() - started > time_budget:
            stopped_early = True
            break
        ctx = build_digest_context(profile.user, today)
        if not has_something(ctx):
            skipped += 1
            profile.last_digest_at = now  # checked today; don't look again until tomorrow
            profile.save(update_fields=['last_digest_at'])
            continue
        try:
            build_digest_message(profile, ctx, request).send()
        except Exception:
            failed += 1
            logger.exception('Daily digest failed for user %s', profile.user_id)
            continue
        profile.last_digest_at = now
        profile.save(update_fields=['last_digest_at'])
        sent += 1
    return {'sent': sent, 'skipped_nothing_due': skipped, 'failed': failed, 'more_to_send': stopped_early}
