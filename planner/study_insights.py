"""Weak topics, revision plan and weekly leaderboard.

All functions are pure reads over the student's own data (the leaderboard shows
usernames only, and only for students who have not opted out).
"""
from collections import defaultdict
from datetime import timedelta

from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone

# A topic only counts as "weak" with enough evidence, so one bad attempt never labels a student.
MIN_ANSWERED = 10          # answered CBT questions in a bank
WEAK_BELOW_PERCENT = 60    # accuracy under this = weak
MIN_REVIEWED_CARDS = 5     # reviewed flashcards in a deck
WEAK_CARD_SHARE = 0.4      # share of reviewed cards the student keeps finding hard
HARD_EASE = 2.0            # ease_factor at/below this = a card they struggle with


def weak_topics(user):
    """Returns a list of dicts, weakest first: {kind, title, course, detail, percent, url}."""
    from resources.models import TestAttempt
    from planner.models import Flashcard

    found = []

    stats = defaultdict(lambda: {'right': 0, 'answered': 0, 'bank': None})
    attempts = TestAttempt.objects.filter(user=user, is_completed=True).select_related('bank', 'bank__course')
    for attempt in attempts:
        questions = {str(q.id): q.correct_option for q in attempt.bank.questions.all()}
        row = stats[attempt.bank_id]
        row['bank'] = attempt.bank
        for qid, choice in (attempt.answers or {}).items():
            if qid in questions and choice:
                row['answered'] += 1
                row['right'] += int(choice == questions[qid])
    for row in stats.values():
        if row['answered'] < MIN_ANSWERED:
            continue
        percent = round(100 * row['right'] / row['answered'])
        if percent < WEAK_BELOW_PERCENT:
            bank = row['bank']
            found.append({
                'kind': 'cbt', 'title': bank.title, 'course': bank.course_id,
                'course_code': bank.course_code or (bank.course.code if bank.course else ''),
                'detail': f"{row['right']} of {row['answered']} answers right",
                'percent': percent, 'url': reverse('cbt_detail', args=[bank.pk]),
            })

    decks = defaultdict(lambda: {'reviewed': 0, 'hard': 0, 'deck': None})
    cards = Flashcard.objects.filter(
        deck__course__user=user, last_reviewed_at__isnull=False
    ).select_related('deck', 'deck__course')
    for card in cards:
        row = decks[card.deck_id]
        row['deck'] = card.deck
        row['reviewed'] += 1
        row['hard'] += int(card.ease_factor <= HARD_EASE)
    for row in decks.values():
        if row['reviewed'] < MIN_REVIEWED_CARDS:
            continue
        share = row['hard'] / row['reviewed']
        if share >= WEAK_CARD_SHARE:
            deck = row['deck']
            found.append({
                'kind': 'cards', 'title': deck.title, 'course': deck.course_id,
                'course_code': deck.course.code,
                'detail': f"{row['hard']} of {row['reviewed']} reviewed cards keep coming back hard",
                'percent': round(100 * (1 - share)), 'url': reverse('flashcards'),
            })

    found.sort(key=lambda t: t['percent'])
    return found


def revision_plan(user, days=7, today=None):
    """Spreads the student's daily study time across upcoming exams.

    Closer exams get more time and weak courses get a boost. Returns
    {'exams': [...], 'days': [{'date', 'items': [{'course', 'minutes', 'focus'}]}], 'daily_minutes'}.
    """
    from planner.models import Course

    today = today or timezone.localdate()
    courses = list(Course.objects.filter(user=user, exam_date__gte=today).order_by('exam_date'))
    weak = weak_topics(user)
    weak_by_course = defaultdict(list)
    for item in weak:
        weak_by_course[item['course']].append(item['title'])

    goal_hours = getattr(getattr(user, 'profile', None), 'weekly_study_goal_hours', 8) or 8
    daily_minutes = max(30, round(goal_hours * 60 / 7 / 5) * 5)

    plan_days = []
    for offset in range(days):
        day = today + timedelta(days=offset)
        active = [c for c in courses if c.exam_date >= day]
        weights = {}
        for course in active:
            left = max(1, (course.exam_date - day).days + 1)
            weight = 1.0 / left
            if weak_by_course.get(course.pk):
                weight *= 1.5
            weights[course.pk] = weight
        total = sum(weights.values())
        items = []
        for course in active:
            minutes = round(daily_minutes * weights[course.pk] / total / 5) * 5 if total else 0
            if minutes < 10:
                continue
            topics = weak_by_course.get(course.pk)
            focus = ('Work on: ' + ', '.join(topics[:2])) if topics else 'Past questions and flashcards'
            if course.exam_date == day:
                focus = 'Exam day: light recap, rest well'
            items.append({'course': course, 'minutes': minutes, 'focus': focus})
        plan_days.append({'date': day, 'items': items})

    exams = [{'course': c, 'days_left': (c.exam_date - today).days, 'weak': weak_by_course.get(c.pk, [])} for c in courses]
    return {'exams': exams, 'days': plan_days, 'daily_minutes': daily_minutes}


def weekly_leaderboard(user, limit=20, today=None):
    """Top XP earners this week (Monday start), usernames only, opted-out students excluded.

    Returns {'rows': [{'rank','username','xp','is_me'}], 'me': row-or-None, 'opted_in': bool}.
    """
    from django.contrib.auth import get_user_model
    from planner.models import StudyStreak, XPLog

    today = today or timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    hidden = StudyStreak.objects.filter(show_on_leaderboard=False).values_list('user_id', flat=True)
    totals = (
        XPLog.objects.filter(created_at__date__gte=week_start)
        .exclude(user_id__in=hidden)
        .values('user_id').annotate(xp=Sum('points')).filter(xp__gt=0)
        .order_by('-xp', 'user_id')
    )
    names = dict(get_user_model().objects.filter(pk__in=[t['user_id'] for t in totals]).values_list('pk', 'username'))
    rows, me = [], None
    for rank, t in enumerate(totals, start=1):
        row = {'rank': rank, 'username': names.get(t['user_id'], '?'), 'xp': t['xp'], 'is_me': t['user_id'] == user.pk}
        if row['is_me']:
            me = row
        if rank <= limit:
            rows.append(row)
    opted_in = not StudyStreak.objects.filter(user=user, show_on_leaderboard=False).exists()
    return {'rows': rows, 'me': me, 'opted_in': opted_in, 'week_start': week_start}
