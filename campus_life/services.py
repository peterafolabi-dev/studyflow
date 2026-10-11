from django.db.models import Sum

from .models import CreditEvent


def earn_credits(user, source_key, reason, amount):
    if amount <= 0:
        return False
    _, created = CreditEvent.objects.get_or_create(
        user=user,
        source_key=source_key,
        defaults={'reason': reason, 'credits': amount},
    )
    return created


def credit_balance(user):
    return CreditEvent.objects.filter(user=user).aggregate(total=Sum('credits'))['total'] or 0