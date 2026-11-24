from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import ChatMessage, Thread, ThreadVote

User = get_user_model()


class ChatApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('sam', password='S7rong-pass-99')
        self.client.login(username='sam', password='S7rong-pass-99')

    def post(self, payload):
        return self.client.post(reverse('chat_api'), data=payload, content_type='application/json')

    def test_message_is_saved_and_returned(self):
        self.assertEqual(self.post({'text': 'hello', 'room': 'global'}).status_code, 200)
        data = self.client.get(reverse('chat_api') + '?room=global').json()
        self.assertEqual([m['text'] for m in data['messages']], ['hello'])
        self.assertTrue(data['messages'][0]['is_me'])

    def test_unknown_rooms_and_bad_json_are_rejected(self):
        self.assertEqual(self.post({'text': 'hi', 'room': 'secret-room'}).status_code, 400)
        response = self.client.post(reverse('chat_api'), data='not json', content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ChatMessage.objects.exists())

    def test_long_messages_are_truncated(self):
        self.post({'text': 'x' * 5000, 'room': 'global'})
        self.assertEqual(len(ChatMessage.objects.get().text), 1000)

    def test_multiline_paste_keeps_line_breaks(self):
        msg = 'Welcome to FUT Minna!\n\nShare notes, ask questions.\n' + 'a' * 400
        self.post({'text': msg, 'room': 'global'})
        self.assertEqual(ChatMessage.objects.get().text, msg)


class VoteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('sam', password='S7rong-pass-99')
        self.thread = Thread.objects.create(title='Help', created_by=self.user)
        self.client.login(username='sam', password='S7rong-pass-99')

    def test_vote_value_is_clamped_and_bad_input_does_not_crash(self):
        url = reverse('vote_thread', args=[self.thread.pk])
        for value in ('1000', 'abc'):
            self.assertEqual(self.client.post(url, {'value': value}).status_code, 302, value)
            self.assertEqual(ThreadVote.objects.get(user=self.user, thread=self.thread).value, 1)
        self.client.post(url, {'value': '-1'})
        self.assertEqual(ThreadVote.objects.get(user=self.user, thread=self.thread).value, -1)


class AnalyticsLiveRefreshTests(TestCase):
    """The analytics page refreshes itself, so the wrapper it swaps must exist and stay staff-only."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.staff = User.objects.create_user('boss', 'boss@example.com', 'pw-12345-x', is_staff=True)
        self.student = User.objects.create_user('stu', 'stu@example.com', 'pw-12345-x')

    def test_staff_page_has_the_live_wrapper_and_script(self):
        self.client.force_login(self.staff)
        html = self.client.get(reverse('admin_dashboard')).content.decode()
        self.assertIn('id="live-dashboard"', html)
        self.assertIn('id="live-badge"', html)
        self.assertEqual(html.count('id="live-dashboard"'), 1)

    def test_students_still_cannot_see_the_dashboard(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse('admin_dashboard')).status_code, 403)
