"""Numbers behind the CGPA tracker and the attendance tracker (kept free of views so they're easy to test)."""
import math

from .models import AttendanceRecord, Semester

DEGREE_CLASSES = [  # common NUC bands on the 5-point scale; schools can differ slightly
    (4.50, 'First Class'),
    (3.50, 'Second Class Upper'),
    (2.40, 'Second Class Lower'),
    (1.50, 'Third Class'),
    (1.00, 'Pass'),
]


def degree_class(cgpa):
    if cgpa is None:
        return ''
    for floor, name in DEGREE_CLASSES:
        if cgpa >= floor - 1e-9:
            return name
    return 'Below pass'


def cgpa_summary(user):
    semesters = list(Semester.objects.filter(user=user).prefetch_related('results'))
    rows, units, points = [], 0, 0
    for s in semesters:
        u, p = s.totals()
        units += u
        points += p
        rows.append({'semester': s, 'units': u, 'gpa': round(p / u, 2) if u else None,
                     'cgpa': round(points / units, 2) if units else None})
    cgpa = round(points / units, 2) if units else None
    return {'rows': rows, 'units': units, 'points': points, 'cgpa': cgpa, 'class': degree_class(cgpa)}


def required_average(points_so_far, units_so_far, target, remaining_units):
    """Average grade point needed over the remaining units to finish on `target`.
    Returns (needed, status) where status is 'ok', 'already', or 'impossible'."""
    if remaining_units <= 0:
        return None, 'impossible'
    needed = (target * (units_so_far + remaining_units) - points_so_far) / remaining_units
    needed = math.ceil(needed * 100) / 100  # round up: being 0.004 short still misses the target
    if needed <= 0:
        return 0.0, 'already'
    if needed > 5:
        return needed, 'impossible'
    return needed, 'ok'


def attendance_summary(user):
    """Per course: attended / total, percent, and how many more classes can be missed (or must be attended)."""
    req = AttendanceRecord.REQUIRED_PERCENT / 100
    out = []
    courses = user.courses.all().prefetch_related('attendance') if hasattr(user, 'courses') else []
    for course in courses:
        marks = list(course.attendance.all())
        total = len(marks)
        attended = sum(1 for m in marks if m.attended)
        percent = round(100 * attended / total) if total else None
        if total == 0:
            status, can_miss, must_attend = 'none', None, 0
        elif attended / total >= req:
            status = 'safe'
            # largest k with attended / (total + k) >= req
            can_miss = math.floor(attended / req - total + 1e-9)
            must_attend = 0
        else:
            status = 'danger'
            can_miss = 0
            # smallest k with (attended + k) / (total + k) >= req
            must_attend = math.ceil((req * total - attended) / (1 - req) - 1e-9)
        if status == 'safe' and can_miss == 0:
            status = 'edge'
        out.append({'course': course, 'total': total, 'attended': attended, 'percent': percent,
                    'status': status, 'can_miss': can_miss, 'must_attend': must_attend,
                    'today': next((m for m in marks if m.date == _today()), None)})
    return out


def _today():
    from django.utils import timezone
    return timezone.localdate()
