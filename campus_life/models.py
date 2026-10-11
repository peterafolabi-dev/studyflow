from django.conf import settings
from django.db import models


class CreditEvent(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='campus_credit_events')
    source_key = models.CharField(max_length=100)
    reason = models.CharField(max_length=40)
    credits = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'source_key'], name='unique_user_credit_source'),
        ]


class CampusProfile(models.Model):
    SKIN_CHOICES = [('#8d5524', 'Deep'), ('#c68642', 'Warm'), ('#e0ac69', 'Golden'), ('#f1c27d', 'Light')]
    HAIR_CHOICES = [('crop', 'Short crop'), ('coils', 'Coils'), ('locs', 'Locs')]
    OUTFIT_CHOICES = [('#2f855a', 'Green'), ('#2563eb', 'Blue'), ('#c2410c', 'Terracotta')]
    ACCESSORY_CHOICES = [('none', 'None'), ('book', 'Book'), ('glasses', 'Glasses')]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='campus_life_profile')
    skin_tone = models.CharField(max_length=12, choices=SKIN_CHOICES, default='#c68642')
    hairstyle = models.CharField(max_length=12, choices=HAIR_CHOICES, default='crop')
    outfit_color = models.CharField(max_length=12, choices=OUTFIT_CHOICES, default='#2f855a')
    accessory = models.CharField(max_length=12, choices=ACCESSORY_CHOICES, default='none')


class SavingsGoal(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='campus_credit_goal')
    title = models.CharField(max_length=80)
    target_credits = models.PositiveIntegerField()
    updated_at = models.DateTimeField(auto_now=True)