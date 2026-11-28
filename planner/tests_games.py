import json
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import games
from .models import Course, Flashcard, FlashcardDeck, GameScore, StudyStreak, UserBadge, XPLog

User = get_user_model()


def submit(client, game, score):
    return client.post(reverse('arcade_submit'), data=json.dumps({'game': game, 'score': score}),
                       content_type='application/json')


def age_scores():
    """Let the next submit through the anti-spam gap."""
    GameScore.objects.update(created_at=timezone.now() - timedelta(minutes=5))


class GameZoneTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('gamer', 'g@example.com', 'pass12345!')
        self.client.force_login(self.user)

    def test_pages_render(self):
        self.assertContains(self.client.get(reverse('arcade_hub')), 'Daily challenge')
        for slug in games.GAMES:
            self.assertEqual(self.client.get(reverse('arcade_game', args=[slug])).status_code, 200)
        self.assertEqual(self.client.get('/arcade/nope/').status_code, 404)

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('arcade_hub')).status_code, 302)
        self.assertEqual(submit(self.client, 'math', 100).status_code, 302)

    def test_valid_score_saved_and_gives_xp_and_first_badge(self):
        resp = submit(self.client, 'math', 250)
        data = resp.json()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['xp'], 2)
        self.assertTrue(data['new_best'])
        self.assertEqual(GameScore.objects.get().score, 250)
        self.assertTrue(UserBadge.objects.filter(user=self.user, badge__slug='arcade-first').exists())

    def test_rejects_impossible_or_bad_scores(self):
        self.assertEqual(submit(self.client, 'math', 999999).status_code, 400)
        self.assertEqual(submit(self.client, 'math', -5).status_code, 400)
        self.assertEqual(submit(self.client, 'nogame', 10).status_code, 400)
        self.assertEqual(self.client.post(reverse('arcade_submit'), data='nope', content_type='application/json').status_code, 400)
        self.assertEqual(GameScore.objects.count(), 0)

    def test_rapid_resubmission_is_blocked(self):
        self.assertEqual(submit(self.client, 'math', 100).status_code, 200)
        self.assertEqual(submit(self.client, 'math', 100).status_code, 429)

    def test_daily_xp_cap(self):
        for _ in range(8):
            submit(self.client, 'snake', 2000)   # 10 XP each, cap is 50
            age_scores()
        total = sum(XPLog.objects.filter(user=self.user, reason='game').values_list('points', flat=True))
        self.assertEqual(total, games.DAILY_XP_CAP)

    def test_daily_challenge_bonus_once(self):
        slug = games.todays_challenge()['slug']
        target = games.GAMES[slug]['target']
        first = submit(self.client, slug, target).json()
        self.assertEqual(first['daily_bonus'], games.DAILY_BONUS_XP)
        age_scores()
        second = submit(self.client, slug, target).json()
        self.assertEqual(second['daily_bonus'], 0)
        self.assertEqual(GameScore.objects.filter(is_daily=True).count(), 1)

    def test_score_below_target_gives_no_daily_bonus(self):
        slug = games.todays_challenge()['slug']
        data = submit(self.client, slug, 1).json()
        self.assertEqual(data['daily_bonus'], 0)

    def test_leaderboard_best_per_user_and_privacy(self):
        other = User.objects.create_user('shy', 's@example.com', 'pass12345!')
        StudyStreak.objects.update_or_create(user=other, defaults={'show_on_leaderboard': False})
        GameScore.objects.create(user=self.user, game='math', score=100)
        GameScore.objects.create(user=self.user, game='math', score=300)
        GameScore.objects.create(user=other, game='math', score=900)
        board = games.weekly_top('math', self.user)
        self.assertEqual([(r['username'], r['best']) for r in board], [('gamer', 300)])

    def test_quiz_questions_use_own_flashcards_and_fill_from_bank(self):
        course = Course.objects.create(user=self.user, name='Physics')
        deck = FlashcardDeck.objects.create(course=course, title='D')
        Flashcard.objects.create(deck=deck, front='Unique question one?', back='Unique answer one')
        data = self.client.get(reverse('arcade_quiz_questions')).json()
        self.assertEqual(len(data['questions']), 10)
        for q in data['questions']:
            self.assertEqual(len(q['options']), 4)
            self.assertIn(q['answer'], range(4))
        self.assertTrue(any('Unique question one?' == q['q'] for q in data['questions']))

    def test_all_rounder_badge(self):
        for slug in games.GAMES:
            submit(self.client, slug, 10)
            age_scores()
        self.assertTrue(UserBadge.objects.filter(user=self.user, badge__slug='arcade-all-rounder').exists())
