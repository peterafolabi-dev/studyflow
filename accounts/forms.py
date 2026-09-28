from django.contrib.auth.forms import UserCreationForm


class SignUpForm(UserCreationForm):
    """Username + password (with confirmation). Django validates password strength."""

    class Meta(UserCreationForm.Meta):
        fields = ('username',)
