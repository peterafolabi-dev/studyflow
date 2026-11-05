"""CGPA tracker and attendance tracker pages."""
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .academics import attendance_summary, cgpa_summary, degree_class, required_average
from .models import GRADE_POINTS, AttendanceRecord, Course, CourseResult, Semester


def _float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ---------- CGPA tracker ----------

@login_required
def cgpa_tracker(request):
    summary = cgpa_summary(request.user)
    target = _float(request.GET.get('target'))
    remaining = _int(request.GET.get('remaining'))
    plan = None
    if target is not None and remaining is not None and 0 < target <= 5 and remaining > 0:
        needed, status = required_average(summary['points'], summary['units'], target, remaining)
        plan = {'target': target, 'remaining': remaining, 'needed': needed, 'status': status,
                'target_class': degree_class(target)}
    return render(request, 'planner/cgpa_tracker.html', {
        'summary': summary, 'plan': plan, 'grades': list(GRADE_POINTS.keys()),
        'target_value': request.GET.get('target', '4.50'), 'remaining_value': request.GET.get('remaining', ''),
    })


@login_required
@require_POST
def semester_create(request):
    name = request.POST.get('name', '').strip()[:80]
    if not name:
        messages.error(request, 'Give the semester a name, e.g. "100 Level · First Semester".')
        return redirect('cgpa_tracker')
    order = Semester.objects.filter(user=request.user).count()
    Semester.objects.create(user=request.user, name=name, order=order)
    messages.success(request, f'Added {name}. Now add its courses.')
    return redirect('cgpa_tracker')


@login_required
@require_POST
def semester_delete(request, pk):
    semester = get_object_or_404(Semester, pk=pk, user=request.user)
    semester.delete()
    messages.success(request, f'Deleted {semester.name}.')
    return redirect('cgpa_tracker')


@login_required
@require_POST
def result_add(request, pk):
    semester = get_object_or_404(Semester, pk=pk, user=request.user)
    code = request.POST.get('code', '').strip().upper()[:20]
    units = _int(request.POST.get('units'))
    grade = request.POST.get('grade', '').strip().upper()
    if not code or units is None or not 0 < units <= 10 or grade not in GRADE_POINTS:
        messages.error(request, 'Enter a course code, units between 1 and 10, and a grade from A to F.')
    else:
        CourseResult.objects.create(semester=semester, code=code, units=units, grade=grade)
    return redirect(f"{_cgpa_url()}#semester-{semester.pk}")


@login_required
@require_POST
def result_delete(request, pk):
    result = get_object_or_404(CourseResult, pk=pk, semester__user=request.user)
    sem = result.semester_id
    result.delete()
    return redirect(f"{_cgpa_url()}#semester-{sem}")


def _cgpa_url():
    from django.urls import reverse
    return reverse('cgpa_tracker')


# ---------- Attendance ----------

@login_required
def attendance(request):
    rows = attendance_summary(request.user)
    recent = AttendanceRecord.objects.filter(course__user=request.user).select_related('course')[:15]
    at_risk = [r for r in rows if r['status'] == 'danger']
    return render(request, 'planner/attendance.html', {
        'rows': rows, 'recent': recent, 'at_risk': at_risk, 'required': AttendanceRecord.REQUIRED_PERCENT,
        'today': timezone.localdate(),
    })


@login_required
@require_POST
def attendance_mark(request, course_pk):
    course = get_object_or_404(Course, pk=course_pk, user=request.user)
    attended = request.POST.get('attended') == '1'
    try:
        day = date.fromisoformat(request.POST.get('date') or timezone.localdate().isoformat())
    except ValueError:
        day = timezone.localdate()
    if day > timezone.localdate():
        messages.error(request, "You can't mark a class that hasn't happened yet.")
        return redirect('attendance')
    AttendanceRecord.objects.update_or_create(course=course, date=day, defaults={'attended': attended})
    label = course.code or course.name
    messages.success(request, f"{label}: marked {'present' if attended else 'absent'} for {day:%a %d %b}.")
    return redirect('attendance')


@login_required
@require_POST
def attendance_delete(request, pk):
    record = get_object_or_404(AttendanceRecord, pk=pk, course__user=request.user)
    record.delete()
    return redirect('attendance')
