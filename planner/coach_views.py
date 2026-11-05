"""Small JSON endpoints behind the coach's buttons: add task, save cards, feedback, memory."""
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .coach.actions import create_task, save_cards
from .coach.prompt import MODES, PLAYBOOK_VERSION
from .models import CoachFeedback, CoachMemory


def _json(request):
    try:
        data = json.loads(request.body or b'{}')
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


@login_required
@require_POST
def coach_add_task(request):
    data = _json(request)
    title = str(data.get('title', '')).strip()
    course = str(data.get('course', '')).strip()
    due = str(data.get('due', '')).strip()
    if not title or not due:
        return JsonResponse({'ok': False, 'error': 'Missing task details.'}, status=400)
    try:
        task, created = create_task(request.user, course, title, due)
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e) or 'Invalid date.'}, status=400)
    label = task.course.code or task.course.name
    return JsonResponse({'ok': True, 'created': created, 'message': f'Added to {label}, due {task.due_date:%a %d %b}.'})


@login_required
@require_POST
def coach_save_cards(request):
    data = _json(request)
    cards = data.get('cards') or []
    if not isinstance(cards, list) or not cards:
        return JsonResponse({'ok': False, 'error': 'No cards to save.'}, status=400)
    deck, made = save_cards(request.user, str(data.get('course', '')).strip(), str(data.get('deck', '')).strip(), cards)
    if not made:
        return JsonResponse({'ok': False, 'error': 'No valid cards to save.'}, status=400)
    return JsonResponse({'ok': True, 'message': f'Saved {made} card{"s" if made != 1 else ""} to "{deck.title}". They\'ll come up in Flashcards for review.'})


@login_required
@require_POST
def coach_feedback(request):
    data = _json(request)
    helpful = data.get('helpful')
    if not isinstance(helpful, bool):
        return JsonResponse({'ok': False, 'error': 'helpful must be true or false.'}, status=400)
    mode = str(data.get('mode', '') or '')
    CoachFeedback.objects.create(
        user=request.user,
        helpful=helpful,
        mode=mode if mode in MODES else '',
        question=str(data.get('question', ''))[:8000],
        reply=str(data.get('reply', ''))[:12000],
        comment=str(data.get('comment', ''))[:300],
        playbook_version=str(data.get('playbook', '') or PLAYBOOK_VERSION)[:30],
        model_name=str(data.get('model', ''))[:80],
    )
    return JsonResponse({'ok': True})


@login_required
@require_GET
def coach_memory(request):
    notes = list(CoachMemory.objects.filter(user=request.user).values('id', 'note'))
    return JsonResponse({'notes': notes})


@login_required
@require_POST
def coach_forget(request):
    data = _json(request)
    qs = CoachMemory.objects.filter(user=request.user)
    if data.get('id'):
        qs = qs.filter(pk=data['id'])
    deleted, _ = qs.delete()
    return JsonResponse({'ok': True, 'deleted': deleted})
