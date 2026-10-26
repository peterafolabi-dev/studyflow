import os
from datetime import timedelta
from unittest import mock

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
        # New users get onboarding demo content (planner.signals); start these tests from a clean slate.
        Course.objects.filter(user__in=[self.alice, self.bob], code='DEMO 101').delete()
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

    def test_new_user_gets_onboarding_content(self):
        self.client.logout()
        carol = User.objects.create_user('carol', password='pass12345!')
        self.client.login(username='carol', password='pass12345!')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Course.objects.filter(user=carol, code='DEMO 101').exists())
        self.assertEqual([t.title for t in response.context['due_soon']], ['Complete StudyFlow Onboarding'])
        self.assertEqual(response.context['due_flashcards_count'], 5)

    def test_new_user_without_courses_sees_empty_state(self):
        self.client.logout()
        carol = User.objects.create_user('carol', password='pass12345!')
        Course.objects.filter(user=carol).delete()
        self.client.login(username='carol', password='pass12345!')
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Add your first course')


class AbuseProtectionTests(BaseCase):
    def test_toggling_a_task_awards_xp_only_once(self):
        from .models import XPLog
        url = reverse('task_toggle', args=[self.alice_task.pk])
        for _ in range(4):
            self.client.post(url)
        self.assertEqual(XPLog.objects.filter(user=self.alice, reason='task_done').count(), 1)

    def test_completed_at_tracks_done_state(self):
        url = reverse('task_toggle', args=[self.alice_task.pk])
        self.client.post(url)
        self.alice_task.refresh_from_db()
        self.assertIsNotNone(self.alice_task.completed_at)
        self.client.post(url)
        self.alice_task.refresh_from_db()
        self.assertIsNone(self.alice_task.completed_at)

    def test_rerating_a_card_that_is_not_due_earns_no_xp(self):
        from .models import XPLog
        deck = FlashcardDeck.objects.create(course=self.alice_course, title='Deck')
        card = Flashcard.objects.create(deck=deck, front='Q', back='A')
        url = reverse('flashcard_rate_review', args=[card.pk])
        for _ in range(3):
            self.client.post(url, data={'rating': 'easy'}, content_type='application/json')
        self.assertEqual(XPLog.objects.filter(user=self.alice, reason='flashcard').count(), 1)

    def test_log_study_rejects_bad_and_huge_durations(self):
        from .models import StudySession
        for value in ('abc', '0', '-5', '999999'):
            response = self.client.post(reverse('log_study'), {'duration': value})
            self.assertEqual(response.status_code, 302, value)
        self.assertFalse(StudySession.objects.filter(user=self.alice).exists())
        self.client.post(reverse('log_study'), {'duration': '25'})
        self.assertEqual(StudySession.objects.filter(user=self.alice).count(), 1)

    def test_ai_chat_requires_login_and_csrf(self):
        from django.test import Client
        anonymous = Client(enforce_csrf_checks=True)
        response = anonymous.post(reverse('ai_chat'), data={'message': 'hi'}, content_type='application/json')
        self.assertEqual(response.status_code, 403)  # CSRF is no longer exempt
        with mock.patch.dict(os.environ, {'GROQ_API_KEY': ''}):  # never call the real API in tests
            response = self.client.post(reverse('ai_chat'), data={'message': 'hi'}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.client.logout()
        response = self.client.post(reverse('ai_chat'), data={'message': 'hi'}, content_type='application/json')
        self.assertEqual(response.status_code, 401)


class BreakRoomTests(BaseCase):
    def test_academic_speed_typer_renders_controls_and_game_logic(self):
        response = self.client.get(reverse('break_room'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Academic Speed Typer')
        self.assertContains(response, 'id="score-typer"')
        self.assertContains(response, 'id="timer-typer"')
        self.assertContains(response, 'id="input-typer"')
        self.assertContains(response, 'setInterval')
        self.assertContains(response, 'sf_academic_typer_best')


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

    def test_flashcard_page_includes_grid_gesture_actions(self):
        response = self.client.get(reverse('flashcards'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'data-card-id="{self.card.pk}"')
        self.assertContains(response, 'window.studyflowGestureOpenPalm')
        self.assertContains(response, 'window.studyflowGestureClosePalm')
        self.assertContains(response, 'window.studyflowGestureThumbsUp')
        self.assertContains(response, 'window.studyflowGestureThumbsDown')
        self.assertContains(response, 'function navigateGridFlashcard')
        self.assertContains(response, 'Desktop only.')
        self.assertContains(response, 'id="gesture-guide"')
        self.assertContains(response, 'aria-modal="true"')
        self.assertContains(response, 'Control your flashcards with your hand')
        self.assertContains(response, 'Swipe right:</strong> next card')
        self.assertContains(response, 'Your camera video stays in your browser and is never uploaded or saved.')
        self.assertContains(response, 'studyflow-flashcard-gesture-guide-seen')
        self.assertContains(response, 'aria-label="Close flashcard review"')
        self.assertContains(response, 'pt-[max(1.5rem,env(safe-area-inset-top))]')
        self.assertContains(response, 'overflow-y-auto')

    def test_camera_assets_are_only_loaded_on_flashcards(self):
        flashcards = self.client.get(reverse('flashcards'))
        self.assertContains(flashcards, '@mediapipe/hands@0.4.1675469240/hands.js')
        self.assertContains(flashcards, 'static/js/hand_gestures.js')

        for page_name in ('study_room', 'dashboard', 'catalogue'):
            response = self.client.get(reverse(page_name))
            self.assertNotContains(response, '@mediapipe/hands', msg_prefix=page_name)
            self.assertNotContains(response, 'static/js/hand_gestures.js', msg_prefix=page_name)
            self.assertNotContains(response, 'getUserMedia', msg_prefix=page_name)

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
        due = Flashcard.objects.filter(
            deck__course__user=self.alice, next_review_date__lte=timezone.localdate()
        ).count()
        self.assertGreaterEqual(due, 1)
        self.assertEqual(response.context['due_flashcards_count'], due)

    def test_cannot_rate_another_users_flashcard(self):
        bob_deck = FlashcardDeck.objects.create(course=self.bob_course, title='Bob Deck')
        bob_card = Flashcard.objects.create(deck=bob_deck, front='Q', back='A')
        url = reverse('flashcard_rate_review', args=[bob_card.pk])
        response = self.client.post(url, data={'rating': 'easy'}, content_type='application/json')
        self.assertEqual(response.status_code, 404)



class WeeklyPlanAndSearchTests(BaseCase):
    def test_weekly_plan_shows_today_summary_and_block_types(self):
        Task.objects.create(course=self.alice_course, title='Late lab', due_date=self.today - timedelta(days=1))
        response = self.client.get(reverse('weekly_plan'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Today')
        self.assertContains(response, 'Planned this week')
        self.assertEqual(response.context['overdue_count'], 1)
        kinds = {item['kind'] for day in response.context['plan_days'] for item in day['items']}
        self.assertIn('overdue', kinds)
        self.assertTrue(response.context['plan_days'][0]['is_today'])

    def test_every_screen_size_has_a_search_entry_point(self):
        response = self.client.get(reverse('dashboard'))
        search_url = reverse('global_search')
        # wide-screen box + mobile-menu box, plus the navigator's "search everything" link
        self.assertGreaterEqual(response.content.decode().count(f'action="{search_url}"'), 2)
        self.assertContains(response, 'data-open-command-palette')
        self.assertContains(response, 'id="command-palette-search-all"')


class GlobalSearchTests(BaseCase):
    def search(self, q):
        return self.client.get(reverse('global_search'), {'q': q})

    def test_page_names_are_searchable(self):
        for query, label in [('gpa', 'GPA Calculator'), ('flashcards', 'Flashcards'), ('where is light', 'Where is Light?')]:
            labels = [page['label'] for page in self.search(query).context['results']['pages']]
            self.assertIn(label, labels, query)

    def test_words_match_in_any_order(self):
        Course.objects.create(user=self.alice, name='Engineering Mathematics II', code='MTH 202')
        courses = self.search('mathematics engineering').context['results']['courses']
        self.assertEqual([c.name for c in courses], ['Engineering Mathematics II'])

    def test_other_users_courses_and_private_banks_stay_hidden(self):
        from resources.models import QuestionBank
        QuestionBank.objects.create(title='Bob private physics', created_by=self.bob, is_public=False)
        response = self.search('physics')
        self.assertEqual(list(response.context['results']['courses']), [])
        self.assertEqual(list(response.context['results']['banks']), [])

    def test_no_results_shows_suggestions(self):
        response = self.search('zzqqxx')
        self.assertEqual(response.context['total'], 0)
        self.assertContains(response, 'Try a course code')


class SpotifyLinkTests(BaseCase):
    PLAYLIST = '37i9dQZF1DWWQRwui0ExPn'

    def test_links_copied_from_the_app_are_accepted(self):
        from .views import _spotify_embed_path
        for url in [
            f'https://open.spotify.com/playlist/{self.PLAYLIST}',
            f'https://open.spotify.com/intl-en/playlist/{self.PLAYLIST}?si=abc123',   # language prefix + tracking
            f'https://open.spotify.com/intl-fr/album/{self.PLAYLIST}',
            f'https://open.spotify.com/show/{self.PLAYLIST}',                         # podcast
        ]:
            self.assertIsNotNone(_spotify_embed_path(url), url)

    def test_non_spotify_and_malformed_links_are_rejected(self):
        from .views import _spotify_embed_path
        for url in ['', 'https://evil.example/playlist/' + self.PLAYLIST, 'javascript:alert(1)',
                    'https://open.spotify.com/playlist/short', 'https://open.spotify.com/user/someone']:
            self.assertIsNone(_spotify_embed_path(url), url)

    def test_saving_an_intl_link_embeds_the_right_player(self):
        url = f'https://open.spotify.com/intl-en/playlist/{self.PLAYLIST}?si=xyz'
        self.client.post(reverse('study_room'), {'action': 'save_spotify_url', 'spotify_url': url})
        response = self.client.get(reverse('study_room'))
        self.assertEqual(response.context['spotify_embed_url'], f'https://open.spotify.com/embed/playlist/{self.PLAYLIST}')

    def test_short_spotify_link_gets_a_helpful_message(self):
        response = self.client.post(reverse('study_room'), {'action': 'save_spotify_url', 'spotify_url': 'https://spotify.link/AbCdEf'})
        self.assertContains(response, 'Short spotify.link links hide the real address')


class StudySessionSaveTests(BaseCase):
    def test_saving_shows_confirmation_and_updates_recap(self):
        response = self.client.post(reverse('log_study'), {'duration': '25', 'course_id': self.alice_course.pk}, follow=True)
        msgs = [str(m) for m in response.context['messages']]
        self.assertTrue(any(m.startswith('✅ Session complete: 25 min of Maths saved.') and '+20 XP' in m for m in msgs), msgs)
        self.assertEqual(response.context['recap']['minutes'], 25)
        self.assertEqual(response.context['recap']['sessions'], 1)
        self.assertEqual(response.context['recap']['course'], 'Maths')

    def test_in_page_save_returns_json_with_fresh_totals(self):
        response = self.client.post(reverse('log_study'), {'duration': '12'}, HTTP_ACCEPT='application/json')
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertIn('12 min', data['message'])
        self.assertNotIn('XP', data['message'])  # under 15 min: time logged, no XP
        self.assertEqual(data['recap']['minutes'], 12)

    def test_in_page_save_rejects_bad_duration_with_json_error(self):
        response = self.client.post(reverse('log_study'), {'duration': '0'}, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['ok'])

    def test_study_room_page_has_session_flow_hooks(self):
        response = self.client.get(reverse('study_room'))
        for hook in ('id="course-select"', 'id="session-saved"', 'id="recap-data"', 'studyflow-focus-timer'):
            self.assertContains(response, hook)
        self.assertNotContains(response, 'Focus session complete!')  # the old blocking popup


class SessionHistoryTests(BaseCase):
    def save(self, **data):
        return self.client.post(reverse('log_study'), data, HTTP_ACCEPT='application/json').json()

    def test_each_session_records_how_it_ended(self):
        self.save(duration='25', mode='timer', planned='25')            # countdown reached zero
        self.save(duration='12', mode='timer', planned='25')            # stopped early
        data = self.save(duration='95', mode='stopwatch', planned='')   # open-ended
        history = data['recap']['history']
        self.assertEqual([h['ended'] for h in history], ['stopwatch', 'stopped', 'completed'])  # newest first
        self.assertEqual([(h['minutes'], h['planned']) for h in history], [(95, None), (12, 25), (25, 25)])
        self.assertTrue(all(h['time'] for h in history))
        self.assertEqual(data['recap']['minutes'], 132)

    def test_stop_messages_say_what_happened(self):
        self.assertTrue(self.save(duration='12', mode='timer', planned='25')['message'].startswith('⏹ Session stopped: 12 min'))
        self.assertTrue(self.save(duration='40', mode='stopwatch')['message'].startswith('⏱ Session saved: 40 min'))

    def test_stopwatch_allows_long_sessions_but_not_unlimited(self):
        self.assertTrue(self.save(duration='150', mode='stopwatch')['ok'])
        response = self.client.post(reverse('log_study'), {'duration': '181', 'mode': 'stopwatch'}, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 400)

    def test_forged_planned_length_is_ignored(self):
        data = self.save(duration='20', mode='timer', planned='999')
        self.assertEqual(data['recap']['history'][0]['planned'], None)
        self.assertEqual(data['recap']['history'][0]['ended'], 'completed')

    def test_page_has_stopwatch_controls_history_and_calculator(self):
        response = self.client.get(reverse('study_room'))
        for hook in ('data-mode="stopwatch"', 'id="stop-btn"', 'id="session-history"', 'data-calculator', 'js/calculator.js'):
            self.assertContains(response, hook)
