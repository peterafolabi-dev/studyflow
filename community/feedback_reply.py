from django.urls import reverse
from django.utils import timezone

from accounts.models import Notification


def save_feedback_reply(fb, staff_user, text):
    """Store a reply on a feedback entry and tell the student. Shared by the admin and the staff page."""
    text = (text or '').strip()[:1000]
    fb.reply = text
    if text:
        fb.replied_at = timezone.now()
        fb.replied_by = staff_user
    else:
        fb.replied_at = None
        fb.replied_by = None
    fb.save()
    if text and fb.user_id:
        Notification.objects.create(
            user_id=fb.user_id, message='The StudyFlow team replied to your feedback: "%s"' % text[:80],
            link=reverse('my_feedback'))
    return fb
