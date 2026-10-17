from django.conf import settings
from django.contrib import messages
from django.contrib.auth.signals import user_logged_in
from django.db import models
from django.dispatch import receiver


class Profile(models.Model):
    UNIVERSITY_CHOICES = [
        ('FUT Minna', 'Federal University of Technology, Minna'),
        ('UNILAG', 'University of Lagos'),
        ('UI', 'University of Ibadan'),
        ('ABU', 'Ahmadu Bello University'),
        ('OAU', 'Obafemi Awolowo University'),
        ('FUTA', 'Federal University of Technology, Akure'),
        ('UNIBEN', 'University of Benin'),
        ('UNIPORT', 'University of Port Harcourt'),
        ('BUK', 'Bayero University Kano'),
        ('Other', 'Other University'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    bio = models.CharField(max_length=280, blank=True)
    department = models.CharField(max_length=120, blank=True)
    level = models.PositiveSmallIntegerField(choices=[
        (100, 'Level 100'), (200, 'Level 200'), (300, 'Level 300'),
        (400, 'Level 400'), (500, 'Level 500')
    ], blank=True, null=True)
    reading_goal = models.PositiveIntegerField(default=12)
    avatar_color = models.PositiveSmallIntegerField(default=0)
    weekly_study_goal_hours = models.PositiveSmallIntegerField(default=8)
    preferred_study_time = models.CharField(
        max_length=12,
        choices=[
            ('morning', 'Morning'), ('afternoon', 'Afternoon'),
            ('evening', 'Evening'), ('flexible', 'Flexible'),
        ],
        default='flexible',
    )
    university = models.CharField(max_length=60, choices=UNIVERSITY_CHOICES, default='FUT Minna')
    spotify_playlist_url = models.URLField(max_length=300, blank=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"



class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=255)
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user.username}: {self.message[:30]}"


class LoginRecord(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='login_records')
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    login_method = models.CharField(max_length=50, default='password')

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Login Record'
        verbose_name_plural = 'Login Records'

    def __str__(self):
        return f"{self.user.username} logged in at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"


class UserPresence(models.Model):
    """Most recent authenticated activity, used for a short online window."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='presence')
    last_seen = models.DateTimeField(db_index=True)

    class Meta:
        verbose_name_plural = 'User presence'

    def __str__(self):
        return f"{self.user.username} last seen {self.last_seen}"


@receiver(user_logged_in)
def record_user_login(sender, request, user, **kwargs):
    is_first_login = not LoginRecord.objects.filter(user=user).exists()
    ip = None
    user_agent = ''
    login_method = 'password'
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]
        if hasattr(request, 'path') and 'google' in str(request.path).lower():
            login_method = 'google_oauth'
        elif hasattr(request, 'sociallogin'):
            login_method = 'google_oauth'
    LoginRecord.objects.create(
        user=user,
        ip_address=ip,
        user_agent=user_agent,
        login_method=login_method
    )
    if request and hasattr(request, '_messages'):
        welcome = (
            f"Welcome to StudyFlow, {user.username}! Let's get started."
            if is_first_login else f'Welcome back, {user.username}!'
        )
        messages.success(request, welcome)
