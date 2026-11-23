from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import CampusEvent, CourseNotice, LostFoundItem, Opportunity

User = get_user_model()


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.ada = User.objects.create_user('ada', 'a@example.com', 'S7rong-pass-99')
        self.bola = User.objects.create_user('bola', 'b@example.com', 'S7rong-pass-99')
        self.staff = User.objects.create_user('staff', 's@example.com', 'S7rong-pass-99', is_staff=True)
        self.client.force_login(self.ada)


class LostFoundTests(Base):
    def _post(self, **extra):
        data = {'kind': 'lost', 'title': 'Casio calculator', 'location': 'ELT', 'description': '', 'whatsapp_number': '+234 801 234 5678'}
        data.update(extra)
        return self.client.post(reverse('lost_found_create'), data)

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('lost_found')).status_code, 302)
        self.assertEqual(self._post().status_code, 302)
        self.assertEqual(LostFoundItem.objects.count(), 0)

    def test_post_normalises_number_and_lists(self):
        self._post()
        item = LostFoundItem.objects.get()
        self.assertEqual(item.whatsapp_number, '2348012345678')
        self.assertContains(self.client.get(reverse('lost_found')), 'https://wa.me/2348012345678')

    def test_bad_number_or_kind_rejected(self):
        self._post(whatsapp_number='abc')
        self._post(whatsapp_number='123')
        self._post(kind='stolen')
        self._post(title='   ')
        self.assertEqual(LostFoundItem.objects.count(), 0)

    def test_html_is_escaped(self):
        self._post(title='<script>alert(1)</script>')
        self.assertNotContains(self.client.get(reverse('lost_found')), '<script>alert(1)</script>')

    def test_filter_by_kind(self):
        self._post(title='Lost thing')
        self._post(kind='found', title='Found thing')
        html = self.client.get(reverse('lost_found') + '?kind=found').content.decode()
        self.assertIn('Found thing', html)
        self.assertNotIn('Lost thing', html)

    def test_only_owner_can_resolve_or_delete_staff_can_delete(self):
        self._post()
        item = LostFoundItem.objects.get()
        self.client.force_login(self.bola)
        self.assertEqual(self.client.post(reverse('lost_found_resolve', args=[item.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('lost_found_delete', args=[item.pk])).status_code, 404)
        self.client.force_login(self.ada)
        self.client.post(reverse('lost_found_resolve', args=[item.pk]))
        item.refresh_from_db()
        self.assertTrue(item.is_resolved)
        self.assertNotContains(self.client.get(reverse('lost_found')), 'wa.me/2348012345678')
        self.client.force_login(self.staff)
        self.client.post(reverse('lost_found_delete', args=[item.pk]))
        self.assertEqual(LostFoundItem.objects.count(), 0)

    def test_get_not_allowed_on_actions(self):
        self._post()
        item = LostFoundItem.objects.get()
        self.assertEqual(self.client.get(reverse('lost_found_delete', args=[item.pk])).status_code, 405)

    def test_posting_is_rate_limited(self):
        for _ in range(12):
            self._post()
        self.assertEqual(LostFoundItem.objects.count(), 10)


class EventTests(Base):
    def _data(self, **extra):
        start = (timezone.localtime() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M')
        data = {'title': 'Tech seminar', 'description': 'AI, talks', 'location': 'Hall A', 'starts_at': start, 'ends_at': ''}
        data.update(extra)
        return data

    def test_student_event_needs_approval_staff_event_does_not(self):
        self.client.post(reverse('campus_event_create'), self._data())
        event = CampusEvent.objects.get()
        self.assertFalse(event.is_approved)
        html = self.client.get(reverse('campus_events')).content.decode()
        self.assertIn('Waiting for staff approval', html)
        self.client.force_login(self.bola)
        self.assertNotContains(self.client.get(reverse('campus_events')), 'Tech seminar')
        self.assertEqual(self.client.get(reverse('campus_event_ics', args=[event.pk])).status_code, 404)
        self.client.force_login(self.staff)
        self.client.post(reverse('campus_event_create'), self._data(title='Staff event'))
        self.assertTrue(CampusEvent.objects.get(title='Staff event').is_approved)

    def test_approved_event_listed_and_ics_is_valid(self):
        self.client.post(reverse('campus_event_create'), self._data(title='Fun, run; 5k'))
        CampusEvent.objects.update(is_approved=True)
        event = CampusEvent.objects.get()
        self.assertContains(self.client.get(reverse('campus_events')), 'Fun, run; 5k')
        r = self.client.get(reverse('campus_event_ics', args=[event.pk]))
        body = r.content.decode()
        self.assertEqual(r['Content-Type'], 'text/calendar; charset=utf-8')
        self.assertIn('BEGIN:VCALENDAR', body)
        self.assertIn('SUMMARY:Fun\\, run\; 5k', body)
        self.assertRegex(body, r'DTSTART:\d{8}T\d{6}Z')
        self.assertIn('DTEND:', body)
        self.assertTrue(body.endswith('END:VCALENDAR\r\n'))
        all_ics = self.client.get(reverse('campus_events_ics')).content.decode()
        self.assertEqual(all_ics.count('BEGIN:VEVENT'), 1)

    def test_past_event_and_bad_end_rejected(self):
        past = (timezone.localtime() - timedelta(days=3)).strftime('%Y-%m-%dT%H:%M')
        self.client.post(reverse('campus_event_create'), self._data(starts_at=past))
        start = timezone.localtime() + timedelta(days=2)
        self.client.post(reverse('campus_event_create'), self._data(
            starts_at=start.strftime('%Y-%m-%dT%H:%M'), ends_at=(start - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M')))
        self.assertEqual(CampusEvent.objects.count(), 0)

    def test_only_organizer_or_staff_can_delete(self):
        self.client.post(reverse('campus_event_create'), self._data())
        event = CampusEvent.objects.get()
        self.client.force_login(self.bola)
        self.assertEqual(self.client.post(reverse('campus_event_delete', args=[event.pk])).status_code, 404)
        self.client.force_login(self.staff)
        self.client.post(reverse('campus_event_delete', args=[event.pk]))
        self.assertEqual(CampusEvent.objects.count(), 0)

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('campus_events')).status_code, 302)
        self.assertEqual(self.client.get(reverse('campus_events_ics')).status_code, 302)


class OpportunityTests(Base):
    def _data(self, **extra):
        data = {'kind': 'scholarship', 'title': 'MTN Scholarship', 'organisation': 'MTN', 'description': '',
                'link': 'https://example.com/apply', 'deadline': (timezone.localdate() + timedelta(days=30)).isoformat()}
        data.update(extra)
        return data

    def test_needs_approval_then_listed_with_safe_link(self):
        self.client.post(reverse('campus_opportunity_create'), self._data())
        item = Opportunity.objects.get()
        self.assertFalse(item.is_approved)
        self.assertNotContains(self.client.get(reverse('campus_opportunities')) , 'href="https://example.com/apply"')
        item.is_approved = True
        item.save()
        html = self.client.get(reverse('campus_opportunities')).content.decode()
        self.assertIn('href="https://example.com/apply"', html)
        self.assertIn('noopener noreferrer nofollow', html)

    def test_rejects_javascript_links_and_past_deadlines(self):
        self.client.post(reverse('campus_opportunity_create'), self._data(link='javascript:alert(1)'))
        self.client.post(reverse('campus_opportunity_create'), self._data(link='ftp://example.com/x'))
        self.client.post(reverse('campus_opportunity_create'), self._data(deadline=(timezone.localdate() - timedelta(days=1)).isoformat()))
        self.assertEqual(Opportunity.objects.count(), 0)

    def test_closing_soon_badge_and_expired_hidden(self):
        today = timezone.localdate()
        Opportunity.objects.create(title='Soon', link='https://e.com', deadline=today + timedelta(days=3), submitted_by=self.ada, is_approved=True)
        Opportunity.objects.create(title='Later', link='https://e.com', deadline=today + timedelta(days=40), submitted_by=self.ada, is_approved=True)
        Opportunity.objects.create(title='Expired', link='https://e.com', deadline=today - timedelta(days=1), submitted_by=self.ada, is_approved=True)
        html = self.client.get(reverse('campus_opportunities')).content.decode()
        self.assertIn('Soon', html)
        self.assertNotIn('Expired', html)
        self.assertEqual(html.count('Closing soon'), 1)
        self.assertLess(html.index('Soon'), html.index('Later'))

    def test_filter_by_kind_and_delete_permissions(self):
        today = timezone.localdate()
        a = Opportunity.objects.create(title='Intern X', kind='internship', link='https://e.com', deadline=today + timedelta(days=9), submitted_by=self.ada, is_approved=True)
        Opportunity.objects.create(title='Schol Y', kind='scholarship', link='https://e.com', deadline=today + timedelta(days=9), submitted_by=self.ada, is_approved=True)
        html = self.client.get(reverse('campus_opportunities') + '?kind=internship').content.decode()
        self.assertIn('Intern X', html)
        self.assertNotIn('Schol Y', html)
        self.client.force_login(self.bola)
        self.assertEqual(self.client.post(reverse('campus_opportunity_delete', args=[a.pk])).status_code, 404)
        self.client.force_login(self.ada)
        self.client.post(reverse('campus_opportunity_delete', args=[a.pk]))
        self.assertFalse(Opportunity.objects.filter(pk=a.pk).exists())


class NoticeMyClassTests(Base):
    def test_my_class_filter_uses_profile(self):
        self.ada.profile.department = 'Computer Science'
        self.ada.profile.level = 300
        self.ada.profile.save()
        mk = lambda t, d, l: CourseNotice.objects.create(title=t, body='b', department=d, level=l, author=self.bola)
        mk('Mine', 'Computer Science', 300)
        mk('Everyone', 'All Departments', 0)
        mk('Other dept', 'Physics', 300)
        mk('Other level', 'Computer Science', 100)
        html = self.client.get(reverse('notice_board') + '?mine=1').content.decode()
        self.assertIn('Mine', html)
        self.assertIn('Everyone', html)
        self.assertNotIn('Other dept', html)
        self.assertNotIn('Other level', html)
        everything = self.client.get(reverse('notice_board')).content.decode()
        self.assertIn('Other dept', everything)

    def test_anonymous_ignores_mine(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('notice_board') + '?mine=1').status_code, 200)


class NavigationTests(Base):
    def test_hub_and_nav_link_to_new_pages(self):
        html = self.client.get(reverse('campus_hub')).content.decode()
        for name in ('campus_events', 'campus_opportunities', 'lost_found'):
            self.assertIn(reverse(name), html)
