from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from planner.models import Course, Flashcard, FlashcardDeck, StudyStreak, XPLog
from planner.study_insights import revision_plan, weak_topics, weekly_leaderboard
from resources.models import CBTQuestion, QuestionBank, TestAttempt

User = get_user_model()


def make_bank(course=None, n=10, title='Limits'):
    bank = QuestionBank.objects.create(title=title, course=course, course_code=course.code if course else '')
    qs = [CBTQuestion.objects.create(bank=bank, text=f'Q{i}', option_a='a', option_b='b', option_c='c',
                                     option_d='d', correct_option='A', order=i) for i in range(n)]
    return bank, qs


def attempt(user, bank, qs, right):
    answers = {str(q.id): ('A' if i < right else 'B') for i, q in enumerate(qs)}
    return TestAttempt.objects.create(user=user, bank=bank, answers=answers, is_completed=True,
                                      total_questions=len(qs), score=right)


class WeakTopicTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ada', 'a@example.com', 'S7rong-pass-99')
        self.course = Course.objects.create(user=self.user, name='Calculus', code='MTH 101')

    def test_needs_enough_evidence(self):
        bank, qs = make_bank(self.course, n=6)
        attempt(self.user, bank, qs, right=1)
        self.assertEqual(weak_topics(self.user), [])  # only 6 answers

    def test_low_accuracy_with_enough_answers_is_weak(self):
        bank, qs = make_bank(self.course, n=10)
        attempt(self.user, bank, qs, right=3)
        topics = weak_topics(self.user)
        self.assertEqual(len(topics), 1)
        self.assertEqual(topics[0]['percent'], 30)
        self.assertEqual(topics[0]['title'], 'Limits')

    def test_good_accuracy_is_not_weak(self):
        bank, qs = make_bank(self.course, n=10)
        attempt(self.user, bank, qs, right=8)
        self.assertEqual(weak_topics(self.user), [])

    def test_evidence_accumulates_across_attempts(self):
        bank, qs = make_bank(self.course, n=5)
        attempt(self.user, bank, qs, right=1)
        attempt(self.user, bank, qs, right=1)
        self.assertEqual(len(weak_topics(self.user)), 1)

    def test_only_own_attempts_count(self):
        other = User.objects.create_user('bola', 'b@example.com', 'S7rong-pass-99')
        bank, qs = make_bank(self.course, n=10)
        attempt(other, bank, qs, right=0)
        self.assertEqual(weak_topics(self.user), [])

    def test_hard_flashcards_flag_a_deck(self):
        deck = FlashcardDeck.objects.create(course=self.course, title='Derivatives')
        for i in range(6):
            Flashcard.objects.create(deck=deck, front=f'f{i}', back='b', ease_factor=1.5,
                                     last_reviewed_at=timezone.now())
        topics = weak_topics(self.user)
        self.assertEqual([t['kind'] for t in topics], ['cards'])

    def test_unreviewed_cards_are_not_evidence(self):
        deck = FlashcardDeck.objects.create(course=self.course, title='Derivatives')
        for i in range(8):
            Flashcard.objects.create(deck=deck, front=f'f{i}', back='b', ease_factor=1.3)
        self.assertEqual(weak_topics(self.user), [])

    def test_page_and_empty_state(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse('weak_topics')), 'Nothing weak so far')
        bank, qs = make_bank(self.course, n=10)
        attempt(self.user, bank, qs, right=2)
        self.assertContains(self.client.get(reverse('weak_topics')), 'Limits')
        self.assertContains(self.client.get(reverse('dashboard')), 'Needs more practice')

    def test_pages_need_login(self):
        for name in ('weak_topics', 'revision_plan', 'leaderboard'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 302)


class RevisionPlanTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ada', 'a@example.com', 'S7rong-pass-99')
        self.today = timezone.localdate()

    def test_no_exams_no_plan(self):
        plan = revision_plan(self.user)
        self.assertEqual(plan['exams'], [])
        self.assertTrue(all(not d['items'] for d in plan['days']))

    def test_past_exams_are_ignored(self):
        Course.objects.create(user=self.user, name='Old', exam_date=self.today - timedelta(days=2))
        self.assertEqual(revision_plan(self.user)['exams'], [])

    def test_closer_exam_gets_more_time(self):
        near = Course.objects.create(user=self.user, name='Near', exam_date=self.today + timedelta(days=3))
        far = Course.objects.create(user=self.user, name='Far', exam_date=self.today + timedelta(days=20))
        items = {i['course'].pk: i['minutes'] for i in revision_plan(self.user)['days'][0]['items']}
        self.assertGreater(items[near.pk], items.get(far.pk, 0))

    def test_exam_day_is_light_and_after_exam_dropped(self):
        c = Course.objects.create(user=self.user, name='Soon', exam_date=self.today + timedelta(days=1))
        days = revision_plan(self.user)['days']
        self.assertIn('Exam day', days[1]['items'][0]['focus'])
        self.assertEqual(days[2]['items'], [])

    def test_weak_course_gets_boost_and_focus(self):
        weak = Course.objects.create(user=self.user, name='Weak', code='W1', exam_date=self.today + timedelta(days=10))
        Course.objects.create(user=self.user, name='Fine', code='F1', exam_date=self.today + timedelta(days=10))
        bank, qs = make_bank(weak, n=10, title='Integration')
        attempt(self.user, bank, qs, right=1)
        items = {i['course'].name: i for i in revision_plan(self.user)['days'][0]['items']}
        self.assertGreaterEqual(items['Weak']['minutes'], items['Fine']['minutes'])
        self.assertIn('Integration', items['Weak']['focus'])

    def test_only_own_courses(self):
        other = User.objects.create_user('bola', 'b@example.com', 'S7rong-pass-99')
        Course.objects.create(user=other, name='Theirs', exam_date=self.today + timedelta(days=4))
        self.assertEqual(revision_plan(self.user)['exams'], [])

    def test_exam_date_saved_from_course_form_and_countdown_shown(self):
        self.client.force_login(self.user)
        date = (self.today + timedelta(days=5)).isoformat()
        r = self.client.post(reverse('course_create'), {'name': 'Physics', 'code': 'PHY 101', 'exam_date': date})
        course = Course.objects.get(name='Physics')
        self.assertEqual(course.days_to_exam, 5)
        self.assertContains(self.client.get(reverse('course_detail', args=[course.pk])), '5 days left')
        self.assertContains(self.client.get(reverse('course_update', args=[course.pk])), f'value="{date}"')
        self.assertContains(self.client.get(reverse('dashboard')), 'In 5 days')
        self.assertContains(self.client.get(reverse('revision_plan')), 'Physics')


class LeaderboardTests(TestCase):
    def setUp(self):
        self.users = [User.objects.create_user(n, f'{n}@example.com', 'S7rong-pass-99') for n in ('ada', 'bola', 'chi')]

    def test_ranks_by_weekly_xp_usernames_only(self):
        for user, pts in zip(self.users, (10, 50, 30)):
            XPLog.objects.create(user=user, reason='task_done', points=pts)
        board = weekly_leaderboard(self.users[0])
        self.assertEqual([r['username'] for r in board['rows']], ['bola', 'chi', 'ada'])
        self.assertEqual(board['me']['rank'], 3)
        self.client.force_login(self.users[0])
        html = self.client.get(reverse('leaderboard')).content.decode()
        self.assertNotIn('bola@example.com', html)

    def test_old_xp_does_not_count(self):
        log = XPLog.objects.create(user=self.users[0], reason='task_done', points=99)
        XPLog.objects.filter(pk=log.pk).update(created_at=timezone.now() - timedelta(days=10))
        self.assertEqual(weekly_leaderboard(self.users[0])['rows'], [])

    def test_opt_out_hides_me_and_can_be_reversed(self):
        XPLog.objects.create(user=self.users[0], reason='task_done', points=40)
        self.client.force_login(self.users[0])
        self.client.post(reverse('leaderboard_visibility'), {'show': '0'})
        self.assertFalse(StudyStreak.objects.get(user=self.users[0]).show_on_leaderboard)
        board = weekly_leaderboard(self.users[1])
        self.assertEqual(board['rows'], [])
        self.client.post(reverse('leaderboard_visibility'), {'show': '1'})
        self.assertEqual(len(weekly_leaderboard(self.users[1])['rows']), 1)

    def test_visibility_requires_post(self):
        self.client.force_login(self.users[0])
        self.assertEqual(self.client.get(reverse('leaderboard_visibility')).status_code, 405)

    def test_zero_xp_students_not_listed_and_limit_respected(self):
        for i in range(25):
            u = User.objects.create_user(f'u{i}', f'u{i}@example.com', 'S7rong-pass-99')
            XPLog.objects.create(user=u, reason='task_done', points=i + 1)
        board = weekly_leaderboard(self.users[0], limit=20)
        self.assertEqual(len(board['rows']), 20)
        self.assertEqual(board['rows'][0]['xp'], 25)


class VoiceButtonTests(TestCase):
    def test_mic_is_hidden_by_default_and_wired_to_recognition(self):
        user = User.objects.create_user('ada', 'a@example.com', 'S7rong-pass-99')
        self.client.force_login(user)
        html = self.client.get(reverse('dashboard')).content.decode()
        self.assertIn('id="ai-chat-mic" hidden', html)
        self.assertIn('webkitSpeechRecognition', html)
        self.assertIn("rec.lang = 'en-NG'", html)
