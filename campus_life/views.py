from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import redirect, render

from planner.models import StudySession
from resources.models import Loan

from .models import CampusProfile, SavingsGoal
from .services import credit_balance


@login_required
def home(request):
    profile, _ = CampusProfile.objects.get_or_create(user=request.user)
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
    })