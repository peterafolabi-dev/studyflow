from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from campus_life.models import CampusProfile, CreditEvent
from campus_life.services import credit_balance, earn_credits
from planner.models import Course, StudySession, Task


class CampusLifeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='campus-test', password='test-pass-123')
        self.client.force_login(self.user)

    def test_credit_events_are_append_only_and_idempotent(self):
        self.assertTrue(earn_credits(self.user, 'session:1', 'focused_minutes', 2))
        self.assertFalse(earn_credits(self.user, 'session:1', 'focused_minutes', 9))
        self.assertEqual(credit_balance(self.user), 2)
        self.assertEqual(CreditEvent.objects.filter(user=self.user).count(), 1)

    def test_campus_life_page_renders_and_rejects_locked_styles(self):
        response = self.client.get(reverse('campus_life_home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No cash value')
        self.assertContains(response, 'Your campus avatar')

        self.client.post(reverse('campus_life_home'), {
            'action': 'save_avatar',
            'skin_tone': '#c68642',
            'hairstyle': 'locs',
            'outfit_color': '#2f855a',
            'accessory': 'none',
        })
        profile = CampusProfile.objects.get(user=self.user)
        self.assertEqual(profile.hairstyle, 'crop')

    def test_on_time_task_awards_credits_only_once(self):
        course = Course.objects.create(user=self.user, name='Calculus')
        task = Task.objects.create(course=course, title='Submit worksheet', due_date=date.today())
        url = reverse('task_toggle', args=[task.pk])

        self.client.post(url)
        self.assertEqual(credit_balance(self.user), 6)
        self.client.post(url)
        self.client.post(url)
        self.assertEqual(credit_balance(self.user), 6)

    def test_study_log_awards_predictable_minutes_and_daily_credit(self):
        response = self.client.post(reverse('log_study'), {'duration': '25', 'course_id': ''})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(credit_balance(self.user), 3)

    def test_partial_sessions_accumulate_at_ten_minutes_per_credit(self):
        self.client.post(reverse('log_study'), {'duration': '5', 'course_id': ''})
        self.assertEqual(credit_balance(self.user), 1)
        self.client.post(reverse('log_study'), {'duration': '5', 'course_id': ''})
        self.assertEqual(credit_balance(self.user), 2)

    def test_profile_milestones_are_private_and_celebrate_once(self):
        StudySession.objects.create(user=self.user, duration_minutes=600)
        first_response = self.client.get(reverse('profile'))
        self.assertEqual(first_response.status_code, 200)
        self.assertContains(first_response, 'First Session')
        self.assertContains(first_response, '10 Hours Logged')
        self.assertTrue(first_response.context['new_achievements'])

        second_response = self.client.get(reverse('profile'))
        self.assertEqual(second_response.context['new_achievements'], [])