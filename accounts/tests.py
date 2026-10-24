import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class AuthTests(TestCase):
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
