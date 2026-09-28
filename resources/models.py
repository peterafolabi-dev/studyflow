from django.conf import settings
from django.db import models
from django.utils import timezone


class Resource(models.Model):
    """A study material students can browse, upload and download:
    past questions, notes, theses/papers, or lecture slides."""

    TYPE_CHOICES = [
        ('past_question', 'Past Question'),
        ('notes', 'Notes'),
        ('thesis', 'Thesis'),
        ('paper', 'Research Paper'),
        ('lecture_slide', 'Lecture Slide'),
    ]

    title = models.CharField(max_length=200)
    course_code = models.CharField(max_length=20, blank=True)
    resource_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to='resources/%Y/%m/', blank=True, null=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='resources',
    )
    download_count = models.PositiveIntegerField(default=0)
    last_downloaded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def is_research(self):
        return self.resource_type in ('thesis', 'paper')

    @property
    def average_rating(self):
        agg = self.ratings.aggregate(avg=models.Avg('stars'))['avg']
        return round(agg, 1) if agg else None

    @property
    def rating_count(self):
        return self.ratings.count()


class PhysicalHolding(models.Model):
    """A demo listing of physical books held at the IBB Library (FUT Minna)."""

    title = models.CharField(max_length=200)
    author = models.CharField(max_length=150, blank=True)
    category = models.CharField(max_length=100, blank=True)
    shelf_location = models.CharField(max_length=100, blank=True)
    is_available = models.BooleanField(default=True)

    class Meta:
        ordering = ['category', 'title']

    def __str__(self):
        return self.title


class Loan(models.Model):
    """A borrow record for a physical IBB Library holding."""

    LOAN_PERIOD_DAYS = 14

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='loans'
    )
    holding = models.ForeignKey(PhysicalHolding, on_delete=models.CASCADE, related_name='loans')
    borrowed_at = models.DateTimeField(auto_now_add=True)
    due_at = models.DateTimeField()
    returned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-borrowed_at']

    def __str__(self):
        return f'{self.user} \u2192 {self.holding} (due {self.due_at:%d %b})'

    @property
    def is_returned(self):
        return self.returned_at is not None

    @property
    def is_overdue(self):
        return not self.is_returned and timezone.now() > self.due_at


class ResourceRating(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name='ratings')
    stars = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'resource')


class ResourceComment(models.Model):
    """A quick question/comment thread directly under one resource — lighter
    weight than a full Study Group discussion."""

    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.user}: {self.body[:30]}'
