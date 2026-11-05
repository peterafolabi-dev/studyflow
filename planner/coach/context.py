"""What the coach knows about the student it's talking to, built fresh on every message.

Only the student's own data goes in, and it's kept short so it doesn't crowd out
the actual conversation.
"""
from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from planner.models import CoachMemory, Course, Flashcard, StudySession, StudyStreak, Task, TimetableEntry

DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


def student_context(user, now=None):
    now = now or timezone.localtime()
    today = now.date()
    lines = [f"Today is {DAYS[today.weekday()]} {today.isoformat()}, {now.strftime('%H:%M')} Lagos time."]

    name = (user.first_name or user.username or '').strip()
    profile = getattr(user, 'profile', None)
    who = [f"Name: {name}"] if name else []
    if profile is not None:
        if profile.university:
            who.append(f"University: {profile.university}")
        if profile.department:
            who.append(f"Department: {profile.department}")
        if profile.level:
            who.append(f"Level: {profile.level}")
        if profile.preferred_study_time and profile.preferred_study_time != 'flexible':
            who.append(f"Prefers to study in the {profile.preferred_study_time}")
        if profile.weekly_study_goal_hours:
            who.append(f"Weekly study goal: {profile.weekly_study_goal_hours}h")
    if who:
        lines.append('; '.join(who) + '.')

    courses = list(Course.objects.filter(user=user).order_by('code', 'name')[:15])
    if courses:
        lines.append('Courses: ' + ', '.join(f"{c.code} {c.name}".strip() for c in courses) + '.')

    open_tasks = Task.objects.filter(course__user=user, is_done=False).select_related('course').order_by('due_date')
    overdue = [t for t in open_tasks if t.due_date < today][:5]
    upcoming = [t for t in open_tasks if today <= t.due_date <= today + timedelta(days=14)][:8]
    if overdue:
        lines.append('OVERDUE: ' + '; '.join(_task(t, today) for t in overdue) + '.')
    if upcoming:
        lines.append('Due in the next 14 days: ' + '; '.join(_task(t, today) for t in upcoming) + '.')
    if not overdue and not upcoming and courses:
        lines.append('No open deadlines in the next 14 days.')

    due_cards = Flashcard.objects.filter(deck__course__user=user, next_review_date__lte=today).count()
    if due_cards:
        lines.append(f"{due_cards} flashcard{'s' if due_cards != 1 else ''} due for review today.")

    week_minutes = (
        StudySession.objects.filter(user=user, created_at__gte=now - timedelta(days=7))
        .aggregate(total=Sum('duration_minutes'))['total'] or 0
    )
    streak = StudyStreak.objects.filter(user=user).first()
    effort = [f"Focused study in the last 7 days: {week_minutes // 60}h {week_minutes % 60}m"]
    if streak and streak.current_streak:
        effort.append(f"current streak {streak.current_streak} day(s)")
    lines.append('; '.join(effort) + '.')

    from planner.academics import attendance_summary, cgpa_summary
    cg = cgpa_summary(user)
    if cg['cgpa'] is not None:
        last = cg['rows'][-1]
        lines.append(f"CGPA {cg['cgpa']:.2f} ({cg['class']}) over {cg['units']} units; last semester GPA "
                     f"{last['gpa']:.2f} ({last['semester'].name})." if last['gpa'] is not None else f"CGPA {cg['cgpa']:.2f} ({cg['class']}).")
    att = [a for a in attendance_summary(user) if a['total']]
    if att:
        low = [a for a in att if a['status'] == 'danger']
        if low:
            lines.append('ATTENDANCE BELOW 75% (exam eligibility at risk): ' + '; '.join(
                f"{a['course'].code or a['course'].name} {a['percent']}% (must attend next {a['must_attend']})" for a in low) + '.')
        else:
            lines.append('Attendance: ' + ', '.join(f"{a['course'].code or a['course'].name} {a['percent']}%" for a in att[:8]) + ' (all at or above 75%).')

    classes = TimetableEntry.objects.filter(user=user, day_of_week=today.weekday()).order_by('start_time')[:6]
    if classes:
        lines.append('Classes today: ' + '; '.join(f"{c.title} {c.start_time:%H:%M}-{c.end_time:%H:%M}" for c in classes) + '.')

    return '\n'.join(lines)


def _task(task, today):
    days = (task.due_date - today).days
    when = 'today' if days == 0 else ('tomorrow' if days == 1 else (f"{-days} days ago" if days < 0 else f"in {days} days"))
    course = task.course.code or task.course.name
    return f"{course}: {task.title} (due {task.due_date.isoformat()}, {when})"


def memory_notes(user):
    notes = CoachMemory.objects.filter(user=user).order_by('-created_at')[:CoachMemory.MAX_PER_USER]
    return '\n'.join(f"- {m.note}" for m in notes)
