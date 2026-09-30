import os
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F, Q
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import ResourceUploadForm
from .models import Loan, PhysicalHolding, Resource, ResourceComment, ResourceRating

# Which underlying resource_type values each hub page shows, and its label +
# url name (used to send an uploader back to the right page afterwards).
TYPE_GROUPS = {
    'past_question': (['past_question'], 'Past Questions', 'past_questions'),
    'notes': (['notes'], 'Notes', 'notes_list'),
    'thesis_paper': (['thesis', 'paper'], 'Theses & Papers', 'theses_papers'),
    'lecture_slide': (['lecture_slide'], 'Lecture Slides', 'lecture_slides'),
    'research': (['thesis', 'paper'], 'Research', 'research'),
}


@login_required
def resource_list(request, rtype):
    types, label, url_name = TYPE_GROUPS[rtype]
    query = request.GET.get('q', '').strip()

    resources = Resource.objects.filter(resource_type__in=types)
    if query:
        resources = resources.filter(
            Q(title__icontains=query) | Q(course_code__icontains=query) | Q(description__icontains=query)
        )

    trending = Resource.objects.filter(
        resource_type__in=types,
        last_downloaded_at__gte=timezone.now() - timedelta(days=7),
    ).order_by('-download_count')[:4]

    my_ratings = dict(
        ResourceRating.objects.filter(user=request.user, resource__resource_type__in=types)
        .values_list('resource_id', 'stars')
    )

    context = {
        'resources': resources,
        'trending': trending,
        'label': label,
        'rtype': rtype,
        'url_name': url_name,
        'query': query,
        'my_ratings': my_ratings,
    }
    return render(request, 'resources/list.html', context)


@login_required
def resource_detail(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    my_rating = ResourceRating.objects.filter(user=request.user, resource=resource).first()
    comments = resource.comments.select_related('user')

    if request.method == 'POST':
        body = request.POST.get('body', '').strip()
        if body:
            ResourceComment.objects.create(resource=resource, user=request.user, body=body)
            return redirect('resource_detail', pk=pk)
        messages.error(request, "Comment can't be empty.")

    back_group = 'thesis_paper' if resource.resource_type in ('thesis', 'paper') else resource.resource_type
    _, _, back_url_name = TYPE_GROUPS.get(back_group, (None, None, 'notes_list'))

    return render(
        request, 'resources/resource_detail.html',
        {'resource': resource, 'my_rating': my_rating, 'comments': comments, 'back_url_name': back_url_name},
    )


from studyflow.upload_config import (
    get_accept_attribute,
    get_allowed_types_display,
    get_allowed_extensions,
    get_allowed_mime_types,
    MAX_UPLOAD_SIZE_MB,
    MAX_UPLOAD_SIZE_BYTES,
)

@login_required
def resource_upload(request):
    default_type = request.GET.get('type', 'notes')
    upload_ctx = {
        'accept_attribute': get_accept_attribute(),
        'allowed_types_display': get_allowed_types_display(),
        'allowed_extensions': get_allowed_extensions(),
        'allowed_mimes': get_allowed_mime_types(),
        'max_size_mb': MAX_UPLOAD_SIZE_MB,
        'max_size_bytes': MAX_UPLOAD_SIZE_BYTES,
    }

    if request.method == 'POST':
        form = ResourceUploadForm(request.POST, request.FILES)
        if form.is_valid():
            resource = form.save(commit=False)
            resource.uploaded_by = request.user
            resource.save()
            messages.success(request, f'"{resource.title}" was added. Thanks for contributing!')
            reverse_type = 'thesis_paper' if resource.resource_type in ('thesis', 'paper') else resource.resource_type
            _, _, url_name = TYPE_GROUPS.get(reverse_type, (None, None, 'notes_list'))
            return redirect(url_name)
        else:
            return render(request, 'resources/upload.html', {'form': form, 'upload_config': upload_ctx}, status=400)
    else:
        form = ResourceUploadForm(initial={'resource_type': default_type})

    return render(request, 'resources/upload.html', {'form': form, 'upload_config': upload_ctx})


@login_required
def resource_download(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    if not resource.file:
        messages.error(request, 'This resource has no file attached yet.')
        return redirect(request.META.get('HTTP_REFERER') or 'dashboard')

    Resource.objects.filter(pk=pk).update(
        download_count=F('download_count') + 1, last_downloaded_at=timezone.now()
    )
    try:
        return FileResponse(
            resource.file.open('rb'), as_attachment=True, filename=os.path.basename(resource.file.name)
        )
    except FileNotFoundError:
        raise Http404('File not found.')


@login_required
@require_POST
def resource_delete(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    if resource.uploaded_by_id != request.user.id and not request.user.is_staff:
        messages.error(request, "You can only remove resources you uploaded.")
    else:
        reverse_type = 'thesis_paper' if resource.resource_type in ('thesis', 'paper') else resource.resource_type
        title = resource.title
        if resource.file:
            resource.file.delete(save=False)
        resource.delete()
        messages.info(request, f'Removed "{title}".')
        _, _, url_name = TYPE_GROUPS.get(reverse_type, (None, None, 'notes_list'))
        return redirect(url_name)
    return redirect(request.META.get('HTTP_REFERER') or 'dashboard')


@login_required
def ibb_library(request):
    """Informational page for the physical IBB Library (FUT Minna)."""
    query = request.GET.get('q', '').strip()
    holdings = PhysicalHolding.objects.all()
    if query:
        holdings = holdings.filter(Q(title__icontains=query) | Q(author__icontains=query))

    my_active_loans = {
        loan.holding_id: loan
        for loan in Loan.objects.filter(user=request.user, returned_at__isnull=True)
    }
    return render(
        request,
        'resources/ibb_library.html',
        {'holdings': holdings, 'query': query, 'my_active_loans': my_active_loans},
    )


@login_required
@require_POST
def reserve_holding(request, pk):
    with transaction.atomic():
        holding = get_object_or_404(PhysicalHolding.objects.select_for_update(), pk=pk)
        if not holding.is_available:
            messages.error(request, f'"{holding.title}" is currently on loan to someone else.')
        else:
            due_at = timezone.now() + timedelta(days=Loan.LOAN_PERIOD_DAYS)
            Loan.objects.create(user=request.user, holding=holding, due_at=due_at)
            holding.is_available = False
            holding.save(update_fields=['is_available'])
            messages.success(
                request, f'"{holding.title}" reserved — due back {due_at.strftime("%d %b %Y")}.'
            )
    return redirect('ibb_library')


@login_required
@require_POST
def return_holding(request, pk):
    holding = get_object_or_404(PhysicalHolding, pk=pk)
    loan = Loan.objects.filter(holding=holding, user=request.user, returned_at__isnull=True).first()
    if not loan:
        messages.error(request, "You don't have an active loan for this item.")
    else:
        loan.returned_at = timezone.now()
        loan.save(update_fields=['returned_at'])
        holding.is_available = True
        holding.save(update_fields=['is_available'])
        messages.success(request, f'"{holding.title}" returned. Thanks!')

    next_url = request.POST.get('next') or 'ibb_library'
    return redirect(next_url)


@login_required
def my_loans(request):
    loans = Loan.objects.filter(user=request.user).select_related('holding')
    return render(
        request,
        'resources/my_loans.html',
        {
            'active_loans': loans.filter(returned_at__isnull=True),
            'past_loans': loans.filter(returned_at__isnull=False),
        },
    )


@login_required
@require_POST
def rate_resource(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    try:
        stars = int(request.POST.get('stars', 0))
    except (ValueError, TypeError):
        stars = 0
    if stars not in range(1, 6):
        messages.error(request, 'Pick a rating from 1 to 5 stars.')
    else:
        ResourceRating.objects.update_or_create(user=request.user, resource=resource, defaults={'stars': stars})
        messages.success(request, 'Thanks for the rating!')
    next_url = request.POST.get('next') or 'notes_list'
    return redirect(next_url)


import json
from planner.models import Course, FlashcardDeck, Flashcard
from .pdf_service import extract_and_chunk_pdf, ScannedOrEmptyPDFError, PDFExtractionError
from .ai_service import (
    check_and_increment_rate_limit,
    RateLimitExceeded,
    AIProcessingError,
    summarize_material,
    generate_flashcards_from_material,
    generate_quiz_from_material,
)


def _extract_pdf_with_rate_limit(request, pk):
    """Common helper to validate resource, check PDF validity, enforce rate limit, and extract text."""
    resource = get_object_or_404(Resource, pk=pk)
    if not resource.file:
        return None, None, JsonResponse({'error': 'No file is attached to this resource.'}, status=400)

    filename = resource.file.name.lower()
    if not filename.endswith('.pdf'):
        return None, None, JsonResponse({'error': 'AI features are currently supported for PDF files only.'}, status=400)

    try:
        check_and_increment_rate_limit(request.user.id)
    except RateLimitExceeded as e:
        return None, None, JsonResponse({'error': str(e)}, status=429)

    try:
        text = extract_and_chunk_pdf(resource.file.path)
    except ScannedOrEmptyPDFError as e:
        return None, None, JsonResponse({'error': str(e)}, status=422)
    except PDFExtractionError as e:
        return None, None, JsonResponse({'error': f'PDF extraction failed: {str(e)}'}, status=400)
    except Exception as e:
        return None, None, JsonResponse({'error': f'Unable to read PDF file: {str(e)}'}, status=500)

    return resource, text, None


@login_required
@require_POST
def resource_ai_summarize(request, pk):
    resource, text, err_resp = _extract_pdf_with_rate_limit(request, pk)
    if err_resp:
        return err_resp
    try:
        data = summarize_material(text, title=resource.title)
        return JsonResponse({'success': True, 'data': data})
    except AIProcessingError as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def resource_ai_flashcards(request, pk):
    resource, text, err_resp = _extract_pdf_with_rate_limit(request, pk)
    if err_resp:
        return err_resp
    try:
        cards = generate_flashcards_from_material(text, title=resource.title, card_count=8)
        user_courses = list(Course.objects.filter(user=request.user).values('id', 'name', 'code'))
        user_decks = list(
            FlashcardDeck.objects.filter(course__user=request.user)
            .values('id', 'title', 'course__name', 'course__code')
        )
        return JsonResponse({
            'success': True,
            'flashcards': cards,
            'user_courses': user_courses,
            'user_decks': user_decks,
            'default_deck_title': f"{resource.title} Cards"[:180]
        })
    except AIProcessingError as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def resource_ai_save_flashcards(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    try:
        data = json.loads(request.body)
    except Exception:
        data = request.POST

    cards_data = data.get('cards', [])
    if isinstance(cards_data, str):
        try:
            cards_data = json.loads(cards_data)
        except Exception:
            cards_data = []

    if not cards_data:
        return JsonResponse({'error': 'No flashcards provided to save.'}, status=400)

    deck_id = data.get('deck_id')
    deck = None
    if deck_id:
        deck = FlashcardDeck.objects.filter(pk=deck_id, course__user=request.user).first()
        if not deck:
            return JsonResponse({'error': 'Selected flashcard deck not found.'}, status=404)
    else:
        # Create a new deck
        deck_title = (data.get('new_deck_title') or f"{resource.title} Cards").strip()
        course_id = data.get('course_id')
        course = None
        if course_id:
            course = Course.objects.filter(pk=course_id, user=request.user).first()

        if not course:
            course_code = resource.course_code.strip() or 'GEN'
            course = Course.objects.filter(user=request.user, code__iexact=course_code).first()
            if not course:
                course = Course.objects.create(
                    user=request.user,
                    name=resource.course_code or 'Study Materials',
                    code=course_code
                )

        deck = FlashcardDeck.objects.create(course=course, title=deck_title)

    cards_to_create = []
    for c in cards_data:
        front = (c.get('front') or '').strip()
        back = (c.get('back') or '').strip()
        if front and back:
            cards_to_create.append(Flashcard(deck=deck, front=front, back=back))

    if cards_to_create:
        Flashcard.objects.bulk_create(cards_to_create)

    return JsonResponse({
        'success': True,
        'message': f"Saved {len(cards_to_create)} flashcards into '{deck.title}'.",
        'deck_id': deck.id,
        'deck_title': deck.title,
        'course_name': deck.course.name,
        'cards_count': len(cards_to_create)
    })


@login_required
@require_POST
def resource_ai_quiz(request, pk):
    resource, text, err_resp = _extract_pdf_with_rate_limit(request, pk)
    if err_resp:
        return err_resp
    try:
        questions = generate_quiz_from_material(text, title=resource.title, question_count=5)
        return JsonResponse({
            'success': True,
            'resource_title': resource.title,
            'questions': questions
        })
    except AIProcessingError as e:
        return JsonResponse({'error': str(e)}, status=500)
