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


class ChatTelegramFeatureTests(TestCase):
    """Files, polls, mentions, search, forward, saved, room rules."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.sam = User.objects.create_user('sam', password='S7rong-pass-99')
        self.ada = User.objects.create_user('ada', password='S7rong-pass-99')
        self.admin = User.objects.create_user('boss', password='S7rong-pass-99', is_staff=True)
        self.client.login(username='sam', password='S7rong-pass-99')

    def jpost(self, name, payload, *args):
        return self.client.post(reverse(name, args=args), data=payload, content_type='application/json')

    def say(self, text, room='global'):
        return self.jpost('chat_api', {'text': text, 'room': room})

    def test_mention_notifies_once_and_not_self(self):
        from accounts.models import Notification
        self.say('hey @ada and @sam check this')
        self.assertEqual(Notification.objects.filter(user=self.ada).count(), 1)
        self.assertFalse(Notification.objects.filter(user=self.sam).exists())
        mid = ChatMessage.objects.get().id
        self.jpost('chat_edit', {'text': 'hey @ada and @sam check this again'}, mid)
        self.assertEqual(Notification.objects.filter(user=self.ada).count(), 1)

    def test_upload_image_and_download(self):
        import io
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        buf = io.BytesIO()
        Image.new('RGB', (4, 4), 'red').save(buf, 'PNG')
        up = SimpleUploadedFile('pic.png', buf.getvalue(), content_type='image/png')
        r = self.client.post(reverse('chat_upload'), {'file': up, 'room': 'global', 'text': 'look'})
        self.assertEqual(r.status_code, 200)
        data = self.client.get(reverse('chat_api') + '?room=global').json()
        att = data['messages'][0]['attachment']
        self.assertEqual(att['kind'], 'image')
        resp = self.client.get(att['url'])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['X-Content-Type-Options'], 'nosniff')
        self.client.logout()
        self.assertEqual(self.client.get(att['url']).status_code, 302)  # login required

    def test_upload_rejects_bad_type_big_and_fake_image(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        bad = SimpleUploadedFile('run.exe', b'MZ', content_type='application/octet-stream')
        self.assertEqual(self.client.post(reverse('chat_upload'), {'file': bad, 'room': 'global'}).status_code, 400)
        fake = SimpleUploadedFile('x.png', b'not an image', content_type='image/png')
        self.assertEqual(self.client.post(reverse('chat_upload'), {'file': fake, 'room': 'global'}).status_code, 400)
        big = SimpleUploadedFile('big.pdf', b'0' * (5 * 1024 * 1024 + 1), content_type='application/pdf')
        self.assertEqual(self.client.post(reverse('chat_upload'), {'file': big, 'room': 'global'}).status_code, 400)
        self.assertFalse(ChatMessage.objects.exists())

    def test_poll_create_vote_switch_and_remove(self):
        r = self.jpost('chat_poll_create', {'room': 'global', 'question': 'Class holds?', 'options': ['Yes', 'No']})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.jpost('chat_poll_create', {'room': 'global', 'question': 'q', 'options': ['only one']}).status_code, 400)
        poll = self.client.get(reverse('chat_api') + '?room=global').json()['messages'][0]['poll']
        yes, no = poll['options'][0]['id'], poll['options'][1]['id']
        self.jpost('chat_poll_vote', {}, yes)
        self.jpost('chat_poll_vote', {}, no)            # switching moves the single vote
        poll = self.client.get(reverse('chat_api') + '?room=global').json()['messages'][0]['poll']
        self.assertEqual((poll['total'], poll['mine']), (1, no))
        self.jpost('chat_poll_vote', {}, no)            # tap again removes
        poll = self.client.get(reverse('chat_api') + '?room=global').json()['messages'][0]['poll']
        self.assertEqual(poll['total'], 0)
        mid = ChatMessage.objects.get().id
        self.assertEqual(self.jpost('chat_edit', {'text': 'x'}, mid).status_code, 403)  # polls are not editable

    def test_search_finds_messages_in_room_only(self):
        self.say('Mapping test on friday')
        self.say('Mapping in futminna', room='futminna')
        hits = self.client.get(reverse('chat_search') + '?room=global&q=mapping').json()['results']
        self.assertEqual(len(hits), 1)
        self.assertEqual(self.client.get(reverse('chat_search') + '?room=global&q=m').json()['results'], [])

    def test_forward_labels_original_author(self):
        self.client.logout(); self.client.login(username='ada', password='S7rong-pass-99')
        self.say('great notes here')
        mid = ChatMessage.objects.get().id
        self.client.logout(); self.client.login(username='sam', password='S7rong-pass-99')
        self.assertEqual(self.jpost('chat_forward', {'room': 'futminna'}, mid).status_code, 200)
        fwd = ChatMessage.objects.get(room='futminna')
        self.assertEqual((fwd.user, fwd.forwarded_from, fwd.text), (self.sam, 'ada', 'great notes here'))

    def test_save_toggle_list_unsave(self):
        self.say('keep me')
        mid = ChatMessage.objects.get().id
        self.assertTrue(self.jpost('chat_save', {}, mid).json()['saved'])
        saved = self.client.get(reverse('chat_saved')).json()['saved']
        self.assertEqual(saved[0]['text'], 'keep me')
        self.assertTrue(self.client.get(reverse('chat_api') + '?room=global').json()['messages'][0]['saved'])
        self.assertEqual(self.jpost('chat_unsave', {}, saved[0]['id']).status_code, 200)
        self.assertEqual(self.client.get(reverse('chat_saved')).json()['saved'], [])

    def test_saved_messages_are_private(self):
        self.say('mine')
        mid = ChatMessage.objects.get().id
        self.jpost('chat_save', {}, mid)
        sid = self.client.get(reverse('chat_saved')).json()['saved'][0]['id']
        self.client.logout(); self.client.login(username='ada', password='S7rong-pass-99')
        self.assertEqual(self.client.get(reverse('chat_saved')).json()['saved'], [])
        self.assertEqual(self.jpost('chat_unsave', {}, sid).status_code, 404)

    def test_announcements_room_is_staff_only(self):
        r = self.say('hello', room='announcements')
        self.assertEqual(r.status_code, 403)
        self.assertFalse(self.client.get(reverse('chat_api') + '?room=announcements').json()['can_post'])
        self.client.logout(); self.client.login(username='boss', password='S7rong-pass-99')
        self.assertEqual(self.say('Exam timetable is out', room='announcements').status_code, 200)

    def test_slow_mode_blocks_students_not_staff(self):
        from .models import ChatRoomConfig
        ChatRoomConfig.objects.create(slug='global', slow_mode_seconds=30)
        self.assertEqual(self.say('one').status_code, 200)
        r = self.say('two')
        self.assertEqual(r.status_code, 429)
        self.assertIn('Slow mode', r.json()['error'])
        self.client.logout(); self.client.login(username='boss', password='S7rong-pass-99')
        self.assertEqual(self.say('a').status_code, 200)
        self.assertEqual(self.say('b').status_code, 200)

    def test_rooms_meta_and_page_controls(self):
        self.say('hi')
        latest = self.client.get(reverse('chat_rooms_meta')).json()['latest']
        self.assertGreater(latest['global'], 0)
        self.assertEqual(latest['futminna'], 0)
        r = self.client.get(reverse('global_chat'))
        for el in ('id="btn-attach"', 'id="btn-poll"', 'id="btn-search"', 'id="btn-saved"', 'id="room-list"'):
            self.assertContains(r, el)
