"""Create in-app deadline reminders (run daily from a scheduler)."""
from django.core.management.base import BaseCommand

from planner.reminders import create_deadline_reminders


class Command(BaseCommand):
    help = 'Create in-app reminders for tasks due within the next seven days.'

    def handle(self, *args, **options):
        count = create_deadline_reminders()
        self.stdout.write(self.style.SUCCESS(f'Created {count} deadline reminder(s).'))
