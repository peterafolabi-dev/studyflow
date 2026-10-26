"""Email over HTTPS for hosts that block SMTP ports (e.g. Render's free plan).

Enabled automatically when BREVO_API_KEY is set (see settings.py). The sender address in
DEFAULT_FROM_EMAIL must be verified in Brevo (Senders & IPs → Senders).
"""
import logging
from email.utils import parseaddr

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

BREVO_API_URL = 'https://api.brevo.com/v3/smtp/email'


class EmailSendError(OSError):
    """Raised when the email API rejects or can't receive a message (an OSError, like SMTP failures)."""


class BrevoEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages:
            try:
                self._send(message)
                sent += 1
            except (requests.RequestException, EmailSendError):
                logger.exception('Brevo email send failed: %s', message.subject)
                if not self.fail_silently:
                    raise
        return sent

    def _send(self, message):
        sender_name, sender_email = parseaddr(message.from_email or settings.DEFAULT_FROM_EMAIL)
        payload = {
            'sender': {'email': sender_email, 'name': sender_name or 'StudyFlow'},
            'to': [{'email': address} for address in message.recipients()],
            'subject': message.subject,
            'textContent': message.body,
        }
        for content, mimetype in getattr(message, 'alternatives', []) or []:
            if mimetype == 'text/html':
                payload['htmlContent'] = content
        response = requests.post(
            BREVO_API_URL,
            json=payload,
            headers={'api-key': settings.BREVO_API_KEY, 'accept': 'application/json'},
            timeout=settings.EMAIL_TIMEOUT,
        )
        if response.status_code >= 400:
            raise EmailSendError(f'Brevo rejected the email ({response.status_code}): {response.text[:300]}')
