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

from django.conf import settings

class StudyBuddyRequest(models.Model):
    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='buddy_requests_sent')
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='buddy_requests_received')
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

class ThreadVote(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name='votes')
    value = models.SmallIntegerField() # 1 or -1
    
    class Meta:
        unique_together = ('user', 'thread')

class ChatMessage(models.Model):
    room = models.CharField(max_length=50, default="global")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


# ── Phase 6: Moderation ──────────────────────────────────────────────────────

class PostReport(models.Model):
    REASONS = [
        ('spam', 'Spam'),
        ('harassment', 'Harassment'),
        ('inappropriate', 'Inappropriate content'),
        ('misinformation', 'Misinformation'),
        ('other', 'Other'),
    ]
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reports_made')
    post = models.ForeignKey('community.Post', on_delete=models.CASCADE, related_name='reports')
    reason = models.CharField(max_length=30, choices=REASONS, default='other')
    detail = models.CharField(max_length=300, blank=True)
    reviewed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('reporter', 'post')

    def __str__(self):
        return f"Report by {self.reporter.username} on post {self.post_id}"


class MutedUser(models.Model):
    """User A mutes User B — A won't see B's posts/messages."""
    muter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='muting')
    muted = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='muted_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('muter', 'muted')

    def __str__(self):
        return f"{self.muter.username} muted {self.muted.username}"


# ── Phase 7: Feedback ────────────────────────────────────────────────────────

class Feedback(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='feedback'
    )
    rating = models.PositiveSmallIntegerField(
        choices=[(1,'⭐'),(2,'⭐⭐'),(3,'⭐⭐⭐'),(4,'⭐⭐⭐⭐'),(5,'⭐⭐⭐⭐⭐')]
    )
    message = models.TextField(max_length=1000, blank=True)
    page = models.CharField(max_length=200, blank=True, help_text='URL path where feedback was submitted')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Feedback'

    def __str__(self):
        return f"{'⭐'*self.rating} from {self.user.username if self.user else 'anonymous'}"

