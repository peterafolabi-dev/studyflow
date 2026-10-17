from datetime import timedelta

from django.utils import timezone


class UserPresenceMiddleware:
    """Refresh authenticated users' last-seen timestamp at most once a minute."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            from .models import UserPresence

            now = timezone.now()
            stale_before = now - timedelta(minutes=1)
            updated = UserPresence.objects.filter(user=user, last_seen__lt=stale_before).update(last_seen=now)
            if not updated:
                UserPresence.objects.get_or_create(user=user, defaults={'last_seen': now})
        return response
