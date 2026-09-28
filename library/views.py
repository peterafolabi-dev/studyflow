import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .content import generate_chapters
from .models import Book, BookRating, SavedBook

LEVELS = [100, 200, 300, 400, 500]


def _saved_ids(user):
    return set(SavedBook.objects.filter(user=user).values_list('book_id', flat=True))


@login_required
def catalogue(request):
    """The reading hub catalogue, covering levels 100 through 500."""
    level = request.GET.get('level')
    query = request.GET.get('q', '').strip()
    subject = request.GET.get('subject', '').strip()

    books = Book.objects.filter(is_postgraduate=False)
    if level and level.isdigit() and int(level) in LEVELS:
        books = books.filter(level=int(level))
    if subject:
        books = books.filter(subject=subject)
    if query:
        books = books.filter(
            Q(title__icontains=query) | Q(author__icontains=query) | Q(subject__icontains=query)
        )

    subjects = (
        Book.objects.filter(is_postgraduate=False)
        .exclude(subject='')
        .order_by('subject')
        .values_list('subject', flat=True)
        .distinct()
    )

    context = {
        'books': books,
        'levels': LEVELS,
        'active_level': int(level) if level and level.isdigit() else None,
        'saved_ids': _saved_ids(request.user),
        'query': query,
        'subjects': subjects,
        'active_subject': subject,
    }
    return render(request, 'library/catalogue.html', context)


@login_required
def postgraduate(request):
    """A separate hub for postgraduate-level reading."""
    query = request.GET.get('q', '').strip()
    books = Book.objects.filter(is_postgraduate=True)
    if query:
        books = books.filter(
            Q(title__icontains=query) | Q(author__icontains=query) | Q(subject__icontains=query)
        )
    return render(
        request,
        'library/postgraduate.html',
        {'books': books, 'saved_ids': _saved_ids(request.user), 'query': query},
    )


@login_required
def my_library(request):
    """Books this user has saved, grouped by reading progress."""
    saved = SavedBook.objects.filter(user=request.user).select_related('book')
    context = {
        'reading': saved.filter(status='reading'),
        'to_read': saved.filter(status='to_read'),
        'finished': saved.filter(status='finished'),
        'total': saved.count(),
    }
    return render(request, 'library/my_library.html', context)


@login_required
def book_detail(request, pk):
    book = get_object_or_404(Book, pk=pk)
    entry = SavedBook.objects.filter(user=request.user, book=book).first()
    my_rating = BookRating.objects.filter(user=request.user, book=book).first()
    similar = (
        Book.objects.filter(subject=book.subject, is_postgraduate=book.is_postgraduate)
        .exclude(pk=book.pk)[:3]
        if book.subject
        else []
    )
    return render(
        request,
        'library/book_detail.html',
        {'book': book, 'entry': entry, 'similar': similar, 'my_rating': my_rating},
    )


@login_required
@require_POST
def rate_book(request, pk):
    book = get_object_or_404(Book, pk=pk)
    try:
        stars = int(request.POST.get('stars', 0))
    except ValueError:
        stars = 0
    if stars not in range(1, 6):
        messages.error(request, 'Pick a rating from 1 to 5 stars.')
    else:
        BookRating.objects.update_or_create(user=request.user, book=book, defaults={'stars': stars})
        messages.success(request, f'Thanks for rating "{book.title}"!')
    return redirect('book_detail', pk=pk)


@login_required
def read_online(request, pk):
    """A lightweight in-browser reader. Opening a book automatically saves it
    to My Library and marks it 'Reading' (unless already finished)."""
    book = get_object_or_404(Book, pk=pk)
    entry, _created = SavedBook.objects.get_or_create(user=request.user, book=book)
    if entry.status == 'to_read':
        entry.status = 'reading'
        entry.save(update_fields=['status', 'updated_at'])

    chapters = generate_chapters(book)
    return render(
        request, 'library/read_online.html', {'book': book, 'chapters': chapters, 'entry': entry}
    )


@login_required
def download_pdf(request, pk):
    """Generates a placeholder study-notes PDF for the book on the fly."""
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    book = get_object_or_404(Book, pk=pk)
    chapters = generate_chapters(book)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=LETTER, title=book.title)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(book.title, styles['Title']),
        Paragraph(
            f'{book.author or "Unknown author"} &middot; '
            f'{"Postgraduate" if book.is_postgraduate else f"Level {book.level}"}',
            styles['Normal'],
        ),
        Spacer(1, 18),
    ]
    for chapter in chapters:
        story.append(Paragraph(chapter['title'], styles['Heading2']))
        for para in chapter['paragraphs']:
            story.append(Paragraph(para, styles['Normal']))
            story.append(Spacer(1, 8))
        story.append(Spacer(1, 12))
    doc.build(story)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    safe_name = ''.join(c for c in book.title if c.isalnum() or c in ' -_').strip() or 'book'
    response['Content-Disposition'] = f'attachment; filename="{safe_name}.pdf"'
    return response


@login_required
@require_POST
def toggle_save(request, pk):
    book = get_object_or_404(Book, pk=pk)
    entry, created = SavedBook.objects.get_or_create(user=request.user, book=book)
    if not created:
        entry.delete()
        messages.info(request, f'Removed "{book.title}" from your library.')
    else:
        messages.success(request, f'Added "{book.title}" to your library.')

    next_url = request.POST.get('next') or 'catalogue'
    return redirect(next_url)


@login_required
@require_POST
def update_status(request, pk):
    book = get_object_or_404(Book, pk=pk)
    status = request.POST.get('status')
    valid_statuses = dict(SavedBook.STATUS_CHOICES)
    if status not in valid_statuses:
        messages.error(request, 'Unrecognised reading status.')
    else:
        entry, _created = SavedBook.objects.get_or_create(user=request.user, book=book)
        entry.status = status
        entry.save(update_fields=['status', 'updated_at'])
        messages.success(request, f'"{book.title}" marked as {valid_statuses[status].lower()}.')

    next_url = request.POST.get('next') or 'my_library'
    return redirect(next_url)
