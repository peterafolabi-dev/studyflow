"""Email verification for students who sign up with email and password.

Flow: sign up → we email a link → clicking it marks the email verified, logs the
student in and sends the welcome email. Until then, logging in shows a
"verify your email" message with a resend button.
"""
import logging

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .emails import _site_url

logger = logging.getLogger(__name__)


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """Like password-reset tokens, but its own salt, and invalid once the email is verified or changed."""

    key_salt = 'studyflow.accounts.EmailVerificationTokenGenerator'

    def _make_hash_value(self, user, timestamp):
        profile = getattr(user, 'profile', None)
        verified = getattr(profile, 'email_verified', True)
        return f'{user.pk}{user.email}{verified}{timestamp}'


email_verification_token = EmailVerificationTokenGenerator()


def verification_required():
    return getattr(settings, 'EMAIL_VERIFICATION_REQUIRED', False)


def needs_verification(user):
    profile = getattr(user, 'profile', None)
    return verification_required() and profile is not None and not profile.email_verified


def verification_link(user, request=None):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    return _site_url(request) + reverse('verify_email', args=[uid, token])


def send_verification_email(user, request=None):
    """Returns True if the email was handed to the mail provider."""
    if not user.email:
        return False
    site = _site_url(request)
    context = {
        'user': user,
        'name': (user.first_name or user.get_username()).strip(),
        'link': verification_link(user, request),
        'site': site,
        'domain': site.split('://', 1)[-1],
        'expiry_days': max(1, settings.PASSWORD_RESET_TIMEOUT // 86400),
    }
    msg = EmailMultiAlternatives(
        subject='Confirm your email for StudyFlow',
        body=render_to_string('accounts/verify_email.txt', context),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    msg.attach_alternative(render_to_string('accounts/verify_email_email.html', context), 'text/html')
    try:
        msg.send()
    except Exception:
        logger.exception('Verification email could not be sent to user %s', user.pk)
        return False
    return True
