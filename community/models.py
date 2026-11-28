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
    text = models.CharField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    reply_to = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='replies')
    edited_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)
    attachment = models.FileField(upload_to='chat/%Y/%m/', null=True, blank=True)
    attachment_name = models.CharField(max_length=200, blank=True)
    attachment_kind = models.CharField(max_length=10, blank=True)   # '', 'image' or 'file'
    forwarded_from = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ['-created_at']


class ChatReaction(models.Model):
    EMOJIS = ['👍', '❤️', '😂', '🙏', '🔥', '😮']

    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    emoji = models.CharField(max_length=8)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['message', 'user', 'emoji'], name='one_reaction_per_emoji_per_user')]


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
    reply = models.TextField(max_length=1000, blank=True, help_text='Your reply. The student sees it and gets a notification.')
    replied_at = models.DateTimeField(null=True, blank=True)
    replied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='feedback_replies')

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Feedback'

    def __str__(self):
        return f"{'⭐'*self.rating} from {self.user.username if self.user else 'anonymous'}"



class ChatPoll(models.Model):
    message = models.OneToOneField(ChatMessage, on_delete=models.CASCADE, related_name='poll')


class ChatPollOption(models.Model):
    poll = models.ForeignKey(ChatPoll, on_delete=models.CASCADE, related_name='options')
    text = models.CharField(max_length=80)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['position', 'id']


class ChatPollVote(models.Model):
    option = models.ForeignKey(ChatPollOption, on_delete=models.CASCADE, related_name='votes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['option', 'user'], name='one_vote_per_option_per_user')]


class SavedChat(models.Model):
    """A private bookmark: a snapshot of a chat message, so it survives the original being deleted."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_chats')
    source = models.ForeignKey(ChatMessage, null=True, blank=True, on_delete=models.SET_NULL, related_name='saved_by')
    text = models.CharField(max_length=1000, blank=True)
    author = models.CharField(max_length=150)
    room = models.CharField(max_length=50, default='global')
    attachment_name = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class ChatRoomConfig(models.Model):
    """Admin-editable rules for a room. No row means normal open chat."""
    slug = models.CharField(max_length=50, unique=True)
    announcements_only = models.BooleanField(default=False, help_text='Only staff can post; everyone can read and react.')
    slow_mode_seconds = models.PositiveSmallIntegerField(default=0, help_text='Seconds a student must wait between messages (0 = off). Staff are exempt.')

    def __str__(self):
        return self.slug


class DirectMessage(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='dm_sent')
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='dm_received')
    text = models.CharField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['id']
        indexes = [models.Index(fields=['recipient', 'read_at']), models.Index(fields=['sender', 'recipient', 'id'])]

    def __str__(self):
        return f"{self.sender} -> {self.recipient}: {self.text[:30]}"
