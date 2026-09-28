import os

with open('studyflow/settings.py', 'r') as f:
    content = f.read()

if 'import dj_database_url' not in content:
    content = content.replace('import os\nfrom pathlib import Path\n', 'import os\nfrom pathlib import Path\nimport dj_database_url\n')

content = content.replace(
    "ALLOWED_HOSTS = [h for h in os.environ.get('ALLOWED_HOSTS', '').split(',') if h] or (['*'] if DEBUG else [])",
    "ALLOWED_HOSTS = [h.strip() for h in os.environ.get('ALLOWED_HOSTS', '').split(',') if h.strip()] or (['*'] if DEBUG else [])\nCSRF_TRUSTED_ORIGINS = [f'https://{h.strip()}' for h in os.environ.get('ALLOWED_HOSTS', '').split(',') if h.strip()]"
)

content = content.replace(
    "'django.middleware.security.SecurityMiddleware',",
    "'django.middleware.security.SecurityMiddleware',\n    'whitenoise.middleware.WhiteNoiseMiddleware',"
)

old_databases = """DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}"""
new_databases = """DATABASES = {
    'default': dj_database_url.config(default=f'sqlite:///{BASE_DIR / "db.sqlite3"}')
}"""
content = content.replace(old_databases, new_databases)

old_mailers = """MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.console.EmailBackend',
    },
}"""
new_settings = """if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
    EMAIL_HOST = os.environ.get('EMAIL_HOST')
    EMAIL_PORT = os.environ.get('EMAIL_PORT', 587)
    EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
    EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
    
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

STORAGES = {
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}"""
content = content.replace(old_mailers, new_settings)

with open('studyflow/settings.py', 'w') as f:
    f.write(content)
print('Settings updated!')
