import re

for filename in ['templates/accounts/login.html', 'templates/accounts/signup.html']:
    with open(filename, 'r', encoding='utf-8') as f:
        text = f.read()
    
    if '{% load socialaccount %}' not in text:
        text = text.replace('{% extends \'base_auth.html\' %}', '{% extends \'base_auth.html\' %}\n{% load socialaccount %}')
    
    text = re.sub(r'<a href="#"(.*?>.*?Continue with Google.*?</a>)', r'<a href="{% provider_login_url \'google\' %}"\1', text, flags=re.DOTALL)
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(text)
print('Updated templates')
