from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from library.models import BookRating, SavedBook
from planner.models import Course, Task, TimetableEntry
from resources.models import Loan, Resource, ResourceRating

from .forms import SignUpForm


def signup(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = SignUpForm()

    return render(request, 'accounts/signup.html', {'form': form})


@login_required
def profile(request):
    finished_count = SavedBook.objects.filter(user=request.user, status='finished').count()
    reading_count = SavedBook.objects.filter(user=request.user, status='reading').count()

    if finished_count >= 6:
        rank = 'Legendary Reader'
        rank_emoji = '🏆'
    elif finished_count >= 3:
        rank = 'Bookworm'
        rank_emoji = '🐛'
    elif finished_count >= 1:
        rank = 'Scholar'
        rank_emoji = '🎓'
    else:
        rank = 'Newcomer'
        rank_emoji = '🌱'

    context = {
        'course_count': Course.objects.filter(user=request.user).count(),
        'open_task_count': Task.objects.filter(
            course__user=request.user, is_done=False
        ).count(),
        'saved_book_count': SavedBook.objects.filter(user=request.user).count(),
        'finished_count': finished_count,
        'reading_count': reading_count,
        'rank': rank,
        'rank_emoji': rank_emoji,
    }
    return render(request, 'accounts/profile.html', context)


@login_required
def export_my_data(request):
    """Lets a user download everything StudyFlow has stored about their
    activity, as one JSON file — courses, tasks, saved books, ratings,
    uploaded resources, library loans, and timetable entries."""
    user = request.user

    data = {
        'exported_at': timezone.now().isoformat(),
        'username': user.username,
        'email': user.email,
        'courses': [
            {'name': c.name, 'code': c.code, 'created_at': c.created_at.isoformat()}
            for c in Course.objects.filter(user=user)
        ],
        'tasks': [
            {
                'title': t.title, 'course': t.course.name, 'due_date': t.due_date.isoformat(),
                'is_done': t.is_done,
            }
            for t in Task.objects.filter(course__user=user).select_related('course')
        ],
        'saved_books': [
            {
                'title': s.book.title, 'status': s.status, 'saved_at': s.saved_at.isoformat(),
            }
            for s in SavedBook.objects.filter(user=user).select_related('book')
        ],
        'book_ratings': [
            {'book': r.book.title, 'stars': r.stars} for r in BookRating.objects.filter(user=user).select_related('book')
        ],
        'uploaded_resources': [
            {
                'title': r.title, 'type': r.get_resource_type_display(), 'course_code': r.course_code,
                'download_count': r.download_count, 'created_at': r.created_at.isoformat(),
            }
            for r in Resource.objects.filter(uploaded_by=user)
        ],
        'resource_ratings': [
            {'resource': r.resource.title, 'stars': r.stars} for r in ResourceRating.objects.filter(user=user).select_related('resource')
        ],
        'library_loans': [
            {
                'title': loan.holding.title, 'borrowed_at': loan.borrowed_at.isoformat(),
                'due_at': loan.due_at.isoformat(),
                'returned_at': loan.returned_at.isoformat() if loan.returned_at else None,
            }
            for loan in Loan.objects.filter(user=user).select_related('holding')
        ],
        'timetable': [
            {
                'title': e.title, 'day': e.get_day_of_week_display(),
                'start_time': e.start_time.strftime('%H:%M'), 'end_time': e.end_time.strftime('%H:%M'),
                'location': e.location,
            }
            for e in TimetableEntry.objects.filter(user=user)
        ],
    }

    response = JsonResponse(data, json_dumps_params={'indent': 2})
    response['Content-Disposition'] = f'attachment; filename="studyflow-{user.username}-data.json"'
    return response
