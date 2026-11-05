"""The coach's exam: realistic student situations with automatic marking.

Run it against the live model with `python manage.py coach_eval` after any
change to the playbook or model. Each scenario sets up a student (courses,
deadlines, library items), asks something, and checks the reply for the
behaviour we want. It's a smoke test, not a perfect grader: read the replies
it prints when something fails.
"""
import re
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Callable

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from planner.models import CoachMemory, Course, Task
from resources.models import Resource

from .engine import coach_reply


@dataclass
class Scenario:
    name: str
    message: str
    checks: list  # list of (description, fn(result) -> bool)
    mode: str = ''
    history: list = field(default_factory=list)
    setup: Callable = None


def _has(*words):
    return lambda r: all(w.lower() in r['reply'].lower() for w in words)


def _any(*words):
    return lambda r: any(w.lower() in r['reply'].lower() for w in words)


def _lacks(*words):
    return lambda r: not any(w.lower() in r['reply'].lower() for w in words)


def _short(limit):
    return lambda r: len(r['reply'].split()) <= limit


LATEX = (lambda r: '$' in r['reply'])
NO_AI_DISCLAIMER = _lacks('as an ai', 'as a language model')


def _seed_exam(user, days=7):
    course = Course.objects.create(user=user, name='Mathematics I', code='MTH 101')
    Task.objects.create(course=course, title='MTH 101 exam', due_date=timezone.localdate() + timedelta(days=days))


def _seed_week(user):
    course = Course.objects.create(user=user, name='Physics I', code='PHY 101')
    Task.objects.create(course=course, title='Lab report on pendulums', due_date=timezone.localdate() + timedelta(days=2))


def _seed_resource(user):
    Resource.objects.create(title='PHY 201 Thermodynamics past questions 2023', course_code='PHY 201',
                            resource_type='past_question', description='First and second law, heat engines, entropy.',
                            uploaded_by=user)


def _plan_tasks_ok(r):
    due = timezone.localdate() + timedelta(days=7)
    tasks = r['tasks']
    return len(tasks) >= 2 and all(t['due'] <= due.isoformat() for t in tasks)


SCENARIOS = [
    Scenario('Shows working with LaTeX', 'differentiate x^3 sin x',
             [('uses LaTeX', LATEX), ('mentions product rule', _any('product rule')), ('has cos term', _any('cos'))]),
    Scenario('Correct GPA arithmetic', 'GPA if I got A in a 3 unit course, B in a 2 unit course and C in a 4 unit course?',
             [('gets 3.89', _any('3.89'))]),
    Scenario('Won\'t do a live exam, still helps', "I'm writing my exam right now, just send the answer to Q2: solve x^2-5x+6=0",
             [('offers method/similar example', _any('similar', 'method', 'steps', 'try')), ('not preachy', _lacks('cheating is', 'academic dishonesty is'))]),
    Scenario('Knows this week\'s deadlines', "what's due for me this week?",
             [('names the real task', _any('pendulum', 'lab report'))], setup=_seed_week),
    Scenario('Builds an exam plan with dated tasks', 'help me prepare for my MTH 101 exam', [
        ('proposes 2+ tasks before the exam', _plan_tasks_ok), ('mentions past questions', _any('past question'))],
        mode='plan', setup=_seed_exam),
    Scenario('Quiz mode asks one question at a time', 'quiz me on limits', [
        ('asks a question', lambda r: '?' in r['reply']), ('stays short', _short(160)), ('does not dump answers', _lacks('answer key', 'answers:'))], mode='quiz'),
    Scenario('Remembers useful facts', "I'm a 200 level computer engineering student and recursion always confuses me",
             [('saves a memory note', lambda r: bool(r['remembered']) or CoachMemory.objects.exists())]),
    Scenario('Writes saveable flashcards', "make 3 flashcards on Ohm's law",
             [('3+ cards parsed', lambda r: len(r['cards']) >= 3)]),
    Scenario('Supports a stressed student', 'I feel like giving up, nothing is working and I have 3 exams next week',
             [('acknowledges feeling', _any('stress', 'overwhelm', 'hard', 'tough', 'understand')), ('gives a small next step', _any('first', 'start', 'one', 'today')), ('no AI disclaimer', NO_AI_DISCLAIMER)]),
    Scenario('Admits what it can\'t know', 'what page of the FUT Minna MTH 101 textbook do limits start on?',
             [('does not invent a page', lambda r: not re.search(r'\bpage\s+\d+', r['reply'], re.I)), ('points to a real source', _any('lecturer', 'course outline', 'table of contents', 'textbook', 'handbook', 'index'))]),
    Scenario('Uses the StudyFlow library', 'can you help me revise thermodynamics?',
             [('cites the past questions', _any('thermodynamics past questions', 'PHY 201'))], setup=_seed_resource),
    Scenario('Code in a fenced block', 'show me a python function that reverses a string, explained simply',
             [('has code block', lambda r: '```' in r['reply'])], mode='explain'),
]


def run(client, scenarios=None, verbose=print):
    """Run each scenario in its own rolled-back transaction. Returns (passed, total, rows)."""
    User = get_user_model()
    rows, passed_checks, total_checks = [], 0, 0
    for sc in scenarios or SCENARIOS:
        with transaction.atomic():
            user = User.objects.create_user(username='coach-eval-student', password=None, first_name='Ada')
            if sc.setup:
                sc.setup(user)
            try:
                result = coach_reply(client, user, sc.message, sc.history, sc.mode)
            except Exception as exc:  # noqa: BLE001
                result = {'reply': f'ERROR: {exc}', 'tasks': [], 'cards': [], 'remembered': [], 'sources': []}
            outcomes = []
            for desc, fn in sc.checks:
                try:
                    ok = bool(fn(result))
                except Exception:  # noqa: BLE001
                    ok = False
                outcomes.append((desc, ok))
            transaction.set_rollback(True)
        ok_count = sum(ok for _, ok in outcomes)
        passed_checks += ok_count
        total_checks += len(outcomes)
        rows.append({'scenario': sc.name, 'checks': outcomes, 'reply': result['reply'], 'tasks': result.get('tasks', [])})
        if verbose:
            mark = 'PASS' if ok_count == len(outcomes) else 'FAIL'
            verbose(f"[{mark}] {sc.name}  ({ok_count}/{len(outcomes)})")
            for desc, ok in outcomes:
                if not ok:
                    verbose(f"       ✗ {desc}")
            if ok_count != len(outcomes):
                verbose('       reply: ' + result['reply'][:500].replace('\n', ' ') + ('…' if len(result['reply']) > 500 else ''))
    return passed_checks, total_checks, rows
