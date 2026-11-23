"""Lost & found, events board and opportunities."""
import re
from datetime import timedelta, timezone as dt_timezone

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.validators import URLValidator
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from resources.ai_service import RateLimitExceeded, check_and_increment_rate_limit

from .models import CampusEvent, LostFoundItem, Opportunity

POSTS_PER_HOUR = 10


def _clean_whatsapp(value):
    digits = re.sub(r'[\s\-+()]', '', value or '')
    if not digits.isdigit() or not 10 <= len(digits) <= 15:
        raise forms.ValidationError('Enter a WhatsApp number with country code, e.g. 2348012345678.')
    return digits


def _allowed_to_post(request, bucket):
    try:
        check_and_increment_rate_limit(request.user.pk, bucket, POSTS_PER_HOUR, 3600)
        return True
    except RateLimitExceeded:
        messages.error(request, 'You are posting too fast. Please try again in a little while.')
        return False


def _first_error(form):
    for errors in form.errors.values():
        return errors[0]
    return 'Please check the form and try again.'


# ── Lost & found ────────────────────────────────────────────────────────────

class LostFoundForm(forms.ModelForm):
    class Meta:
        model = LostFoundItem
        fields = ['kind', 'title', 'description', 'location', 'whatsapp_number']

    def clean_whatsapp_number(self):
        return _clean_whatsapp(self.cleaned_data['whatsapp_number'])

    def clean_title(self):
        title = self.cleaned_data['title'].strip()
        if not title:
            raise forms.ValidationError('Add a short title.')
        return title


@login_required
def lost_found(request):
    kind = request.GET.get('kind', '')
    items = LostFoundItem.objects.select_related('reporter')
    if kind in ('lost', 'found'):
        items = items.filter(kind=kind)
    return render(request, 'campus/lost_found.html', {'items': items[:100], 'selected_kind': kind})


@login_required
@require_POST
def lost_found_create(request):
    if not _allowed_to_post(request, 'lost_found_post'):
        return redirect('lost_found')
    form = LostFoundForm(request.POST)
    if form.is_valid():
        item = form.save(commit=False)
        item.reporter = request.user
        item.save()
        messages.success(request, 'Posted. Mark it as resolved once it is sorted out.')
    else:
        messages.error(request, _first_error(form))
    return redirect('lost_found')


@login_required
@require_POST
def lost_found_resolve(request, pk):
    item = get_object_or_404(LostFoundItem, pk=pk, reporter=request.user)
    item.is_resolved = not item.is_resolved
    item.save(update_fields=['is_resolved'])
    return redirect('lost_found')


@login_required
@require_POST
def lost_found_delete(request, pk):
    item = get_object_or_404(LostFoundItem, pk=pk)
    if item.reporter_id != request.user.pk and not request.user.is_staff:
        raise Http404
    item.delete()
    messages.success(request, 'Post removed.')
    return redirect('lost_found')


# ── Events ──────────────────────────────────────────────────────────────────

class EventForm(forms.ModelForm):
    starts_at = forms.DateTimeField(input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M'])
    ends_at = forms.DateTimeField(required=False, input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M'])

    class Meta:
        model = CampusEvent
        fields = ['title', 'description', 'location', 'starts_at', 'ends_at']

    def clean(self):
        data = super().clean()
        start, end = data.get('starts_at'), data.get('ends_at')
        if start and end and end <= start:
            self.add_error('ends_at', 'The end must be after the start.')
        if start and start < timezone.now() - timedelta(hours=1):
            self.add_error('starts_at', 'Events must be in the future.')
        return data


@login_required
def events(request):
    now = timezone.now()
    upcoming = CampusEvent.objects.filter(is_approved=True).filter(
        starts_at__gte=now - timedelta(hours=3)
    )
    mine_pending = CampusEvent.objects.filter(organizer=request.user, is_approved=False)
    return render(request, 'campus/events.html', {'events': upcoming, 'pending': mine_pending})


@login_required
@require_POST
def event_create(request):
    if not _allowed_to_post(request, 'event_post'):
        return redirect('campus_events')
    form = EventForm(request.POST)
    if form.is_valid():
        event = form.save(commit=False)
        event.organizer = request.user
        event.is_approved = request.user.is_staff
        event.save()
        messages.success(request, 'Event posted.' if event.is_approved else 'Thanks! Your event will appear once staff approve it.')
    else:
        messages.error(request, _first_error(form))
    return redirect('campus_events')


@login_required
@require_POST
def event_delete(request, pk):
    event = get_object_or_404(CampusEvent, pk=pk)
    if event.organizer_id != request.user.pk and not request.user.is_staff:
        raise Http404
    event.delete()
    messages.success(request, 'Event removed.')
    return redirect('campus_events')


def _ics_escape(text):
    return (text or '').replace('\\', '\\\\').replace(';', '\;').replace(',', '\\,').replace('\r', '').replace('\n', '\\n')


def _ics_dt(dt):
    return dt.astimezone(dt_timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def _calendar(events, filename):
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//StudyFlow//Campus Events//EN', 'CALSCALE:GREGORIAN']
    stamp = _ics_dt(timezone.now())
    for e in events:
        end = e.ends_at or (e.starts_at + timedelta(hours=1))
        lines += [
            'BEGIN:VEVENT',
            f'UID:studyflow-event-{e.pk}@studyflow.local',
            f'DTSTAMP:{stamp}',
            f'DTSTART:{_ics_dt(e.starts_at)}',
            f'DTEND:{_ics_dt(end)}',
            f'SUMMARY:{_ics_escape(e.title)}',
            f'LOCATION:{_ics_escape(e.location)}',
            f'DESCRIPTION:{_ics_escape(e.description)}',
            'END:VEVENT',
        ]
    lines.append('END:VCALENDAR')
    response = HttpResponse('\r\n'.join(lines) + '\r\n', content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def event_ics(request, pk):
    event = get_object_or_404(CampusEvent, pk=pk, is_approved=True)
    return _calendar([event], f'studyflow-event-{event.pk}.ics')


@login_required
def events_ics(request):
    upcoming = CampusEvent.objects.filter(is_approved=True, starts_at__gte=timezone.now())
    return _calendar(upcoming, 'studyflow-campus-events.ics')


# ── Opportunities ───────────────────────────────────────────────────────────

class OpportunityForm(forms.ModelForm):
    class Meta:
        model = Opportunity
        fields = ['kind', 'title', 'organisation', 'description', 'link', 'deadline']

    def clean_link(self):
        link = self.cleaned_data['link']
        URLValidator(schemes=['http', 'https'])(link)
        return link

    def clean_deadline(self):
        deadline = self.cleaned_data['deadline']
        if deadline < timezone.localdate():
            raise forms.ValidationError('The deadline has already passed.')
        return deadline


@login_required
def opportunities(request):
    kind = request.GET.get('kind', '')
    items = Opportunity.objects.filter(is_approved=True, deadline__gte=timezone.localdate())
    if kind in dict(Opportunity.KIND_CHOICES):
        items = items.filter(kind=kind)
    pending = Opportunity.objects.filter(submitted_by=request.user, is_approved=False)
    return render(request, 'campus/opportunities.html', {
        'items': items, 'pending': pending, 'selected_kind': kind, 'kinds': Opportunity.KIND_CHOICES,
    })


@login_required
@require_POST
def opportunity_create(request):
    if not _allowed_to_post(request, 'opportunity_post'):
        return redirect('campus_opportunities')
    form = OpportunityForm(request.POST)
    if form.is_valid():
        item = form.save(commit=False)
        item.submitted_by = request.user
        item.is_approved = request.user.is_staff
        item.save()
        messages.success(request, 'Opportunity posted.' if item.is_approved else 'Thanks! It will appear once staff approve it.')
    else:
        messages.error(request, _first_error(form))
    return redirect('campus_opportunities')


@login_required
@require_POST
def opportunity_delete(request, pk):
    item = get_object_or_404(Opportunity, pk=pk)
    if item.submitted_by_id != request.user.pk and not request.user.is_staff:
        raise Http404
    item.delete()
    messages.success(request, 'Opportunity removed.')
    return redirect('campus_opportunities')
