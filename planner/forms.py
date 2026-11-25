from django import forms

from .models import Course, Task, TimetableEntry


import re

COURSE_LINE_RE = re.compile(r'^\s*([A-Za-z]{2,5}\s?-?\d{3}[A-Za-z]?)\s*[:\-–]?\s*(.*)$')


def parse_course_line(line):
    """'EEE 301 Signals and Systems' -> ('EEE 301', 'Signals and Systems'). A bare name has no code."""
    line = (line or '').strip()
    match = COURSE_LINE_RE.match(line)
    if match and match.group(2).strip():
        code = re.sub(r'\s*-\s*', ' ', match.group(1)).upper()
        code = re.sub(r'^([A-Z]+)(\d)', r'\1 \2', code)
        return code[:20], match.group(2).strip()[:100]
    if match:  # only a code, e.g. 'MTH 101': use it as the name too
        code = match.group(1).upper()
        code = re.sub(r'^([A-Z]+)(\d)', r'\1 \2', code)
        return code[:20], code
    return '', line[:100]


def find_or_create_course(user, text):
    """Returns (course, created) for a typed course like 'CSC 201 Data Structures'."""
    code, name = parse_course_line(text)
    if not name:
        return None, False
    existing = Course.objects.filter(user=user)
    match = None
    if code:
        match = existing.filter(code__iexact=code).first()
    if match is None:
        match = existing.filter(name__iexact=name).first()
    if match:
        return match, False
    return Course.objects.create(user=user, name=name, code=code), True


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['name', 'code', 'exam_date']
        labels = {'name': 'Course name', 'code': 'Course code (optional)', 'exam_date': 'Exam date (optional)'}
        widgets = {
            'exam_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'name': forms.TextInput(attrs={'placeholder': 'e.g. Signals and Systems'}),
            'code': forms.TextInput(attrs={'placeholder': 'e.g. EEE 301'}),
        }


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'due_date']
        labels = {'title': 'Task', 'due_date': 'Due date'}
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'e.g. Assignment 2'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }


class TimetableEntryForm(forms.ModelForm):
    class Meta:
        model = TimetableEntry
        fields = ['title', 'course', 'day_of_week', 'start_time', 'end_time', 'location']
        labels = {'title': 'Class name (optional)', 'course': 'Course'}
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'e.g. CPE 205 Lecture'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
            'location': forms.TextInput(attrs={'placeholder': 'e.g. LT 2'}),
        }

    new_course = forms.CharField(
        required=False, max_length=120, label='Not in the list? Type a new course',
        widget=forms.TextInput(attrs={'placeholder': 'e.g. CSC 201 Data Structures'}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user is not None:
            self.fields['course'].queryset = Course.objects.filter(user=user)
        self.fields['course'].required = False
        self.fields['course'].empty_label = 'Choose a course (or type a new one below)'
        self.fields['title'].required = False
        self.fields['title'].widget.attrs['placeholder'] = 'Optional, e.g. CPE 205 Lecture'
        self.fields['start_time'].initial = '08:00'
        self.fields['end_time'].initial = '10:00'
        self.fields['start_time'].widget.format = '%H:%M'
        self.fields['end_time'].widget.format = '%H:%M'
        self.order_fields(['course', 'new_course', 'title', 'day_of_week', 'start_time', 'end_time', 'location'])

    def clean(self):
        data = super().clean()
        start, end = data.get('start_time'), data.get('end_time')
        if start and end and end <= start:
            self.add_error('end_time', 'The class must end after it starts.')
        typed = (data.get('new_course') or '').strip()
        if typed and not data.get('course') and self.user is not None and not self.errors.get('end_time'):
            course, _ = find_or_create_course(self.user, typed)
            data['course'] = course
        if not (data.get('title') or '').strip():
            course = data.get('course')
            if course:
                data['title'] = f'{course.code} {course.name}'.strip() if course.code and course.code not in course.name else course.name
            else:
                self.add_error('title', 'Choose a course or give this class a name.')
        return data
