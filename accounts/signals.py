from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile

User = get_user_model()


@receiver(post_save, sender=User)
def create_profile_for_new_user(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)


try:
    from allauth.account.signals import user_signed_up
except ImportError:  # allauth not installed
    user_signed_up = None

if user_signed_up is not None:

    @receiver(user_signed_up)
    def welcome_new_google_user(sender, request, user, **kwargs):
        """Google (allauth) sign-ups get the same welcome email as the sign-up form."""
        from .emails import send_welcome_email

        send_welcome_email(user, request)
