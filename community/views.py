from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Post, Thread


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
