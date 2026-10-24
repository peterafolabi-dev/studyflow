"""Online / active-user tracking.

UserPresence holds each user's latest activity (for "online now"), and
DailyActivity keeps one row per user per active day (for DAU/WAU/MAU history).
"""
from datetime import timedelta

from django.utils import timezone

ONLINE_WINDOW = timedelta(minutes=5)
# Writes are throttled so a busy user costs at most one UPDATE a minute.
TOUCH_INTERVAL = timedelta(minutes=1)


def touch_presence(user, force=False):
    from .models import DailyActivity, UserPresence

    now = timezone.now()
    presence = UserPresence.objects.filter(user=user)
    if not force:
        presence = presence.filter(last_seen__lt=now - TOUCH_INTERVAL)
    updated = presence.update(last_seen=now)
    if not updated:
        _, created = UserPresence.objects.get_or_create(user=user, defaults={'last_seen': now})
        if not created and not force:
            return  # seen within the last minute; today's activity is already recorded
    DailyActivity.objects.get_or_create(user=user, date=timezone.localdate(now))


def mark_offline(user):
    """Push last_seen just outside the online window so logout shows immediately."""
    from .models import UserPresence

    UserPresence.objects.filter(user=user).update(
        last_seen=timezone.now() - ONLINE_WINDOW - timedelta(seconds=1)
    )


def online_users():
    from .models import UserPresence

    return UserPresence.objects.filter(
        last_seen__gte=timezone.now() - ONLINE_WINDOW, user__is_active=True
    ).select_related('user').order_by('-last_seen')


def active_user_count(days):
    """Distinct users active in the last `days` days (1 = today)."""
    from .models import DailyActivity

    since = timezone.localdate() - timedelta(days=days - 1)
    return DailyActivity.objects.filter(date__gte=since, user__is_active=True).values('user').distinct().count()


def is_online(presence):
    return presence is not None and presence.last_seen >= timezone.now() - ONLINE_WINDOW
