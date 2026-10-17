from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.models import Profile
from planner.models import StudySession
from resources.models import Loan

from .models import CampusGameLog, CampusProfile, SavingsGoal
from .services import credit_balance


GAME_ACTIONS = {
    'lecture': {'label': 'Make it to class', 'icon': '🎓', 'cost': 0, 'energy': -12, 'hunger': -7, 'community': 2, 'wellbeing': 3, 'wallet': 1500, 'effect': 'Earn ₦1,500 game cash · build your campus routine', 'story': 'You made it to class and caught the important bits.'},
    'library': {'label': 'Lock in at the library', 'icon': '📚', 'cost': 0, 'energy': -16, 'hunger': -8, 'community': 0, 'wellbeing': 5, 'wallet': 2000, 'effect': 'Earn ₦2,000 game cash · improve wellbeing', 'story': 'A focused library session moved your semester forward.'},
    'hustle': {'label': 'Pick up a student gig', 'icon': '💼', 'cost': 0, 'energy': -20, 'hunger': -12, 'community': 2, 'wellbeing': -3, 'wallet': 7000, 'effect': 'Earn ₦7,000 game cash · uses more energy', 'story': 'You finished a small student gig and earned game cash.'},
    'food': {'label': 'Grab a proper meal', 'icon': '🍛', 'cost': 1500, 'energy': 5, 'hunger': 30, 'community': 0, 'wellbeing': 5, 'wallet': -1500, 'effect': 'Spend ₦1,500 game cash · restore fullness', 'story': 'You stopped for a filling campus meal.'},
    'linkup': {'label': 'Catch up with your people', 'icon': '🫶', 'cost': 1000, 'energy': -8, 'hunger': -3, 'community': 22, 'wellbeing': 12, 'wallet': -1000, 'effect': 'Spend ₦1,000 game cash · boost community', 'story': 'A good link-up boosted your community and mood.'},
    'rest': {'label': 'Take a proper breather', 'icon': '🛏️', 'cost': 0, 'energy': 28, 'hunger': -5, 'community': 0, 'wellbeing': 8, 'wallet': 0, 'effect': 'Free · restore energy and wellbeing', 'story': 'You took time to rest and reset.'},
}

MISSIONS = [
    {'title': 'Book smart', 'description': 'Lock in for one library session.', 'action': 'library'},
    {'title': 'Touch base', 'description': 'Make time for your campus community.', 'action': 'linkup'},
    {'title': 'Student hustle', 'description': 'Complete one small student gig.', 'action': 'hustle'},
    {'title': 'Show up', 'description': 'Make it to one class today.', 'action': 'lecture'},
]


@login_required
def home(request):
    profile, _ = CampusProfile.objects.get_or_create(user=request.user)
    today = timezone.localdate()
    if profile.last_game_date != today:
        if profile.last_game_date:
            profile.game_day += max(1, (today - profile.last_game_date).days)
        profile.actions_today = 0
        profile.last_game_date = today
        profile.save(update_fields=['game_day', 'actions_today', 'last_game_date'])

    account_profile = Profile.objects.filter(user=request.user).first()
    university = getattr(account_profile, 'university', 'FUT Minna')
    if university == 'UNILAG':
        places = [
            {'name': 'Akoka Campus', 'icon': '🏛️', 'tag': 'Lecture halls & lagoon breeze'},
            {'name': 'Yaba', 'icon': '💻', 'tag': 'Tech, cafés & creative energy'},
            {'name': 'Onike', 'icon': '🍲', 'tag': 'Mainland food stop'},
            {'name': 'Lagos Island', 'icon': '🌆', 'tag': 'Big-city side quest'},
        ]
    elif university == 'LASU':
        places = [
            {'name': 'Ojo Campus', 'icon': '🏛️', 'tag': 'Your student home base'},
            {'name': 'Iyana-Iba', 'icon': '🚌', 'tag': 'The everyday commute'},
            {'name': 'Mile 2', 'icon': '🚏', 'tag': 'Mainland connection'},
            {'name': 'Yaba', 'icon': '💻', 'tag': 'Tech and creative side quest'},
        ]
    else:
        places = [
            {'name': 'Gidan Kwano', 'icon': '🏛️', 'tag': 'Main campus home base'},
            {'name': 'Bosso', 'icon': '📍', 'tag': 'Second campus stop'},
            {'name': 'Tunga', 'icon': '🍲', 'tag': 'Food and errands'},
            {'name': 'Minna City', 'icon': '🌆', 'tag': 'A break from campus'},
        ]

    mission = MISSIONS[(profile.game_day - 1) % len(MISSIONS)]
    game_log = CampusGameLog.objects.filter(user=request.user)[:5]
    if request.method == 'POST' and request.POST.get('action') == 'play_game':
        if profile.actions_today >= 3:
            messages.info(request, 'That is your three moves for today. Your next campus day opens tomorrow; nothing decays while you are away.')
            return redirect('campus_life_home')

        game_action = request.POST.get('game_action', '')
        if game_action == 'explore':
            place_name = request.POST.get('place', '')
            allowed_places = {place['name'] for place in places}
            if place_name not in allowed_places:
                messages.error(request, 'Choose a place on your campus map.')
                return redirect('campus_life_home')
            if profile.game_wallet < 500:
                messages.error(request, 'You need ₦500 game cash for this ride. Try a free campus activity first.')
                return redirect('campus_life_home')
            profile.game_wallet -= 500
            profile.game_location = place_name
            profile.energy = max(0, profile.energy - 6)
            profile.community = min(100, profile.community + 5)
            profile.wellbeing = min(100, profile.wellbeing + 5)
            story = f'You explored {place_name} and found a new corner of student life.'
            wallet_delta = -500
            code = 'explore'
        else:
            action_data = GAME_ACTIONS.get(game_action)
            if not action_data:
                messages.error(request, 'Choose one of the available campus activities.')
                return redirect('campus_life_home')
            if profile.energy < max(0, -action_data['energy']):
                messages.error(request, 'You are low on energy. Rest first, then take on another activity.')
                return redirect('campus_life_home')
            if profile.game_wallet < action_data['cost']:
                messages.error(request, 'Not enough game cash for that activity. Try class, library, a gig, or a rest.')
                return redirect('campus_life_home')
            profile.game_wallet += action_data['wallet']
            profile.energy = max(0, min(100, profile.energy + action_data['energy']))
            profile.hunger = max(0, min(100, profile.hunger + action_data['hunger']))
            profile.community = max(0, min(100, profile.community + action_data['community']))
            profile.wellbeing = max(0, min(100, profile.wellbeing + action_data['wellbeing']))
            story = action_data['story']
            wallet_delta = action_data['wallet']
            code = game_action
            if game_action == mission['action'] and profile.mission_claim_day != profile.game_day:
                profile.game_wallet += 3000
                wallet_delta += 3000
                profile.mission_claim_day = profile.game_day
                story += ' Daily mission complete: +₦3,000 game cash.'

        profile.actions_today += 1
        profile.save(update_fields=[
            'game_wallet', 'game_location', 'energy', 'hunger', 'community',
            'wellbeing', 'actions_today', 'mission_claim_day',
        ])
        CampusGameLog.objects.create(
            user=request.user, action_code=code, message=story,
            wallet_delta=wallet_delta, game_day=profile.game_day,
        )
        messages.success(request, story)
        return redirect('campus_life_home')

    credits = credit_balance(request.user)
    hours = StudySession.objects.filter(user=request.user).aggregate(
        total=Sum('duration_minutes')
    )['total'] or 0
    hours = hours / 60
    title = 'Fresher'
    if hours >= 100:
        title = 'Final Year Finisher'
    elif hours >= 50:
        title = "Dean's List Contender"
    elif hours >= 10:
        title = 'Sophomore Hustler'
    career_levels = ['Fresher', 'Sophomore Hustler', "Dean's List Contender", 'Final Year Finisher']
    if career_levels.index(title) > career_levels.index(profile.career_title):
        profile.career_title = title
        profile.career_celebration_pending = True
        profile.save(update_fields=['career_title', 'career_celebration_pending'])
    title = profile.career_title
    show_career_celebration = profile.career_celebration_pending
    if show_career_celebration:
        profile.career_celebration_pending = False
        profile.save(update_fields=['career_celebration_pending'])

    furniture = [
        {'name': 'Study desk', 'icon': '🪑', 'threshold': 0},
        {'name': 'Lecture notes', 'icon': '📚', 'threshold': 5},
        {'name': 'Wall poster', 'icon': '🖼️', 'threshold': 15},
        {'name': 'Reading lamp', 'icon': '💡', 'threshold': 30},
    ]
    landmarks = [{
        'name': 'IBB Library regular',
        'earned': Loan.objects.filter(user=request.user).count() >= 3,
        'description': 'Borrow from the IBB Library three times.',
    }]
    goal = SavingsGoal.objects.filter(user=request.user).first()
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'save_avatar':
            values = {
                'skin_tone': request.POST.get('skin_tone', ''),
                'hairstyle': request.POST.get('hairstyle', ''),
                'outfit_color': request.POST.get('outfit_color', ''),
                'accessory': request.POST.get('accessory', ''),
            }
            allowed = {
                'skin_tone': dict(CampusProfile.SKIN_CHOICES),
                'hairstyle': {'crop': 0, 'coils': 10, 'locs': 25},
                'outfit_color': {'#2f855a': 0, '#2563eb': 10, '#c2410c': 25},
                'accessory': {'none': 0, 'book': 5, 'glasses': 20},
            }
            valid = all(value in allowed[field] for field, value in values.items())
            valid = valid and all(
                isinstance(allowed[field][value], str) or credits >= allowed[field][value]
                for field, value in values.items()
            )
            if valid:
                for field, value in values.items():
                    setattr(profile, field, value)
                profile.save(update_fields=list(values))
                messages.success(request, 'Campus avatar saved. No Credits were deducted.')
            else:
                messages.error(request, 'Some avatar styles are still locked at your current lifetime Credits.')
            return redirect('campus_life_home')
        if action == 'save_goal':
            title_value = request.POST.get('title', '').strip()[:80]
            try:
                target = int(request.POST.get('target_credits', '0'))
            except ValueError:
                target = 0
            if title_value and target > 0:
                SavingsGoal.objects.update_or_create(
                    user=request.user,
                    defaults={'title': title_value, 'target_credits': target},
                )
                messages.success(request, 'Your playful study goal was saved.')
            else:
                messages.error(request, 'Enter a goal name and a positive Credits target.')
            return redirect('campus_life_home')

    return render(request, 'campus_life/home.html', {
        'profile': profile,
        'credits': credits,
        'career_title': title,
        'show_career_celebration': show_career_celebration,
        'study_hours': round(hours, 1),
        'furniture': [item for item in furniture if credits >= item['threshold']],
        'goal': goal,
        'goal_progress': min(100, int(credits * 100 / goal.target_credits)) if goal else 0,
        'goal_credits': min(credits, goal.target_credits) if goal else 0,
        'landmarks': landmarks,
        'skin_choices': CampusProfile.SKIN_CHOICES,
        'hair_choices': CampusProfile.HAIR_CHOICES,
        'outfit_choices': CampusProfile.OUTFIT_CHOICES,
        'accessory_choices': CampusProfile.ACCESSORY_CHOICES,
        'game_profile': profile,
        'game_actions': GAME_ACTIONS,
        'places': places,
        'game_log': game_log,
        'mission': mission,
        'mission_complete': profile.mission_claim_day == profile.game_day,
        'moves_left': max(0, 3 - profile.actions_today),
        'game_university': university,
    })
