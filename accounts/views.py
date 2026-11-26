from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from library.models import BookRating, SavedBook
from planner.models import Course, Task, TimetableEntry
from resources.models import Loan, Resource, ResourceRating
from studyflow.http import redirect_next

from .forms import LoginForm, SignUpForm
from .presence import mark_offline, touch_presence


def signup(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    from .referrals import attach_referrer, capture_referral
    capture_referral(request)

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            attach_referrer(request, user)
            from .verification import send_verification_email, verification_required
            if verification_required():
                user.profile.email_verified = False
                user.profile.save(update_fields=['email_verified'])
                if not send_verification_email(user, request):
                    messages.error(request, "Your account was created, but we couldn't send the confirmation email. Use “Send a new code” below.")
                request.session['verify_login'] = user.email
                return redirect('verify_email_sent')
            from .emails import send_welcome_email
            send_welcome_email(user, request)
            messages.success(request, "You've signed up successfully! We've sent a welcome email. Please log in.")
            return redirect('login')
        messages.error(request, 'Sign-up failed. Check that the username is available, the email is valid and unused, and both passwords match.')
    else:
        form = SignUpForm()

    return render(request, 'accounts/signup.html', {'form': form})


def login_view(request):
    """Custom login that authenticates via ModelBackend (username + password).
    This bypasses allauth's email-first flow so username-only accounts can log in."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    from .referrals import capture_referral
    capture_referral(request)

    error = None
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            from resources.ai_service import RateLimitExceeded, check_and_increment_rate_limit
            try:
                # Slows password guessing against one account; legit users rarely hit 10 tries.
                check_and_increment_rate_limit(username.lower(), bucket='login', max_requests=10, window=900)
            except RateLimitExceeded:
                error = 'Too many login attempts. Please wait a few minutes and try again.'
                messages.error(request, error)
                return render(request, 'accounts/login.html', {'form': form, 'error': error}, status=429)
            user = authenticate(request, username=username, password=password,
                                backend='django.contrib.auth.backends.ModelBackend')
            from .verification import needs_verification
            if user is not None and needs_verification(user):
                request.session['verify_login'] = user.email
                error = 'Please confirm your email first. We sent you a 6-digit code when you signed up.'
                messages.error(request, error)
                return redirect('verify_email_sent')
            if user is not None:
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                return redirect_next(request, 'dashboard', url=request.GET.get('next', ''))
            else:
                error = 'Invalid username or password. Please try again.'
                messages.error(request, error)
        else:
            error = 'Please enter a valid username and password.'
            messages.error(request, error)
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form, 'error': error})


@require_POST
def logout_view(request):
    if request.user.is_authenticated:
        mark_offline(request.user)
    logout(request)
    messages.success(request, "You've been logged out. See you soon!")
    return redirect('login')


@login_required
def profile(request):
    from django.db.models import Sum
    from planner.models import Badge, StudySession, StudyStreak, UserBadge, XPLog

    streak, _ = StudyStreak.objects.get_or_create(user=request.user)
    total_minutes = StudySession.objects.filter(user=request.user).aggregate(
        total=Sum('duration_minutes')
    )['total'] or 0
    flashcard_reviews = XPLog.objects.filter(user=request.user, reason='flashcard').count()
    achievement_definitions = [
        ('achievement-first-session', 'First Session', 'Complete a tracked study session', '⏱️', StudySession.objects.filter(user=request.user).exists()),
        ('achievement-week-streak', '7-Day Streak', 'Reach a seven-day study streak', '🔥', streak.longest_streak >= 7),
        ('achievement-ten-hours', '10 Hours Logged', 'Log ten hours of focused study', '📚', total_minutes >= 600),
        ('achievement-fifty-cards', '50 Flashcards Reviewed', 'Review fifty flashcards', '🃏', flashcard_reviews >= 50),
    ]
    for slug, name, description, icon, earned in achievement_definitions:
        badge, _ = Badge.objects.get_or_create(
            slug=slug,
            defaults={'name': name, 'description': description, 'icon': icon, 'xp_reward': 0},
        )
        if earned:
            UserBadge.objects.get_or_create(user=request.user, badge=badge)

    unseen = list(UserBadge.objects.filter(
        user=request.user, celebration_seen=False,
        badge__slug__startswith='achievement-'
    ).select_related('badge'))
    if unseen:
        UserBadge.objects.filter(pk__in=[entry.pk for entry in unseen]).update(celebration_seen=True)

    finished_count = SavedBook.objects.filter(user=request.user, status='finished').count()
    reading_count = SavedBook.objects.filter(user=request.user, status='reading').count()

    if finished_count >= 6:
        rank = 'Legendary Reader'
        rank_emoji = '🏆'
    elif finished_count >= 3:
        rank = 'Bookworm'
        rank_emoji = '🐛'
    elif finished_count >= 1:
        rank = 'Scholar'
        rank_emoji = '🎓'
    else:
        rank = 'Newcomer'
        rank_emoji = '🌱'

    context = {
        'course_count': Course.objects.filter(user=request.user).count(),
        'open_task_count': Task.objects.filter(
            course__user=request.user, is_done=False
        ).count(),
        'saved_book_count': SavedBook.objects.filter(user=request.user).count(),
        'finished_count': finished_count,
        'reading_count': reading_count,
        'rank': rank,
        'rank_emoji': rank_emoji,
        'achievements': UserBadge.objects.filter(
            user=request.user, badge__slug__startswith='achievement-'
        ).select_related('badge').order_by('awarded_at'),
        'new_achievements': [entry.badge.name for entry in unseen],
    }
    return render(request, 'accounts/profile.html', context)


@login_required
def export_my_data(request):
    """Lets a user download everything StudyFlow has stored about their
    activity, as one JSON file — courses, tasks, saved books, ratings,
    uploaded resources, library loans, and timetable entries."""
    user = request.user

    data = {
        'exported_at': timezone.now().isoformat(),
        'username': user.username,
        'email': user.email,
        'courses': [
            {'name': c.name, 'code': c.code, 'created_at': c.created_at.isoformat()}
            for c in Course.objects.filter(user=user)
        ],
        'tasks': [
            {
                'title': t.title, 'course': t.course.name, 'due_date': t.due_date.isoformat(),
                'is_done': t.is_done,
            }
            for t in Task.objects.filter(course__user=user).select_related('course')
        ],
        'saved_books': [
            {
                'title': s.book.title, 'status': s.status, 'saved_at': s.saved_at.isoformat(),
            }
            for s in SavedBook.objects.filter(user=user).select_related('book')
        ],
        'book_ratings': [
            {'book': r.book.title, 'stars': r.stars} for r in BookRating.objects.filter(user=user).select_related('book')
        ],
        'uploaded_resources': [
            {
                'title': r.title, 'type': r.get_resource_type_display(), 'course_code': r.course_code,
                'download_count': r.download_count, 'created_at': r.created_at.isoformat(),
            }
            for r in Resource.objects.filter(uploaded_by=user)
        ],
        'resource_ratings': [
            {'resource': r.resource.title, 'stars': r.stars} for r in ResourceRating.objects.filter(user=user).select_related('resource')
        ],
        'library_loans': [
            {
                'title': loan.holding.title, 'borrowed_at': loan.borrowed_at.isoformat(),
                'due_at': loan.due_at.isoformat(),
                'returned_at': loan.returned_at.isoformat() if loan.returned_at else None,
            }
            for loan in Loan.objects.filter(user=user).select_related('holding')
        ],
        'timetable': [
            {
                'title': e.title, 'day': e.get_day_of_week_display(),
                'start_time': e.start_time.strftime('%H:%M'), 'end_time': e.end_time.strftime('%H:%M'),
                'location': e.location,
            }
            for e in TimetableEntry.objects.filter(user=user)
        ],
    }

    response = JsonResponse(data, json_dumps_params={'indent': 2})
    response['Content-Disposition'] = f'attachment; filename="studyflow-{user.username}-data.json"'
    return response


from django.shortcuts import get_object_or_404
from .models import Profile, Notification
from .forms import ProfileForm

@login_required
def edit_profile(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('profile')
    else:
        form = ProfileForm(instance=profile)
    return render(request, 'accounts/edit_profile.html', {'form': form})

@login_required
def public_profile(request, username):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    target_user = get_object_or_404(User, username=username)
    profile, _ = Profile.objects.get_or_create(user=target_user)
    return render(request, 'accounts/public_profile.html', {'target_user': target_user, 'profile': profile})

@login_required
@require_POST
def presence_ping(request):
    """Heartbeat from open tabs so users on long pages (e.g. a Pomodoro) stay 'online'."""
    touch_presence(request.user)
    return JsonResponse({'ok': True})


@login_required
def notifications_view(request):
    notifs = Notification.objects.filter(user=request.user)
    notifs.update(is_read=True)
    return render(request, 'accounts/notifications.html', {'notifications': notifs})



from django.views.decorators.csrf import csrf_exempt  # noqa: E402


@csrf_exempt  # mail apps' one-click unsubscribe POSTs without a CSRF token
def digest_unsubscribe(request, token):
    from .models import Profile
    profile = Profile.objects.filter(digest_token=token).select_related('user').first() if token else None
    if profile is None:
        return render(request, 'accounts/digest_unsubscribe.html', {'invalid': True}, status=404)
    if request.method == 'POST':
        if profile.daily_digest:
            profile.daily_digest = False
            profile.save(update_fields=['daily_digest'])
        return render(request, 'accounts/digest_unsubscribe.html', {'done': True})
    return render(request, 'accounts/digest_unsubscribe.html', {'email': profile.user.email})


def cron_daily_digest(request):
    """Called each morning by the GitHub Actions workflow with `Authorization: Bearer <CRON_SECRET>`."""
    import hmac
    from django.conf import settings
    from django.http import JsonResponse
    from .digest import send_daily_digest
    secret = getattr(settings, 'CRON_SECRET', '')
    if not secret:
        return JsonResponse({'error': 'CRON_SECRET is not configured'}, status=503)
    if not hmac.compare_digest(request.headers.get('Authorization', '').encode(), f'Bearer {secret}'.encode()):
        return JsonResponse({'error': 'unauthorized'}, status=401)
    return JsonResponse(send_daily_digest(request=request))


def verify_email_sent(request):
    """'Check your email' page: enter the 6-digit code, or ask for a new one."""
    login_hint = request.session.get('verify_login', '')
    return render(request, 'accounts/verify_email.html', {'state': 'sent', 'email': login_hint, 'login': login_hint})


def _finish_verification(request, user):
    """Marks the email confirmed (first time only: welcome email), logs the student in."""
    from .emails import send_welcome_email

    if not user.profile.email_verified:
        user.profile.email_verified = True
        user.profile.save(update_fields=['email_verified'])
        send_welcome_email(user, request)
        if user.profile.referred_by_id:
            from .referrals import award_referral_badge
            award_referral_badge(user.profile.referred_by)
    request.session.pop('verify_login', None)
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    messages.success(request, 'Email confirmed. Welcome to StudyFlow! 🎉')
    return redirect('dashboard')


def verify_email(request, uidb64, token):
    from django.contrib.auth import get_user_model
    from django.utils.encoding import force_str
    from django.utils.http import urlsafe_base64_decode
    from .verification import email_verification_token

    try:
        user = get_user_model().objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (TypeError, ValueError, OverflowError, get_user_model().DoesNotExist):
        user = None
    if user is None or not email_verification_token.check_token(user, token):
        return render(request, 'accounts/verify_email.html', {'state': 'invalid'}, status=400)
    return _finish_verification(request, user)


@require_POST
def verify_code(request):
    """Checks the 6-digit code from the email. Wrong, expired and unknown all look the same."""
    from django.contrib.auth import get_user_model
    from django.db.models import Q
    from resources.ai_service import RateLimitExceeded, check_and_increment_rate_limit
    from .verification import check_code

    login_value = (request.session.get('verify_login') or request.POST.get('login', '')).strip()
    if not login_value:
        messages.error(request, 'Enter your username or email, then the 6-digit code.')
        return redirect('verify_email_sent')
    request.session['verify_login'] = login_value
    try:
        # Slows guessing: 10 tries per 15 minutes per account (each code also locks after 5 wrong tries).
        check_and_increment_rate_limit(login_value.lower(), bucket='verify_code', max_requests=10, window=900)
    except RateLimitExceeded:
        messages.error(request, 'Too many tries. Please wait 15 minutes, or ask for a new code.')
        return redirect('verify_email_sent')
    user = get_user_model().objects.filter(
        Q(username__iexact=login_value) | Q(email__iexact=login_value)
    ).select_related('profile').first()
    if user and user.email and not user.profile.email_verified and check_code(user, request.POST.get('code', '')):
        return _finish_verification(request, user)
    messages.error(request, "That code is wrong or has expired. Check your latest email, or send a new code below.")
    return redirect('verify_email_sent')


@require_POST
def resend_verification(request):
    """Sends a fresh code. Always shows the same message, so it can't be used to discover accounts."""
    from django.contrib.auth import get_user_model
    from django.db.models import Q
    from resources.ai_service import RateLimitExceeded, check_and_increment_rate_limit
    from .verification import send_verification_email

    login_value = request.POST.get('login', '').strip()
    if login_value:
        try:
            check_and_increment_rate_limit(login_value.lower(), bucket='verify_resend', max_requests=5, window=3600)
            user = get_user_model().objects.filter(Q(username__iexact=login_value) | Q(email__iexact=login_value)).select_related('profile').first()
            if user and user.email and not user.profile.email_verified:
                send_verification_email(user, request)
        except RateLimitExceeded:
            messages.error(request, 'Too many requests. Please wait an hour and try again.')
            return redirect('verify_email_sent')
    request.session['verify_login'] = login_value
    messages.success(request, "If that account is waiting for confirmation, we've sent a new code.")
    return redirect('verify_email_sent')


@login_required
def invite(request):
    """Personal invite link, share buttons and how many friends have joined."""
    from urllib.parse import quote

    from .referrals import BADGE_TARGET, award_referral_badge, invite_url, verified_referral_count

    link = invite_url(request, request.user.profile)
    joined = verified_referral_count(request.user)
    award_referral_badge(request.user)
    text = f'Join me on StudyFlow, a free study app for university students: {link}'
    return render(request, 'accounts/invite.html', {
        'invite_link': link,
        'joined': joined,
        'target': BADGE_TARGET,
        'remaining': max(0, BADGE_TARGET - joined),
        'whatsapp_url': 'https://wa.me/?text=' + quote(text),
    })


@login_required
def delete_account(request):
    """Self-service account deletion. Asks for the password first; staff
    accounts are not deletable here so the site cannot lose its last admin."""
    if request.user.is_staff or request.user.is_superuser:
        messages.error(request, 'Staff accounts cannot be deleted here. Ask another admin.')
        return redirect('profile')
    if request.method == 'POST':
        if not request.user.check_password(request.POST.get('password', '')):
            messages.error(request, 'That password is not correct, so nothing was deleted.')
            return render(request, 'accounts/delete_account.html', status=400)
        user = request.user
        logout(request)
        user.delete()
        messages.success(request, 'Your account and its data have been deleted.')
        return redirect('/')
    return render(request, 'accounts/delete_account.html')

