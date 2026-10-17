from django.conf import settings
from django.db import models
from django.utils import timezone


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
    career_title = models.CharField(max_length=40, default='Fresher')
    career_celebration_pending = models.BooleanField(default=False)
    game_wallet = models.PositiveIntegerField(default=25000)
    energy = models.PositiveSmallIntegerField(default=80)
    hunger = models.PositiveSmallIntegerField(default=75)
    community = models.PositiveSmallIntegerField(default=45)
    wellbeing = models.PositiveSmallIntegerField(default=70)
    game_day = models.PositiveIntegerField(default=1)
    actions_today = models.PositiveSmallIntegerField(default=0)
    last_game_date = models.DateField(null=True, blank=True)
    game_location = models.CharField(max_length=40, default='Campus')
    mission_claim_day = models.PositiveIntegerField(default=0)


class SavingsGoal(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='campus_credit_goal')
    title = models.CharField(max_length=80)
    target_credits = models.PositiveIntegerField()
    updated_at = models.DateTimeField(auto_now=True)


class CampusGameLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='campus_game_logs')
    action_code = models.CharField(max_length=24)
    message = models.CharField(max_length=180)
    wallet_delta = models.IntegerField(default=0)
    game_day = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']
