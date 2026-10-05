import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Creates or updates the superuser from environment variables'

    def handle(self, *args, **options):
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'StudyFlowAdmin123!')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@studyflow.local')

        User = get_user_model()
        
        user, created = User.objects.get_or_create(username=username)
        
        user.email = email
        user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f"Successfully created superuser '{username}'"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Successfully updated superuser '{username}'"))
