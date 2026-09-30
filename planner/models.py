from datetime import timedelta
from django.conf import settings
from django.db import models
from django.utils import timezone


class Course(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='courses'
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.code} {self.name}'.strip()

    @property
    def color_index(self):
        """Picks one of 6 accent colours so each course looks different."""
        return self.pk % 6


class Task(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=200)
    due_date = models.DateField()
    is_done = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Open tasks first, soonest deadline first.
        ordering = ['is_done', 'due_date', 'title']

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        return not self.is_done and self.due_date < timezone.localdate()

    @property
    def days_left(self):
        return (self.due_date - timezone.localdate()).days


class TimetableEntry(models.Model):
    DAY_CHOICES = [
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'),
        (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='timetable_entries'
    )
    course = models.ForeignKey(
        Course, on_delete=models.SET_NULL, null=True, blank=True, related_name='timetable_entries'
    )
    title = models.CharField(max_length=100)
    day_of_week = models.PositiveSmallIntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    location = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['day_of_week', 'start_time']

    def __str__(self):
        return f'{self.title} ({self.get_day_of_week_display()})'


class StudySession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='study_sessions')
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name='study_sessions')
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True, related_name='study_sessions')
    duration_minutes = models.PositiveIntegerField()
    date = models.DateField(auto_now_add=True)


class FlashcardDeck(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='flashcard_decks')
    title = models.CharField(max_length=200)

    def __str__(self):
        return self.title

    @property
    def due_cards_count(self):
        return self.cards.filter(next_review_date__lte=timezone.localdate()).count()


class Flashcard(models.Model):
    deck = models.ForeignKey(FlashcardDeck, on_delete=models.CASCADE, related_name='cards')
    front = models.TextField()
    back = models.TextField()
    repetitions = models.PositiveIntegerField(default=0)
    interval_days = models.PositiveIntegerField(default=1)
    ease_factor = models.FloatField(default=2.5)
    next_review_date = models.DateField(default=timezone.localdate)
    last_reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['next_review_date', 'id']

    def __str__(self):
        return f"{self.front[:30]} ({self.deck.title})"

    @property
    def is_due(self):
        return self.next_review_date <= timezone.localdate()

    def process_review(self, rating):
        """
        Applies SM-2 spaced repetition algorithm.
        rating: 'hard', 'medium', or 'easy'
        """
        today = timezone.localdate()
        self.last_reviewed_at = timezone.now()

        rating = str(rating).lower().strip()
        if rating == 'hard':
            self.repetitions = 0
            self.interval_days = 1
            self.ease_factor = max(1.3, self.ease_factor - 0.2)
        elif rating == 'medium':
            self.repetitions += 1
            if self.repetitions == 1:
                self.interval_days = 1
            elif self.repetitions == 2:
                self.interval_days = 3
            else:
                self.interval_days = max(1, round(self.interval_days * self.ease_factor))
        elif rating == 'easy':
            self.repetitions += 1
            self.ease_factor = min(3.0, self.ease_factor + 0.15)
            if self.repetitions == 1:
                self.interval_days = 2
            elif self.repetitions == 2:
                self.interval_days = 6
            else:
                self.interval_days = max(1, round(self.interval_days * self.ease_factor * 1.2))

        self.next_review_date = today + timedelta(days=self.interval_days)
        self.save(update_fields=['repetitions', 'interval_days', 'ease_factor', 'next_review_date', 'last_reviewed_at'])
        return self.next_review_date
