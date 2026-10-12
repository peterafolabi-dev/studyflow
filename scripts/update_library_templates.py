import os

my_library_html = '''{% extends 'base.html' %}
{% block title %}My Library · StudyFlow{% endblock %}
{% block content %}
  <div class="mb-6 fade-in-up">
    <h1 class="font-display text-2xl font-bold text-brand-800 dark:text-brand-200">My Library</h1>
    <p class="text-slate-500 dark:text-slate-400 mt-1">Everything you've saved, sorted by progress.</p>
  </div>

  {% if reading_goal > 0 %}
  <div class="mb-8 p-6 bg-white dark:bg-slate-900 border border-brand-200 dark:border-slate-700 rounded-2xl shadow-sm fade-in-up">
    <h3 class="font-display font-bold text-lg mb-2">Reading Goal 🎯</h3>
    <div class="flex justify-between text-sm mb-2 text-slate-700 dark:text-slate-300">
      <span>{{ finished_count }} / {{ reading_goal }} books finished</span>
      <span class="font-bold text-brand-600 dark:text-brand-400">{{ progress_percent }}%</span>
    </div>
    <div class="w-full bg-brand-100 dark:bg-slate-800 rounded-full h-3 overflow-hidden">
      <div class="bg-brand-600 h-3 rounded-full transition-all duration-1000 ease-out" style="width: {{ progress_percent }}%"></div>
    </div>
    {% if progress_percent >= 100 %}
    <p class="text-emerald-600 dark:text-emerald-400 text-sm mt-3 font-medium">Legendary! You've hit your yearly reading goal! 🎉</p>
    {% endif %}
  </div>
  {% endif %}

  {% if total %}
    {% if reading %}
      <section class="mb-8 fade-in-up">
        <h2 class="font-display font-bold text-lg mb-3">📖 Continue reading</h2>
        <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {% for entry in reading %}
            {% include 'library/_saved_card.html' %}
          {% endfor %}
        </div>
      </section>
    {% endif %}

    {% if to_read %}
      <section class="mb-8 fade-in-up" style="animation-delay: 0.1s">
        <h2 class="font-display font-bold text-lg mb-3">🔖 To read</h2>
        <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {% for entry in to_read %}
            {% include 'library/_saved_card.html' %}
          {% endfor %}
        </div>
      </section>
    {% endif %}

    {% if finished %}
      <section class="mb-8 fade-in-up" style="animation-delay: 0.2s">
        <h2 class="font-display font-bold text-lg mb-3">✅ Finished</h2>
        <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {% for entry in finished %}
            {% include 'library/_saved_card.html' %}
          {% endfor %}
        </div>
      </section>
    {% endif %}
  {% else %}
    <div class="rounded-2xl border border-dashed border-brand-300 dark:border-slate-700 p-8 text-center text-slate-500 dark:text-slate-400 fade-in-up">
      <p class="mb-3">Your library is empty.</p>
      <a href="{% url 'catalogue' %}" class="inline-block rounded-lg bg-brand-600 hover:bg-brand-700 text-white font-medium px-4 py-2 text-sm">Browse the catalogue</a>
    </div>
  {% endif %}
{% endblock %}'''

saved_card_html = '''<div class="rounded-2xl border border-brand-100 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm p-5 flex flex-col transition-transform hover:-translate-y-1 hover:shadow-md duration-300">
  <div class="flex justify-between items-start">
    <div>
      <span class="text-xs font-semibold uppercase tracking-wide text-brand-600 dark:text-brand-300">
        {% if entry.book.is_postgraduate %}Postgraduate{% else %}Level {{ entry.book.level }}{% endif %}
      </span>
      <a href="{% url 'book_detail' entry.book.pk %}" class="block font-display font-bold text-lg mt-1 mb-1 hover:text-brand-600 dark:hover:text-brand-300">{{ entry.book.title }}</a>
      {% if entry.book.author %}<p class="text-sm text-slate-500 dark:text-slate-400 mb-4">{{ entry.book.author }}</p>{% endif %}
    </div>
  </div>

  <details class="mb-4 group">
    <summary class="cursor-pointer text-sm font-medium text-brand-600 hover:text-brand-700 dark:text-brand-400 list-none flex items-center gap-1 transition-colors">
      <span>Notes & Progress</span>
      <svg class="w-4 h-4 transition-transform duration-300 group-open:rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
    </summary>
    <div class="mt-3 p-3 bg-brand-50 dark:bg-slate-800 rounded-lg">
      <form method="post" action="{% url 'update_progress' entry.book.pk %}" class="flex flex-col gap-2">
        {% csrf_token %}
        <div>
          <label class="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">Current Page</label>
          <input type="number" name="current_page" value="{{ entry.current_page }}" class="w-full rounded border border-brand-200 dark:border-slate-600 bg-white dark:bg-slate-900 px-2 py-1 text-sm focus:ring-2 focus:ring-brand-500 focus:outline-none" min="0">
        </div>
        <div>
          <label class="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">Personal Notes</label>
          <textarea name="notes" rows="3" class="w-full rounded border border-brand-200 dark:border-slate-600 bg-white dark:bg-slate-900 px-2 py-1 text-sm focus:ring-2 focus:ring-brand-500 focus:outline-none" placeholder="Jot down your thoughts...">{{ entry.notes }}</textarea>
        </div>
        <button type="submit" class="w-full bg-brand-600 text-white rounded text-xs py-1.5 font-medium hover:bg-brand-700 transition-colors">Save Notes</button>
      </form>
    </div>
  </details>

  <div class="mt-auto flex gap-2">
    <a href="{% url 'read_online' entry.book.pk %}"
       class="flex-1 text-center rounded-lg bg-brand-600 hover:bg-brand-700 text-white font-medium py-2 text-sm transition-colors">
      Read
    </a>
    <a href="{% url 'download_pdf' entry.book.pk %}"
       class="flex-1 text-center rounded-lg border border-brand-300 dark:border-slate-600 font-medium py-2 text-sm hover:bg-brand-50 dark:hover:bg-slate-800 transition-colors">
      PDF
    </a>
  </div>
  <form method="post" action="{% url 'toggle_save' entry.book.pk %}" class="mt-2">
    {% csrf_token %}
    <input type="hidden" name="next" value="{% url 'my_library' %}">
    <button class="w-full text-xs text-rose-500 hover:underline">Remove from library</button>
  </form>
</div>'''

with open('templates/library/my_library.html', 'w', encoding='utf-8') as f:
    f.write(my_library_html)
with open('templates/library/_saved_card.html', 'w', encoding='utf-8') as f:
    f.write(saved_card_html)
print('Templates updated!')
