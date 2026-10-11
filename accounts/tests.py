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
            'username': 'newstudent', 'password1': 'S7rong-pass-99', 'password2': 'S7rong-pass-99',
        })
        self.assertRedirects(response, reverse('login'))
        self.assertTrue(User.objects.filter(username='newstudent').exists())
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 302)
        self.assertContains(self.client.get(reverse('login')), 'You&#x27;ve signed up successfully! Please log in.')

    def test_signup_rejects_mismatched_passwords(self):
        response = self.client.post(reverse('signup'), {
            'username': 'x', 'password1': 'S7rong-pass-99', 'password2': 'different-pass-1',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='x').exists())
        self.assertContains(response, 'Sign-up failed. Check that the username is available')

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
