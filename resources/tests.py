import io
from unittest.mock import MagicMock, patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, TransactionTestCase
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


class AccessAndRedirectTests(TestCase):
    def setUp(self):
        from resources.models import CBTQuestion, QuestionBank
        User = get_user_model()
        self.owner = User.objects.create_user('owner', password='S7rong-pass-99')
        self.other = User.objects.create_user('other', password='S7rong-pass-99')
        self.private_bank = QuestionBank.objects.create(title='Private', created_by=self.owner, is_public=False)
        self.question = CBTQuestion.objects.create(
            bank=self.private_bank, text='2+2?', option_a='3', option_b='4', option_c='5', option_d='6',
            correct_option='B',
        )
        self.client.login(username='other', password='S7rong-pass-99')

    def test_private_bank_is_hidden_from_other_users(self):
        for name in ('cbt_detail', 'cbt_take'):
            self.assertEqual(self.client.get(reverse(name, args=[self.private_bank.pk])).status_code, 404, name)
        response = self.client.post(reverse('cbt_submit', args=[self.private_bank.pk]), {'answers': '{}'})
        self.assertEqual(response.status_code, 404)
        response = self.client.post(
            reverse('cbt_explain_answer'), {'question_id': self.question.pk, 'user_choice': 'A'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)

    def test_owner_can_open_private_bank(self):
        self.client.login(username='owner', password='S7rong-pass-99')
        self.assertEqual(self.client.get(reverse('cbt_detail', args=[self.private_bank.pk])).status_code, 200)

    def test_cbt_take_embeds_questions_without_script_breakout(self):
        from resources.models import CBTQuestion
        self.private_bank.is_public = True
        self.private_bank.save()
        CBTQuestion.objects.create(
            bank=self.private_bank, text='</script><script>alert(1)</script>',
            option_a='a', option_b='b', option_c='c', option_d='d', correct_option='A',
        )
        response = self.client.get(reverse('cbt_take', args=[self.private_bank.pk]))
        self.assertNotContains(response, '</script><script>alert(1)')
        self.assertContains(response, 'id="cbt-questions"')

    def test_rating_ignores_external_next(self):
        resource = Resource.objects.create(title='Notes', course_code='MTH101', resource_type='notes')
        response = self.client.post(
            reverse('rate_resource', args=[resource.pk]), {'stars': 5, 'next': 'https://evil.example/'}
        )
        self.assertRedirects(response, reverse('notes_list'), fetch_redirect_response=False)


class WhatsAppShareTests(TestCase):
    def test_resource_page_has_encoded_whatsapp_share_with_invite(self):
        from django.contrib.auth import get_user_model
        from .models import Resource
        user = get_user_model().objects.create_user('ada', 'a@example.com', 'S7rong-pass-99')
        resource = Resource.objects.create(title='CSC 201 & Notes', resource_type='notes', uploaded_by=user)
        self.client.force_login(user)
        html = self.client.get(reverse('resource_detail', args=[resource.pk])).content.decode()
        self.assertIn('https://wa.me/?text=', html)
        self.assertIn('CSC%20201%20%26%20Notes', html)
        self.assertIn('signup/%3Fref%3D', html)

class ResourceReportTests(TestCase):
    """Students can flag a shared resource; a moderator reviews it by hand in the admin."""

    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user('owner', password='S7rong-pass-99')
        self.student = User.objects.create_user('reader', password='S7rong-pass-99')
        self.resource = Resource.objects.create(
            title='MTH101 Past Questions', resource_type='past_question', uploaded_by=self.owner,
        )
        self.url = reverse('report_resource', args=[self.resource.pk])

    def _report(self, **data):
        data.setdefault('reason', 'copyright')
        return self.client.post(self.url, data, follow=True)

    def test_must_be_signed_in(self):
        response = self.client.post(self.url, {'reason': 'spam'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])
        from resources.models import ResourceReport
        self.assertEqual(ResourceReport.objects.count(), 0)

    def test_get_is_not_allowed(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_report_is_saved_and_confirmed(self):
        from resources.models import ResourceReport
        self.client.force_login(self.student)
        response = self._report(reason='copyright', detail='This is a textbook scan.')
        self.assertContains(response, 'Your report was sent')
        report = ResourceReport.objects.get()
        self.assertEqual((report.reporter, report.resource, report.reason), (self.student, self.resource, 'copyright'))
        self.assertEqual(report.detail, 'This is a textbook scan.')
        self.assertFalse(report.reviewed)

    def test_reporting_twice_keeps_one_report(self):
        from resources.models import ResourceReport
        self.client.force_login(self.student)
        self._report()
        response = self._report(reason='spam')
        self.assertContains(response, 'You already reported this resource')
        self.assertEqual(ResourceReport.objects.count(), 1)
        self.assertEqual(ResourceReport.objects.get().reason, 'copyright')

    def test_cannot_report_your_own_upload(self):
        from resources.models import ResourceReport
        self.client.force_login(self.owner)
        response = self._report()
        self.assertContains(response, 'your own upload')
        self.assertEqual(ResourceReport.objects.count(), 0)

    def test_unknown_reason_becomes_other_and_detail_is_capped(self):
        from resources.models import ResourceReport
        self.client.force_login(self.student)
        self._report(reason='<script>', detail='x' * 1000)
        report = ResourceReport.objects.get()
        self.assertEqual(report.reason, 'other')
        self.assertEqual(len(report.detail), 300)

    def test_reports_are_rate_limited(self):
        from resources.models import ResourceReport
        self.client.force_login(self.student)
        for i in range(10):
            res = Resource.objects.create(title=f'R{i}', resource_type='notes', uploaded_by=self.owner)
            self.client.post(reverse('report_resource', args=[res.pk]), {'reason': 'spam'})
        extra = Resource.objects.create(title='one too many', resource_type='notes', uploaded_by=self.owner)
        response = self.client.post(reverse('report_resource', args=[extra.pk]), {'reason': 'spam'}, follow=True)
        self.assertContains(response, 'sent a lot of reports')
        self.assertEqual(ResourceReport.objects.count(), 10)

    def test_resource_is_never_hidden_by_reports(self):
        # reports are for a moderator to review; a few reports must not hide a resource
        self.client.force_login(self.student)
        self._report()
        other = User.objects.create_user('third', password='S7rong-pass-99')
        self.client.force_login(other)
        self._report(reason='spam')
        self.assertEqual(self.client.get(reverse('resource_detail', args=[self.resource.pk])).status_code, 200)

    def test_report_button_shows_for_others_but_not_for_the_owner(self):
        self.client.force_login(self.student)
        self.assertContains(self.client.get(reverse('resource_detail', args=[self.resource.pk])), self.url)
        self.client.force_login(self.owner)
        self.assertNotContains(self.client.get(reverse('resource_detail', args=[self.resource.pk])), self.url)

    def test_admin_can_mark_reports_reviewed(self):
        from resources.models import ResourceReport
        self.client.force_login(self.student)
        self._report()
        admin = User.objects.create_superuser('boss', 'boss@example.com', 'S7rong-pass-99')
        self.client.force_login(admin)
        response = self.client.post(reverse('admin:resources_resourcereport_changelist'), {
            'action': 'mark_reviewed', '_selected_action': [ResourceReport.objects.get().pk],
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ResourceReport.objects.get().reviewed)


class LegalPagesTests(TestCase):
    """The Privacy Policy and Terms are public, accurate pages, and the footer links to them."""

    def test_pages_are_public(self):
        for name in ('privacy', 'terms'):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Last updated')

    def test_privacy_names_the_real_services_and_the_data(self):
        text = self.client.get(reverse('privacy')).content.decode()
        for word in ('Groq', 'Brevo', 'Render', 'Google', 'session cookie', 'only to you and to the site administrator'):
            self.assertIn(word, text)

    def test_terms_warn_that_free_hosting_can_lose_uploads(self):
        text = self.client.get(reverse('terms')).content.decode()
        self.assertIn('can be lost when the server restarts', text)
        self.assertIn('not run, approved or endorsed by any university', text)

    def test_footer_links_point_at_the_pages(self):
        page = self.client.get(reverse('login'))
        self.assertContains(page, f'href="{reverse("privacy")}"')
        self.assertContains(page, f'href="{reverse("terms")}"')

    def test_signup_page_links_to_both(self):
        page = self.client.get(reverse('signup'))
        self.assertContains(page, 'By signing up you agree to the')
        self.assertContains(page, reverse('terms'))
        self.assertContains(page, reverse('privacy'))

    def test_license_file_exists_and_is_mit(self):
        from pathlib import Path
        from django.conf import settings
        text = (Path(settings.BASE_DIR) / 'LICENSE').read_text()
        self.assertTrue(text.startswith('MIT License'))
        self.assertIn('Afolabi Peter', text)


class AIHardeningTests(TestCase):
    """Limits, outages and bad model output must give students a readable result, not a raw API error."""

    def _client(self, *behaviours):
        calls = []
        def create(**kw):
            calls.append(kw)
            b = behaviours[min(len(calls) - 1, len(behaviours) - 1)]
            if isinstance(b, Exception):
                raise b
            return MagicMock(choices=[MagicMock(message=MagicMock(content=b))])
        client = MagicMock()
        client.chat.completions.create.side_effect = create
        return client, calls

    def _limit_error(self):
        err = Exception('Error code: 413 - Request too large')
        err.status_code = 413
        return err

    def test_falls_back_to_next_model_when_first_is_over_limit(self):
        from resources import ai_service
        client, calls = self._client(self._limit_error(), '{"summary": "ok", "key_points": ["a"]}')
        with patch.object(ai_service, 'get_groq_client', return_value=client):
            out = ai_service.summarize_material('text', title='T')
        self.assertEqual(out['summary'], 'ok')
        self.assertNotEqual(calls[0]['model'], calls[1]['model'])
        self.assertTrue(all(c['max_tokens'] <= ai_service.AI_MAX_OUTPUT_TOKENS for c in calls))

    def test_all_models_limited_gives_friendly_message(self):
        from resources import ai_service
        client, _ = self._client(self._limit_error())
        with patch.object(ai_service, 'get_groq_client', return_value=client):
            with self.assertRaises(ai_service.AIProcessingError) as ctx:
                ai_service.summarize_material('text')
        self.assertNotIn('413', str(ctx.exception))
        self.assertIn('busy', str(ctx.exception))

    def test_long_documents_are_clipped_before_sending(self):
        from resources import ai_service
        client, calls = self._client('{"summary": "s", "key_points": []}')
        with patch.object(ai_service, 'get_groq_client', return_value=client):
            ai_service.summarize_material('x' * 50000)
        sent = calls[0]['messages'][-1]['content']
        self.assertLess(len(sent), ai_service.AI_MAX_INPUT_CHARS + 500)

    def test_broken_json_is_repaired_once(self):
        from resources import ai_service
        client, calls = self._client('not json at all', '{"summary": "fixed", "key_points": []}')
        with patch.object(ai_service, 'get_groq_client', return_value=client):
            self.assertEqual(ai_service.summarize_material('t')['summary'], 'fixed')
        self.assertEqual(len(calls), 2)

    def test_quiz_skips_questions_without_a_valid_answer_key(self):
        from resources import ai_service
        payload = ('{"questions": [{"question": "Q1", "options": ["a","b","c","d"], "correct_index": 9, "explanation": "e"},'
                   '{"question": "Q2", "options": ["a","b","c","d"], "correct_index": 2, "explanation": "e"}]}')
        client, _ = self._client(payload)
        with patch.object(ai_service, 'get_groq_client', return_value=client):
            qs = ai_service.generate_quiz_from_material('t')
        self.assertEqual([q['question'] for q in qs], ['Q2'])
        self.assertEqual(qs[0]['correct_index'], 2)

    def test_explain_answer_falls_back_to_base_text_on_failure(self):
        from resources import ai_service
        client, _ = self._client(Exception('boom'))
        with patch.object(ai_service, 'get_groq_client', return_value=client):
            out = ai_service.explain_cbt_answer_with_ai('Q', 'a', 'b', 'c', 'd', 'A', 'B', base_explanation='Because B.')
        self.assertEqual(out, 'Because B.')


class UploadStorageFailureTests(TransactionTestCase):  # real transactions: a failed save inside TestCase's atomic poisons it
    def test_storage_error_shows_friendly_message_not_500(self):
        from unittest import mock
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.create_user('up', password='S7rong-pass-99')
        self.client.login(username='up', password='S7rong-pass-99')
        pdf = SimpleUploadedFile('n.pdf', b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF', content_type='application/pdf')
        with mock.patch('django.core.files.storage.FileSystemStorage.save', side_effect=OSError('boom')):
            r = self.client.post(reverse('resource_upload'), {'title': 'T', 'course_code': 'BIO 101', 'resource_type': 'notes', 'description': 'd', 'file': pdf})
        self.assertEqual(r.status_code, 503)
        self.assertContains(r, 'file storage problem', status_code=503)
        self.assertFalse(Resource.objects.exists())
