from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .academics import attendance_summary, cgpa_summary, degree_class, required_average
from .coach.context import student_context
from .models import AttendanceRecord, Course, CourseResult, Semester

User = get_user_model()


class Base(TestCase):
    def setUp(self):
        self.ada = User.objects.create_user('ada', 'ada@example.com', 'pw-12345-x')
        self.bob = User.objects.create_user('bob', 'bob@example.com', 'pw-12345-x')
        self.client.force_login(self.ada)
        self.today = timezone.localdate()


class CgpaMathTests(Base):
    def test_gpa_and_cgpa_across_semesters(self):
        s1 = Semester.objects.create(user=self.ada, name='100L First', order=0)
        CourseResult.objects.create(semester=s1, code='MTH 101', units=3, grade='A')   # 15
        CourseResult.objects.create(semester=s1, code='PHY 101', units=2, grade='B')   # 8
        CourseResult.objects.create(semester=s1, code='CHM 101', units=4, grade='C')   # 12 -> 35/9
        s2 = Semester.objects.create(user=self.ada, name='100L Second', order=1)
        CourseResult.objects.create(semester=s2, code='MTH 102', units=3, grade='A')   # 15/3
        summary = cgpa_summary(self.ada)
        self.assertEqual(summary['rows'][0]['gpa'], 3.89)
        self.assertEqual(summary['rows'][1]['gpa'], 5.0)
        self.assertEqual(summary['cgpa'], round(50 / 12, 2))  # 4.17
        self.assertEqual(summary['class'], 'Second Class Upper')

    def test_degree_class_boundaries(self):
        self.assertEqual(degree_class(4.50), 'First Class')
        self.assertEqual(degree_class(4.49), 'Second Class Upper')
        self.assertEqual(degree_class(3.50), 'Second Class Upper')
        self.assertEqual(degree_class(2.40), 'Second Class Lower')
        self.assertEqual(degree_class(1.50), 'Third Class')
        self.assertEqual(degree_class(None), '')

    def test_required_average(self):
        # 40 units at 4.0 (160 points), 60 units left, target 4.5 -> (450-160)/60 = 4.8333 -> 4.84
        self.assertEqual(required_average(160, 40, 4.5, 60), (4.84, 'ok'))
        self.assertEqual(required_average(160, 40, 1.0, 60), (0.0, 'already'))
        needed, status = required_average(100, 40, 4.9, 10)
        self.assertEqual(status, 'impossible')
        self.assertEqual(required_average(100, 40, 4.0, 0), (None, 'impossible'))


class CgpaPageTests(Base):
    def test_add_semester_and_results_then_plan(self):
        self.client.post(reverse('semester_create'), {'name': '200L First'})
        sem = Semester.objects.get(user=self.ada)
        self.client.post(reverse('result_add', args=[sem.pk]), {'code': 'cpe 211', 'units': '3', 'grade': 'a'})
        self.client.post(reverse('result_add', args=[sem.pk]), {'code': 'X', 'units': '99', 'grade': 'A'})  # rejected
        self.client.post(reverse('result_add', args=[sem.pk]), {'code': 'Y', 'units': '3', 'grade': 'Z'})  # rejected
        self.assertEqual(list(sem.results.values_list('code', 'grade')), [('CPE 211', 'A')])
        r = self.client.get(reverse('cgpa_tracker'), {'target': '4.5', 'remaining': '30'})
        self.assertContains(r, '5.00')
        self.assertContains(r, '4.45')  # (4.5 x 33 - 15) / 30
        r = self.client.get(reverse('cgpa_tracker'), {'target': '0.4', 'remaining': '30'})
        self.assertContains(r, 'already on track')

    def test_cannot_touch_someone_elses_semester(self):
        theirs = Semester.objects.create(user=self.bob, name='Bob sem')
        r = self.client.post(reverse('result_add', args=[theirs.pk]), {'code': 'A', 'units': '3', 'grade': 'A'})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.client.post(reverse('semester_delete', args=[theirs.pk])).status_code, 404)

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('cgpa_tracker')).status_code, 302)


class AttendanceTests(Base):
    def setUp(self):
        super().setUp()
        self.course = Course.objects.create(user=self.ada, name='Circuits', code='EEE 201')

    def mark(self, days_ago, attended):
        AttendanceRecord.objects.create(course=self.course, date=self.today - timedelta(days=days_ago), attended=attended)

    def summary(self):
        return next(r for r in attendance_summary(self.ada) if r['course'] == self.course)

    def test_safe_course_counts_classes_you_can_miss(self):
        for i in range(8):
            self.mark(i + 1, True)       # 8/8
        s = self.summary()
        self.assertEqual((s['percent'], s['status'], s['can_miss']), (100, 'safe', 2))  # 8/10 = 80%, 8/11 < 75%

    def test_danger_course_counts_classes_needed(self):
        for i in range(3):
            self.mark(i + 1, True)
        for i in range(3):
            self.mark(i + 10, False)     # 3/6 = 50%
        s = self.summary()
        self.assertEqual(s['status'], 'danger')
        self.assertEqual(s['must_attend'], 6)   # 9/12 = 75%

    def test_exactly_on_the_line_is_edge(self):
        for i in range(3):
            self.mark(i + 1, True)
        self.mark(9, False)              # 3/4 = 75%
        self.assertEqual(self.summary()['status'], 'edge')

    def test_mark_today_then_change_it(self):
        url = reverse('attendance_mark', args=[self.course.pk])
        self.client.post(url, {'attended': '1'})
        self.client.post(url, {'attended': '0'})
        rec = AttendanceRecord.objects.get(course=self.course)
        self.assertFalse(rec.attended)
        self.assertEqual(rec.date, self.today)

    def test_cannot_mark_future_or_others(self):
        url = reverse('attendance_mark', args=[self.course.pk])
        self.client.post(url, {'attended': '1', 'date': (self.today + timedelta(days=1)).isoformat()})
        self.assertFalse(AttendanceRecord.objects.exists())
        other = Course.objects.create(user=self.bob, name='Bob course')
        self.assertEqual(self.client.post(reverse('attendance_mark', args=[other.pk]), {'attended': '1'}).status_code, 404)

    def test_page_warns_when_below_75(self):
        self.mark(1, False)
        r = self.client.get(reverse('attendance'))
        self.assertContains(r, 'Below 75%')
        self.assertContains(r, 'EEE 201 (0%')


class CoachSeesAcademicsTests(Base):
    def test_context_includes_cgpa_and_attendance_risk(self):
        sem = Semester.objects.create(user=self.ada, name='100L First')
        CourseResult.objects.create(semester=sem, code='MTH 101', units=3, grade='B')
        course = Course.objects.create(user=self.ada, name='Circuits', code='EEE 201')
        AttendanceRecord.objects.create(course=course, date=self.today, attended=False)
        ctx = student_context(self.ada)
        self.assertIn('CGPA 4.00 (Second Class Upper)', ctx)
        self.assertIn('ATTENDANCE BELOW 75%', ctx)
        self.assertIn('EEE 201 0%', ctx)
