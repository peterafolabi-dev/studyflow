from django.contrib.auth.forms import UserCreationForm


class SignUpForm(UserCreationForm):
    """Username + password (with confirmation). Django validates password strength."""

    class Meta(UserCreationForm.Meta):
        fields = ('username',)


from django import forms
from .models import Profile

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['bio', 'department', 'level', 'reading_goal', 'avatar_color']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Tell us about your academic interests...'}),
            'department': forms.TextInput(attrs={'placeholder': 'e.g. Computer Science'}),
        }
        help_texts = {
            'reading_goal': 'How many books do you want to read this year?',
            'avatar_color': 'Choose a number from 0 to 5 to set your theme color.',
        }

