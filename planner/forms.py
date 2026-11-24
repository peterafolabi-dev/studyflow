from django import forms

from .models import Course, Task, TimetableEntry


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
    """One class that can repeat on several days, for a course you pick or add on the spot."""
    days = forms.MultipleChoiceField(
        choices=TimetableEntry.DAY_CHOICES, widget=forms.CheckboxSelectMultiple, label='Days',
        error_messages={'required': 'Pick at least one day.'},
    )
    new_course_code = forms.CharField(
        max_length=20, required=False, label='Course code',
        widget=forms.TextInput(attrs={'placeholder': 'e.g. CPE 205'}),
    )
    new_course_name = forms.CharField(
        max_length=100, required=False, label='Course name',
        widget=forms.TextInput(attrs={'placeholder': 'e.g. Digital Logic Design'}),
    )

    class Meta:
        model = TimetableEntry
        fields = ['course', 'title', 'start_time', 'end_time', 'location']
        labels = {'title': 'Class name (optional)'}
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'e.g. Lecture, Tutorial, Lab'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
            'end_time': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
            'location': forms.TextInput(attrs={'placeholder': 'e.g. LT 2, ETF Hall'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user is not None:
            self.fields['course'].queryset = Course.objects.filter(user=user)
        self.fields['course'].required = False
        self.fields['course'].empty_label = 'Choose a course you added'
        self.fields['title'].required = False

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get('start_time'), cleaned.get('end_time')
        if start and end and end <= start:
            self.add_error('end_time', 'End time must be after the start time.')
        code = (cleaned.get('new_course_code') or '').strip()
        name = (cleaned.get('new_course_name') or '').strip()
        if cleaned.get('course') is None:
            if code or name:
                cleaned['new_course_code'], cleaned['new_course_name'] = code, name or code
            elif not (cleaned.get('title') or '').strip():
                self.add_error('course', 'Choose a course, add a new one below, or type a class name.')
        return cleaned

    def resolve_course(self):
        """The chosen course, or a new/existing one from the 'add a course' boxes."""
        course = self.cleaned_data.get('course')
        if course is not None:
            return course
        code = self.cleaned_data.get('new_course_code', '')
        name = self.cleaned_data.get('new_course_name', '')
        if not (code or name):
            return None
        existing = Course.objects.filter(user=self.user, code__iexact=code).first() if code else None
        existing = existing or Course.objects.filter(user=self.user, name__iexact=name).first()
        return existing or Course.objects.create(user=self.user, code=code, name=name)
