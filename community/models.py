from django.conf import settings
from django.db import models


class Thread(models.Model):
    """A study-group discussion, loosely grouped by course code (not tied to
    any one user's private Course row, so anyone taking that course can join)."""

    course_code = models.CharField(max_length=20, blank=True)
    title = models.CharField(max_length=200)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='threads'
    )
    is_anonymous = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def starter_name(self):
        if self.is_anonymous:
            return 'Anonymous'
        return self.created_by.username if self.created_by else 'a student'


class Post(models.Model):
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name='posts')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    body = models.TextField()
    is_anonymous = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.user}: {self.body[:30]}'

    @property
    def display_name(self):
        if self.is_anonymous:
            return 'Anonymous'
        return self.user.username if self.user else 'a student'
