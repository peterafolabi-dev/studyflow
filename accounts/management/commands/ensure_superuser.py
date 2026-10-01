import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Creates a superuser from environment variables if none exists.

    Reads:
        DJANGO_SUPERUSER_USERNAME  (default: admin)
        DJANGO_SUPERUSER_PASSWORD  (required — skips if not set)
        DJANGO_SUPERUSER_EMAIL     (default: admin@studyflow.local)

    Safe to run on every deploy: it does nothing if the user already exists.
    """

    help = 'Auto-create a superuser from env vars (idempotent).'

    def handle(self, *args, **options):
        User = get_user_model()

        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@studyflow.local')

        if not password:
            self.stdout.write(self.style.WARNING(
                'DJANGO_SUPERUSER_PASSWORD not set — skipping superuser creation.'
            ))
            return

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.SUCCESS(
                f'Superuser "{username}" already exists — nothing to do.'
            ))
            return

        User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
        )
        self.stdout.write(self.style.SUCCESS(
            f'Superuser "{username}" created successfully.'
        ))
