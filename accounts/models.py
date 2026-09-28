from django.db import models

# Create your models here.

from django.conf import settings

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    bio = models.CharField(max_length=280, blank=True)
    department = models.CharField(max_length=120, blank=True)
    level = models.PositiveSmallIntegerField(choices=[
        (100, 'Level 100'), (200, 'Level 200'), (300, 'Level 300'),
        (400, 'Level 400'), (500, 'Level 500')
    ], blank=True, null=True)
    reading_goal = models.PositiveIntegerField(default=12)
    avatar_color = models.PositiveSmallIntegerField(default=0)

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
