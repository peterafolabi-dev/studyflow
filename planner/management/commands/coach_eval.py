import json
import os

from django.core.management.base import BaseCommand, CommandError

from planner.coach import evals
from planner.coach.engine import model_candidates
from planner.coach.prompt import PLAYBOOK_VERSION


class Command(BaseCommand):
    help = "Give StudyFlow Coach its exam: run realistic student scenarios against the live model and mark the replies."

    def add_arguments(self, parser):
        parser.add_argument('--only', help='Run scenarios whose name contains this text')
        parser.add_argument('--json', help='Write the full report (with replies) to this file')
        parser.add_argument('--min-score', type=float, default=0.0, help='Fail (exit 1) below this pass rate, e.g. 0.8')

    def handle(self, *args, **opts):
        key = os.environ.get('GROQ_API_KEY')
        if not key:
            raise CommandError('Set GROQ_API_KEY to run the coach exam against the real model.')
        from groq import Groq
        scenarios = [s for s in evals.SCENARIOS if not opts['only'] or opts['only'].lower() in s.name.lower()]
        self.stdout.write(f"StudyFlow Coach exam · playbook {PLAYBOOK_VERSION} · model {model_candidates()[0]} · {len(scenarios)} scenarios\n")
        passed, total, rows = evals.run(Groq(api_key=key), scenarios, verbose=self.stdout.write)
        score = passed / total if total else 0
        self.stdout.write(self.style.SUCCESS(f"\nScore: {passed}/{total} checks ({score:.0%})") if score >= 0.8 else self.style.WARNING(f"\nScore: {passed}/{total} checks ({score:.0%})"))
        if opts['json']:
            with open(opts['json'], 'w', encoding='utf-8') as fh:
                json.dump({'playbook': PLAYBOOK_VERSION, 'model': model_candidates()[0], 'score': score, 'rows': rows}, fh, indent=2, default=str)
        if score < opts['min_score']:
            raise CommandError(f'Score {score:.0%} is below --min-score {opts["min_score"]:.0%}')
