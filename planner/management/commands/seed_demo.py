from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from planner.models import Course, Task


class Command(BaseCommand):
    help = 'Create a demo user (demo / demo12345) with sample courses and tasks, for screenshots.'

    def handle(self, *args, **options):
        User = get_user_model()
        user, created = User.objects.get_or_create(username='demo')
        if not created:
            self.stdout.write('Demo user already exists, nothing changed.')
            return
        user.set_password('demo12345')
        user.save()

        today = timezone.localdate()
        data = {
            ('Signals and Systems', 'EEE 301'): [
                ('Assignment 2: Fourier series', -2, False),
                ('Mid-semester test', 3, False),
                ('Lab report 1', -6, True),
            ],
            ('Data Structures', 'CPE 205'): [
                ('Implement linked list', 1, False),
                ('Quiz on trees', 5, False),
            ],
            ('Engineering Mathematics', 'MTH 201'): [
                ('Problem set 4', 0, False),
                ('Read chapter 7', 12, False),
            ],
        }
        for (name, code), tasks in data.items():
            course = Course.objects.create(user=user, name=name, code=code)
            for title, offset, done in tasks:
                Task.objects.create(
                    course=course, title=title,
                    due_date=today + timedelta(days=offset), is_done=done,
                )
        self.stdout.write(self.style.SUCCESS('Demo data created. Log in as demo / demo12345.'))
