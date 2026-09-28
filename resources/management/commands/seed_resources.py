from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from resources.models import PhysicalHolding, Resource


class Command(BaseCommand):
    help = 'Seed demo past questions, notes, theses/papers, lecture slides, and IBB Library holdings.'

    def handle(self, *args, **options):
        User = get_user_model()
        uploader, _ = User.objects.get_or_create(username='demo')

        demo_resources = [
            ('CPE 205 Past Questions (2023/2024)', 'CPE 205', 'past_question',
             'Two most recent semester exams with the marking scheme.'),
            ('EEE 301 Past Questions (2022/2023)', 'EEE 301', 'past_question',
             'Mid-semester test and final exam papers.'),
            ('Signals and Systems — Lecture Notes', 'EEE 301', 'notes',
             'Condensed notes covering convolution and Fourier series.'),
            ('Data Structures — Week 1-6 Notes', 'CPE 205', 'notes',
             'Summarised notes on arrays, linked lists, stacks and queues.'),
            ('Final Year Thesis: Solar-Powered Irrigation System', '', 'thesis',
             'Undergraduate thesis on a low-cost solar irrigation controller.'),
            ('Research Paper: ML for Crop Yield Prediction', '', 'paper',
             'A short applied-ML paper predicting crop yield from soil sensor data.'),
            ('MTH 201 Lecture Slides — Week 3', 'MTH 201', 'lecture_slide',
             'Slide deck covering differential equations, first order.'),
            ('CPE 205 Lecture Slides — Trees & Graphs', 'CPE 205', 'lecture_slide',
             'Slide deck introducing tree and graph data structures.'),
        ]

        created = 0
        for title, course_code, rtype, description in demo_resources:
            resource, was_created = Resource.objects.get_or_create(
                title=title,
                defaults={
                    'course_code': course_code, 'resource_type': rtype,
                    'description': description, 'uploaded_by': uploader,
                },
            )
            if was_created:
                placeholder = (
                    f'{title}\n\nThis is a demo placeholder file standing in for the real '
                    f'{dict(Resource.TYPE_CHOICES)[rtype].lower()}.\n\n{description}\n'
                )
                resource.file.save(f'{title[:40]}.txt', ContentFile(placeholder), save=True)
                created += 1

        holdings = [
            ('Introduction to Thermodynamics', 'Y. A. Cengel', 'Mechanical Engineering', 'Floor 2, Shelf B12'),
            ('Electric Circuits', 'J. W. Nilsson', 'Electrical Engineering', 'Floor 2, Shelf C04'),
            ('Discrete Mathematics and Its Applications', 'K. Rosen', 'Mathematics', 'Floor 1, Shelf A08'),
            ('Fundamentals of Database Systems', 'Elmasri & Navathe', 'Computer Science', 'Floor 1, Shelf A21'),
            ('Organic Chemistry', 'Clayden et al.', 'Chemistry', 'Floor 3, Shelf D02'),
            ('Structural Analysis', 'R. C. Hibbeler', 'Civil Engineering', 'Floor 2, Shelf B19'),
        ]
        for i, (title, author, category, shelf) in enumerate(holdings):
            PhysicalHolding.objects.get_or_create(
                title=title,
                defaults={
                    'author': author, 'category': category, 'shelf_location': shelf,
                    'is_available': i % 3 != 0,
                },
            )

        if created:
            self.stdout.write(self.style.SUCCESS(f'Added {created} demo resource(s) and IBB Library holdings.'))
        else:
            self.stdout.write('Resources already seeded, nothing changed.')
