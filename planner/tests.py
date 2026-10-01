from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Course, Task, FlashcardDeck, Flashcard

User = get_user_model()


class BaseCase(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', password='pass12345!')
        self.bob = User.objects.create_user('bob', password='pass12345!')
        self.alice_course = Course.objects.create(user=self.alice, name='Maths', code='MTH 101')
        self.bob_course = Course.objects.create(user=self.bob, name='Physics')
        self.today = timezone.localdate()
        self.alice_task = Task.objects.create(
            course=self.alice_course, title='Alice task', due_date=self.today + timedelta(days=2)
        )
        self.bob_task = Task.objects.create(
            course=self.bob_course, title='Bob task', due_date=self.today + timedelta(days=2)
        )
        self.client.login(username='alice', password='pass12345!')


class LoginRequiredTests(TestCase):
    def test_pages_redirect_anonymous_users_to_login(self):
        for name in ('dashboard', 'course_list', 'course_create'):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302, name)
            self.assertIn('/login/', response.url)


class CourseTests(BaseCase):
    def test_create_course_belongs_to_current_user(self):
        response = self.client.post(reverse('course_create'), {'name': 'Chemistry', 'code': 'CHM 101'})
        course = Course.objects.get(name='Chemistry')
        self.assertEqual(course.user, self.alice)
        self.assertRedirects(response, reverse('course_detail', args=[course.pk]))

    def test_course_name_is_required(self):
        response = self.client.post(reverse('course_create'), {'name': '', 'code': ''})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Course.objects.filter(user=self.alice, name='').exists())

    def test_update_course(self):
        self.client.post(reverse('course_update', args=[self.alice_course.pk]), {'name': 'Advanced Maths', 'code': ''})
        self.alice_course.refresh_from_db()
        self.assertEqual(self.alice_course.name, 'Advanced Maths')

    def test_delete_course_removes_its_tasks(self):
        self.client.post(reverse('course_delete', args=[self.alice_course.pk]))
        self.assertFalse(Course.objects.filter(pk=self.alice_course.pk).exists())
        self.assertFalse(Task.objects.filter(pk=self.alice_task.pk).exists())

    def test_course_list_shows_only_own_courses(self):
        response = self.client.get(reverse('course_list'))
        self.assertContains(response, 'Maths')
        self.assertNotContains(response, 'Physics')


class OwnershipTests(BaseCase):
    """User A must never be able to see or change user B's data."""

    def test_cannot_view_edit_or_delete_someone_elses_course(self):
        for name in ('course_detail', 'course_update', 'course_delete'):
            response = self.client.get(reverse(name, args=[self.bob_course.pk]))
            self.assertEqual(response.status_code, 404, name)

    def test_cannot_change_someone_elses_course_by_post(self):
        self.client.post(reverse('course_update', args=[self.bob_course.pk]), {'name': 'Hacked', 'code': ''})
        self.client.post(reverse('course_delete', args=[self.bob_course.pk]))
        self.bob_course.refresh_from_db()
        self.assertEqual(self.bob_course.name, 'Physics')

    def test_cannot_add_task_to_someone_elses_course(self):
        response = self.client.post(
            reverse('task_create', args=[self.bob_course.pk]),
            {'title': 'Sneaky', 'due_date': self.today.isoformat()},
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Task.objects.filter(title='Sneaky').exists())

    def test_cannot_edit_delete_or_toggle_someone_elses_task(self):
        self.assertEqual(self.client.get(reverse('task_update', args=[self.bob_task.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('task_delete', args=[self.bob_task.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('task_toggle', args=[self.bob_task.pk])).status_code, 404)
        self.bob_task.refresh_from_db()
        self.assertFalse(self.bob_task.is_done)


class TaskTests(BaseCase):
    def test_create_task(self):
        self.client.post(
            reverse('task_create', args=[self.alice_course.pk]),
            {'title': 'Assignment 1', 'due_date': self.today.isoformat()},
        )
        self.assertTrue(Task.objects.filter(course=self.alice_course, title='Assignment 1').exists())

    def test_task_needs_a_valid_date(self):
        response = self.client.post(
            reverse('task_create', args=[self.alice_course.pk]),
            {'title': 'No date', 'due_date': 'not-a-date'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Task.objects.filter(title='No date').exists())

    def test_update_task(self):
        self.client.post(
            reverse('task_update', args=[self.alice_task.pk]),
            {'title': 'Renamed', 'due_date': self.today.isoformat()},
        )
        self.alice_task.refresh_from_db()
        self.assertEqual(self.alice_task.title, 'Renamed')

    def test_delete_task(self):
        self.client.post(reverse('task_delete', args=[self.alice_task.pk]))
        self.assertFalse(Task.objects.filter(pk=self.alice_task.pk).exists())

    def test_toggle_flips_done_both_ways(self):
        url = reverse('task_toggle', args=[self.alice_task.pk])
        self.client.post(url)
        self.alice_task.refresh_from_db()
        self.assertTrue(self.alice_task.is_done)
        self.client.post(url)
        self.alice_task.refresh_from_db()
        self.assertFalse(self.alice_task.is_done)

    def test_toggle_rejects_get(self):
        response = self.client.get(reverse('task_toggle', args=[self.alice_task.pk]))
        self.assertEqual(response.status_code, 405)

    def test_toggle_ignores_external_redirect(self):
        response = self.client.post(
            reverse('task_toggle', args=[self.alice_task.pk]), {'next': 'https://evil.example/'}
        )
        self.assertRedirects(response, reverse('course_detail', args=[self.alice_course.pk]))


class DashboardTests(BaseCase):
    def test_overdue_and_due_soon_are_separated(self):
        Task.objects.create(course=self.alice_course, title='Late one', due_date=self.today - timedelta(days=3))
        Task.objects.create(course=self.alice_course, title='Far away', due_date=self.today + timedelta(days=30))
        response = self.client.get(reverse('dashboard'))
        self.assertEqual([t.title for t in response.context['overdue']], ['Late one'])
        self.assertEqual([t.title for t in response.context['due_soon']], ['Alice task'])

    def test_done_tasks_are_hidden(self):
        self.alice_task.is_done = True
        self.alice_task.save()
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(len(response.context['due_soon']), 0)
        self.assertEqual(response.context['done_count'], 1)

    def test_other_users_tasks_never_appear(self):
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response, 'Bob task')

    def test_new_user_sees_empty_state(self):
        self.client.logout()
        User.objects.create_user('carol', password='pass12345!')
        self.client.login(username='carol', password='pass12345!')
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Add your first course')


class FlashcardSpacedRepetitionTests(BaseCase):
    def setUp(self):
        super().setUp()
        self.deck = FlashcardDeck.objects.create(
            course=self.alice_course,
            title='Calculus Definitions'
        )
        self.card = Flashcard.objects.create(
            deck=self.deck,
            front='What is a limit?',
            back='The value a function approaches.',
            next_review_date=self.today
        )

    def test_due_property(self):
        self.assertTrue(self.card.is_due)
        self.card.next_review_date = self.today + timedelta(days=3)
        self.card.save()
        self.assertFalse(self.card.is_due)

    def test_sm2_process_review_easy(self):
        initial_ef = self.card.ease_factor
        next_date = self.card.process_review('easy')
        self.assertEqual(self.card.repetitions, 1)
        self.assertEqual(self.card.interval_days, 2)
        self.assertGreater(self.card.ease_factor, initial_ef)
        self.assertEqual(next_date, self.today + timedelta(days=2))

    def test_sm2_process_review_medium(self):
        next_date = self.card.process_review('medium')
        self.assertEqual(self.card.repetitions, 1)
        self.assertEqual(self.card.interval_days, 1)
        self.assertEqual(next_date, self.today + timedelta(days=1))

    def test_sm2_process_review_hard(self):
        self.card.repetitions = 5
        self.card.interval_days = 10
        self.card.save()

        next_date = self.card.process_review('hard')
        self.assertEqual(self.card.repetitions, 0)
        self.assertEqual(self.card.interval_days, 1)
        self.assertEqual(next_date, self.today + timedelta(days=1))

    def test_rate_review_endpoint(self):
        url = reverse('flashcard_rate_review', args=[self.card.pk])
        response = self.client.post(
            url,
            data={'rating': 'easy'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['rating'], 'easy')
        self.assertEqual(data['interval_days'], 2)

    def test_rate_review_rejects_invalid_rating(self):
        url = reverse('flashcard_rate_review', args=[self.card.pk])
        response = self.client.post(
            url,
            data={'rating': 'super_easy'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_due_flashcards_count_on_dashboard(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['due_flashcards_count'], 1)

    def test_cannot_rate_another_users_flashcard(self):
        bob_deck = FlashcardDeck.objects.create(course=self.bob_course, title='Bob Deck')
        bob_card = Flashcard.objects.create(deck=bob_deck, front='Q', back='A')
        url = reverse('flashcard_rate_review', args=[bob_card.pk])
        response = self.client.post(url, data={'rating': 'easy'}, content_type='application/json')
        self.assertEqual(response.status_code, 404)

