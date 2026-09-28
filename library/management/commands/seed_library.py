from django.core.management.base import BaseCommand

from library.models import Book


class Command(BaseCommand):
    help = 'Seed the reading hub (levels 100-500) and the postgraduate shelf with sample books.'

    def handle(self, *args, **options):
        undergrad = [
            ('Foundations of Engineering Math', 'R. Adeyemi', 'Mathematics', 100,
             'A gentle on-ramp to the calculus and algebra used throughout engineering courses.'),
            ('Intro to Programming with Python', 'A. Musa', 'Computer Science', 100,
             'Variables, loops and functions, taught through small, practical projects.'),
            ('Academic Writing Essentials', 'C. Bello', 'Communication Skills', 100,
             'Structuring essays, citing sources, and writing with clarity and confidence.'),
            ('Circuit Theory I', 'T. Okafor', 'Electrical Engineering', 200,
             'Kirchhoff\'s laws, resistive networks, and first-order transient analysis.'),
            ('Data Structures & Algorithms', 'S. Chen', 'Computer Science', 200,
             'Arrays, trees, and graphs, with a focus on choosing the right structure for the job.'),
            ('Organic Chemistry Basics', 'F. Ibrahim', 'Chemistry', 200,
             'Functional groups, reaction mechanisms, and how to read a synthesis pathway.'),
            ('Signals and Systems', 'J. Adamu', 'Electrical Engineering', 300,
             'Convolution, Fourier analysis, and the language used to describe how systems respond.'),
            ('Database Systems', 'M. Yusuf', 'Computer Science', 300,
             'Relational design, normalization, and writing queries that actually scale.'),
            ('Thermodynamics', 'K. Eze', 'Mechanical Engineering', 300,
             'The laws of thermodynamics applied to real engines, cycles, and processes.'),
            ('Operating Systems Concepts', 'A. Silberschatz', 'Computer Science', 400,
             'Processes, memory management, and the scheduling decisions behind every OS.'),
            ('Control Systems Engineering', 'N. Katsina', 'Electrical Engineering', 400,
             'Feedback loops, stability analysis, and tuning a controller that actually works.'),
            ('Numerical Methods for Engineers', 'S. Chapra', 'Mathematics', 400,
             'Turning equations that can\'t be solved by hand into ones a computer can.'),
            ('Final Year Project Handbook', 'Dept. of Engineering', 'Research Skills', 500,
             'Scoping, planning, and writing up a capstone project from start to defence.'),
            ('Machine Learning Foundations', 'I. Goodfellow', 'Computer Science', 500,
             'The maths and intuition behind the models most of modern AI is built on.'),
            ('Renewable Energy Systems', 'B. Danjuma', 'Electrical Engineering', 500,
             'Solar, wind, and storage technologies, and how they connect to the grid.'),
        ]
        postgrad = [
            ('Advanced Research Methodology', 'Prof. O. Adebayo', 'Research Skills',
             'Designing a rigorous study, from research question to defensible methodology.'),
            ('Deep Learning: A Postgraduate Companion', 'I. Goodfellow', 'Computer Science',
             'A deeper pass through neural network theory, aimed at thesis-level work.'),
            ('Power System Stability and Control', 'P. Kundur', 'Electrical Engineering',
             'The standard reference on keeping large power grids stable under stress.'),
            ('Thesis Writing and Academic Publishing', 'Prof. L. Nwosu', 'Communication Skills',
             'Turning research into a thesis chapter, and a thesis chapter into a paper.'),
            ('Applied Convex Optimization', 'S. Boyd', 'Mathematics',
             'Optimization problems that come up constantly in research, and how to solve them.'),
        ]

        created = 0
        for i, (title, author, subject, level, description) in enumerate(undergrad):
            _, was_created = Book.objects.get_or_create(
                title=title,
                defaults={
                    'author': author, 'subject': subject, 'level': level,
                    'description': description, 'cover_color': i, 'is_postgraduate': False,
                },
            )
            created += was_created

        for i, (title, author, subject, description) in enumerate(postgrad):
            _, was_created = Book.objects.get_or_create(
                title=title,
                defaults={
                    'author': author, 'subject': subject, 'level': 500,
                    'description': description, 'cover_color': i, 'is_postgraduate': True,
                },
            )
            created += was_created

        if created:
            self.stdout.write(self.style.SUCCESS(f'Added {created} book(s) to the reading hub.'))
        else:
            self.stdout.write('Reading hub already seeded, nothing changed.')
