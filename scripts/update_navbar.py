import os

with open('templates/base.html', 'r', encoding='utf-8') as f:
    html = f.read()

new_links = '''            <a href="{% url 'edit_profile' %}" class="block px-4 py-2 hover:bg-brand-50 dark:hover:bg-slate-800">Edit Profile</a>
            <a href="{% url 'notifications' %}" class="block px-4 py-2 hover:bg-brand-50 dark:hover:bg-slate-800">Notifications</a>
            <a href="{% url 'study_room' %}" class="block px-4 py-2 hover:bg-brand-50 dark:hover:bg-slate-800">Pomodoro Timer</a>
            <a href="{% url 'flashcards' %}" class="block px-4 py-2 hover:bg-brand-50 dark:hover:bg-slate-800">Flashcards</a>
            <a href="{% url 'find_buddies' %}" class="block px-4 py-2 hover:bg-brand-50 dark:hover:bg-slate-800">Find Buddies</a>'''

# insert into profile menu after 'My Profile'
html = html.replace('<a href="{% url \'profile\' %}" class="block px-4 py-2 hover:bg-brand-50 dark:hover:bg-slate-800">My Profile</a>', 
                    '<a href="{% url \'profile\' %}" class="block px-4 py-2 hover:bg-brand-50 dark:hover:bg-slate-800">My Profile</a>\n' + new_links)

with open('templates/base.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Navbar updated!')
