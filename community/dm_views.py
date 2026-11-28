from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from accounts.models import Notification
from .models import DirectMessage, MutedUser

User = get_user_model()
MAX_LEN = 1000


def unread_count(user):
    return DirectMessage.objects.filter(recipient=user, read_at__isnull=True).count()


def _pair(a, b):
    return DirectMessage.objects.filter(Q(sender=a, recipient=b) | Q(sender=b, recipient=a))


def _row(m, me):
    return {'id': m.id, 'mine': m.sender_id == me.id, 'text': m.text,
            'when': timezone.localtime(m.created_at).strftime('%d %b %H:%M')}


@login_required
def inbox(request):
    me = request.user
    msgs = DirectMessage.objects.filter(Q(sender=me) | Q(recipient=me))
    last = {}
    for m in msgs.order_by('-id').select_related('sender', 'recipient')[:400]:
        other = m.recipient if m.sender_id == me.id else m.sender
        last.setdefault(other.id, (other, m))
    unread = dict(DirectMessage.objects.filter(recipient=me, read_at__isnull=True)
                  .values_list('sender_id').annotate(n=Count('id')))
    convos = [{'user': o, 'last': m, 'mine': m.sender_id == me.id, 'unread': unread.get(o.id, 0)}
              for o, m in last.values()]
    q = request.GET.get('q', '').strip().lstrip('@')[:30]
    results = []
    if len(q) >= 2:
        results = User.objects.filter(username__icontains=q, is_active=True).exclude(pk=me.pk)[:10]
    return render(request, 'community/dm_inbox.html', {'convos': convos, 'q': q, 'results': results})


@login_required
def thread(request, username):
    other = get_object_or_404(User, username=username, is_active=True)
    if other == request.user:
        return redirect('dm_inbox')
    DirectMessage.objects.filter(sender=other, recipient=request.user, read_at__isnull=True).update(read_at=timezone.now())
    msgs = list(_pair(request.user, other).order_by('-id')[:100])[::-1]
    blocked = MutedUser.objects.filter(muter=other, muted=request.user).exists()
    return render(request, 'community/dm_thread.html', {
        'other': other, 'msgs': [_row(m, request.user) for m in msgs],
        'last_id': msgs[-1].id if msgs else 0, 'blocked': blocked})


@login_required
@require_POST
def send(request, username):
    other = get_object_or_404(User, username=username, is_active=True)
    me = request.user
    text = ' '.join(request.POST.get('text', '').split())[:MAX_LEN]
    if other == me or not text:
        return JsonResponse({'error': 'Write a message first.'}, status=400)
    if MutedUser.objects.filter(muter=other, muted=me).exists():
        return JsonResponse({'error': 'This person is not accepting messages from you.'}, status=403)
    if DirectMessage.objects.filter(sender=me, created_at__gte=timezone.now() - timedelta(seconds=30)).count() >= 12:
        return JsonResponse({'error': 'Slow down a little.'}, status=429)
    m = DirectMessage.objects.create(sender=me, recipient=other, text=text)
    already = Notification.objects.filter(user=other, is_read=False, link=reverse('dm_thread', args=[me.username])).exists()
    if not already:
        Notification.objects.create(user=other, message=f'{me.username} sent you a message: "{text[:60]}"',
                                    link=reverse('dm_thread', args=[me.username]))
    return JsonResponse({'message': _row(m, me)})


@login_required
@require_GET
def poll(request, username):
    other = get_object_or_404(User, username=username, is_active=True)
    try:
        after = int(request.GET.get('after', 0))
    except ValueError:
        after = 0
    new = list(_pair(request.user, other).filter(id__gt=after).order_by('id')[:100])
    DirectMessage.objects.filter(sender=other, recipient=request.user, read_at__isnull=True).update(read_at=timezone.now())
    return JsonResponse({'messages': [_row(m, request.user) for m in new]})
