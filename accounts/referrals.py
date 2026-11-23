"""Invite links: remember who invited a new student and reward the inviter."""
import re

from django.urls import reverse

CODE_RE = re.compile(r'^[a-z0-9]{4,16}$')
SESSION_KEY = 'referral_code'
BADGE_TARGET = 3
BADGE_SLUG = 'invite-3'


def capture_referral(request):
    """Remember ?ref=CODE in the session (only well-formed codes)."""
    code = (request.GET.get('ref') or '').strip().lower()
    if CODE_RE.match(code):
        request.session[SESSION_KEY] = code


def attach_referrer(request, user):
    """Link a brand-new user to whoever invited them. Never self-referral, never overwrites."""
    from .models import Profile

    code = request.session.pop(SESSION_KEY, None) if hasattr(request, 'session') else None
    if not code:
        return None
    referrer = Profile.objects.filter(referral_code=code).select_related('user').first()
    if not referrer or referrer.user_id == user.pk:
        return None
    profile = user.profile
    if profile.referred_by_id:
        return None
    profile.referred_by = referrer.user
    profile.save(update_fields=['referred_by'])
    return referrer.user


def verified_referral_count(user):
    from .models import Profile

    return Profile.objects.filter(referred_by=user, email_verified=True).count()


def award_referral_badge(user):
    """Gives the 'Squad Builder' badge at 3 verified friends. Safe to call repeatedly."""
    from planner.models import Badge, UserBadge

    if verified_referral_count(user) < BADGE_TARGET:
        return False
    badge, _ = Badge.objects.get_or_create(
        slug=BADGE_SLUG,
        defaults={'name': 'Squad Builder', 'description': 'Bring 3 friends to StudyFlow',
                  'icon': '🚀', 'xp_reward': 0},
    )
    _, created = UserBadge.objects.get_or_create(user=user, badge=badge)
    return created


def invite_url(request, profile):
    return request.build_absolute_uri(reverse('signup')) + f'?ref={profile.ensure_referral_code()}'
