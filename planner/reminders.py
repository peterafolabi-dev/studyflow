from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from accounts.models import Notification
from .models import Task


def create_deadline_reminders(user=None):
    """Create one in-app reminder per task and deadline stage (7d, 2d, due)."""
    today = timezone.localdate()
    tasks = Task.objects.filter(
        is_done=False,
        due_date__gte=today,
        due_date__lte=today + timedelta(days=7),
    ).select_related('course', 'course__user')
    if user is not None:
        tasks = tasks.filter(course__user=user)

    created = 0
    for task in tasks:
        days_left = (task.due_date - today).days
        stage = 'due' if days_left == 0 else '2day' if days_left <= 2 else '7day'
        link = f"{reverse('course_detail', args=[task.course_id])}?reminder={task.pk}-{task.due_date:%Y%m%d}-{stage}"
        if Notification.objects.filter(user=task.course.user, link=link).exists():
            continue
        due_label = 'today' if days_left == 0 else f"in {days_left} day{'s' if days_left != 1 else ''}"
        Notification.objects.create(
            user=task.course.user,
            message=f'⏰ Reminder: “{task.title}” for {task.course.name} is due {due_label}.',
            link=link,
        )
        created += 1
    return created
