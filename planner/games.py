"""Game Zone: arcade hub, score submission, XP, badges, leaderboards, daily challenge."""
import json
import random
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Max, Sum
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Badge, Flashcard, GameScore, StudyStreak, UserBadge, XPLog

GAMES = {
    'quiz': {'name': 'Quiz Battle', 'icon': '🧠', 'blurb': 'Ten timed questions from your own flashcards.', 'max': 1500, 'target': 600},
    'math': {'name': 'Math Sprint', 'icon': '➗', 'blurb': '60 seconds of mental maths. Build a streak.', 'max': 2500, 'target': 300},
    'scramble': {'name': 'Word Scramble', 'icon': '🔤', 'blurb': 'Unscramble study words before time runs out.', 'max': 2000, 'target': 400},
    'snake': {'name': 'Snake', 'icon': '🐍', 'blurb': 'The classic. Eat, grow, do not crash.', 'max': 3000, 'target': 100},
    'tictactoe': {'name': 'Tic-Tac-Toe', 'icon': '⭕', 'blurb': 'Best of five against the computer.', 'max': 500, 'target': 200},
}
DAILY_ORDER = ['quiz', 'math', 'scramble', 'snake', 'tictactoe']
DAILY_XP_CAP = 50        # XP from playing, per day
DAILY_BONUS_XP = 20
MIN_SECONDS_BETWEEN_SUBMITS = 8


def todays_challenge(today=None):
    today = today or timezone.localdate()
    slug = DAILY_ORDER[today.toordinal() % len(DAILY_ORDER)]
    return {'slug': slug, **GAMES[slug]}


def play_xp(score):
    return min(10, max(1, score // 100))


def _week_start(today=None):
    today = today or timezone.localdate()
    return today - timedelta(days=today.weekday())


def weekly_top(game, user, limit=10):
    """Best score this week per student for a game. Hidden students are excluded."""
    hidden = set(StudyStreak.objects.filter(show_on_leaderboard=False).values_list('user_id', flat=True))
    rows = (GameScore.objects.filter(game=game, created_at__date__gte=_week_start())
            .exclude(user_id__in=hidden)
            .values('user_id', 'user__username').annotate(best=Max('score')).order_by('-best', 'user_id'))
    out = []
    for rank, row in enumerate(rows, start=1):
        if rank <= limit or row['user_id'] == user.pk:
            out.append({'rank': rank, 'username': row['user__username'], 'best': row['best'],
                        'is_me': row['user_id'] == user.pk})
    return out


def _arcade_badges(user):
    plays = GameScore.objects.filter(user=user)
    checks = [
        ('arcade-first', 'First Play', 'Finish your first Game Zone game', '🎮', 10, plays.exists()),
        ('arcade-all-rounder', 'All-Rounder', 'Play 5 different Game Zone games', '🕹️', 40,
         plays.values('game').distinct().count() >= 5),
        ('arcade-daily-3', 'Challenge Accepted', 'Beat the daily challenge 3 times', '🔥', 40,
         plays.filter(is_daily=True).count() >= 3),
        ('arcade-high-roller', 'High Roller', 'Score 1000+ in any game', '🏅', 30,
         plays.filter(score__gte=1000).exists()),
    ]
    earned = []
    for slug, name, desc, icon, reward, ok in checks:
        if not ok:
            continue
        badge, _ = Badge.objects.get_or_create(slug=slug, defaults={
            'name': name, 'description': desc, 'icon': icon, 'xp_reward': reward})
        _, created = UserBadge.objects.get_or_create(user=user, badge=badge)
        if created:
            if reward:
                XPLog.objects.create(user=user, reason='game_bonus', points=reward)
            earned.append({'name': name, 'icon': icon})
    return earned


@login_required
def arcade_hub(request):
    today = timezone.localdate()
    challenge = todays_challenge(today)
    done_today = GameScore.objects.filter(user=request.user, is_daily=True, created_at__date=today).exists()
    best = dict(GameScore.objects.filter(user=request.user).values_list('game').annotate(b=Max('score')))
    cards = [{'slug': s, **g, 'best': best.get(s)} for s, g in GAMES.items()]
    xp_today = (XPLog.objects.filter(user=request.user, reason='game', created_at__date=today)
                .aggregate(s=Sum('points'))['s'] or 0)
    return render(request, 'planner/arcade/hub.html', {
        'cards': cards, 'challenge': challenge, 'done_today': done_today,
        'xp_today': xp_today, 'xp_cap': DAILY_XP_CAP,
    })


@login_required
def arcade_game(request, slug):
    game = GAMES.get(slug)
    if not game:
        raise Http404
    today = timezone.localdate()
    challenge = todays_challenge(today)
    mine = GameScore.objects.filter(user=request.user, game=slug)
    return render(request, 'planner/arcade/game.html', {
        'slug': slug, 'game': game, 'board': weekly_top(slug, request.user),
        'my_best': mine.aggregate(b=Max('score'))['b'],
        'is_daily': challenge['slug'] == slug,
        'daily_done': GameScore.objects.filter(user=request.user, is_daily=True, created_at__date=today).exists(),
    })


@login_required
@require_POST
def arcade_submit(request):
    try:
        payload = json.loads(request.body or b'{}')
        slug = payload.get('game')
        score = int(payload.get('score'))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Bad request'}, status=400)
    game = GAMES.get(slug)
    if not game or score < 0 or score > game['max']:
        return JsonResponse({'error': 'Invalid score'}, status=400)

    now = timezone.now()
    last = GameScore.objects.filter(user=request.user, game=slug).first()
    if last and (now - last.created_at).total_seconds() < MIN_SECONDS_BETWEEN_SUBMITS:
        return JsonResponse({'error': 'Slow down a little'}, status=429)

    today = timezone.localdate()
    challenge = todays_challenge(today)
    previous_best = GameScore.objects.filter(user=request.user, game=slug).aggregate(b=Max('score'))['b']
    daily_done = GameScore.objects.filter(user=request.user, is_daily=True, created_at__date=today).exists()
    hit_daily = (not daily_done and challenge['slug'] == slug and score >= game['target'])
    GameScore.objects.create(user=request.user, game=slug, score=score, is_daily=hit_daily)

    xp_so_far = (XPLog.objects.filter(user=request.user, reason='game', created_at__date=today)
                 .aggregate(s=Sum('points'))['s'] or 0)
    xp = max(0, min(play_xp(score), DAILY_XP_CAP - xp_so_far)) if score > 0 else 0
    if xp:
        XPLog.objects.create(user=request.user, reason='game', points=xp)
    if hit_daily:
        XPLog.objects.create(user=request.user, reason='game_bonus', points=DAILY_BONUS_XP)

    return JsonResponse({
        'xp': xp, 'daily_bonus': DAILY_BONUS_XP if hit_daily else 0,
        'best': max(score, previous_best or 0), 'new_best': previous_best is None or score > previous_best,
        'badges': _arcade_badges(request.user),
    })


QUESTION_BANK = [
    ('What does CPU stand for?', 'Central Processing Unit', ['Central Program Utility', 'Computer Power Unit', 'Core Processing Unit']),
    ('What is the SI unit of force?', 'Newton', ['Joule', 'Watt', 'Pascal']),
    ('What is 15% of 200?', '30', ['25', '35', '20']),
    ('Which planet is closest to the Sun?', 'Mercury', ['Venus', 'Mars', 'Earth']),
    ('What is the chemical symbol for sodium?', 'Na', ['So', 'Sd', 'N']),
    ('Who wrote "Things Fall Apart"?', 'Chinua Achebe', ['Wole Soyinka', 'Chimamanda Adichie', 'Ben Okri']),
    ('What does HTML stand for?', 'HyperText Markup Language', ['HighText Machine Language', 'Hyperlink Text Mode Language', 'Home Tool Markup Language']),
    ('What is the capital of Niger State?', 'Minna', ['Abuja', 'Kontagora', 'Suleja']),
    ('The derivative of x squared is?', '2x', ['x', 'x squared', '2']),
    ('What is the powerhouse of the cell?', 'Mitochondria', ['Nucleus', 'Ribosome', 'Golgi body']),
    ('Binary 101 equals which decimal number?', '5', ['3', '6', '10']),
    ('What is the speed of light, roughly?', '300,000 km/s', ['150,000 km/s', '30,000 km/s', '3,000 km/s']),
    ('Which data structure works first-in, first-out?', 'Queue', ['Stack', 'Tree', 'Graph']),
    ('What is the formula for the area of a circle?', 'pi r squared', ['2 pi r', 'pi d', 'r squared']),
    ('In Ohm\'s law, V equals?', 'I times R', ['I divided by R', 'R divided by I', 'I plus R']),
    ('Which gas do plants take in for photosynthesis?', 'Carbon dioxide', ['Oxygen', 'Nitrogen', 'Hydrogen']),
]


def _short(text, n=90):
    text = ' '.join(str(text).split())
    return text if len(text) <= n else text[:n - 1] + '…'


@login_required
def arcade_quiz_questions(request):
    """10 multiple-choice questions: the student's own flashcards first, general bank to fill."""
    own = list(Flashcard.objects.filter(deck__course__user=request.user).values_list('front', 'back'))
    random.shuffle(own)
    pool_backs = [_short(b) for _, b in own] + [q[1] for q in QUESTION_BANK]
    questions = []
    for front, back in own[:6]:
        correct = _short(back)
        wrong = [b for b in set(pool_backs) if b != correct]
        random.shuffle(wrong)
        if len(wrong) < 3:
            continue
        options = wrong[:3] + [correct]
        random.shuffle(options)
        questions.append({'q': _short(front, 160), 'options': options, 'answer': options.index(correct)})
    bank = QUESTION_BANK[:]
    random.shuffle(bank)
    for q, correct, wrong in bank:
        if len(questions) >= 10:
            break
        options = wrong + [correct]
        random.shuffle(options)
        questions.append({'q': q, 'options': options, 'answer': options.index(correct)})
    random.shuffle(questions)
    return JsonResponse({'questions': questions[:10], 'from_flashcards': min(6, len(own))})
