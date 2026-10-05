import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Create or update the admin user from environment variables.'

    def handle(self, *args, **options):
        User = get_user_model()
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')

        if not password:
            raise CommandError('DJANGO_SUPERUSER_PASSWORD must be set.')

        lookup = {User.USERNAME_FIELD: username}
        user = User._default_manager.filter(**lookup).first()
        created = user is None
        if created:
            user = User(**lookup)

        if hasattr(user, 'email'):
            user.email = email
        user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.save()

        action = 'created' if created else 'updated'
        self.stdout.write(self.style.SUCCESS(f'Admin user "{username}" {action}.'))

        # Ensure Site domain is set correctly for OAuth callbacks
        try:
            from django.contrib.sites.models import Site
            site = Site.objects.filter(id=1).first()
            if site:
                site.domain = 'studyflow-xt1x.onrender.com'
                site.name = 'StudyFlow'
                site.save()
                self.stdout.write(self.style.SUCCESS(f'Site domain updated to: {site.domain}'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Could not update site domain: {e}'))

