import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from planner.models import Course
from resources.models import CBTQuestion, QuestionBank, Resource, TestAttempt
from resources.pdf_service import extract_and_chunk_pdf, ScannedOrEmptyPDFError, PDFExtractionError
from resources.ai_service import (
    check_and_increment_rate_limit,
    RateLimitExceeded,
    AIProcessingError,
    generate_cbt_bank_from_pdf,
    explain_cbt_answer_with_ai,
)


@login_required
def cbt_home(request):
    """
    CBT Mode Home: lists practice question banks and the student's recent test attempts.
    """
    query = request.GET.get('q', '').strip()
    banks = QuestionBank.objects.filter(
        Q(is_public=True) | Q(created_by=request.user)
    ).select_related('course', 'created_by')

    if query:
        banks = banks.filter(
            Q(title__icontains=query) |
            Q(course_code__icontains=query) |
            Q(description__icontains=query)
        )

    recent_attempts = TestAttempt.objects.filter(
        user=request.user, is_completed=True
    ).select_related('bank', 'bank__course').order_by('-completed_at')[:8]

    # Available past-question PDFs the user can convert to CBT
    past_question_pdfs = Resource.objects.filter(
        resource_type='past_question', file__isnull=False
    ).exclude(file='').order_by('-created_at')[:6]

    context = {
        'banks': banks,
        'recent_attempts': recent_attempts,
        'past_question_pdfs': past_question_pdfs,
        'query': query,
    }
    return render(request, 'cbt/cbt_home.html', context)


@login_required
def cbt_detail(request, bank_id):
    """
    Overview of a CBT test bank before taking the timed exam.
    """
    bank = get_object_or_404(QuestionBank, pk=bank_id)
    recent_attempts = TestAttempt.objects.filter(
        user=request.user, bank=bank, is_completed=True
    ).order_by('-completed_at')[:5]

    context = {
        'bank': bank,
        'questions_count': bank.questions.count(),
        'recent_attempts': recent_attempts,
    }
    return render(request, 'cbt/cbt_detail.html', context)


@login_required
def cbt_take(request, bank_id):
    """
    Interactive Timed Exam Runner with countdown timer, question navigator, and auto-submit.
    """
    bank = get_object_or_404(QuestionBank, pk=bank_id)
    questions = list(bank.questions.order_by('order', 'id'))

    if not questions:
        messages.error(request, "This question bank has no questions yet.")
        return redirect('cbt_home')

    # Convert questions into JSON-friendly format for client-side CBT runner
    questions_data = []
    for idx, q in enumerate(questions):
        questions_data.append({
            'id': q.id,
            'number': idx + 1,
            'text': q.text,
            'options': [
                {'letter': 'A', 'text': q.option_a},
                {'letter': 'B', 'text': q.option_b},
                {'letter': 'C', 'text': q.option_c},
                {'letter': 'D', 'text': q.option_d},
            ]
        })

    context = {
        'bank': bank,
        'questions_count': len(questions),
        'time_limit_minutes': bank.time_limit_minutes,
        'time_limit_seconds': bank.time_limit_minutes * 60,
        'questions_json': json.dumps(questions_data),
    }
    return render(request, 'cbt/cbt_take.html', context)


@login_required
@require_POST
def cbt_submit(request, bank_id):
    """
    Calculates practice score, records answers, and redirects to the results page.
    Handles both manual submission and countdown timer auto-submission.
    """
    bank = get_object_or_404(QuestionBank, pk=bank_id)
    questions = {str(q.id): q for q in bank.questions.all()}

    # Parse submitted JSON or POST body
    try:
        data = json.loads(request.body)
    except Exception:
        data = request.POST

    answers_raw = data.get('answers', {})
    if isinstance(answers_raw, str):
        try:
            answers_raw = json.loads(answers_raw)
        except Exception:
            answers_raw = {}

    try:
        time_taken_seconds = int(data.get('time_taken_seconds', 0))
    except (ValueError, TypeError):
        time_taken_seconds = 0

    # Cap time taken to bank time limit
    max_seconds = bank.time_limit_minutes * 60
    if time_taken_seconds > max_seconds:
        time_taken_seconds = max_seconds

    # Grade attempt
    score = 0
    total = len(questions)
    formatted_answers = {}

    for q_id, q in questions.items():
        user_choice = str(answers_raw.get(q_id, '')).strip().upper()
        if user_choice in ['A', 'B', 'C', 'D']:
            formatted_answers[q_id] = user_choice
            if user_choice == q.correct_option:
                score += 1
        else:
            formatted_answers[q_id] = None

    attempt = TestAttempt.objects.create(
        user=request.user,
        bank=bank,
        score=score,
        total_questions=total,
        time_taken_seconds=time_taken_seconds,
        answers=formatted_answers,
        is_completed=True,
        completed_at=timezone.now(),
    )

    if (
        request.headers.get('x-requested-with') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
        or getattr(request, 'content_type', '') == 'application/json'
    ):
        return JsonResponse({
            'success': True,
            'attempt_id': attempt.id,
            'redirect_url': f'/cbt/attempt/{attempt.id}/results/',
            'score': score,
            'total': total,
            'percentage': attempt.percentage,
        })

    return redirect('cbt_result', attempt_id=attempt.id)


@login_required
def cbt_result(request, attempt_id):
    """
    Results page: Displays score, time taken, breakdown of wrong & correct answers,
    and includes an 'Explain this answer' button for the AI coach.
    """
    attempt = get_object_or_404(TestAttempt, pk=attempt_id, user=request.user)
    detailed_results = attempt.get_detailed_results()

    wrong_results = [r for r in detailed_results if not r['is_correct']]
    correct_results = [r for r in detailed_results if r['is_correct']]

    context = {
        'attempt': attempt,
        'bank': attempt.bank,
        'detailed_results': detailed_results,
        'wrong_results': wrong_results,
        'correct_results': correct_results,
        'wrong_count': len(wrong_results),
        'correct_count': len(correct_results),
    }
    return render(request, 'cbt/cbt_result.html', context)


@login_required
@require_POST
def cbt_explain_answer(request):
    """
    AI Coach endpoint: Explains a question step-by-step for the student.
    """
    try:
        data = json.loads(request.body)
    except Exception:
        data = request.POST

    question_id = data.get('question_id')
    user_choice = data.get('user_choice', '')

    question = get_object_or_404(CBTQuestion, pk=question_id)

    try:
        check_and_increment_rate_limit(request.user.id, bucket='cbt_explain', max_requests=15, window=300)
    except RateLimitExceeded as e:
        return JsonResponse({'error': str(e)}, status=429)

    ai_explanation = explain_cbt_answer_with_ai(
        question_text=question.text,
        option_a=question.option_a,
        option_b=question.option_b,
        option_c=question.option_c,
        option_d=question.option_d,
        user_choice=user_choice,
        correct_choice=question.correct_option,
        base_explanation=question.explanation,
    )

    return JsonResponse({
        'success': True,
        'question_id': question.id,
        'ai_explanation': ai_explanation,
    })


@login_required
@require_POST
def resource_ai_generate_cbt(request, pk):
    """
    Generates a full CBT Question Bank directly from an uploaded past-question PDF.
    Reuses Phase 1 PDF text extraction and chunking.
    """
    resource = get_object_or_404(Resource, pk=pk)
    if not resource.file:
        return JsonResponse({'error': 'No file is attached to this resource.'}, status=400)

    filename = resource.file.name.lower()
    if not filename.endswith('.pdf'):
        return JsonResponse({'error': 'CBT generation is only supported for PDF files.'}, status=400)

    try:
        check_and_increment_rate_limit(request.user.id, bucket='pdf_ai')
    except RateLimitExceeded as e:
        return JsonResponse({'error': str(e)}, status=429)

    try:
        text = extract_and_chunk_pdf(resource.file.path, max_chars=14000)
    except ScannedOrEmptyPDFError as e:
        return JsonResponse({'error': str(e)}, status=422)
    except PDFExtractionError as e:
        return JsonResponse({'error': f'PDF extraction failed: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Unable to read PDF file: {str(e)}'}, status=500)

    try:
        bank_data = generate_cbt_bank_from_pdf(text, title=resource.title, count=10)
    except AIProcessingError as e:
        return JsonResponse({'error': str(e)}, status=500)

    # Link or auto-create course
    course_code = (resource.course_code or 'GEN').strip()
    course = Course.objects.filter(user=request.user, code__iexact=course_code).first()
    if not course:
        course = Course.objects.create(
            user=request.user,
            name=resource.course_code or 'Study Materials',
            code=course_code
        )

    # Create QuestionBank
    bank = QuestionBank.objects.create(
        course=course,
        course_code=course.code,
        resource=resource,
        created_by=request.user,
        title=bank_data.get('title') or f"{resource.title} CBT Practice",
        time_limit_minutes=bank_data.get('time_limit_minutes', 15),
        description=f"Generated by StudyFlow AI from past questions: '{resource.title}'.",
        is_public=True
    )

    questions_to_create = []
    for idx, q in enumerate(bank_data.get('questions', [])):
        questions_to_create.append(
            CBTQuestion(
                bank=bank,
                text=q['question'],
                option_a=q['option_a'],
                option_b=q['option_b'],
                option_c=q['option_c'],
                option_d=q['option_d'],
                correct_option=q['correct_option'],
                explanation=q.get('explanation', ''),
                order=idx,
            )
        )

    if questions_to_create:
        CBTQuestion.objects.bulk_create(questions_to_create)

    return JsonResponse({
        'success': True,
        'message': f"Generated {len(questions_to_create)} CBT questions.",
        'bank_id': bank.id,
        'bank_title': bank.title,
        'question_count': len(questions_to_create),
        'redirect_url': f'/cbt/bank/{bank.id}/take/',
    })
