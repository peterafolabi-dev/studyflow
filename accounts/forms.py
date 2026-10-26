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
    """Username + email + password (with confirmation). Django validates password strength.
    Email is required so password-reset emails can reach the user."""

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'autocomplete': 'email'}),
    )

    class Meta(UserCreationForm.Meta):
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.help_text = ''

    def clean_email(self):
        from django.contrib.auth import get_user_model
        email = self.cleaned_data['email'].strip().lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email
from .models import Profile


class ProfileForm(forms.ModelForm):
    # Stored on the user account; needed to receive password-reset emails.
    email = forms.EmailField(
        required=False,
        help_text='Used for password reset emails.',
        widget=forms.EmailInput(attrs={'autocomplete': 'email', 'placeholder': 'you@example.com'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].initial = self.instance.user.email
        # Show email first so it's easy to find.
        self.order_fields(['email'] + [name for name in self.fields if name != 'email'])

    def clean_email(self):
        from django.contrib.auth import get_user_model
        email = self.cleaned_data['email'].strip().lower()
        if email and get_user_model().objects.filter(email__iexact=email).exclude(pk=self.instance.user_id).exists():
            raise forms.ValidationError('Another account already uses this email.')
        return email

    def save(self, commit=True):
        profile = super().save(commit=commit)
        user = profile.user
        if user.email != self.cleaned_data['email']:
            user.email = self.cleaned_data['email']
            user.save(update_fields=['email'])
        return profile

    class Meta:
        model = Profile
        fields = [
            'bio', 'department', 'level', 'reading_goal', 'avatar_color',
            'weekly_study_goal_hours', 'preferred_study_time',
        ]
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Tell us about your academic interests...'}),
            'department': forms.TextInput(attrs={'placeholder': 'e.g. Computer Science'}),
        }
        help_texts = {
            'reading_goal': 'How many books do you want to read this year?',
            'avatar_color': 'Choose a number from 0 to 5 to set your theme color.',
            'weekly_study_goal_hours': 'Used by the study buddy matcher and weekly plan.',
            'preferred_study_time': 'Used to place suggested study blocks at a time that suits you.',
        }

