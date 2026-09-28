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

