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
