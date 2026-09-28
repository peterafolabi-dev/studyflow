from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Book(models.Model):
    """A reading-hub item. Levels 100-500 mirror undergraduate course numbering;
    is_postgraduate marks items that belong on the Postgraduate page instead."""

    LEVEL_CHOICES = [
        (100, 'Level 100'),
        (200, 'Level 200'),
        (300, 'Level 300'),
        (400, 'Level 400'),
        (500, 'Level 500'),
    ]

    title = models.CharField(max_length=200)
    author = models.CharField(max_length=150, blank=True)
    subject = models.CharField(max_length=100, blank=True)
    level = models.PositiveSmallIntegerField(choices=LEVEL_CHOICES, default=100)
    is_postgraduate = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    cover_color = models.PositiveSmallIntegerField(default=0)  # 0-5, picks an accent
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['level', 'title']

    def __str__(self):
        return self.title

    @property
    def accent(self):
        return self.cover_color % 6

    @property
    def is_new(self):
        return timezone.now() - self.added_at <= timedelta(days=14)

    @property
    def average_rating(self):
        agg = self.ratings.aggregate(avg=models.Avg('stars'))['avg']
        return round(agg, 1) if agg else None

    @property
    def rating_count(self):
        return self.ratings.count()


class SavedBook(models.Model):
    """Join table for 'My Library' — the books a user has saved from the catalogue,
    plus their reading progress on each one."""

    STATUS_CHOICES = [
        ('to_read', 'To read'),
        ('reading', 'Reading'),
        ('finished', 'Finished'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_books'
    )
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='saved_by')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='to_read')
    saved_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'book')
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.user} \u2192 {self.book}'


class BookRating(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='ratings')
    stars = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'book')

    def __str__(self):
        return f'{self.user} rated {self.book} {self.stars}\u2605'
