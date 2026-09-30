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


class QuestionBank(models.Model):
    """A collection of CBT practice questions, typically generated from past questions or course materials."""

    course = models.ForeignKey(
        'planner.Course', on_delete=models.SET_NULL, null=True, blank=True, related_name='question_banks'
    )
    course_code = models.CharField(max_length=20, blank=True)
    resource = models.ForeignKey(
        Resource, on_delete=models.SET_NULL, null=True, blank=True, related_name='question_banks'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_question_banks'
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    time_limit_minutes = models.PositiveIntegerField(default=15)
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.course_code or 'General'} - {self.title}"

    @property
    def question_count(self):
        return self.questions.count()


class CBTQuestion(models.Model):
    """An individual multiple-choice question belonging to a CBT Question Bank."""

    bank = models.ForeignKey(QuestionBank, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    option_a = models.CharField(max_length=500)
    option_b = models.CharField(max_length=500)
    option_c = models.CharField(max_length=500)
    option_d = models.CharField(max_length=500)
    correct_option = models.CharField(
        max_length=1,
        choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')]
    )
    explanation = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"Q{self.order + 1}: {self.text[:50]}"

    def get_option_text(self, letter):
        mapping = {
            'A': self.option_a,
            'B': self.option_b,
            'C': self.option_c,
            'D': self.option_d,
        }
        return mapping.get(str(letter).upper(), '')


class TestAttempt(models.Model):
    """Records a student's timed practice test attempt with scores and answers."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='test_attempts'
    )
    bank = models.ForeignKey(
        QuestionBank, on_delete=models.CASCADE, related_name='attempts'
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    time_taken_seconds = models.PositiveIntegerField(default=0)
    score = models.PositiveIntegerField(default=0)
    total_questions = models.PositiveIntegerField(default=0)
    answers = models.JSONField(default=dict)  # {"<question_id>": "A"}
    is_completed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.user} - {self.bank.title} ({self.score}/{self.total_questions})"

    @property
    def percentage(self):
        if not self.total_questions:
            return 0
        return round((self.score / self.total_questions) * 100)

    @property
    def formatted_time(self):
        mins = self.time_taken_seconds // 60
        secs = self.time_taken_seconds % 60
        if mins > 0:
            return f"{mins}m {secs}s"
        return f"{secs}s"

    @property
    def passed(self):
        return self.percentage >= 50

    def get_detailed_results(self):
        """Returns a list of dicts with question, user choice, correct option, whether correct, and explanation."""
        questions = list(self.bank.questions.all())
        results = []
        for q in questions:
            user_choice = self.answers.get(str(q.id))
            is_correct = (user_choice == q.correct_option)
            results.append({
                'question': q,
                'user_choice': user_choice,
                'user_choice_text': q.get_option_text(user_choice) if user_choice else 'Not Answered',
                'correct_option': q.correct_option,
                'correct_option_text': q.get_option_text(q.correct_option),
                'is_correct': is_correct,
                'explanation': q.explanation,
            })
        return results
