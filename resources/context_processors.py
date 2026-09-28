from django.utils import timezone

from .models import Loan


def overdue_loans(request):
    """Adds `overdue_loan_count` to every template's context, so base.html can
    show a persistent banner without every view having to remember to pass it."""
    if not request.user.is_authenticated:
        return {}
    count = Loan.objects.filter(
        user=request.user, returned_at__isnull=True, due_at__lt=timezone.now()
    ).count()
    return {'overdue_loan_count': count}
