import os

with open('accounts/forms.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_signup = '''class SignUpForm(UserCreationForm):
    """Username + password (with confirmation). Django validates password strength."""

    class Meta(UserCreationForm.Meta):
        fields = ('username',)
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.help_text = ''
'''

content = content.replace('''class SignUpForm(UserCreationForm):
    """Username + password (with confirmation). Django validates password strength."""

    class Meta(UserCreationForm.Meta):
        fields = ('username',)''', new_signup)

with open('accounts/forms.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Updated SignUpForm help texts!')
