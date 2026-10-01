from django import forms
from django.contrib.auth.forms import UserCreationForm


class LoginForm(forms.Form):
    """Simple username + password login form that works with ModelBackend."""
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'autofocus': True, 'autocomplete': 'username'}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),
    )


class SignUpForm(UserCreationForm):
    """Username + password (with confirmation). Django validates password strength."""

    class Meta(UserCreationForm.Meta):
        fields = ('username',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.help_text = ''
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

