from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Post, Thread, ChatMessage



@login_required
def thread_list(request):
    course_code = request.GET.get('course', '').strip()
    query = request.GET.get('q', '').strip()

    threads = Thread.objects.all()
    if course_code:
        threads = threads.filter(course_code__iexact=course_code)
    if query:
        threads = threads.filter(Q(title__icontains=query) | Q(course_code__icontains=query))

    return render(
        request, 'community/thread_list.html',
        {'threads': threads, 'course_code': course_code, 'query': query},
    )


def generate_ai_answer_for_thread(thread, question_context=''):
    import os
    api_key = os.environ.get('GROQ_API_KEY')
    if not api_key:
        return (
            "🤖 **StudyFlow AI Coach:**\n\n"
            "I'm here to help while your classmates are offline! Once the administrator activates the GROQ_API_KEY, "
            "I will generate step-by-step academic solutions, derivations, and practice tips right here."
        )

    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        model = os.environ.get('MODEL_NAME') or 'openai/gpt-oss-20b'

        prompt = (
            f"You are the StudyFlow AI Coach, an expert academic tutor for university students. "
            f"A student in a course discussion group has asked a question while others might not be online.\n"
            f"Course Code: {thread.course_code or 'General University'}\n"
            f"Discussion Question / Topic: {thread.title}\n"
            f"Additional Details: {question_context or 'None provided'}\n\n"
            f"Provide a thorough, accurate, step-by-step academic answer explaining the core concepts, "
            f"working out any math, and giving practical tips. Use clean markdown with headings and bullets. "
            f"Write math in LaTeX using $...$ for inline and $$...$$ for display formulas. Keep it motivating."
        )

        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are StudyFlow Coach, a legendary academic mentor and university tutor."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=850
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"🤖 **StudyFlow AI Coach:** I tried to generate an answer for you, but encountered an error: {e}. Please try again shortly!"


@login_required
def thread_create(request):
    default_course = request.GET.get('course', '')
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        course_code = request.POST.get('course_code', '').strip()
        body = request.POST.get('body', '').strip()
        ask_ai = bool(request.POST.get('ask_ai'))
        if not title:
            messages.error(request, 'Give the discussion a title.')
        else:
            thread = Thread.objects.create(
                title=title, course_code=course_code, created_by=request.user,
                is_anonymous=bool(request.POST.get('is_anonymous')),
            )
            if body:
                Post.objects.create(
                    thread=thread, user=request.user, body=body,
                    is_anonymous=bool(request.POST.get('is_anonymous')),
                )
            if ask_ai:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                ai_user, _ = User.objects.get_or_create(username='StudyFlow AI Coach', defaults={'first_name': 'StudyFlow', 'last_name': 'AI Coach'})
                ai_reply = generate_ai_answer_for_thread(thread, body)
                Post.objects.create(thread=thread, user=ai_user, body=ai_reply, is_anonymous=False)
                messages.success(request, 'Discussion started & StudyFlow AI Coach provided an instant answer!')
            else:
                messages.success(request, 'Discussion started.')
            return redirect('thread_detail', pk=thread.pk)

    return render(request, 'community/thread_form.html', {'default_course': default_course})


@login_required
def thread_detail(request, pk):
    thread = get_object_or_404(Thread, pk=pk)
    from django.contrib.auth import get_user_model
    User = get_user_model()
    ai_user, _ = User.objects.get_or_create(username='StudyFlow AI Coach', defaults={'first_name': 'StudyFlow', 'last_name': 'AI Coach'})

    if request.method == 'POST':
        if 'ask_ai' in request.POST:
            first_post = thread.posts.first()
            context = first_post.body if first_post else ''
            ai_reply = generate_ai_answer_for_thread(thread, context)
            Post.objects.create(thread=thread, user=ai_user, body=ai_reply, is_anonymous=False)
            messages.success(request, 'StudyFlow AI Coach answered your question!')
            return redirect('thread_detail', pk=thread.pk)

        body = request.POST.get('body', '').strip()
        if body:
            Post.objects.create(
                thread=thread, user=request.user, body=body,
                is_anonymous=bool(request.POST.get('is_anonymous')),
            )
            return redirect('thread_detail', pk=thread.pk)
        messages.error(request, "Reply can't be empty.")

    posts = thread.posts.select_related('user')
    return render(request, 'community/thread_detail.html', {
        'thread': thread,
        'posts': posts,
        'ai_user_id': ai_user.id
    })


@login_required
@require_POST
def thread_delete(request, pk):
    thread = get_object_or_404(Thread, pk=pk)
    if thread.created_by_id != request.user.id and not request.user.is_staff:
        messages.error(request, 'Only the person who started this discussion can delete it.')
        return redirect('thread_detail', pk=pk)
    thread.delete()
    messages.info(request, 'Discussion deleted.')
    return redirect('thread_list')


from .models import ThreadVote
from django.contrib.auth import get_user_model
from planner.models import Course

@login_required
def find_buddies(request):
    User = get_user_model()
    from accounts.models import Profile
    from .models import StudyBuddyRequest
    from planner.models import TimetableEntry
    from datetime import time

    my_profile, _ = Profile.objects.get_or_create(user=request.user)
    my_courses = {
        code.strip().upper() for code in Course.objects.filter(user=request.user)
        .exclude(code='').values_list('code', flat=True)
    }
    user_ids = list(User.objects.filter(is_active=True).exclude(pk=request.user.pk).values_list('pk', flat=True))
    courses_by_user = {}
    for user_id, code in Course.objects.filter(user_id__in=user_ids).exclude(code='').values_list('user_id', 'code'):
        courses_by_user.setdefault(user_id, set()).add(code.strip().upper())

    entries_by_user = {}
    entries = list(TimetableEntry.objects.filter(user_id__in=[*user_ids, request.user.pk]))
    for entry in entries:
        entries_by_user.setdefault(entry.user_id, []).append(entry)

    def free_slots(entries):
        return {
            (day, hour)
            for day in range(7)
            for hour in range(9, 20)
            if all(
                time(hour + 1) <= entry.start_time or time(hour) >= entry.end_time
                for entry in entries if entry.day_of_week == day
            )
        }

    my_free = free_slots(entries_by_user.get(request.user.pk, []))
    profiles = {
        profile.user_id: profile
        for profile in Profile.objects.filter(user_id__in=user_ids)
    }
    my_time = my_profile.preferred_study_time
    buddies = []
    if my_courses:
        for user in User.objects.filter(pk__in=user_ids).only('id', 'username'):
            overlap = my_courses.intersection(courses_by_user.get(user.pk, set()))
            if not overlap:
                continue
            their_profile = profiles.get(user.pk)
            goal = their_profile.weekly_study_goal_hours if their_profile else 8
            study_time = their_profile.preferred_study_time if their_profile else 'flexible'
            their_entries = entries_by_user.get(user.pk, [])
            comparable_availability = bool(entries_by_user.get(request.user.pk) and their_entries)
            shared_slots = len(my_free & free_slots(their_entries)) if comparable_availability else 0
            time_match = my_time == study_time or 'flexible' in {my_time, study_time}
            goal_match = abs(my_profile.weekly_study_goal_hours - goal) <= 2
            score = len(overlap) * 4 + min(3, shared_slots // 10) + int(time_match) * 2 + int(goal_match)
            buddies.append({
                'user': user, 'overlap': sorted(overlap), 'shared_slots': shared_slots,
                'comparable_availability': comparable_availability,
                'time_match': time_match, 'goal': goal, 'score': score,
            })
    buddies.sort(key=lambda item: (-item['score'], item['user'].username.lower()))

    sent_status = {}
    for buddy_request in StudyBuddyRequest.objects.filter(from_user=request.user).order_by('-created_at'):
        sent_status.setdefault(buddy_request.to_user_id, buddy_request.status)
    for buddy in buddies:
        buddy['request_status'] = sent_status.get(buddy['user'].pk, '')

    incoming = StudyBuddyRequest.objects.filter(
        to_user=request.user, status='pending'
    ).select_related('from_user').order_by('-created_at')
    return render(request, 'community/find_buddies.html', {
        'buddies': buddies,
        'incoming_requests': incoming,
        'my_profile': my_profile,
    })


@login_required
@require_POST
def send_buddy_request(request, user_id):
    User = get_user_model()
    from accounts.models import Notification
    from .models import StudyBuddyRequest

    target = get_object_or_404(User, pk=user_id, is_active=True)
    if target.pk == request.user.pk:
        messages.error(request, 'You cannot send a study request to yourself.')
        return redirect('find_buddies')

    buddy_request = StudyBuddyRequest.objects.filter(
        from_user=request.user, to_user=target
    ).order_by('-created_at').first()
    if buddy_request and buddy_request.status in {'pending', 'accepted'}:
        messages.info(request, 'You already have an active request with this student.')
    else:
        if buddy_request:
            buddy_request.status = 'pending'
            buddy_request.created_at = timezone.now()
            buddy_request.save(update_fields=['status', 'created_at'])
        else:
            StudyBuddyRequest.objects.create(from_user=request.user, to_user=target)
        Notification.objects.create(
            user=target,
            message=f'{request.user.username} wants to study with you.',
            link='/study-groups/buddies/',
        )
        messages.success(request, f'Study request sent to {target.username}.')
    return redirect('find_buddies')


@login_required
@require_POST
def respond_buddy_request(request, request_id):
    from accounts.models import Notification
    from .models import StudyBuddyRequest

    buddy_request = get_object_or_404(
        StudyBuddyRequest, pk=request_id, to_user=request.user, status='pending'
    )
    decision = request.POST.get('decision')
    if decision not in {'accepted', 'rejected'}:
        messages.error(request, 'Choose whether to accept or decline the request.')
        return redirect('find_buddies')
    buddy_request.status = decision
    buddy_request.save(update_fields=['status'])
    if decision == 'accepted':
        Notification.objects.create(
            user=buddy_request.from_user,
            message=f'{request.user.username} accepted your study request.',
            link='/study-groups/buddies/',
        )
        messages.success(request, f'You and {buddy_request.from_user.username} are now study buddies.')
    else:
        messages.info(request, 'Study request declined.')
    return redirect('find_buddies')

@login_required
@require_POST
def vote_thread(request, pk):
    thread = get_object_or_404(Thread, pk=pk)
    val = int(request.POST.get('value', 1))
    ThreadVote.objects.update_or_create(user=request.user, thread=thread, defaults={'value': val})
    return redirect('thread_detail', pk=pk)



from django.http import JsonResponse
import json

@login_required
def global_chat(request):
    return render(request, 'community/global_chat.html')

@login_required
def chat_api(request):
    room = request.GET.get('room', 'global')
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            text = data.get('text', '').strip()
            room = data.get('room', 'global')
            if text:
                ChatMessage.objects.create(user=request.user, text=text, room=room)
                return JsonResponse({'status': 'ok'})
        except Exception as e:
            pass
        return JsonResponse({'status': 'error'}, status=400)
    messages = ChatMessage.objects.filter(room=room).order_by('-created_at')[:50]
    data = []
    for msg in reversed(messages):
        data.append({
            'username': msg.user.username,
            'text': msg.text,
            'time': msg.created_at.strftime('%H:%M'),
            'is_me': msg.user == request.user
        })
    return JsonResponse({'messages': data})


# ── Phase 6: Moderation ──────────────────────────────────────────────────────

@login_required
@require_POST
def report_post(request, pk):
    from .models import PostReport
    post = get_object_or_404(Post, pk=pk)
    reason = request.POST.get('reason', 'other')
    detail = request.POST.get('detail', '')[:300]

    _, created = PostReport.objects.get_or_create(
        reporter=request.user,
        post=post,
        defaults={'reason': reason, 'detail': detail},
    )
    if created:
        messages.success(request, 'Report submitted. Our team will review it.')
    else:
        messages.info(request, 'You already reported this post.')
    return redirect(request.META.get('HTTP_REFERER', 'thread_list'))


@login_required
@require_POST
def mute_user(request, username):
    from django.contrib.auth import get_user_model
    from .models import MutedUser
    User = get_user_model()
    target = get_object_or_404(User, username=username)

    if target == request.user:
        messages.error(request, "You can't mute yourself.")
        return redirect(request.META.get('HTTP_REFERER', 'thread_list'))

    obj, created = MutedUser.objects.get_or_create(muter=request.user, muted=target)
    if created:
        messages.success(request, f'@{target.username} muted. You won\'t see their posts.')
    else:
        # Toggle off — unmute
        obj.delete()
        messages.success(request, f'@{target.username} unmuted.')
    return redirect(request.META.get('HTTP_REFERER', 'thread_list'))


# ── Phase 7: Feedback ────────────────────────────────────────────────────────

@login_required
@require_POST
def submit_feedback(request):
    from .models import Feedback
    from django.http import JsonResponse
    try:
        rating = int(request.POST.get('rating', 0))
        message_text = request.POST.get('message', '').strip()[:1000]
        page = request.POST.get('page', '')[:200]

        if rating < 1 or rating > 5:
            return JsonResponse({'error': 'Rating must be 1–5.'}, status=400)

        Feedback.objects.create(
            user=request.user if request.user.is_authenticated else None,
            rating=rating,
            message=message_text,
            page=page,
        )
        return JsonResponse({'success': True, 'message': 'Thanks for your feedback! 🙏'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def admin_dashboard(request):
    """Phase 7: Admin-only analytics dashboard."""
    from django.contrib.auth import get_user_model
    from django.db.models import Count
    from django.db.models.functions import TruncDate, TruncWeek
    from datetime import timedelta
    from django.utils import timezone
    from .models import Feedback
    from planner.models import StudySession, XPLog
    from accounts.models import LoginRecord, UserPresence

    if not request.user.is_staff:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    User = get_user_model()
    today = timezone.localdate()
    thirty_days_ago = today - timedelta(days=30)

    # Signups over last 30 days
    signups = (
        User.objects.filter(date_joined__date__gte=thirty_days_ago)
        .annotate(day=TruncDate('date_joined'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )

    now = timezone.now()
    online_cutoff = now - timedelta(minutes=5)
    active_cutoff = now - timedelta(days=7)
    online_users = UserPresence.objects.filter(
        last_seen__gte=online_cutoff, user__is_active=True
    ).select_related('user').order_by('-last_seen')
    active_users = UserPresence.objects.filter(
        last_seen__gte=active_cutoff, user__is_active=True
    ).values('user').distinct().count()
    recent_logins = LoginRecord.objects.select_related('user').order_by('-timestamp')[:25]

    # Feature usage this week
    week_ago = today - timedelta(days=7)
    feature_usage = {
        'Pomodoro sessions': StudySession.objects.filter(date__gte=week_ago).count(),
        'Flashcard reviews': XPLog.objects.filter(reason='flashcard', created_at__date__gte=week_ago).count(),
        'Tasks completed': XPLog.objects.filter(reason='task_done', created_at__date__gte=week_ago).count(),
        'Quizzes done': XPLog.objects.filter(reason='quiz_done', created_at__date__gte=week_ago).count(),
    }

    # Recent feedback
    recent_feedback = Feedback.objects.select_related('user')[:20]
    avg_rating = Feedback.objects.aggregate(avg=models.Avg('rating'))['avg'] or 0

    context = {
        'total_users': User.objects.filter(is_active=True).count(),
        'active_users': active_users,
        'online_users': online_users,
        'recent_logins': recent_logins,
        'total_login_records': LoginRecord.objects.count(),
        'online_window_minutes': 5,
        'total_signups_30d': User.objects.filter(date_joined__date__gte=thirty_days_ago).count(),
        'signups': list(signups),
        'feature_usage': feature_usage,
        'recent_feedback': recent_feedback,
        'avg_rating': round(avg_rating, 1),
        'feedback_count': Feedback.objects.count(),
    }
    return render(request, 'community/admin_dashboard.html', context)

