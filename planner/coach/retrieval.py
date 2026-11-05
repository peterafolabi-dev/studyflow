"""Find real StudyFlow items that match a question, so the coach can cite them.

Plain keyword scoring that works the same on SQLite and Postgres: no extra
services, no embeddings bill. It looks at shared resources (notes, past
questions), public CBT question banks, and the student's own flashcards.
"""
import re

from django.db.models import Q
from django.urls import reverse

from planner.models import Flashcard
from resources.models import CBTQuestion, Resource

STOPWORDS = set("""
a an the and or but if then so to of in on at by for with from into about as is are was were be been being do does did
how what why when where which who whom whose this that these those it its i me my we our you your he she they them their
can could would should will shall may might must please explain tell give show help need want know understand solve find
make get some any all more most very much many just also not no yes than too vs versus between there here up down out
question questions answer answers topic topics course note notes chapter study exam test quiz
""".split())

COURSE_CODE = re.compile(r'\b([A-Za-z]{3})\s?(\d{3})\b')


def keywords(text, limit=8):
    words = re.findall(r"[A-Za-z][A-Za-z0-9'+-]{2,}", (text or '').lower())
    seen, out = set(), []
    for w in words:
        w = w.strip("'")
        if w in STOPWORDS or w in seen or len(w) < 3:
            continue
        seen.add(w)
        out.append(w)
    return out[:limit]


def course_codes(text):
    return {f"{a.upper()} {b}" for a, b in COURSE_CODE.findall(text or '')}


def _score(text, words):
    text = (text or '').lower()
    return sum(1 for w in words if w in text)


def search_library(user, question, limit=4):
    """Return a short text block for the prompt plus a list of links for the UI."""
    words = keywords(question)
    codes = course_codes(question)
    if not words and not codes:
        return '', []

    hits = []  # (score, kind, title, url, snippet)

    q = Q()
    for w in words:
        q |= Q(title__icontains=w) | Q(description__icontains=w)
    for c in codes:
        q |= Q(course_code__iexact=c) | Q(course_code__iexact=c.replace(' ', ''))
    for r in Resource.objects.filter(q).order_by('-created_at')[:40]:
        s = _score(f"{r.title} {r.description}", words) + (3 if (r.course_code or '').upper().replace(' ', '') in {c.replace(' ', '') for c in codes} else 0)
        if s:
            hits.append((s, r.get_resource_type_display(), r.title, reverse('resource_detail', args=[r.pk]),
                         (r.description or '')[:160]))

    if words:
        qq = Q()
        for w in words:
            qq |= Q(text__icontains=w)
        bank_filter = Q(bank__is_public=True) | Q(bank__created_by=user)
        for cq in CBTQuestion.objects.filter(qq).filter(bank_filter).select_related('bank')[:40]:
            s = _score(cq.text, words)
            if s >= max(1, min(2, len(words))):
                answer = getattr(cq, f"option_{(cq.correct_option or 'a').lower()}", '')
                snippet = f"Q: {cq.text[:140]} | Answer: {answer[:80]}" + (f" | Why: {cq.explanation[:140]}" if cq.explanation else '')
                hits.append((s + 1, 'Past question', cq.bank.title, reverse('cbt_detail', args=[cq.bank_id]), snippet))

        fq = Q()
        for w in words:
            fq |= Q(front__icontains=w) | Q(back__icontains=w)
        for card in Flashcard.objects.filter(fq, deck__course__user=user).select_related('deck')[:20]:
            s = _score(f"{card.front} {card.back}", words)
            if s:
                hits.append((s, 'Your flashcard', card.deck.title, reverse('flashcards'),
                             f"Front: {card.front[:100]} | Back: {card.back[:100]}"))

    hits.sort(key=lambda h: -h[0])
    seen, picked = set(), []
    for h in hits:
        key = (h[1], h[2])
        if key in seen:
            continue
        seen.add(key)
        picked.append(h)
        if len(picked) >= limit:
            break

    block = '\n'.join(f"- [{kind}] {title}: {snippet}" if snippet else f"- [{kind}] {title}" for _, kind, title, _, snippet in picked)
    links = [{'kind': kind, 'title': title, 'url': url} for _, kind, title, url, _ in picked]
    return block, links
