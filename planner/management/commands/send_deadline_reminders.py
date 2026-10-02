"""Management command: send in-app deadline reminders.

Run daily (e.g. via a cron job or Render Cron Service):
    python manage.py send_deadline_reminders

Creates a Notification for each user who has tasks due within 2 days
that they have not yet been notified about today.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model

from planner.models import Task
from accounts.models import Notification


class Command(BaseCommand):
    help = 'Send in-app deadline reminder notifications for tasks due within 2 days.'

    def handle(self, *args, **options):
        today = timezone.localdate()
        deadline = today + timedelta(days=2)

        upcoming = Task.objects.filter(
            is_done=False,
            due_date__gte=today,
            due_date__lte=deadline,
        ).select_related('course', 'course__user')

        sent = 0
        for task in upcoming:
            user = task.course.user
            days_left = (task.due_date - today).days
            label = 'today' if days_left == 0 else f'in {days_left} day{"s" if days_left > 1 else ""}'

            # Avoid duplicate notifications for the same task on the same day
            already_notified = Notification.objects.filter(
                user=user,
                link=f'/tasks/',
                message__icontains=task.title,
                created_at__date=today,
            ).exists()

            if not already_notified:
                Notification.objects.create(
                    user=user,
                    message=f'⏰ Reminder: "{task.title}" is due {label}.',
                    link='/tasks/',
                )
                sent += 1

        self.stdout.write(self.style.SUCCESS(f'Sent {sent} deadline reminder(s).'))
