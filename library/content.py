"""Placeholder reading content.

StudyFlow's catalogue is a demo dataset, not a licensed book supplier, so
'Read online' and 'Download PDF' render generated placeholder chapters
built from the book's own title/subject/description rather than real text.
"""

CHAPTER_TITLES = [
    'Introduction & Key Concepts',
    'Core Principles',
    'Worked Examples',
    'Common Pitfalls',
    'Review & Practice Questions',
]


def generate_chapters(book, count=5):
    subject = book.subject or 'this subject'
    chapters = []
    for i in range(min(count, len(CHAPTER_TITLES))):
        title = CHAPTER_TITLES[i]
        paragraphs = [
            f'This is placeholder study content for "{book.title}" '
            f'({subject}), standing in for the real chapter text.',
            book.description
            or f'Chapter {i + 1} would normally walk through {subject.lower()} '
               f'topics relevant to Level {book.level if not book.is_postgraduate else "postgraduate"} study.',
            'Use this space to take your own notes as you read, and mark the '
            'book as finished from My Library once you\'re done.',
        ]
        chapters.append({'title': title, 'paragraphs': paragraphs})
    return chapters
