"""Campus chat: messages, replies, edits, reactions, pins, files, polls, mentions, search, forwards, saved."""
import json
import mimetypes
import os
import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import FileResponse, Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import get_valid_filename
from django.views.decorators.http import require_GET, require_POST

from accounts.models import Notification
from django.conf import settings

from .models import (ChatMessage, ChatPoll, ChatPollOption, ChatPollVote, ChatReaction, ChatRoomConfig, SavedChat)

CHAT_ROOMS = {'global', 'futminna', 'announcements'}
CHAT_MAX_LENGTH = 1000  # matches ChatMessage.text max_length
CHAT_RATE_LIMIT = 12        # messages ...
CHAT_RATE_WINDOW = 30       # ... per this many seconds, per student
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
IMAGE_EXTS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
FILE_EXTS = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'txt', 'csv'}
MENTION = re.compile(r'(?<![\w@])@([A-Za-z0-9_.+-]{2,150})')
User = get_user_model()


def _json_body(request):
    try:
        data = json.loads(request.body or b'{}')
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


def _err(text, status=400):
    return JsonResponse({'status': 'error', 'error': text}, status=status)


@login_required
def global_chat(request):
    return render(request, 'community/global_chat.html', {'is_chat_staff': request.user.is_staff})


# ---------- rules for posting ----------

def _room_config(room):
    return ChatRoomConfig.objects.filter(slug=room).first()


def _post_block(user, room):
    """None if the student may post in this room right now, else an error response."""
    if room not in CHAT_ROOMS:
        return _err('Unknown room.')
    cfg = _room_config(room)
    announce_only = (cfg.announcements_only if cfg else False) or (room == 'announcements' and cfg is None)
    if announce_only and not user.is_staff:
        return _err('Only admins can post in this room. You can still read and react.', 403)
    key = f'chat-rate:{user.id}'
    cache.add(key, 0, CHAT_RATE_WINDOW)
    try:
        sent = cache.incr(key)
    except ValueError:
        sent = 1
    if sent > CHAT_RATE_LIMIT:
        return _err('Slow down a little. Try again in a few seconds.', 429)
    if cfg and cfg.slow_mode_seconds and not user.is_staff:
        slow_key = f'chat-slow:{room}:{user.id}'
        if not cache.add(slow_key, 1, cfg.slow_mode_seconds):
            return _err(f'Slow mode is on: wait {cfg.slow_mode_seconds} seconds between messages here.', 429)
    return None


def _notify_mentions(msg, previous_text=''):
    already = set(MENTION.findall(previous_text or ''))
    names = [n for n in dict.fromkeys(MENTION.findall(msg.text)) if n not in already][:5]
    if not names:
        return
    snippet = ' '.join(msg.text.split())[:80]
    for u in User.objects.filter(username__in=names, is_active=True).exclude(pk=msg.user_id):
        Notification.objects.create(user=u, message=f'{msg.user.username} mentioned you in chat: "{snippet}"',
                                    link=reverse('global_chat'))


# ---------- reading ----------

def _snippet(msg):
    if msg.is_deleted:
        return ''
    return ' '.join(msg.text.split())[:90] or (f'📎 {msg.attachment_name}' if msg.attachment_name else '')


def _poll_payload(msg, me_id):
    poll = getattr(msg, 'poll', None)
    if poll is None:
        return None
    options = list(poll.options.all())
    votes = {}
    mine = None
    for v in ChatPollVote.objects.filter(option__poll=poll).values('option_id', 'user_id'):
        votes[v['option_id']] = votes.get(v['option_id'], 0) + 1
        if v['user_id'] == me_id:
            mine = v['option_id']
    total = sum(votes.values())
    return {'total': total, 'mine': mine,
            'options': [{'id': o.id, 'text': o.text, 'votes': votes.get(o.id, 0),
                         'pct': round(100 * votes.get(o.id, 0) / total) if total else 0} for o in options]}


def _serialize_chat(messages_qs, me):
    msgs = list(messages_qs)
    ids = [m.id for m in msgs]
    counts, mine = {}, set()
    for r in ChatReaction.objects.filter(message_id__in=ids).values('message_id', 'emoji', 'user_id'):
        counts.setdefault(r['message_id'], {}).setdefault(r['emoji'], 0)
        counts[r['message_id']][r['emoji']] += 1
        if r['user_id'] == me.id:
            mine.add((r['message_id'], r['emoji']))
    saved_ids = set(SavedChat.objects.filter(user=me, source_id__in=ids).values_list('source_id', flat=True))
    out = []
    for m in msgs:
        reactions = [{'emoji': e, 'count': counts.get(m.id, {}).get(e, 0), 'mine': (m.id, e) in mine}
                     for e in ChatReaction.EMOJIS if counts.get(m.id, {}).get(e)]
        reply = None
        if m.reply_to_id and m.reply_to:
            reply = {'id': m.reply_to_id, 'username': m.reply_to.user.username, 'text': _snippet(m.reply_to)}
        attachment = None
        if m.attachment and not m.is_deleted:
            attachment = {'url': reverse('chat_file', args=[m.id]), 'name': m.attachment_name, 'kind': m.attachment_kind}
        out.append({
            'id': m.id, 'username': m.user.username, 'text': '' if m.is_deleted else m.text,
            'time': timezone.localtime(m.created_at).strftime('%H:%M'), 'is_me': m.user_id == me.id,
            'deleted': m.is_deleted, 'edited': bool(m.edited_at), 'pinned': m.is_pinned,
            'reply': reply, 'reactions': reactions, 'attachment': attachment,
            'forwarded_from': m.forwarded_from, 'saved': m.id in saved_ids,
            'poll': None if m.is_deleted else _poll_payload(m, me.id),
            'mentions_me': bool(not m.is_deleted and me.username in MENTION.findall(m.text)),
            'can_edit': m.user_id == me.id and not m.is_deleted and not hasattr(m, 'poll'),
        })
    return out


@login_required
def chat_api(request):
    room = request.GET.get('room', 'global')
    if request.method == 'POST':
        data = _json_body(request)
        text = str(data.get('text', '')).strip()
        room = data.get('room', 'global')
        if not text:
            return _err('Type a message first.')
        blocked = _post_block(request.user, room)
        if blocked:
            return blocked
        reply = ChatMessage.objects.filter(pk=data.get('reply_to'), room=room).first() if data.get('reply_to') else None
        msg = ChatMessage.objects.create(user=request.user, text=text[:CHAT_MAX_LENGTH], room=room, reply_to=reply)
        _notify_mentions(msg)
        return JsonResponse({'status': 'ok', 'id': msg.id})
    if room not in CHAT_ROOMS:
        room = 'global'
    recent = (ChatMessage.objects.filter(room=room).select_related('user', 'reply_to__user')
              .prefetch_related('poll__options').order_by('-created_at')[:50])
    pinned = ChatMessage.objects.filter(room=room, is_pinned=True, is_deleted=False).select_related('user').first()
    cfg = _room_config(room)
    announce_only = (cfg.announcements_only if cfg else False) or (room == 'announcements' and cfg is None)
    return JsonResponse({
        'messages': _serialize_chat(reversed(list(recent)), request.user),
        'pinned': {'id': pinned.id, 'username': pinned.user.username, 'text': pinned.text[:300]} if pinned else None,
        'can_moderate': request.user.is_staff,
        'can_post': request.user.is_staff or not announce_only,
        'slow_mode_seconds': cfg.slow_mode_seconds if cfg else 0,
    })


@login_required
@require_GET
def chat_rooms_meta(request):
    """Newest message id per room, so the page can show unread dots without loading every room."""
    from django.db.models import Max
    latest = {r: 0 for r in CHAT_ROOMS}
    for row in ChatMessage.objects.filter(room__in=CHAT_ROOMS).values('room').annotate(m=Max('id')):
        latest[row['room']] = row['m']
    return JsonResponse({'latest': latest})


# ---------- files ----------

@login_required
@require_POST
def chat_upload(request):
    room = request.POST.get('room', 'global')
    upload = request.FILES.get('file')
    if not upload:
        return _err('Choose a file first.')
    ext = os.path.splitext(upload.name)[1].lower().lstrip('.')
    if ext not in IMAGE_EXTS | FILE_EXTS:
        return _err('That file type is not allowed. Use an image, PDF, Word, PowerPoint, Excel, text or CSV file.')
    if upload.size > MAX_UPLOAD_BYTES:
        return _err('That file is too big. The limit is 5 MB.')
    kind = 'image' if ext in IMAGE_EXTS else 'file'
    if kind == 'image':
        try:
            from PIL import Image
            Image.open(upload).verify()
            upload.seek(0)
        except Exception:  # noqa: BLE001 - anything unreadable is not a safe image
            return _err('That image could not be read. Try another one.')
    blocked = _post_block(request.user, room)
    if blocked:
        return blocked
    caption = str(request.POST.get('text', '')).strip()[:CHAT_MAX_LENGTH]
    reply = ChatMessage.objects.filter(pk=request.POST.get('reply_to') or 0, room=room).first()
    name = get_valid_filename(os.path.basename(upload.name))[:120] or f'file.{ext}'
    msg = ChatMessage(user=request.user, room=room, text=caption, reply_to=reply, attachment_name=name, attachment_kind=kind)
    msg.attachment.save(name, upload, save=False)
    msg.save()
    _notify_mentions(msg)
    return JsonResponse({'status': 'ok', 'id': msg.id})


@login_required
def chat_file(request, pk):
    msg = get_object_or_404(ChatMessage, pk=pk, is_deleted=False)
    if not msg.attachment:
        raise Http404
    if getattr(settings, 'USING_CLOUDINARY', False):
        return HttpResponseRedirect(msg.attachment.url)
    try:
        handle = msg.attachment.open('rb')
    except Exception:  # noqa: BLE001
        raise Http404
    ctype = mimetypes.guess_type(msg.attachment_name)[0] or 'application/octet-stream'
    resp = FileResponse(handle, content_type=ctype, as_attachment=(msg.attachment_kind != 'image'), filename=msg.attachment_name)
    resp['X-Content-Type-Options'] = 'nosniff'
    return resp


# ---------- edit / delete / react / pin ----------

def _msg_or_404(pk):
    return get_object_or_404(ChatMessage, pk=pk)


@login_required
@require_POST
def chat_edit(request, pk):
    msg = _msg_or_404(pk)
    if msg.user_id != request.user.id or msg.is_deleted or hasattr(msg, 'poll'):
        return _err('You can only edit your own messages.', 403)
    text = str(_json_body(request).get('text', '')).strip()
    if not text:
        return _err('A message cannot be empty. Delete it instead.')
    old = msg.text
    msg.text = text[:CHAT_MAX_LENGTH]
    msg.edited_at = timezone.now()
    msg.save(update_fields=['text', 'edited_at'])
    _notify_mentions(msg, previous_text=old)
    return JsonResponse({'status': 'ok'})


@login_required
@require_POST
def chat_delete(request, pk):
    msg = _msg_or_404(pk)
    if msg.user_id != request.user.id and not request.user.is_staff:
        return _err('You can only delete your own messages.', 403)
    msg.is_deleted, msg.is_pinned, msg.text = True, False, ''
    msg.save(update_fields=['is_deleted', 'is_pinned', 'text'])
    ChatReaction.objects.filter(message=msg).delete()
    return JsonResponse({'status': 'ok'})


@login_required
@require_POST
def chat_react(request, pk):
    msg = _msg_or_404(pk)
    emoji = str(_json_body(request).get('emoji', ''))
    if emoji not in ChatReaction.EMOJIS or msg.is_deleted:
        return _err('Pick one of the available reactions.')
    reaction, created = ChatReaction.objects.get_or_create(message=msg, user=request.user, emoji=emoji)
    if not created:
        reaction.delete()
    return JsonResponse({'status': 'ok', 'added': created})


@login_required
@require_POST
def chat_pin(request, pk):
    if not request.user.is_staff:
        return _err('Only admins can pin messages.', 403)
    msg = _msg_or_404(pk)
    if msg.is_deleted:
        return _err('That message was deleted.')
    pin = not msg.is_pinned
    if pin:
        ChatMessage.objects.filter(room=msg.room, is_pinned=True).update(is_pinned=False)
    msg.is_pinned = pin
    msg.save(update_fields=['is_pinned'])
    return JsonResponse({'status': 'ok', 'pinned': pin})


# ---------- polls ----------

@login_required
@require_POST
def chat_poll_create(request):
    data = _json_body(request)
    room = data.get('room', 'global')
    question = ' '.join(str(data.get('question', '')).split())[:200]
    options = [' '.join(str(o).split())[:80] for o in (data.get('options') or []) if str(o).strip()][:6]
    if not question or len(options) < 2:
        return _err('A poll needs a question and at least 2 options.')
    blocked = _post_block(request.user, room)
    if blocked:
        return blocked
    msg = ChatMessage.objects.create(user=request.user, room=room, text=question)
    poll = ChatPoll.objects.create(message=msg)
    ChatPollOption.objects.bulk_create([ChatPollOption(poll=poll, text=t, position=i) for i, t in enumerate(options)])
    return JsonResponse({'status': 'ok', 'id': msg.id})


@login_required
@require_POST
def chat_poll_vote(request, option_id):
    option = get_object_or_404(ChatPollOption.objects.select_related('poll__message'), pk=option_id)
    if option.poll.message.is_deleted:
        return _err('That poll was deleted.')
    existing = ChatPollVote.objects.filter(option__poll=option.poll, user=request.user)
    if existing.filter(option=option).exists():
        existing.delete()                     # tapping your choice again removes your vote
        return JsonResponse({'status': 'ok', 'voted': False})
    existing.delete()                         # one vote per poll: switching moves it
    ChatPollVote.objects.create(option=option, user=request.user)
    return JsonResponse({'status': 'ok', 'voted': True})


# ---------- mentions, search ----------

@login_required
@require_GET
def chat_users(request):
    """Usernames for @mention autocomplete: only people who have chatted in the last 30 days."""
    q = request.GET.get('q', '').strip().lstrip('@')[:30]
    since = timezone.now() - timedelta(days=30)
    names = (ChatMessage.objects.filter(created_at__gte=since, user__username__istartswith=q, user__is_active=True)
             .exclude(user=request.user).values_list('user__username', flat=True).distinct()[:6])
    return JsonResponse({'users': list(names)})


@login_required
@require_GET
def chat_search(request):
    room = request.GET.get('room', 'global')
    q = ' '.join(request.GET.get('q', '').split())[:60]
    if room not in CHAT_ROOMS or len(q) < 2:
        return JsonResponse({'results': []})
    hits = (ChatMessage.objects.filter(room=room, is_deleted=False, text__icontains=q)
            .select_related('user').order_by('-created_at')[:30])
    return JsonResponse({'results': [
        {'id': m.id, 'username': m.user.username, 'text': m.text[:200],
         'when': timezone.localtime(m.created_at).strftime('%d %b %H:%M')} for m in hits]})


# ---------- forward, saved ----------

@login_required
@require_POST
def chat_forward(request, pk):
    src = _msg_or_404(pk)
    room = _json_body(request).get('room')
    if src.is_deleted:
        return _err('That message was deleted.')
    blocked = _post_block(request.user, room)
    if blocked:
        return blocked
    msg = ChatMessage(user=request.user, room=room, text=src.text, forwarded_from=src.forwarded_from or src.user.username,
                      attachment_name=src.attachment_name, attachment_kind=src.attachment_kind)
    if src.attachment:
        msg.attachment.name = src.attachment.name       # same stored file, no copy
    msg.save()
    return JsonResponse({'status': 'ok', 'id': msg.id})


@login_required
@require_POST
def chat_save(request, pk):
    msg = _msg_or_404(pk)
    existing = SavedChat.objects.filter(user=request.user, source=msg)
    if existing.exists():
        existing.delete()
        return JsonResponse({'status': 'ok', 'saved': False})
    if msg.is_deleted:
        return _err('That message was deleted.')
    SavedChat.objects.create(user=request.user, source=msg, text=msg.text, author=msg.user.username,
                             room=msg.room, attachment_name=msg.attachment_name)
    return JsonResponse({'status': 'ok', 'saved': True})


@login_required
@require_GET
def chat_saved(request):
    items = SavedChat.objects.filter(user=request.user)[:100]
    return JsonResponse({'saved': [{'id': s.id, 'author': s.author, 'text': s.text[:300], 'file': s.attachment_name, 'room': s.room,
                                    'when': timezone.localtime(s.created_at).strftime('%d %b')} for s in items]})


@login_required
@require_POST
def chat_unsave(request, pk):
    get_object_or_404(SavedChat, pk=pk, user=request.user).delete()
    return JsonResponse({'status': 'ok'})
