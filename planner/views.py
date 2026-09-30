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
from .models import Course, Task, TimetableEntry

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

    context = {
        'overdue': open_tasks.filter(due_date__lt=today),
        'due_soon': open_tasks.filter(due_date__gte=today, due_date__lte=week_end),
        'course_count': Course.objects.filter(user=request.user).count(),
        'open_count': open_tasks.count(),
        'done_count': Task.objects.filter(course__user=request.user, is_done=True).count(),
        'trending_resources': Resource.objects.filter(
            last_downloaded_at__gte=timezone.now() - timedelta(days=7)
        ).order_by('-download_count')[:5],
        'quick_links': [
            ('Break Room', '🎮', 'break_room'),
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
    return redirect('study_room')

@login_required
def flashcard_hubs(request):
    decks = FlashcardDeck.objects.filter(course__user=request.user)
    return render(request, 'planner/flashcards.html', {'decks': decks})


from django.http import JsonResponse
import json
from django.views.decorators.csrf import csrf_exempt
import os

@csrf_exempt
def ai_chat_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '')
            
            api_key = os.environ.get('GEMINI_API_KEY')
            if not api_key:
                return JsonResponse({'reply': 'I am ready to go! To activate me, add GEMINI_API_KEY to the .env file.'})
            
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-flash-latest')
            response = model.generate_content(user_message)
            
            return JsonResponse({'reply': response.text})
        except Exception as e:
            return JsonResponse({'reply': 'Oops, I encountered an error connecting to Gemini! Check your API key. Error: ' + str(e)}, status=500)
    return JsonResponse({'error': 'Invalid method'}, status=405)


@login_required
def break_room(request):
    return render(request, 'planner/break_room.html')
