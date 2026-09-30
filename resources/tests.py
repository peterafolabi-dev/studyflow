import io
from unittest.mock import MagicMock, patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from planner.models import Course, Flashcard, FlashcardDeck
from resources.models import Resource
from resources.pdf_service import (
    PDFExtractionError,
    ScannedOrEmptyPDFError,
    extract_and_chunk_pdf,
)
from resources.ai_service import (
    RateLimitExceeded,
    check_and_increment_rate_limit,
    parse_strict_json,
)

User = get_user_model()


class PDFServiceTests(TestCase):
    def test_scanned_or_empty_pdf_raises_error(self):
        # Generate a minimal valid PDF without any text
        from reportlab.pdfgen import canvas
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer)
        c.drawString(10, 10, "") # empty
        c.showPage()
        c.save()
        buffer.seek(0)

        with self.assertRaises(ScannedOrEmptyPDFError):
            extract_and_chunk_pdf(buffer)

    def test_valid_pdf_extracts_text(self):
        from reportlab.pdfgen import canvas
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer)
        c.drawString(100, 700, "Thermodynamics is the study of heat, work, and energy transformations in physical systems.")
        c.showPage()
        c.save()
        buffer.seek(0)

        extracted = extract_and_chunk_pdf(buffer)
        self.assertIn("Thermodynamics", extracted)
        self.assertIn("[Page 1]", extracted)


class AIServiceUnitTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_parse_strict_json_with_fences(self):
        raw = """```json
        {
            "flashcards": [
                {"front": "What is Newton's First Law?", "back": "Law of inertia"}
            ]
        }
        ```"""
        parsed = parse_strict_json(raw)
        self.assertEqual(len(parsed["flashcards"]), 1)
        self.assertEqual(parsed["flashcards"][0]["front"], "What is Newton's First Law?")

    def test_parse_strict_json_with_surrounding_text(self):
        raw = """Here is your output:
        {"summary": "Study of dynamics.", "key_points": ["Point 1", "Point 2"]}
        Hope this helps!"""
        parsed = parse_strict_json(raw)
        self.assertEqual(parsed["summary"], "Study of dynamics.")
        self.assertEqual(len(parsed["key_points"]), 2)

    def test_rate_limiting_enforcement(self):
        user_id = 999
        # Max 3 requests in test window
        check_and_increment_rate_limit(user_id, bucket='test_bucket', max_requests=2, window=60)
        check_and_increment_rate_limit(user_id, bucket='test_bucket', max_requests=2, window=60)
        
        # Third should exceed
        with self.assertRaises(RateLimitExceeded):
            check_and_increment_rate_limit(user_id, bucket='test_bucket', max_requests=2, window=60)


class ResourceAIViewsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='student1', password='password123')
        self.client.login(username='student1', password='password123')

        # Create a mock PDF file
        from reportlab.pdfgen import canvas
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer)
        c.drawString(100, 700, "Calculus differentiation formulas and practice questions for university engineering students.")
        c.showPage()
        c.save()
        buffer.seek(0)

        pdf_file = SimpleUploadedFile("calculus_notes.pdf", buffer.getvalue(), content_type="application/pdf")
        self.resource = Resource.objects.create(
            title="Calculus Notes",
            course_code="MTH101",
            resource_type="notes",
            file=pdf_file,
            uploaded_by=self.user,
        )

    @patch('resources.views.summarize_material')
    def test_summarize_endpoint(self, mock_summarize):
        mock_summarize.return_value = {
            "summary": "This document covers core calculus differentiation techniques.",
            "key_points": ["Power rule", "Chain rule", "Product rule"]
        }
        url = reverse('resource_ai_summarize', args=[self.resource.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn("differentiation", data['data']['summary'])
        self.assertEqual(len(data['data']['key_points']), 3)

    @patch('resources.views.generate_flashcards_from_material')
    def test_flashcards_endpoint_and_save(self, mock_gen_cards):
        mock_gen_cards.return_value = [
            {"front": "Derivative of sin(x)?", "back": "cos(x)"},
            {"front": "Derivative of e^x?", "back": "e^x"}
        ]
        url = reverse('resource_ai_flashcards', args=[self.resource.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['flashcards']), 2)

        # Test saving into a new deck
        save_url = reverse('resource_ai_save_flashcards', args=[self.resource.pk])
        save_payload = {
            "new_deck_title": "MTH101 Exam Prep",
            "cards": data['flashcards']
        }
        save_response = self.client.post(save_url, data=save_payload, content_type='application/json')
        self.assertEqual(save_response.status_code, 200)
        save_data = save_response.json()
        self.assertTrue(save_data['success'])
        self.assertEqual(save_data['cards_count'], 2)

        # Verify flashcard deck and cards exist in database
        deck = FlashcardDeck.objects.get(title="MTH101 Exam Prep")
        self.assertEqual(deck.course.user, self.user)
        self.assertEqual(deck.cards.count(), 2)

    @patch('resources.views.generate_quiz_from_material')
    def test_quiz_endpoint(self, mock_gen_quiz):
        mock_gen_quiz.return_value = [
            {
                "question": "What is the derivative of x^2?",
                "options": ["A) x", "B) 2x", "C) 2", "D) x^3"],
                "correct_index": 1,
                "explanation": "Using the power rule: d/dx(x^n) = n*x^(n-1), so d/dx(x^2) = 2x."
            }
        ]
        url = reverse('resource_ai_quiz', args=[self.resource.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['questions']), 1)
        self.assertEqual(data['questions'][0]['correct_index'], 1)
