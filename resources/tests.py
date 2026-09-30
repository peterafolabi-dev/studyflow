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


from resources.models import CBTQuestion, QuestionBank, TestAttempt


class CBTModeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='cbt_student', password='password123')
        self.client.login(username='cbt_student', password='password123')

        self.course = Course.objects.create(user=self.user, name="Physics I", code="PHY101")
        self.bank = QuestionBank.objects.create(
            course=self.course,
            course_code="PHY101",
            created_by=self.user,
            title="PHY101 2023 Mock Exam",
            time_limit_minutes=10,
        )

        self.q1 = CBTQuestion.objects.create(
            bank=self.bank,
            text="What is the SI unit of force?",
            option_a="Joule",
            option_b="Newton",
            option_c="Watt",
            option_d="Pascal",
            correct_option="B",
            explanation="The SI unit of force is the Newton (N = kg*m/s^2).",
            order=0,
        )

        self.q2 = CBTQuestion.objects.create(
            bank=self.bank,
            text="Acceleration due to gravity on Earth is approximately:",
            option_a="9.8 m/s^2",
            option_b="8.9 m/s^2",
            option_c="10.8 m/s^2",
            option_d="12.0 m/s^2",
            correct_option="A",
            explanation="Standard acceleration due to gravity is 9.80665 m/s^2.",
            order=1,
        )

    def test_cbt_models_and_properties(self):
        self.assertEqual(self.bank.question_count, 2)
        self.assertEqual(self.q1.get_option_text('B'), "Newton")

        # Test attempt
        attempt = TestAttempt.objects.create(
            user=self.user,
            bank=self.bank,
            score=2,
            total_questions=2,
            time_taken_seconds=125,
            answers={str(self.q1.id): "B", str(self.q2.id): "A"},
            is_completed=True,
        )
        self.assertEqual(attempt.percentage, 100)
        self.assertEqual(attempt.formatted_time, "2m 5s")
        self.assertTrue(attempt.passed)

        detailed = attempt.get_detailed_results()
        self.assertEqual(len(detailed), 2)
        self.assertTrue(detailed[0]['is_correct'])

    def test_cbt_home_and_take_views(self):
        home_res = self.client.get(reverse('cbt_home'))
        self.assertEqual(home_res.status_code, 200)
        self.assertContains(home_res, "PHY101 2023 Mock Exam")

        take_res = self.client.get(reverse('cbt_take', args=[self.bank.pk]))
        self.assertEqual(take_res.status_code, 200)
        self.assertContains(take_res, "Question Navigator")
        self.assertContains(take_res, "timer-display")

    def test_cbt_submit_and_results(self):
        submit_url = reverse('cbt_submit', args=[self.bank.pk])
        payload = {
            "answers": {
                str(self.q1.id): "B", # Correct
                str(self.q2.id): "D", # Incorrect
            },
            "time_taken_seconds": 95,
        }
        res = self.client.post(submit_url, data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['score'], 1)
        self.assertEqual(data['total'], 2)
        self.assertEqual(data['percentage'], 50)

        # Check Results page
        attempt_id = data['attempt_id']
        result_res = self.client.get(reverse('cbt_result', args=[attempt_id]))
        self.assertEqual(result_res.status_code, 200)
        self.assertContains(result_res, "Detailed Answer Breakdown")
        self.assertContains(result_res, "Explain this answer")

    @patch('resources.cbt_views.explain_cbt_answer_with_ai')
    def test_cbt_explain_answer_ai(self, mock_explain):
        mock_explain.return_value = "Option B is correct because Force = mass * acceleration."
        url = reverse('cbt_explain_answer')
        res = self.client.post(
            url,
            data={"question_id": self.q1.id, "user_choice": "A"},
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertIn("Force = mass * acceleration", data['ai_explanation'])

    @patch('resources.cbt_views.generate_cbt_bank_from_pdf')
    def test_resource_generate_cbt_from_pdf(self, mock_gen_cbt):
        mock_gen_cbt.return_value = {
            "title": "PHY101 Generated Test",
            "time_limit_minutes": 15,
            "questions": [
                {
                    "question": "What is momentum?",
                    "option_a": "Mass * velocity",
                    "option_b": "Force * time",
                    "option_c": "Energy / time",
                    "option_d": "None of the above",
                    "correct_option": "A",
                    "explanation": "p = m * v"
                }
            ]
        }

        # Create a mock PDF resource
        from reportlab.pdfgen import canvas
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer)
        c.drawString(100, 700, "Physics past questions exam paper on momentum and kinematics for engineering students.")
        c.showPage()
        c.save()
        buffer.seek(0)

        pdf_file = SimpleUploadedFile("phy101_past_question.pdf", buffer.getvalue(), content_type="application/pdf")
        resource = Resource.objects.create(
            title="PHY101 Past Questions 2022",
            course_code="PHY101",
            resource_type="past_question",
            file=pdf_file,
            uploaded_by=self.user,
        )

        url = reverse('resource_ai_generate_cbt', args=[resource.pk])
        res = self.client.post(url)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['question_count'], 1)
        self.assertIn("take", data['redirect_url'])

        # Verify QuestionBank and Question created in DB
        bank = QuestionBank.objects.get(pk=data['bank_id'])
        self.assertEqual(bank.questions.count(), 1)
        self.assertEqual(bank.questions.first().correct_option, "A")
