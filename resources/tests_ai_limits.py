"""Groq's free tier allows 8,000 tokens a minute. These tests keep every request well under that."""
import io
import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from resources import ai_service
from resources.ai_service import AIBusyError, AIProcessingError, summarize_material
from resources.models import Resource
from resources.pdf_service import AI_INPUT_CHARS, extract_and_chunk_pdf

User = get_user_model()

SECRET = "org_01kq55j0rnfefrwk0tpjbatkwf https://console.groq.com/settings/billing"


def make_pdf(pages, words_per_page=400):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    for n in range(1, pages + 1):
        text = c.beginText(40, 800)
        text.setFont("Helvetica", 9)
        line = []
        for w in range(words_per_page):
            line.append(f"word{n}x{w}")
            if len(line) == 14:
                text.textLine(" ".join(line))
                line = []
        c.drawText(text)
        c.showPage()
    c.save()
    buffer.seek(0)
    return buffer


class FakeError(Exception):
    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


def groq_reply(payload):
    reply = MagicMock()
    reply.choices = [MagicMock(message=MagicMock(content=json.dumps(payload)))]
    return reply


class PdfBudgetTests(TestCase):
    def test_long_pdf_stays_inside_budget_and_covers_whole_document(self):
        text = extract_and_chunk_pdf(make_pdf(60))
        self.assertLessEqual(len(text), AI_INPUT_CHARS + 300)  # budget + the short note
        self.assertIn("[Page 1]", text)
        self.assertRegex(text, r"\[Page (5\d|4\d)\]")  # pages from the end, not only the start
        self.assertIn("60 pages", text)

    def test_short_pdf_is_untouched(self):
        text = extract_and_chunk_pdf(make_pdf(1, words_per_page=60))
        self.assertNotIn("[Note:", text)

    def test_default_budget_is_about_2700_tokens(self):
        self.assertLessEqual(AI_INPUT_CHARS, 8000)


class GroqCallTests(TestCase):
    def setUp(self):
        cache.clear()

    def _run(self, side_effect):
        client = MagicMock()
        client.chat.completions.create.side_effect = side_effect
        with patch.object(ai_service, 'get_groq_client', return_value=client), \
             patch.object(ai_service.time, 'sleep') as sleep:
            try:
                result = summarize_material("some text", "T")
            except Exception as err:  # noqa: BLE001
                result = err
        return result, client, sleep

    def test_reply_length_is_capped_so_requests_stay_under_the_limit(self):
        result, client, _ = self._run([groq_reply({"summary": "s", "key_points": ["a"]})])
        kwargs = client.chat.completions.create.call_args.kwargs
        self.assertLessEqual(kwargs['max_tokens'], 3500)
        self.assertGreaterEqual(kwargs['max_tokens'], 1000)
        self.assertEqual(result['summary'], 's')

    def test_short_rate_limit_waits_once_then_succeeds(self):
        err = FakeError("Error code: 413 ... Please try again in 3.5s.", 413)
        result, client, sleep = self._run([err, groq_reply({"summary": "ok", "key_points": []})])
        self.assertEqual(result['summary'], 'ok')
        self.assertEqual(client.chat.completions.create.call_count, 2)
        sleep.assert_called_once()

    def test_long_wait_gives_friendly_busy_message_without_secrets(self):
        err = FakeError(f"Error code: 413 {SECRET} rate_limit_exceeded Please try again in 55s", 413)
        result, client, sleep = self._run([err])
        self.assertIsInstance(result, AIBusyError)
        self.assertEqual(client.chat.completions.create.call_count, 1)
        sleep.assert_not_called()
        for leak in ("org_", "billing", "Groq", "413"):
            self.assertNotIn(leak, str(result))

    def test_rate_limit_without_hint_does_not_sleep(self):
        err = FakeError("rate_limit_exceeded", 429)
        result, _, sleep = self._run([err])
        self.assertIsInstance(result, AIBusyError)
        sleep.assert_not_called()

    def test_still_limited_after_waiting_is_busy_not_crash(self):
        err = FakeError("Please try again in 2s", 413)
        result, client, _ = self._run([err, FakeError("Please try again in 2s", 413)])
        self.assertIsInstance(result, AIBusyError)
        self.assertEqual(client.chat.completions.create.call_count, 2)

    def test_other_errors_never_leak_provider_details(self):
        result, _, _ = self._run([RuntimeError(f"boom {SECRET}")])
        self.assertIsInstance(result, AIProcessingError)
        self.assertNotIsInstance(result, AIBusyError)
        self.assertNotIn("org_", str(result))
        self.assertNotIn("boom", str(result))


class SummarizeViewLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('ada', 'a@example.com', 'S7rong-pass-99')
        self.client.force_login(self.user)
        pdf = SimpleUploadedFile("big.pdf", make_pdf(40).getvalue(), content_type="application/pdf")
        self.resource = Resource.objects.create(title="Big", course_code="EEE101", resource_type="notes",
                                                file=pdf, uploaded_by=self.user)

    def test_big_pdf_sends_a_small_request_and_busy_returns_503(self):
        sent = {}

        def fake(text, title=""):
            sent['chars'] = len(text)
            raise AIBusyError(ai_service.BUSY_MESSAGE)

        with patch('resources.views.summarize_material', side_effect=fake):
            r = self.client.post(reverse('resource_ai_summarize', args=[self.resource.pk]))
        self.assertLessEqual(sent['chars'], AI_INPUT_CHARS + 300)
        self.assertEqual(r.status_code, 503)
        self.assertIn('busy', r.json()['error'])
        self.assertNotIn('org_', r.json()['error'])
