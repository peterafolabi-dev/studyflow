import os

dashboard_html = '''{% extends 'base.html' %}
{% block title %}Dashboard · StudyFlow{% endblock %}
{% block content %}
  <div class="mb-8 fade-in-up">
    <h1 class="font-display text-4xl font-bold tracking-tight text-slate-900 dark:text-white mb-2">
      Welcome back, {{ user.username }}
    </h1>
    <p class="text-lg text-slate-500 dark:text-slate-400">
      You have <strong class="text-brand-600 dark:text-brand-400">{{ open_count }} open task{{ open_count|pluralize }}</strong> across {{ course_count }} course{{ course_count|pluralize }}. Let's get to work.
    </p>
  </div>

  <!-- BENTO BOX GRID LAYOUT -->
  <div class="grid grid-cols-1 md:grid-cols-3 gap-6">

    <!-- Main Column (Tasks & Courses) -->
    <div class="md:col-span-2 flex flex-col gap-6">
      
      {% if not course_count %}
        <div class="rounded-3xl border border-dashed border-brand-300 dark:border-slate-700 bg-brand-50/50 dark:bg-slate-900/30 p-10 text-center text-slate-500 dark:text-slate-400 fade-in-up flex flex-col items-center justify-center min-h-[300px]">
          <div class="text-5xl mb-4">📚</div>
          <p class="mb-6 text-lg font-medium text-slate-700 dark:text-slate-300">Your dashboard is empty.</p>
          <a class="btn inline-block rounded-full bg-brand-600 hover:bg-brand-700 text-white font-medium px-6 py-3 shadow-xl shadow-brand-500/20 transition-transform hover:-translate-y-1" href="{% url 'course_create' %}">Add your first course</a>
        </div>
      {% else %}

        <!-- Overdue -->
        {% if overdue %}
          <section class="rounded-3xl border border-rose-200 dark:border-rose-900/50 bg-rose-50/50 dark:bg-rose-950/20 p-6 fade-in-up">
            <div class="flex items-center justify-between mb-4">
                <h2 class="font-display font-bold text-xl text-rose-600 dark:text-rose-400 flex items-center gap-2">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    Overdue
                </h2>
            </div>
            <ul class="tasks space-y-3">
              {% for task in overdue %}
                {% include 'planner/_task_row.html' with next=request.path show_course=True %}
              {% endfor %}
            </ul>
          </section>
        {% endif %}

        <!-- Due This Week -->
        <section class="rounded-3xl border border-brand-100 dark:border-slate-800 bg-white/60 dark:bg-slate-900/50 backdrop-blur-xl p-6 fade-in-up shadow-sm" style="animation-delay: 0.1s">
          <div class="flex items-center justify-between mb-4">
              <h2 class="font-display font-bold text-xl text-slate-800 dark:text-white">Due in the next 7 days</h2>
          </div>
          {% if due_soon %}
            <ul class="tasks space-y-3">
              {% for task in due_soon %}
                {% include 'planner/_task_row.html' with next=request.path show_course=True %}
              {% endfor %}
            </ul>
          {% else %}
            <div class="py-8 text-center bg-slate-50/50 dark:bg-slate-800/30 rounded-2xl border border-dashed border-slate-200 dark:border-slate-700">
                <span class="text-3xl block mb-2">🎉</span>
                <p class="text-slate-500 dark:text-slate-400 font-medium">Nothing due this week. Enjoy your free time!</p>
            </div>
          {% endif %}
        </section>

      {% endif %}
    </div>

    <!-- Right Column (Quick Access & Tools) -->
    <div class="flex flex-col gap-6">

        <!-- Quick Access Bento -->
        <section class="rounded-3xl border border-brand-100 dark:border-slate-800 bg-brand-600 dark:bg-slate-800 p-6 fade-in-up shadow-xl shadow-brand-500/10 text-white" style="animation-delay: 0.15s">
            <h2 class="font-display font-bold text-lg mb-4 text-brand-50 dark:text-white">Quick Tools</h2>
            <div class="grid grid-cols-2 gap-3">
            {% for label, icon, url_name in quick_links %}
                {% if forloop.counter <= 6 %}
                <a href="{% url url_name %}" class="rounded-2xl bg-white/10 hover:bg-white/20 border border-white/10 p-3 text-center transition-all hover:scale-105 backdrop-blur-md flex flex-col items-center justify-center aspect-square">
                    <div class="text-3xl mb-2 drop-shadow-md">{{ icon }}</div>
                    <div class="text-xs font-semibold tracking-wide">{{ label }}</div>
                </a>
                {% endif %}
            {% endfor %}
            </div>
        </section>

        <!-- Trending Materials -->
        {% if trending_resources %}
        <section class="rounded-3xl border border-amber-100 dark:border-amber-900/30 bg-gradient-to-br from-amber-50 to-orange-50 dark:from-slate-900 dark:to-slate-900 p-6 fade-in-up shadow-sm" style="animation-delay: 0.2s">
            <h2 class="font-display font-bold text-lg mb-4 text-amber-900 dark:text-amber-500 flex items-center gap-2">
                🔥 Trending
            </h2>
            <div class="flex flex-col gap-3">
            {% for r in trending_resources %}
                <a href="{% url 'resource_download' r.pk %}" class="group rounded-2xl bg-white/80 dark:bg-slate-800 border border-amber-200/50 dark:border-slate-700 p-4 hover:shadow-md transition-all">
                <div class="flex justify-between items-start mb-1">
                    <span class="text-[10px] font-bold uppercase tracking-wider text-amber-600 dark:text-amber-400 bg-amber-100 dark:bg-amber-900/30 px-2 py-0.5 rounded-full">{{ r.get_resource_type_display }}</span>
                    <span class="text-xs text-slate-400 font-medium">{{ r.download_count }} dl</span>
                </div>
                <p class="font-semibold text-sm text-slate-800 dark:text-slate-200 group-hover:text-brand-600 transition-colors line-clamp-2 leading-snug">{{ r.title }}</p>
                </a>
            {% endfor %}
            </div>
        </section>
        {% endif %}

    </div>
  </div>
{% endblock %}'''

with open('templates/planner/dashboard.html', 'w', encoding='utf-8') as f:
    f.write(dashboard_html)
print('Redesigned dashboard to Bento Box layout!')
