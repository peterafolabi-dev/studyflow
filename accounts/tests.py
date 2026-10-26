import os
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class AuthTests(TestCase):
    def test_healthz_is_public_cheap_and_uncached(self):
        response = self.client.get(reverse('healthz'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'ok')
        self.assertIn('no-cache', response['Cache-Control'])

    def test_public_admin_setup_route_is_not_exposed(self):
        self.assertEqual(self.client.get('/setup-admin-777/').status_code, 404)

    def test_signup_creates_user_redirects_to_login_without_logging_in(self):
        response = self.client.post(reverse('signup'), {
            'username': 'newstudent', 'email': 'New@Example.com',
            'password1': 'S7rong-pass-99', 'password2': 'S7rong-pass-99',
        }, follow=True)
        self.assertEqual(response.redirect_chain, [(reverse('login'), 302)])
        self.assertEqual(User.objects.get(username='newstudent').email, 'new@example.com')
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertContains(response, 'You&#x27;ve signed up successfully! Please log in.')
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 302)

    def test_signup_rejects_mismatched_passwords(self):
        response = self.client.post(reverse('signup'), {
            'username': 'x', 'password1': 'S7rong-pass-99', 'password2': 'different-pass-1',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='x').exists())
        self.assertContains(response, 'Sign-up failed. Check that the username is available')

    def test_signup_requires_unique_email(self):
        User.objects.create_user('taken', email='taken@example.com', password='S7rong-pass-99')
        for email in ('', 'TAKEN@example.com'):
            response = self.client.post(reverse('signup'), {
                'username': 'another', 'email': email,
                'password1': 'S7rong-pass-99', 'password2': 'S7rong-pass-99',
            })
            self.assertEqual(response.status_code, 200, email)
        self.assertFalse(User.objects.filter(username='another').exists())

    def test_login_ignores_external_next(self):
        User.objects.create_user('sam', password='S7rong-pass-99')
        response = self.client.post(
            reverse('login') + '?next=https://evil.example/phish',
            {'username': 'sam', 'password': 'S7rong-pass-99'},
        )
        self.assertRedirects(response, reverse('dashboard'), fetch_redirect_response=False)

    def test_login_is_rate_limited_per_username(self):
        User.objects.create_user('sam', password='S7rong-pass-99')
        for _ in range(10):
            self.client.post(reverse('login'), {'username': 'sam', 'password': 'wrong'})
        response = self.client.post(reverse('login'), {'username': 'sam', 'password': 'S7rong-pass-99'})
        self.assertEqual(response.status_code, 429)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_login_follows_local_next(self):
        User.objects.create_user('sam', password='S7rong-pass-99')
        response = self.client.post(
            reverse('login') + '?next=/courses/', {'username': 'sam', 'password': 'S7rong-pass-99'},
        )
        self.assertRedirects(response, '/courses/', fetch_redirect_response=False)

    def test_login_and_logout(self):
        User.objects.create_user('sam', password='S7rong-pass-99')
        response = self.client.post(reverse('login'), {
            'username': 'sam', 'password': 'S7rong-pass-99'
        }, follow=True)
        self.assertContains(response, 'Welcome to StudyFlow, sam! Let&#x27;s get started.')
        logout_response = self.client.post(reverse('logout'), follow=True)
        self.assertEqual(
            [str(message) for message in logout_response.context['messages']],
            ["You've been logged out. See you soon!"],
        )
        self.assertContains(logout_response, 'You&#x27;ve been logged out. See you soon!')
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 302)

    def test_returning_login_shows_welcome_back_once(self):
        User.objects.create_user('sam', password='S7rong-pass-99')
        first_login = self.client.post(reverse('login'), {
            'username': 'sam', 'password': 'S7rong-pass-99'
        }, follow=True)
        self.assertContains(first_login, 'Welcome to StudyFlow, sam!')
        self.client.post(reverse('logout'))
        returning_login = self.client.post(reverse('login'), {
            'username': 'sam', 'password': 'S7rong-pass-99'
        }, follow=True)
        self.assertContains(returning_login, 'Welcome back, sam!')
        self.assertNotContains(returning_login, "Let's get started")

    def test_logout_rejects_get(self):
        User.objects.create_user('sam', password='S7rong-pass-99')
        self.client.login(username='sam', password='S7rong-pass-99')
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)

    def test_login_with_wrong_password_fails(self):
        User.objects.create_user('sam', password='S7rong-pass-99')
        response = self.client.post(reverse('login'), {'username': 'sam', 'password': 'wrong'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid username or password. Please try again.')


class PresenceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('sam', password='S7rong-pass-99')

    def test_login_marks_user_online_and_active_today(self):
        from .models import DailyActivity
        from .presence import active_user_count, online_users
        self.client.post(reverse('login'), {'username': 'sam', 'password': 'S7rong-pass-99'})
        self.assertIn(self.user.pk, [p.user_id for p in online_users()])
        self.assertTrue(DailyActivity.objects.filter(user=self.user).exists())
        self.assertEqual(active_user_count(1), 1)

    def test_browsing_records_one_activity_row_per_day(self):
        from .models import DailyActivity
        self.client.login(username='sam', password='S7rong-pass-99')
        for _ in range(3):
            self.client.get(reverse('profile'))
        self.assertEqual(DailyActivity.objects.filter(user=self.user).count(), 1)

    def test_logout_marks_user_offline_immediately(self):
        from .presence import online_users
        self.client.post(reverse('login'), {'username': 'sam', 'password': 'S7rong-pass-99'})
        self.client.post(reverse('logout'))
        self.assertNotIn(self.user.pk, [p.user_id for p in online_users()])

    def test_presence_ping_requires_login_and_post(self):
        url = reverse('presence_ping')
        self.assertEqual(self.client.post(url).status_code, 302)
        self.client.login(username='sam', password='S7rong-pass-99')
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 200)

    def test_staff_dashboard_shows_activity(self):
        staff = User.objects.create_user('boss', password='S7rong-pass-99', is_staff=True)
        self.client.login(username='boss', password='S7rong-pass-99')
        self.client.get(reverse('profile'))
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active_today'], 1)
        self.assertEqual(len(response.context['dau_series']), 14)
        self.assertIn(staff.pk, [p.user_id for p in response.context['online_users']])


class AdminBootstrapTests(TestCase):
    @patch.dict(os.environ, {
        'DJANGO_SUPERUSER_USERNAME': 'renderadmin',
        'DJANGO_SUPERUSER_EMAIL': 'admin@example.com',
        'DJANGO_SUPERUSER_PASSWORD': 'S7rong-admin-pass-99',
    }, clear=True)
    def test_command_creates_and_updates_admin(self):
        call_command('create_or_update_admin')
        admin = User.objects.get(username='renderadmin')
        self.assertTrue(admin.check_password('S7rong-admin-pass-99'))
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_active)

        admin.is_staff = False
        admin.is_superuser = False
        admin.is_active = False
        admin.save()
        with patch.dict(os.environ, {'DJANGO_SUPERUSER_PASSWORD': 'N3w-admin-pass-99'}):
            call_command('create_or_update_admin')

        admin.refresh_from_db()
        self.assertTrue(admin.check_password('N3w-admin-pass-99'))
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_active)

    @patch.dict(os.environ, {}, clear=True)
    def test_command_requires_password(self):
        with self.assertRaises(CommandError):
            call_command('create_or_update_admin')


class PasswordResetFlowTests(TestCase):
    def test_full_reset_flow_sends_email_and_changes_password(self):
        import re
        from django.core import mail
        User.objects.create_user('ada', email='ada@example.com', password='Old-pass-S7rong')

        response = self.client.post(reverse('password_reset'), {'email': 'ADA@example.com'})
        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ['ada@example.com'])
        self.assertIn('StudyFlow', email.body)

        link = re.search(r'https?://[^/\s]+(/reset/\S+/)', email.body).group(1)
        form_page = self.client.get(link, follow=True)   # Django swaps the token into the session
        self.assertEqual(form_page.status_code, 200)
        set_password_url = form_page.redirect_chain[-1][0] if form_page.redirect_chain else link
        done = self.client.post(set_password_url, {
            'new_password1': 'Brand-new-S7rong-99', 'new_password2': 'Brand-new-S7rong-99',
        })
        self.assertRedirects(done, reverse('password_reset_complete'))
        self.assertTrue(self.client.login(username='ada', password='Brand-new-S7rong-99'))

        # The link is single-use.
        self.client.logout()
        reused = self.client.get(link, follow=True)
        self.assertNotIn('new_password1', reused.content.decode())
        self.assertContains(reused, 'This reset link has expired')

    def test_unknown_email_sends_nothing_but_looks_the_same(self):
        from django.core import mail
        response = self.client.post(reverse('password_reset'), {'email': 'nobody@example.com'})
        self.assertRedirects(response, reverse('password_reset_done'))  # no account enumeration
        self.assertEqual(len(mail.outbox), 0)


class EmailDeliveryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ada', email='ada@example.com', password='Old-pass-S7rong')

    def test_failed_email_send_is_logged_not_a_crash_or_hang(self):
        # Django logs send failures and still shows the generic "check your inbox" page
        # (so the form can't be used to discover which emails have accounts).
        from django.conf import settings
        self.assertEqual(settings.EMAIL_TIMEOUT, 15)  # a blocked mail server can't hang the request
        with patch('django.core.mail.EmailMultiAlternatives.send', side_effect=TimeoutError('blocked')),                 self.assertLogs('django.contrib.auth', level='ERROR'):
            response = self.client.post(reverse('password_reset'), {'email': 'ada@example.com'})
        self.assertRedirects(response, reverse('password_reset_done'))

    def test_reset_button_shows_sending_state(self):
        self.assertContains(self.client.get(reverse('password_reset')), 'Sending…')

    def test_brevo_backend_sends_expected_payload_and_raises_on_rejection(self):
        from django.core.mail import EmailMessage
        from django.test import override_settings
        from studyflow.email_backends import BrevoEmailBackend, EmailSendError
        ok = MagicMock(status_code=201, text='{}')
        with override_settings(BREVO_API_KEY='test-key', DEFAULT_FROM_EMAIL='StudyFlow <me@example.com>'), \
                patch('studyflow.email_backends.requests.post', return_value=ok) as post:
            sent = BrevoEmailBackend().send_messages([EmailMessage('Reset', 'Body text', None, ['ada@example.com'])])
        self.assertEqual(sent, 1)
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['to'], [{'email': 'ada@example.com'}])
        self.assertEqual(payload['sender'], {'email': 'me@example.com', 'name': 'StudyFlow'})
        self.assertEqual(post.call_args.kwargs['headers']['api-key'], 'test-key')

        rejected = MagicMock(status_code=401, text='unauthorized')
        with override_settings(BREVO_API_KEY='bad'), patch('studyflow.email_backends.requests.post', return_value=rejected):
            with self.assertRaises(EmailSendError):
                BrevoEmailBackend().send_messages([EmailMessage('Reset', 'Body', 'me@example.com', ['ada@example.com'])])


class AccountEmailTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('sam', password='S7rong-pass-99')  # old account: no email
        self.client.login(username='sam', password='S7rong-pass-99')

    def test_dashboard_asks_users_without_email_to_add_one(self):
        self.assertContains(self.client.get(reverse('dashboard')), 'Add your email')
        self.user.email = 'sam@example.com'
        self.user.save()
        self.assertNotContains(self.client.get(reverse('dashboard')), 'Add your email')

    def test_email_can_be_added_in_settings_and_must_be_unique(self):
        User.objects.create_user('other', email='taken@example.com', password='S7rong-pass-99')
        base = {'reading_goal': 12, 'avatar_color': 0, 'weekly_study_goal_hours': 8, 'preferred_study_time': 'flexible'}
        response = self.client.post(reverse('edit_profile'), {**base, 'email': 'TAKEN@example.com'})
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, '')
        response = self.client.post(reverse('edit_profile'), {**base, 'email': 'Sam@Example.com'})
        self.assertRedirects(response, reverse('profile'), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'sam@example.com')


class PasswordResetEmailDesignTests(TestCase):
    def test_reset_email_has_branded_html_and_plain_text_versions(self):
        import re
        from django.core import mail
        User.objects.create_user('ada', email='ada@example.com', password='Old-pass-S7rong')
        self.client.post(reverse('password_reset'), {'email': 'ada@example.com'})
        email = mail.outbox[0]
        self.assertEqual(email.subject, 'Reset your StudyFlow password')
        self.assertIn('Your username: ada', email.body)
        self.assertIn('expires in 3 days', email.body)
        html, mimetype = email.alternatives[0]
        self.assertEqual(mimetype, 'text/html')
        self.assertIn('Choose a new password', html)
        self.assertIn('ada', html)
        # The button and the fallback text link both carry the real reset link.
        link = re.search(r'(https?://[^\s<]+/reset/[^\s<]+/)', email.body).group(1)
        self.assertEqual(html.count(f'href="{link}"'), 2)


class GoogleAccountResetTests(TestCase):
    def test_google_signup_without_password_still_gets_reset_email(self):
        from django.core import mail
        user = User.objects.create_user('googler', email='googler@gmail.com')
        user.set_unusable_password()
        user.save()
        response = self.client.post(reverse('password_reset'), {'email': 'Googler@Gmail.com'})
        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual([m.to for m in mail.outbox], [['googler@gmail.com']])

    def test_inactive_accounts_get_nothing(self):
        from django.core import mail
        User.objects.create_user('gone', email='gone@example.com', password='S7rong-pass-99', is_active=False)
        self.client.post(reverse('password_reset'), {'email': 'gone@example.com'})
        self.assertEqual(len(mail.outbox), 0)


class DashboardGreetingTests(TestCase):
    def test_first_login_says_welcome_then_welcome_back(self):
        User.objects.create_user('newbie', password='S7rong-pass-99')
        creds = {'username': 'newbie', 'password': 'S7rong-pass-99'}
        first = self.client.post(reverse('login'), creds, follow=True)
        self.assertContains(first, 'Welcome to StudyFlow, newbie')
        self.assertNotContains(first, 'Welcome back, newbie')
        self.client.post(reverse('logout'))
        second = self.client.post(reverse('login'), creds, follow=True)
        self.assertContains(second, 'Welcome back, newbie')
        self.assertNotContains(second, 'Welcome to StudyFlow, newbie')
