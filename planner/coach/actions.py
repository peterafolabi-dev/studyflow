"""Turn the coach's action lines into buttons, and carry them out when tapped.

The model only *proposes* actions. Tasks are created only when the student
taps the button; "remember" notes are saved straight away but are visible
and deletable by the student.
"""
import re
from datetime import date, timedelta

from django.utils import timezone

from planner.models import CoachMemory, Course, Flashcard, FlashcardDeck, Task

ACTION_LINE = re.compile(r'^\s*\[\[\s*(task|remember)\s*:\s*(.+?)\s*\]\]\s*$', re.IGNORECASE | re.MULTILINE)
CARD = re.compile(
    r'\*\*\s*Front\s*:?\s*\*\*\s*:?\s*(?P<front>.+?)\s*\n\s*\*\*\s*Back\s*:?\s*\*\*\s*:?\s*(?P<back>.+?)(?=\n\s*\n|\n\s*\*\*\s*Card|\Z)',
    re.IGNORECASE | re.DOTALL,
)
SENSITIVE = re.compile(r'password|passcode|\bpin\b|bvn|\bnin\b|card number|account number|\+?\d[\d\s-]{8,}\d', re.IGNORECASE)
MAX_TASKS = 5


def split_reply(reply):
    """Return (clean_reply, proposed_tasks, memory_notes)."""
    tasks, notes = [], []
    today = timezone.localdate()
    for kind, body in ACTION_LINE.findall(reply or ''):
        kind = kind.lower()
        if kind == 'task' and len(tasks) < MAX_TASKS:
            parts = [p.strip() for p in body.split('|')]
            if len(parts) != 3 or not parts[1]:
                continue
            try:
                due = date.fromisoformat(parts[2])
            except ValueError:
                continue
            if due < today or due > today + timedelta(days=366):
                continue
            tasks.append({'course': parts[0][:100], 'title': parts[1][:200], 'due': due.isoformat()})
        elif kind == 'remember' and not notes:
            note = body.strip()[:200]
            if note and not SENSITIVE.search(note):
                notes.append(note)
    clean = ACTION_LINE.sub('', reply or '').rstrip()
    clean = re.sub(r'\n{3,}', '\n\n', clean)
    return clean, tasks, notes


def extract_cards(reply, limit=30):
    cards = []
    for m in CARD.finditer(reply or ''):
        front, back = m.group('front').strip(), m.group('back').strip()
        if front and back:
            cards.append({'front': front[:1000], 'back': back[:2000]})
        if len(cards) >= limit:
            break
    return cards


def save_memory(user, notes):
    saved = []
    existing = {n.lower() for n in CoachMemory.objects.filter(user=user).values_list('note', flat=True)}
    for note in notes:
        if note.lower() in existing:
            continue
        saved.append(CoachMemory.objects.create(user=user, note=note).note)
    # keep only the newest MAX_PER_USER
    stale = CoachMemory.objects.filter(user=user).order_by('-created_at')[CoachMemory.MAX_PER_USER:]
    CoachMemory.objects.filter(pk__in=[m.pk for m in stale]).delete()
    return saved


def match_course(user, label):
    """Find the student's course by code or name; create it only if nothing matches."""
    label = (label or '').strip()
    courses = Course.objects.filter(user=user)
    squash = label.upper().replace(' ', '')
    for c in courses:
        if squash and (c.code or '').upper().replace(' ', '') == squash:
            return c
    for c in courses:
        if label and (c.name.lower() == label.lower() or label.lower() in f"{c.code} {c.name}".lower()):
            return c
    code_match = re.match(r'^([A-Za-z]{3})\s?(\d{3})$', label)
    if code_match:
        code = f"{code_match.group(1).upper()} {code_match.group(2)}"
        return Course.objects.create(user=user, name=code, code=code)
    return Course.objects.create(user=user, name=(label or 'General')[:100])


def create_task(user, course_label, title, due_iso):
    due = date.fromisoformat(due_iso)
    if due < timezone.localdate():
        raise ValueError('That date has passed.')
    course = match_course(user, course_label)
    task, created = Task.objects.get_or_create(course=course, title=title.strip()[:200], due_date=due)
    return task, created


def save_cards(user, course_label, deck_title, cards):
    course = match_course(user, course_label or 'General')
    deck, _ = FlashcardDeck.objects.get_or_create(course=course, title=(deck_title or 'From StudyFlow Coach')[:200])
    made = 0
    for c in cards[:30]:
        front, back = str(c.get('front', '')).strip(), str(c.get('back', '')).strip()
        if front and back:
            Flashcard.objects.create(deck=deck, front=front[:1000], back=back[:2000])
            made += 1
    return deck, made
