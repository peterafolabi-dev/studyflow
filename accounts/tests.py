from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class AuthTests(TestCase):
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
