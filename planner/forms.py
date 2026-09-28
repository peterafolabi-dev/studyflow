from django import forms

from .models import Course, Task, TimetableEntry


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['name', 'code']
        labels = {'name': 'Course name', 'code': 'Course code (optional)'}
        widgets = {
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
        labels = {'title': 'Class / activity'}
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'e.g. CPE 205 Lecture'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
            'location': forms.TextInput(attrs={'placeholder': 'e.g. LT 2'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['course'].queryset = Course.objects.filter(user=user)
        self.fields['course'].required = False
