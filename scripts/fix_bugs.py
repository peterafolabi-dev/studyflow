import os
import glob

# 1. Fix accounts/views.py N+1 queries
with open('accounts/views.py', 'r', encoding='utf-8') as f:
    av = f.read()

av = av.replace('Task.objects.filter(course__user=user)', 'Task.objects.filter(course__user=user).select_related(\'course\')')
av = av.replace('BookRating.objects.filter(user=user)', 'BookRating.objects.filter(user=user).select_related(\'book\')')
av = av.replace('ResourceRating.objects.filter(user=user)', 'ResourceRating.objects.filter(user=user).select_related(\'resource\')')

with open('accounts/views.py', 'w', encoding='utf-8') as f:
    f.write(av)

# 2. Fix resources/views.py
with open('resources/views.py', 'r', encoding='utf-8') as f:
    rv = f.read()

# Race condition in reserve_holding
rc_old = '''def reserve_holding(request, pk):
    holding = get_object_or_404(PhysicalHolding, pk=pk)
    if not holding.is_available:'''

rc_new = '''from django.db import transaction
def reserve_holding(request, pk):
    with transaction.atomic():
        holding = get_object_or_404(PhysicalHolding.objects.select_for_update(), pk=pk)
        if not holding.is_available:'''
rv = rv.replace(rc_old, rc_new)

# Orphaned file in resource_delete
del_old = '''        resource.delete()
        messages.info(request, f'Removed "{title}".')'''
del_new = '''        if resource.file:
            resource.file.delete(save=False)
        resource.delete()
        messages.info(request, f'Removed "{title}".')'''
rv = rv.replace(del_old, del_new)

# TypeError in rate_resource
rate_old = '''    try:
        stars = int(request.POST.get('stars', 0))
    except ValueError:
        stars = 0'''
rate_new = '''    try:
        stars = int(request.POST.get('stars', 0))
    except (ValueError, TypeError):
        stars = 0'''
rv = rv.replace(rate_old, rate_new)

with open('resources/views.py', 'w', encoding='utf-8') as f:
    f.write(rv)

# 3. requirements.txt
with open('requirements.txt', 'r', encoding='utf-8') as f:
    reqs = f.readlines()

# deduplicate while preserving order
seen = set()
new_reqs = []
for r in reqs:
    r = r.strip()
    if not r: continue
    if r not in seen:
        seen.add(r)
        new_reqs.append(r)

with open('requirements.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(new_reqs) + '\n')

# 4. CSS and HTML
with open('static/css/style.css', 'r', encoding='utf-8') as f:
    css = f.read()
css = css.replace('.block { margin-top: 2rem; }', '.section-block { margin-top: 2rem; }')
with open('static/css/style.css', 'w', encoding='utf-8') as f:
    f.write(css)

for html_file in glob.glob('templates/**/*.html', recursive=True):
    with open(html_file, 'r', encoding='utf-8') as f:
        html = f.read()
    if '<section class="block' in html:
        html = html.replace('<section class="block', '<section class="section-block')
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html)

print('All legendary fixes applied!')
