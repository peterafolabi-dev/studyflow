import os

# 1. Accounts Models (Profile & Notification)
with open('accounts/models.py', 'r', encoding='utf-8') as f:
    acc_models = f.read()

if 'class Profile' not in acc_models:
    new_acc_models = '''
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
'''
    with open('accounts/models.py', 'a', encoding='utf-8') as f:
        f.write(new_acc_models)

# 2. Planner Models (StudySession, FlashcardDeck, Flashcard)
with open('planner/models.py', 'r', encoding='utf-8') as f:
    plan_models = f.read()

if 'class StudySession' not in plan_models:
    new_plan_models = '''
from django.conf import settings

class StudySession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='study_sessions')
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name='study_sessions')
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True, related_name='study_sessions')
    duration_minutes = models.PositiveIntegerField()
    date = models.DateField(auto_now_add=True)

class FlashcardDeck(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='flashcard_decks')
    title = models.CharField(max_length=200)

class Flashcard(models.Model):
    deck = models.ForeignKey(FlashcardDeck, on_delete=models.CASCADE, related_name='cards')
    front = models.TextField()
    back = models.TextField()
'''
    with open('planner/models.py', 'a', encoding='utf-8') as f:
        f.write(new_plan_models)

# 3. Community Models (StudyBuddyRequest, ThreadVote)
with open('community/models.py', 'r', encoding='utf-8') as f:
    comm_models = f.read()

if 'class StudyBuddyRequest' not in comm_models:
    new_comm_models = '''
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
'''
    with open('community/models.py', 'a', encoding='utf-8') as f:
        f.write(new_comm_models)

print('Models added successfully.')
