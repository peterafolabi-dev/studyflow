import os

with open('templates/planner/dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('<section class="section-block mb-8">', '<section class="section-block mb-8 fade-in-up">')
content = content.replace('<div id="onboarding" class="hidden', '<div id="onboarding" class="fade-in-up hidden')
content = content.replace('class="empty rounded-2xl', 'class="empty fade-in-up rounded-2xl')

if '<div class="mb-6 fade-in-up">' not in content:
    content = content.replace(
        '<h1 class="scroll-mt-24 font-display text-2xl font-bold text-brand-800 dark:text-brand-200 mb-1">This week</h1>\n  <p class="summary text-slate-500 dark:text-slate-400 mb-6">\n    {{ open_count }} open task{{ open_count|pluralize }} across {{ course_count }} course{{ course_count|pluralize }}.\n    {{ done_count }} finished so far.\n  </p>',
        '<div class="mb-6 fade-in-up">\n    <h1 class="scroll-mt-24 font-display text-2xl font-bold text-brand-800 dark:text-brand-200 mb-1">This week</h1>\n    <p class="summary text-slate-500 dark:text-slate-400">\n      {{ open_count }} open task{{ open_count|pluralize }} across {{ course_count }} course{{ course_count|pluralize }}.\n      {{ done_count }} finished so far.\n    </p>\n  </div>'
    )

with open('templates/planner/dashboard.html', 'w', encoding='utf-8') as f:
    f.write(content)
print('Dashboard updated!')
