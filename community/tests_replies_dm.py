from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Notification
from .models import DirectMessage, Feedback, MutedUser

User = get_user_model()
PW = 'S7rong-pass-99'


class FeedbackReplyTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('boss', 'b@example.com', PW)
        self.stu = User.objects.create_user('stu', 's@example.com', PW)
        self.fb = Feedback.objects.create(user=self.stu, rating=5, message='I want to be a growth marketer')

    def test_staff_reply_from_site_notifies_student(self):
        self.client.force_login(self.admin)
        r = self.client.post(reverse('feedback_reply', args=[self.fb.pk]), {'reply': 'Welcome aboard!'})
        self.assertEqual(r.status_code, 302)
        self.fb.refresh_from_db()
        self.assertEqual((self.fb.reply, self.fb.replied_by), ('Welcome aboard!', self.admin))
        self.assertTrue(Notification.objects.filter(user=self.stu, message__contains='replied').exists())

    def test_reply_from_django_admin(self):
        self.client.force_login(self.admin)
        url = reverse('admin:community_feedback_change', args=[self.fb.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url, {'reply': 'Hi from admin'})
        self.fb.refresh_from_db()
        self.assertEqual(self.fb.reply, 'Hi from admin')
        self.assertIsNotNone(self.fb.replied_at)
        self.assertEqual(Notification.objects.filter(user=self.stu).count(), 1)

    def test_non_staff_cannot_reply(self):
        self.client.force_login(self.stu)
        self.assertEqual(self.client.post(reverse('feedback_reply', args=[self.fb.pk]), {'reply': 'x'}).status_code, 404)

    def test_student_sees_reply(self):
        self.fb.reply = 'Thanks for the idea'
        self.fb.save()
        self.client.force_login(self.stu)
        self.assertContains(self.client.get(reverse('my_feedback')), 'Thanks for the idea')

    def test_anonymous_feedback_reply_does_not_crash(self):
        anon = Feedback.objects.create(rating=3, message='hm')
        self.client.force_login(self.admin)
        self.client.post(reverse('feedback_reply', args=[anon.pk]), {'reply': 'ok'})
        self.assertEqual(Notification.objects.count(), 0)


class DirectMessageTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user('alice', 'a@example.com', PW)
        self.b = User.objects.create_user('bob', 'b@example.com', PW)

    def send(self, text, to='bob'):
        return self.client.post(reverse('dm_send', args=[to]), {'text': text})

    def test_login_required(self):
        self.assertEqual(self.client.get(reverse('dm_inbox')).status_code, 302)

    def test_send_receive_read_and_unread_badge(self):
        self.client.force_login(self.a)
        self.assertEqual(self.send('hello bob').status_code, 200)
        self.assertEqual(self.send('second').status_code, 200)
        self.assertEqual(Notification.objects.filter(user=self.b).count(), 1)  # not spammed
        self.client.force_login(self.b)
        self.assertContains(self.client.get(reverse('dm_inbox')), 'second')
        self.assertEqual(DirectMessage.objects.filter(read_at__isnull=True).count(), 2)
        self.client.get(reverse('dm_thread', args=['alice']))
        self.assertEqual(DirectMessage.objects.filter(read_at__isnull=True).count(), 0)

    def test_poll_returns_only_new(self):
        self.client.force_login(self.a)
        first = self.send('one').json()['message']['id']
        self.send('two')
        got = self.client.get(reverse('dm_poll', args=['bob']), {'after': first}).json()['messages']
        self.assertEqual([m['text'] for m in got], ['two'])

    def test_cannot_message_self_empty_or_blocked(self):
        self.client.force_login(self.a)
        self.assertEqual(self.send('hi', to='alice').status_code, 400)
        self.assertEqual(self.send('   ').status_code, 400)
        MutedUser.objects.create(muter=self.b, muted=self.a)
        self.assertEqual(self.send('hi').status_code, 403)

    def test_strangers_cannot_read_each_others_thread(self):
        c = User.objects.create_user('carol', 'c@example.com', PW)
        DirectMessage.objects.create(sender=self.a, recipient=self.b, text='secret')
        self.client.force_login(c)
        self.assertNotContains(self.client.get(reverse('dm_thread', args=['alice'])), 'secret')

    def test_rate_limit(self):
        self.client.force_login(self.a)
        codes = [self.send('m%d' % i).status_code for i in range(14)]
        self.assertEqual(codes.count(429), 2)

    def test_html_is_escaped(self):
        self.client.force_login(self.a)
        self.send('<script>alert(1)</script>')
        r = self.client.get(reverse('dm_thread', args=['bob']))
        self.assertNotContains(r, '<script>alert(1)</script>')

    def test_profile_has_message_button(self):
        self.client.force_login(self.a)
        self.assertContains(self.client.get(reverse('public_profile', args=['bob'])), reverse('dm_thread', args=['bob']))
