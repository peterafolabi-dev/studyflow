from django.core.management.base import BaseCommand

from accounts.digest import send_daily_digest


class Command(BaseCommand):
    help = "Send today's study email to students who have tasks or flashcards due."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(str(send_daily_digest(time_budget=10_000))))
