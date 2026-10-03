from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.db.models import Q
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from resources.models import Resource
from community.models import Thread
from library.models import Book

from .forms import CourseForm, TaskForm, TimetableEntryForm
from .models import Course, Task, TimetableEntry, FlashcardDeck, Flashcard

# SECURITY RULE: every query below is filtered by the logged-in user.
# Without that, a user could open someone else's data by editing the ID in the URL.


def _user_course(request, pk):
    return get_object_or_404(Course, pk=pk, user=request.user)


def _user_task(request, pk):
    return get_object_or_404(Task, pk=pk, course__user=request.user)


@login_required
def dashboard(request):
    today = timezone.localdate()
    week_end = today + timedelta(days=7)

    open_tasks = Task.objects.filter(
        course__user=request.user, is_done=False
    ).select_related('course')

    due_flashcards_count = Flashcard.objects.filter(
        deck__course__user=request.user, next_review_date__lte=today
    ).count()

    # Onboarding Checklist State
    has_reviewed_flashcards = Flashcard.objects.filter(deck__course__user=request.user, last_reviewed_at__isnull=False).exists()
    has_done_tasks = Task.objects.filter(course__user=request.user, is_done=True).exists()
    from .models import StudySession
    has_pomodoro = StudySession.objects.filter(user=request.user).exists()
    
    onboarding_completed = sum([has_reviewed_flashcards, has_done_tasks, has_pomodoro])
    onboarding_percentage = int((onboarding_completed / 3) * 100)
    show_onboarding = onboarding_completed < 3

    context = {
        'overdue': open_tasks.filter(due_date__lt=today),
        'due_soon': open_tasks.filter(due_date__gte=today, due_date__lte=week_end),
        'course_count': Course.objects.filter(user=request.user).count(),
        'open_count': open_tasks.count(),
        'done_count': Task.objects.filter(course__user=request.user, is_done=True).count(),
        'due_flashcards_count': due_flashcards_count,
        'has_reviewed_flashcards': has_reviewed_flashcards,
        'has_done_tasks': has_done_tasks,
        'has_pomodoro': has_pomodoro,
        'onboarding_completed': onboarding_completed,
        'onboarding_percentage': onboarding_percentage,
        'show_onboarding': show_onboarding,
        'trending_resources': Resource.objects.filter(
            last_downloaded_at__gte=timezone.now() - timedelta(days=7)
        ).order_by('-download_count')[:5],
        'quick_links': [
            ('Break Room', '🎮', 'break_room'),
            ('CBT Practice', '🎯', 'cbt_home'),
            ('Catalogue', '📚', 'catalogue'),
            ('My Library', '🔖', 'my_library'),
            ('Past Questions', '📝', 'past_questions'),
            ('Notes', '🗒️', 'notes_list'),
            ('Theses & Papers', '🎓', 'theses_papers'),
            ('Lecture Slides', '📊', 'lecture_slides'),
            ('IBB Library', '🏛️', 'ibb_library'),
            ('Postgraduate', '🧑\u200d🎓', 'postgraduate'),
            ('Timetable', '🗓️', 'timetable'),
            ('GPA Calculator', '🧮', 'gpa_calculator'),
            ('Study Groups', '💬', 'thread_list'),
            ('Research', '🔬', 'research'),
        ],
    }
    return render(request, 'planner/dashboard.html', context)


# ---------- Courses ----------

@login_required
def course_list(request):
    courses = Course.objects.filter(user=request.user)
    return render(request, 'planner/course_list.html', {'courses': courses})


@login_required
def course_create(request):
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save(commit=False)
            course.user = request.user
            course.save()
            messages.success(request, f'Added {course.name}.')
            return redirect('course_detail', pk=course.pk)
    else:
        form = CourseForm()
    return render(request, 'planner/course_form.html', {'form': form, 'heading': 'Add a course'})


@login_required
def course_detail(request, pk):
    course = _user_course(request, pk)
    related_resources = (
        Resource.objects.filter(course_code__iexact=course.code) if course.code else Resource.objects.none()
    )
    threads = Thread.objects.filter(course_code__iexact=course.code)[:5] if course.code else []
    return render(
        request,
        'planner/course_detail.html',
        {
            'course': course,
            'tasks': course.tasks.all(),
            'related_resources': related_resources,
            'threads': threads,
        },
    )


@login_required
def course_update(request, pk):
    course = _user_course(request, pk)
    if request.method == 'POST':
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, 'Course updated.')
            return redirect('course_detail', pk=course.pk)
    else:
        form = CourseForm(instance=course)
    return render(request, 'planner/course_form.html', {'form': form, 'heading': f'Edit {course.name}', 'course': course})


@login_required
def course_delete(request, pk):
    course = _user_course(request, pk)
    if request.method == 'POST':
        name = course.name
        course.delete()
        messages.success(request, f'Deleted {name} and its tasks.')
        return redirect('course_list')
    return render(request, 'planner/course_confirm_delete.html', {'course': course})


# ---------- Tasks ----------

@login_required
def task_create(request, course_pk):
    course = _user_course(request, course_pk)
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.course = course
            task.save()
            messages.success(request, f'Added {task.title}.')
            return redirect('course_detail', pk=course.pk)
    else:
        form = TaskForm(initial={'due_date': timezone.localdate() + timedelta(days=1)})
    return render(request, 'planner/task_form.html', {'form': form, 'course': course, 'heading': 'Add a task'})


@login_required
def task_update(request, pk):
    task = _user_task(request, pk)
    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, 'Task updated.')
            return redirect('course_detail', pk=task.course_id)
    else:
        form = TaskForm(instance=task)
    return render(request, 'planner/task_form.html', {'form': form, 'course': task.course, 'heading': 'Edit task'})


@login_required
def task_delete(request, pk):
    task = _user_task(request, pk)
    if request.method == 'POST':
        course_pk = task.course_id
        task.delete()
        messages.success(request, 'Task deleted.')
        return redirect('course_detail', pk=course_pk)
    return render(request, 'planner/task_confirm_delete.html', {'task': task})


@login_required
@require_POST
def task_toggle(request, pk):
    task = _user_task(request, pk)
    task.is_done = not task.is_done
    task.save(update_fields=['is_done'])

    # Award XP when task is completed
    if task.is_done:
        _award_xp(request.user, 'task_done', points=15)

    # Go back to the page the click came from, but only if it's a safe local URL.
    next_url = request.POST.get('next', '')
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_url = ''
    if next_url:
        return redirect(next_url)
    return redirect('course_detail', pk=task.course_id)



@login_required
def gpa_calculator(request):
    return render(request, 'planner/gpa_calculator.html')


@login_required
def timetable(request):
    entries = TimetableEntry.objects.filter(user=request.user).select_related('course')
    days = [
        (num, label, entries.filter(day_of_week=num))
        for num, label in TimetableEntry.DAY_CHOICES
    ]
    return render(request, 'planner/timetable.html', {'days': days})


@login_required
def timetable_create(request):
    if request.method == 'POST':
        form = TimetableEntryForm(request.POST, user=request.user)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.user = request.user
            entry.save()
            messages.success(request, f'Added "{entry.title}" to your timetable.')
            return redirect('timetable')
    else:
        form = TimetableEntryForm(user=request.user)
    return render(request, 'planner/timetable_form.html', {'form': form})


@login_required
@require_POST
def timetable_delete(request, pk):
    entry = get_object_or_404(TimetableEntry, pk=pk, user=request.user)
    entry.delete()
    messages.info(request, 'Removed from your timetable.')
    return redirect('timetable')


@login_required
def export_calendar(request):
    """A minimal .ics feed of the user's task deadlines, hand-built (no external
    calendar library needed) so it opens in Google Calendar, Apple Calendar, Outlook, etc."""
    tasks = Task.objects.filter(course__user=request.user, is_done=False).select_related('course')

    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//StudyFlow//Task Deadlines//EN',
        'CALSCALE:GREGORIAN',
    ]
    for task in tasks:
        date_str = task.due_date.strftime('%Y%m%d')
        summary = f'{task.course.code or task.course.name}: {task.title}'.replace(',', '\\,')
        lines += [
            'BEGIN:VEVENT',
            f'UID:studyflow-task-{task.pk}@studyflow.local',
            f'DTSTAMP:{timezone.now().strftime("%Y%m%dT%H%M%SZ")}',
            f'DTSTART;VALUE=DATE:{date_str}',
            f'DTEND;VALUE=DATE:{date_str}',
            f'SUMMARY:{summary}',
            'END:VEVENT',
        ]
    lines.append('END:VCALENDAR')

    response = HttpResponse('\r\n'.join(lines), content_type='text/calendar')
    response['Content-Disposition'] = 'attachment; filename="studyflow.ics"'
    return response


@login_required
def global_search(request):
    query = request.GET.get('q', '').strip()
    results = {'books': [], 'resources': [], 'courses': [], 'threads': []}

    if query:
        results['books'] = Book.objects.filter(
            Q(title__icontains=query) | Q(author__icontains=query) | Q(subject__icontains=query)
        )[:8]
        results['resources'] = Resource.objects.filter(
            Q(title__icontains=query) | Q(course_code__icontains=query) | Q(description__icontains=query)
        )[:8]
        results['courses'] = Course.objects.filter(
            user=request.user
        ).filter(Q(name__icontains=query) | Q(code__icontains=query))[:8]
        results['threads'] = Thread.objects.filter(
            Q(title__icontains=query) | Q(course_code__icontains=query)
        )[:8]

    total = sum(len(v) for v in results.values())
    return render(request, 'planner/search.html', {'query': query, 'results': results, 'total': total})


from .models import StudySession, FlashcardDeck, Flashcard

@login_required
def study_room(request):
    courses = Course.objects.filter(user=request.user)
    return render(request, 'planner/study_room.html', {'courses': courses})

@login_required
@require_POST
def log_study(request):
    duration = int(request.POST.get('duration', 0))
    course_id = request.POST.get('course_id')
    if duration > 0:
        course = Course.objects.filter(id=course_id, user=request.user).first() if course_id else None
        StudySession.objects.create(user=request.user, course=course, duration_minutes=duration)
        _award_xp(request.user, 'pomodoro', points=20)
    return redirect('study_room')


@login_required
def flashcard_hubs(request):
    courses = Course.objects.filter(user=request.user)
    decks = FlashcardDeck.objects.filter(course__user=request.user).prefetch_related('cards')

    if request.method == 'POST':
        action = request.POST.get('action')

        # --- Create a new deck ---
        if action == 'create_deck':
            title = request.POST.get('title', '').strip()
            course_id = request.POST.get('course_id')
            course = get_object_or_404(Course, pk=course_id, user=request.user)
            if title:
                FlashcardDeck.objects.create(title=title, course=course)
            return redirect('flashcards')

        # --- Add a card to a deck ---
        elif action == 'add_card':
            deck_id = request.POST.get('deck_id')
            front = request.POST.get('front', '').strip()
            back = request.POST.get('back', '').strip()
            deck = get_object_or_404(FlashcardDeck, pk=deck_id, course__user=request.user)
            if front and back:
                Flashcard.objects.create(deck=deck, front=front, back=back)
            return redirect('flashcards')

        # --- Delete a card ---
        elif action == 'delete_card':
            card_id = request.POST.get('card_id')
            card = get_object_or_404(Flashcard, pk=card_id, deck__course__user=request.user)
            card.delete()
            return redirect('flashcards')

        # --- Delete a deck ---
        elif action == 'delete_deck':
            deck_id = request.POST.get('deck_id')
            deck = get_object_or_404(FlashcardDeck, pk=deck_id, course__user=request.user)
            deck.delete()
            return redirect('flashcards')

    today = timezone.localdate()
    due_cards_qs = Flashcard.objects.filter(
        deck__course__user=request.user, next_review_date__lte=today
    ).select_related('deck', 'deck__course')
    due_count = due_cards_qs.count()

    due_cards_data = [
        {
            'id': c.id,
            'front': c.front,
            'back': c.back,
            'deck_title': c.deck.title,
            'course_code': c.deck.course.code,
            'interval_days': c.interval_days,
            'repetitions': c.repetitions,
        }
        for c in due_cards_qs
    ]

    context = {
        'decks': decks,
        'courses': courses,
        'due_count': due_count,
        'due_cards_json': json.dumps(due_cards_data),
    }
    return render(request, 'planner/flashcards.html', context)


@login_required
@require_POST
def flashcard_rate_review(request, pk):
    """
    Applies SM-2 spaced repetition rating: 'easy', 'medium', or 'hard'.
    """
    card = get_object_or_404(Flashcard, pk=pk, deck__course__user=request.user)
    try:
        data = json.loads(request.body)
        rating = data.get('rating', 'medium')
    except Exception:
        rating = request.POST.get('rating', 'medium')

    if rating not in ['hard', 'medium', 'easy']:
        return JsonResponse({'error': 'Rating must be hard, medium, or easy.'}, status=400)

    next_date = card.process_review(rating)
    _award_xp(request.user, 'flashcard', points=5)
    return JsonResponse({
        'success': True,
        'card_id': card.id,
        'rating': rating,
        'next_review_date': next_date.strftime('%Y-%m-%d'),
        'interval_days': card.interval_days,
        'repetitions': card.repetitions,
    })



from django.http import JsonResponse
import json
from django.views.decorators.csrf import csrf_exempt
import os

import logging
logger = logging.getLogger('django.request')

@csrf_exempt
@require_POST
def ai_chat_api(request):
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        if not user_message:
            return JsonResponse({'reply': 'Ask me something!'})
            
        api_key = os.environ.get('GROQ_API_KEY')
        if not api_key:
            return JsonResponse({'reply': 'I am ready to go! To activate me, add GROQ_API_KEY to your Render environment variables (or .env file).'})
            
        from groq import Groq
        client = Groq(api_key=api_key)
        
        system_prompt = """You are StudyFlow Coach, a smart, friendly, and highly capable AI assistant inside the StudyFlow app. You help students learn, plan, and succeed, and you can answer questions on any subject.

CORE BEHAVIOR
- Answer the actual question directly first, then add helpful detail. Don't dodge or give vague replies.
- Be accurate. If you're unsure or don't know, say so instead of guessing. Never make up facts, sources, quotes, or links.
- Explain step by step when a topic is complex. Start simple, then go deeper if the student wants.
- Match the student's level. If they seem to be a beginner, use plain language and examples. If advanced, be precise and technical.
- For math, science, and coding, show the working and explain why, not just the final answer.
- Help students learn rather than just handing over answers to graded work. Guide them, check their understanding, and offer practice questions.
- If a request is unclear, ask one short clarifying question with 2-3 options. Otherwise, make a reasonable assumption and proceed.
- Remember the conversation. Use earlier messages for context and never restart with a greeting mid-chat.

TASKS YOU HANDLE WELL
- Explaining concepts, summarizing readings and notes, and rewriting text more simply.
- Making flashcards, quizzes, practice problems, and study plans.
- Planning schedules, breaking big tasks into steps, and Pomodoro-style focus sessions.
- Essay outlining, feedback on writing, brainstorming, and citations guidance.
- Coding help, debugging, and math walkthroughs.

STYLE
- Warm, motivating, and confident, like a coach who believes in the student. Keep it natural, not over the top.
- Use clear structure: short paragraphs, and bullets or numbered steps when they help. Use bold sparingly for key terms.
- Keep answers as short as the question allows. Give longer answers only when the topic needs it.
- At most one or two emojis, and only when they fit.
- End with a useful next step, such as a practice question, a quick challenge, or an offer to go deeper.

STUDYFLOW FEATURES
When relevant, point students to real app features: Dashboard, Pomodoro Timer (Deep Focus, Lo-Fi Spotify), Flashcards, Catalogue, Resources, IBB Library reservations, Study Groups, Break Room mini-games, and the GPA calculator. Only mention features that exist.

SAFETY AND HONESTY
- Don't help with cheating on exams or plagiarism. Offer to help them understand the material instead.
- Be kind and supportive if a student is stressed or overwhelmed. If someone seems to be in serious distress, encourage them to reach out to a trusted person or a professional.
- Don't share personal data or pretend to be a human.

FORMATTING RULES
- Use short paragraphs with a blank line between them.
- For steps, use a numbered list with one step per line.
- For options or tips, use bullets with one item per line.
- Bold only key terms or step titles.
- Keep replies under 150 words unless the student asks for more detail.
- Never write a whole reply as one block of text.

ACCURACY RULES
- Only describe screens, buttons, menus, and steps that exist in StudyFlow. Known features: Dashboard, Pomodoro Timer (Deep Focus, Lo-Fi Spotify), Flashcards, Catalogue, Resources, IBB Library reservations, Study Groups, Break Room mini-games, GPA calculator.
- Never invent exact button names, icons, menu paths, or settings. If you're not sure how a feature works, say so and describe it in general terms.
- Don't suggest clearing the cache or updating the app unless the student reports a bug.

MATH FORMATTING
- Write all math in LaTeX using $...$ for inline math and $$...$$ on their own lines for display math.
- Never use plain parentheses or square brackets to wrap formulas.
- Example: The derivative is $f'(x)=3x^2-8x+2$.

FLASHCARD FORMAT
When making a flashcard, use exactly this layout:

**Card 1**
**Front:** question text
**Back:** answer text

Do not add a stray number or heading before the card."""

        model_name = os.environ.get('MODEL_NAME') or os.environ.get('GROQ_MODEL_NAME') or 'openai/gpt-oss-20b'

        # Build full message history with system prompt first
        history = data.get('history', [])
        formatted_messages = [{"role": "system", "content": system_prompt}]
        for item in history:
            role = item.get('role')
            content = item.get('content', '').strip()
            if role in ['user', 'assistant'] and content:
                formatted_messages.append({"role": role, "content": content})

        formatted_messages.append({"role": "user", "content": user_message})

        chat_completion = client.chat.completions.create(
            messages=formatted_messages,
            model=model_name,
        )
        reply = chat_completion.choices[0].message.content
        return JsonResponse({'reply': reply})
    except Exception as e:
        logger.error('AI chat error: %s', e, exc_info=True)
        error_msg = str(e)
        # Check if error is model_not_found (404)
        if (hasattr(e, 'status_code') and e.status_code == 404) or 'model_not_found' in error_msg or 'does not exist' in error_msg:
            available_list = []
            try:
                available_list = [m.id for m in client.models.list().data if 'whisper' not in m.id]
            except Exception:
                pass
            extra = f" Available models: {', '.join(available_list[:6])}." if available_list else ""
            return JsonResponse({
                'reply': f"Model '{model_name}' not found on Groq.{extra} Set MODEL_NAME in your environment to choose an available model."
            }, status=500)
        return JsonResponse({'reply': f'Oops, error: {type(e).__name__} - {e}'}, status=500)


@login_required
def break_room(request):
    return render(request, 'planner/break_room.html')


# ── Phase 5: Progress & Gamification ────────────────────────────────────────

def _award_xp(user, reason, points=10):
    """Award XP and update streak. Call after any study activity."""
    from .models import XPLog, StudyStreak
    XPLog.objects.create(user=user, reason=reason, points=points)
    streak, _ = StudyStreak.objects.get_or_create(user=user)
    streak.record_activity()
    _check_badges(user, streak)


def _check_badges(user, streak):
    """Award badges based on milestones."""
    from .models import Badge, UserBadge, XPLog, StudyStreak
    from django.db.models import Sum

    total_xp = XPLog.objects.filter(user=user).aggregate(s=Sum('points'))['s'] or 0
    milestones = [
        ('first-task', 'First Step', 'Complete your first task', '🎯', 20,
         lambda: XPLog.objects.filter(user=user, reason='task_done').exists()),
        ('streak-3', '3-Day Streak', 'Study 3 days in a row', '🔥', 30,
         lambda: streak.current_streak >= 3),
        ('streak-7', 'Week Warrior', 'Study 7 days in a row', '🏆', 100,
         lambda: streak.current_streak >= 7),
        ('xp-100', 'Century Club', 'Earn 100 XP', '💯', 0,
         lambda: total_xp >= 100),
        ('pomodoro-5', 'Focus Master', 'Complete 5 Pomodoro sessions', '⏱️', 50,
         lambda: XPLog.objects.filter(user=user, reason='pomodoro').count() >= 5),
        ('flashcard-10', 'Card Sharp', 'Review 10 flashcards', '🃏', 50,
         lambda: XPLog.objects.filter(user=user, reason='flashcard').count() >= 10),
    ]

    for slug, name, desc, icon, xp_reward, condition in milestones:
        badge, _ = Badge.objects.get_or_create(
            slug=slug,
            defaults={'name': name, 'description': desc, 'icon': icon, 'xp_reward': xp_reward}
        )
        if not UserBadge.objects.filter(user=user, badge=badge).exists():
            if condition():
                UserBadge.objects.create(user=user, badge=badge)
                if xp_reward:
                    XPLog.objects.create(user=user, reason='streak_bonus', points=xp_reward)


@login_required
def progress(request):
    """Phase 5: Progress dashboard — streak, XP, badges, weekly stats."""
    from django.db.models import Sum, Count
    from datetime import date
    from .models import XPLog, StudyStreak, UserBadge, StudySession

    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())  # Monday

    streak, _ = StudyStreak.objects.get_or_create(user=request.user)
    total_xp = XPLog.total_xp(request.user)
    badges = UserBadge.objects.filter(user=request.user).select_related('badge').order_by('-awarded_at')

    # Weekly study hours per course
    weekly_sessions = StudySession.objects.filter(
        user=request.user,
        date__gte=week_start,
    ).select_related('course')

    weekly_minutes = weekly_sessions.aggregate(total=Sum('duration_minutes'))['total'] or 0
    sessions_by_course = {}
    for s in weekly_sessions:
        name = s.course.name if s.course else 'General'
        sessions_by_course[name] = sessions_by_course.get(name, 0) + s.duration_minutes

    # Weekly counts
    pomodoro_count = StudySession.objects.filter(user=request.user, date__gte=week_start).count()
    tasks_done_week = Task.objects.filter(
        course__user=request.user, is_done=True,
        created_at__date__gte=week_start
    ).count()
    flashcards_reviewed_week = XPLog.objects.filter(
        user=request.user, reason='flashcard', created_at__date__gte=week_start
    ).count()

    # Recent XP log
    recent_xp = XPLog.objects.filter(user=request.user)[:10]

    # XP level: every 200 XP = 1 level
    level = (total_xp // 200) + 1
    xp_in_level = total_xp % 200
    xp_to_next = 200

    context = {
        'streak': streak,
        'total_xp': total_xp,
        'level': level,
        'xp_in_level': xp_in_level,
        'xp_to_next': xp_to_next,
        'xp_pct': min(100, int(xp_in_level / xp_to_next * 100)),
        'badges': badges,
        'weekly_hours': round(weekly_minutes / 60, 1),
        'weekly_minutes': weekly_minutes,
        'pomodoro_count': pomodoro_count,
        'tasks_done_week': tasks_done_week,
        'flashcards_reviewed_week': flashcards_reviewed_week,
        'sessions_by_course': sessions_by_course,
        'recent_xp': recent_xp,
    }
    return render(request, 'planner/progress.html', context)

