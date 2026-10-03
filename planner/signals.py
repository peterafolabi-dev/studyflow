from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from .models import Course, Task, FlashcardDeck, Flashcard, StudyStreak

User = get_user_model()

@receiver(post_save, sender=User)
def create_demo_content_for_new_user(sender, instance, created, **kwargs):
    if created:
        # Create a StudyStreak object
        StudyStreak.objects.get_or_create(user=instance)

        # Create Demo Course
        course = Course.objects.create(
            user=instance,
            code='DEMO 101',
            name='Introduction to StudyFlow',
            instructor='AI Study Coach',
            description='A sample course to help you explore StudyFlow.'
        )

        # Create a sample task due tomorrow
        Task.objects.create(
            course=course,
            title='Complete StudyFlow Onboarding',
            due_date=timezone.localdate() + timedelta(days=1),
            is_done=False
        )

        # Create a Flashcard Deck
        deck = FlashcardDeck.objects.create(
            course=course,
            title='StudyFlow Core Concepts'
        )

        # Add 5 Sample Flashcards
        cards = [
            ("What is the Spaced Repetition (SM-2) algorithm?", "A memory algorithm that schedules flashcard reviews right before you're about to forget them, maximizing retention."),
            ("Where can I chat with other students on the platform?", "In the Campus Chat or inside specific Study Groups."),
            ("How do I earn XP in StudyFlow?", "By completing tasks, reviewing flashcards, and running Pomodoro sessions."),
            ("What is the IBB Library?", "A central hub to search, save, and read university lecture slides and past papers."),
            ("How long is a standard Pomodoro session?", "25 minutes of deep focus followed by a 5-minute break.")
        ]

        for front, back in cards:
            Flashcard.objects.create(
                deck=deck,
                front=front,
                back=back,
                next_review_date=timezone.localdate()
            )
