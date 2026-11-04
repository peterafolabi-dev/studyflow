"""Transactional emails sent by the accounts app."""
import logging
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

logger = logging.getLogger(__name__)

DEFAULT_SITE_URL = 'https://studyflow-xt1x.onrender.com'


def _site_url(request=None):
    if request is not None:
        return request.build_absolute_uri('/').rstrip('/')
    return getattr(settings, 'SITE_URL', '') or DEFAULT_SITE_URL


def build_welcome_email(user, request=None):
    site = _site_url(request)
    context = {
        'user': user,
        'name': (user.first_name or user.get_username()).strip(),
        'site': site,
        'domain': site.split('://', 1)[-1],
        'dashboard_url': site + reverse('dashboard'),
        'courses_url': site + reverse('course_create'),
        'study_url': site + reverse('study_room'),
        'flashcards_url': site + reverse('flashcards'),
    }
    msg = EmailMultiAlternatives(
        subject='Welcome to StudyFlow 🎓 Here’s how to get started',
        body=render_to_string('accounts/welcome_email.txt', context),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    msg.attach_alternative(render_to_string('accounts/welcome_email.html', context), 'text/html')
    return msg


def _deliver(msg):
    try:
        msg.send()
    except Exception:  # an email problem must never break sign-up
        logger.exception('Welcome email could not be sent to %s', msg.to)


def send_welcome_email(user, request=None):
    """Sends the welcome email. Skips users without an address.

    Sends in a background thread so a slow mail provider never slows down sign-up;
    tests set WELCOME_EMAIL_SYNC = True to send inline.
    """
    if not user.email:
        return False
    msg = build_welcome_email(user, request)
    if getattr(settings, 'WELCOME_EMAIL_SYNC', False):
        _deliver(msg)
    else:
        threading.Thread(target=_deliver, args=(msg,), daemon=True).start()
    return True
