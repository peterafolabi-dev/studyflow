from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
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


@login_required
def thread_create(request):
    default_course = request.GET.get('course', '')
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        course_code = request.POST.get('course_code', '').strip()
        body = request.POST.get('body', '').strip()
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
            messages.success(request, 'Discussion started.')
            return redirect('thread_detail', pk=thread.pk)

    return render(request, 'community/thread_form.html', {'default_course': default_course})


@login_required
def thread_detail(request, pk):
    thread = get_object_or_404(Thread, pk=pk)
    if request.method == 'POST':
        body = request.POST.get('body', '').strip()
        if body:
            Post.objects.create(
                thread=thread, user=request.user, body=body,
                is_anonymous=bool(request.POST.get('is_anonymous')),
            )
            return redirect('thread_detail', pk=thread.pk)
        messages.error(request, "Reply can't be empty.")

    return render(request, 'community/thread_detail.html', {'thread': thread, 'posts': thread.posts.select_related('user')})


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
    my_courses = set(Course.objects.filter(user=request.user).values_list('code', flat=True))
    buddies = []
    if my_courses:
        other_users = User.objects.exclude(id=request.user.id)
        for u in other_users:
            u_courses = set(Course.objects.filter(user=u).values_list('code', flat=True))
            overlap = my_courses.intersection(u_courses)
            if overlap:
                buddies.append({'user': u, 'overlap': overlap})
    return render(request, 'community/find_buddies.html', {'buddies': buddies})

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
