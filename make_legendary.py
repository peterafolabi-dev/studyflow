import os

# 1. Update library/models.py
with open('library/models.py', 'r', encoding='utf-8') as f:
    models_content = f.read()

if 'current_page' not in models_content:
    models_content = models_content.replace(
        "status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='to_read')",
        "status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='to_read')\n    current_page = models.PositiveIntegerField(default=0)\n    notes = models.TextField(blank=True)"
    )
    with open('library/models.py', 'w', encoding='utf-8') as f:
        f.write(models_content)
    print("Updated library/models.py")

# 2. Update library/views.py
with open('library/views.py', 'r', encoding='utf-8') as f:
    views_content = f.read()

if 'def update_progress' not in views_content:
    new_view = '''
@login_required
@require_POST
def update_progress(request, pk):
    book = get_object_or_404(Book, pk=pk)
    entry, _created = SavedBook.objects.get_or_create(user=request.user, book=book)
    notes = request.POST.get('notes', '')
    try:
        page = int(request.POST.get('current_page', 0))
    except ValueError:
        page = 0
    
    entry.notes = notes
    entry.current_page = page
    entry.save(update_fields=['notes', 'current_page', 'updated_at'])
    messages.success(request, f'Progress and notes saved for "{book.title}".')
    
    return redirect('my_library')
'''
    views_content += new_view
    
    # Update my_library view to pass progress info
    old_my_library = '''    context = {
        'reading': saved.filter(status='reading'),
        'to_read': saved.filter(status='to_read'),
        'finished': saved.filter(status='finished'),
        'total': saved.count(),
    }
    return render(request, 'library/my_library.html', context)'''
    
    new_my_library = '''    try:
        from accounts.models import Profile
        profile = Profile.objects.filter(user=request.user).first()
        goal = profile.reading_goal if profile else 0
    except ImportError:
        goal = 0

    finished_count = saved.filter(status='finished').count()
    progress_percent = min(100, int((finished_count / goal) * 100)) if goal > 0 else 0

    context = {
        'reading': saved.filter(status='reading'),
        'to_read': saved.filter(status='to_read'),
        'finished': saved.filter(status='finished'),
        'total': saved.count(),
        'reading_goal': goal,
        'finished_count': finished_count,
        'progress_percent': progress_percent,
    }
    return render(request, 'library/my_library.html', context)'''
    
    views_content = views_content.replace(old_my_library, new_my_library)

    with open('library/views.py', 'w', encoding='utf-8') as f:
        f.write(views_content)
    print("Updated library/views.py")

# 3. Update library/urls.py
with open('library/urls.py', 'r', encoding='utf-8') as f:
    urls = f.read()

if "path('my-library/<int:pk>/progress/', views.update_progress, name='update_progress')," not in urls:
    urls = urls.replace(
        "path('my-library/<int:pk>/status/', views.update_status, name='update_status'),",
        "path('my-library/<int:pk>/status/', views.update_status, name='update_status'),\n    path('my-library/<int:pk>/progress/', views.update_progress, name='update_progress'),"
    )
    with open('library/urls.py', 'w', encoding='utf-8') as f:
        f.write(urls)
    print("Updated library/urls.py")


# 4. Add modern scrolling CSS
with open('static/css/style.css', 'r', encoding='utf-8') as f:
    css = f.read()

if 'scroll-behavior: smooth;' not in css:
    css = "html { scroll-behavior: smooth; }\n\n" + css
    
    animation_css = '''
/* 2026 Modern Scroll Animations */
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(20px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.fade-in-up {
  animation: fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
  animation-timeline: view();
  animation-range: entry 10% cover 25%;
}

@supports not (animation-timeline: view()) {
  .fade-in-up {
    animation-timeline: auto;
    animation-range: normal;
  }
}
'''
    css += animation_css
    with open('static/css/style.css', 'w', encoding='utf-8') as f:
        f.write(css)
    print("Updated style.css")
