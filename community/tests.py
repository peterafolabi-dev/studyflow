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


class ChatUpgradeTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.sam = User.objects.create_user('sam2', password='S7rong-pass-99')
        self.amy = User.objects.create_user('amy', password='S7rong-pass-99')
        self.boss = User.objects.create_user('boss', password='S7rong-pass-99', is_staff=True)
        self.client.login(username='sam2', password='S7rong-pass-99')

    def send(self, text='hello', **extra):
        return self.client.post(reverse('chat_api'), data={'text': text, 'room': 'global', **extra}, content_type='application/json')

    def act(self, name, pk, body=None):
        return self.client.post(reverse(name, args=[pk]), data=body or {}, content_type='application/json')

    def feed(self):
        return self.client.get(reverse('chat_api') + '?room=global').json()

    def test_reply_is_linked_and_must_be_same_room(self):
        first = self.send('question?').json()['id']
        self.send('answer', reply_to=first)
        msgs = self.feed()['messages']
        self.assertEqual(msgs[1]['reply']['text'], 'question?')
        other_room = ChatMessage.objects.create(user=self.amy, text='elsewhere', room='campus')
        self.send('cross', reply_to=other_room.pk)
        self.assertIsNone(self.feed()['messages'][-1]['reply'])

    def test_edit_own_message_marks_it_edited_with_no_time_limit(self):
        from datetime import timedelta
        from django.utils import timezone
        mid = self.send('typo').json()['id']
        self.assertEqual(self.act('chat_edit', mid, {'text': 'fixed'}).status_code, 200)
        m = self.feed()['messages'][0]
        self.assertEqual((m['text'], m['edited']), ('fixed', True))
        ChatMessage.objects.filter(pk=mid).update(created_at=timezone.now() - timedelta(days=30))
        self.assertEqual(self.act('chat_edit', mid, {'text': 'a month later'}).status_code, 200)
        self.assertTrue(self.feed()['messages'][0]['can_edit'])
        self.assertEqual(self.feed()['messages'][0]['text'], 'a month later')

    def test_cannot_edit_or_delete_someone_elses_message(self):
        theirs = ChatMessage.objects.create(user=self.amy, text='mine', room='global')
        self.assertEqual(self.act('chat_edit', theirs.pk, {'text': 'hacked'}).status_code, 403)
        self.assertEqual(self.act('chat_delete', theirs.pk).status_code, 403)
        theirs.refresh_from_db()
        self.assertEqual((theirs.text, theirs.is_deleted), ('mine', False))

    def test_delete_blanks_text_and_staff_can_moderate(self):
        mid = self.send('oops').json()['id']
        self.act('chat_delete', mid)
        m = self.feed()['messages'][0]
        self.assertTrue(m['deleted'])
        self.assertEqual(m['text'], '')
        theirs = ChatMessage.objects.create(user=self.amy, text='rude', room='global')
        self.client.login(username='boss', password='S7rong-pass-99')
        self.assertEqual(self.act('chat_delete', theirs.pk).status_code, 200)

    def test_reactions_toggle_count_and_reject_unknown_emoji(self):
        mid = self.send('nice').json()['id']
        self.assertTrue(self.act('chat_react', mid, {'emoji': '🔥'}).json()['added'])
        self.client.login(username='amy', password='S7rong-pass-99')
        self.act('chat_react', mid, {'emoji': '🔥'})
        r = self.feed()['messages'][0]['reactions']
        self.assertEqual((r[0]['emoji'], r[0]['count'], r[0]['mine']), ('🔥', 2, True))
        self.assertFalse(self.act('chat_react', mid, {'emoji': '🔥'}).json()['added'])   # toggles off
        self.assertEqual(self.act('chat_react', mid, {'emoji': '<script>'}).status_code, 400)

    def test_only_staff_can_pin_and_one_pin_per_room(self):
        a = ChatMessage.objects.create(user=self.boss, text='Welcome!', room='global')
        b = ChatMessage.objects.create(user=self.boss, text='Rules', room='global')
        self.assertEqual(self.act('chat_pin', a.pk).status_code, 403)
        self.client.login(username='boss', password='S7rong-pass-99')
        self.act('chat_pin', a.pk); self.act('chat_pin', b.pk)
        data = self.feed()
        self.assertEqual(data['pinned']['text'], 'Rules')
        self.assertTrue(data['can_moderate'])
        self.act('chat_pin', b.pk)
        self.assertIsNone(self.feed()['pinned'])

    def test_sending_too_fast_is_slowed_down(self):
        codes = [self.send(f'm{i}').status_code for i in range(15)]
        self.assertEqual(codes[:12], [200] * 12)
        self.assertEqual(codes[12:], [429] * 3)

    def test_page_renders_new_controls(self):
        r = self.client.get(reverse('global_chat'))
        self.assertContains(r, 'id="reply-bar"')
        self.assertContains(r, 'id="chat-pinned"')
