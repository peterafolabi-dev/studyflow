import os

with open('templates/base.html', 'r', encoding='utf-8') as f:
    base = f.read()

new_link = '<a href="{% url \'break_room\' %}" class="block px-4 py-2 hover:bg-brand-50 dark:hover:bg-slate-800">Break Room 🎮</a>'

if 'Break Room 🎮' not in base:
    base = base.replace('<a href="{% url \'study_room\' %}"', new_link + '\n            <a href="{% url \'study_room\' %}"')
    with open('templates/base.html', 'w', encoding='utf-8') as f:
        f.write(base)
print('Added to base.html dropdown!')
