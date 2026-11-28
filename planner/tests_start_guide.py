from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Course, Task, TimetableEntry

User = get_user_model()


class WeeklyPlanStartGuideTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('newbie', 'n@example.com', 'pass12345!')
        self.client.force_login(self.user)

    def test_new_user_sees_three_step_guide_and_no_empty_rows(self):
        resp = self.client.get(reverse('weekly_plan'))
        self.assertContains(resp, 'Start here: 3 quick steps')
        self.assertContains(resp, reverse('course_create'))
        self.assertContains(resp, reverse('timetable_create'))
        self.assertNotContains(resp, 'Free — no study blocks needed')

    def test_guide_checks_off_finished_steps(self):
        course = Course.objects.create(user=self.user, name='Maths')
        resp = self.client.get(reverse('weekly_plan'))
        self.assertContains(resp, '✅ Add your courses')
        self.assertContains(resp, '2️⃣ Add your class timetable')

    def test_guide_hidden_when_everything_is_set_up(self):
        course = Course.objects.create(user=self.user, name='Maths')
        TimetableEntry.objects.create(
            user=self.user, course=course, title='MTH101', day_of_week=0,
            start_time=time(9, 0), end_time=time(10, 0))
        Task.objects.create(course=course, title='Assignment',
                            due_date=timezone.localdate() + timedelta(days=2))
        resp = self.client.get(reverse('weekly_plan'))
        self.assertNotContains(resp, 'Start here: 3 quick steps')
