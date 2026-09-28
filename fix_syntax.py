import os

with open('resources/views.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove the broken import
content = content.replace('@require_POST\nfrom django.db import transaction\ndef reserve_holding(request, pk):', '@require_POST\ndef reserve_holding(request, pk):')

# 2. Add the import at the top
if 'from django.db import transaction' not in content:
    content = content.replace('from django.db.models import F, Q', 'from django.db import transaction\nfrom django.db.models import F, Q')

# 3. Fix the indentation of reserve_holding
bad_func = '''@require_POST
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
    return redirect('ibb_library')'''

good_func = '''@require_POST
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
    return redirect('ibb_library')'''

content = content.replace(bad_func, good_func)

with open('resources/views.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed syntax and indentation')
