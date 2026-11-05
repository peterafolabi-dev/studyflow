import json

from django.core.management.base import BaseCommand

from planner.models import CoachFeedback


class Command(BaseCommand):
    help = ("Export thumbs-up coach replies as chat-format JSONL (good examples to study or fine-tune on), "
            "and thumbs-down ones separately so you can fix the playbook.")

    def add_arguments(self, parser):
        parser.add_argument('--out', default='coach_feedback.jsonl', help='Where to write the helpful examples')
        parser.add_argument('--bad-out', default='coach_feedback_unhelpful.jsonl', help='Where to write the unhelpful ones')

    def handle(self, *args, **opts):
        good = bad = 0
        with open(opts['out'], 'w', encoding='utf-8') as g, open(opts['bad_out'], 'w', encoding='utf-8') as b:
            for fb in CoachFeedback.objects.order_by('created_at').iterator():
                row = {'messages': [{'role': 'user', 'content': fb.question}, {'role': 'assistant', 'content': fb.reply}],
                       'mode': fb.mode, 'playbook': fb.playbook_version, 'model': fb.model_name, 'comment': fb.comment}
                (g if fb.helpful else b).write(json.dumps(row, ensure_ascii=False) + '\n')
                good += fb.helpful
                bad += not fb.helpful
        self.stdout.write(self.style.SUCCESS(f'{good} helpful -> {opts["out"]}; {bad} unhelpful -> {opts["bad_out"]}'))
