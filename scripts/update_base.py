import os

with open('templates/base.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Fix dropdown scrolling
old_menu_class = 'class="hidden absolute right-0 mt-2 w-56 rounded-xl border border-brand-100 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-lg py-2 text-sm"'
new_menu_class = 'class="hidden absolute right-0 mt-2 w-56 rounded-xl border border-brand-100 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-lg py-2 text-sm max-h-[70vh] overflow-y-auto"'
html = html.replace(old_menu_class, new_menu_class)

# Fix footer
start_idx = html.find('<footer')
end_idx = html.find('</footer>') + len('</footer>')

new_footer = '''<footer class="mt-12 bg-brand-50 dark:bg-slate-900/50 border-t border-brand-100 dark:border-slate-800">
    <div class="mx-auto max-w-6xl px-4 py-8 flex flex-col md:flex-row justify-between gap-8 text-sm text-slate-500 dark:text-slate-400">
      <div class="max-w-xs">
        <span class="font-display font-bold text-xl text-brand-700 dark:text-brand-300">StudyFlow</span>
        <p class="mt-2">The ultimate student planner and resource library, built exclusively for FUT Minna students.</p>
      </div>

      {% if user.is_authenticated %}
        <div class="flex gap-12">
          <nav class="flex flex-col gap-2" aria-label="Footer Library">
            <h4 class="font-semibold text-slate-900 dark:text-white uppercase tracking-wider text-xs">Library</h4>
            <a href="{% url 'catalogue' %}" class="hover:text-brand-600 dark:hover:text-brand-300">Catalogue</a>
            <a href="{% url 'ibb_library' %}" class="hover:text-brand-600 dark:hover:text-brand-300">IBB Library</a>
            <a href="{% url 'my_library' %}" class="hover:text-brand-600 dark:hover:text-brand-300">My Library</a>
          </nav>
          <nav class="flex flex-col gap-2" aria-label="Footer Tools">
            <h4 class="font-semibold text-slate-900 dark:text-white uppercase tracking-wider text-xs">Tools</h4>
            <a href="{% url 'thread_list' %}" class="hover:text-brand-600 dark:hover:text-brand-300">Study Groups</a>
            <a href="{% url 'resource_upload' %}" class="hover:text-brand-600 dark:hover:text-brand-300">Upload a resource</a>
            <a href="{% url 'gpa_calculator' %}" class="hover:text-brand-600 dark:hover:text-brand-300">GPA Calculator</a>
          </nav>
        </div>
      {% endif %}
    </div>
    <div class="border-t border-brand-100 dark:border-slate-800 mx-auto max-w-6xl px-4 py-4 flex flex-col sm:flex-row justify-between items-center text-xs text-slate-400">
      <span>&copy; {% now "Y" %} StudyFlow. All rights reserved.</span>
      <span class="mt-2 sm:mt-0">Designed for excellence.</span>
    </div>
  </footer>'''

html = html[:start_idx] + new_footer + html[end_idx:]

with open('templates/base.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Updated base.html')
