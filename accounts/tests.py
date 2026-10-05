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

    def test_signup_creates_user_and_logs_in(self):
        response = self.client.post(reverse('signup'), {
            'username': 'newstudent', 'password1': 'S7rong-pass-99', 'password2': 'S7rong-pass-99',
        })
        self.assertRedirects(response, reverse('dashboard'))
        self.assertTrue(User.objects.filter(username='newstudent').exists())
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)

    def test_signup_rejects_mismatched_passwords(self):
        response = self.client.post(reverse('signup'), {
            'username': 'x', 'password1': 'S7rong-pass-99', 'password2': 'different-pass-1',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='x').exists())

    def test_login_and_logout(self):
        User.objects.create_user('sam', password='S7rong-pass-99')
        response = self.client.post(reverse('login'), {'username': 'sam', 'password': 'S7rong-pass-99'})
        self.assertRedirects(response, reverse('dashboard'))
        self.client.post(reverse('logout'))
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 302)

    def test_login_with_wrong_password_fails(self):
        User.objects.create_user('sam', password='S7rong-pass-99')
        response = self.client.post(reverse('login'), {'username': 'sam', 'password': 'wrong'})
        self.assertEqual(response.status_code, 200)


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
