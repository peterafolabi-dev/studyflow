import csv

from django.core.management.base import BaseCommand, CommandError

from library.models import Book
from resources.models import PhysicalHolding

TRUTHY = {'1', 'true', 'yes', 'y', 't'}


class Command(BaseCommand):
    help = (
        'Bulk-import books or IBB Library holdings from a CSV file.\n\n'
        'Books CSV columns:    title, author, subject, level, is_postgraduate, description\n'
        'Holdings CSV columns: title, author, category, shelf_location, is_available\n\n'
        'Example: python manage.py import_csv books my_books.csv'
    )

    def add_arguments(self, parser):
        parser.add_argument('kind', choices=['books', 'holdings'])
        parser.add_argument('path', help='Path to the CSV file (needs a header row)')

    def handle(self, *args, **options):
        kind, path = options['kind'], options['path']
        try:
            handle = open(path, newline='', encoding='utf-8-sig')
        except OSError as exc:
            raise CommandError(f'Could not open {path}: {exc}')

        created = skipped = 0
        with handle:
            reader = csv.DictReader(handle)
            if 'title' not in (reader.fieldnames or []):
                raise CommandError('CSV needs a header row with at least a "title" column.')

            for line_no, row in enumerate(reader, start=2):
                title = (row.get('title') or '').strip()
                if not title:
                    self.stderr.write(f'Line {line_no}: no title, skipped.')
                    skipped += 1
                    continue

                if kind == 'books':
                    try:
                        level = int((row.get('level') or '100').strip())
                    except ValueError:
                        self.stderr.write(f'Line {line_no}: level must be 100-500, skipped.')
                        skipped += 1
                        continue
                    if level not in (100, 200, 300, 400, 500):
                        self.stderr.write(f'Line {line_no}: level {level} not in 100-500, skipped.')
                        skipped += 1
                        continue
                    _, was_created = Book.objects.get_or_create(
                        title=title,
                        defaults={
                            'author': (row.get('author') or '').strip(),
                            'subject': (row.get('subject') or '').strip(),
                            'level': level,
                            'is_postgraduate': (row.get('is_postgraduate') or '').strip().lower() in TRUTHY,
                            'description': (row.get('description') or '').strip(),
                            'cover_color': created % 6,
                        },
                    )
                else:
                    available = (row.get('is_available') or 'yes').strip().lower() in TRUTHY
                    _, was_created = PhysicalHolding.objects.get_or_create(
                        title=title,
                        defaults={
                            'author': (row.get('author') or '').strip(),
                            'category': (row.get('category') or '').strip(),
                            'shelf_location': (row.get('shelf_location') or '').strip(),
                            'is_available': available,
                        },
                    )

                if was_created:
                    created += 1
                else:
                    skipped += 1  # already existed (matched on title)

        self.stdout.write(self.style.SUCCESS(
            f'Imported {created} new {kind}. Skipped {skipped} (blank, invalid, or already present).'
        ))
