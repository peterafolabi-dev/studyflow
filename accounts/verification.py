"""Email verification for students who sign up with email and password.

Flow: sign up → we email a 6-digit code (and a one-tap link as a backup) → entering the
code, or opening the link, marks the email verified, logs the student in and sends the
welcome email. Until then, logging in shows a "verify your email" page with a resend button.

Codes are kept only as a keyed hash in the cache, expire after 10 minutes, work once, and
stop working after 5 wrong tries. Asking for a new code replaces the old one.
"""
import hashlib
import hmac
import logging
import secrets
import time

from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .emails import _site_url

logger = logging.getLogger(__name__)

CODE_TTL_SECONDS = 600
CODE_MAX_ATTEMPTS = 5


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


def _code_key(user):
    return f'verify_code_{user.pk}'


def _code_digest(user, code):
    message = f'{user.pk}:{(user.email or "").lower()}:{code}'.encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def clean_code(raw):
    """Keeps only the digits a student typed; returns '' unless that makes exactly 6."""
    digits = ''.join(ch for ch in str(raw or '') if ch in '0123456789')
    return digits if len(digits) == 6 else ''


def issue_code(user):
    """Makes a new 6-digit code for this student and forgets any earlier one."""
    code = f'{secrets.randbelow(1_000_000):06d}'
    cache.set(
        _code_key(user),
        {'digest': _code_digest(user, code), 'tries': 0, 'expires': time.time() + CODE_TTL_SECONDS},
        CODE_TTL_SECONDS,
    )
    return code


def check_code(user, raw):
    """True only for the current, unexpired code with tries left. A correct code is used up."""
    key = _code_key(user)
    entry = cache.get(key)
    if not entry or entry['expires'] <= time.time():
        cache.delete(key)
        return False
    code = clean_code(raw)
    if not code:
        return False
    entry['tries'] += 1
    if hmac.compare_digest(entry['digest'], _code_digest(user, code)):
        cache.delete(key)
        return True
    if entry['tries'] >= CODE_MAX_ATTEMPTS:
        cache.delete(key)
    else:
        cache.set(key, entry, max(1, int(entry['expires'] - time.time())))
    return False


def send_verification_email(user, request=None):
    """Returns True if the email was handed to the mail provider."""
    if not user.email:
        return False
    site = _site_url(request)
    code = issue_code(user)
    context = {
        'user': user,
        'name': (user.first_name or user.get_username()).strip(),
        'code': code,
        'code_minutes': CODE_TTL_SECONDS // 60,
        'link': verification_link(user, request),
        'site': site,
        'domain': site.split('://', 1)[-1],
        'expiry_days': max(1, settings.PASSWORD_RESET_TIMEOUT // 86400),
    }
    msg = EmailMultiAlternatives(
        subject=f'{code} is your StudyFlow confirmation code',
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
