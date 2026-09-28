import os

def append_to_file(filepath, content):
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write('\n' + content + '\n')

def write_file(filepath, content):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content.strip() + '\n')

# ----------------- ACCOUNTS -----------------
accounts_views = '''
from django.shortcuts import get_object_or_404
from .models import Profile, Notification
from .forms import ProfileForm

@login_required
def edit_profile(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('profile')
    else:
        form = ProfileForm(instance=profile)
    return render(request, 'accounts/edit_profile.html', {'form': form})

@login_required
def public_profile(request, username):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    target_user = get_object_or_404(User, username=username)
    profile, _ = Profile.objects.get_or_create(user=target_user)
    return render(request, 'accounts/public_profile.html', {'target_user': target_user, 'profile': profile})

@login_required
def notifications_view(request):
    notifs = Notification.objects.filter(user=request.user)
    notifs.update(is_read=True)
    return render(request, 'accounts/notifications.html', {'notifications': notifs})
'''
append_to_file('accounts/views.py', accounts_views)

accounts_forms = '''
from django import forms
from .models import Profile

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['bio', 'department', 'level', 'reading_goal', 'avatar_color']
'''
if os.path.exists('accounts/forms.py'):
    append_to_file('accounts/forms.py', accounts_forms)
else:
    write_file('accounts/forms.py', accounts_forms)

with open('accounts/urls.py', 'r', encoding='utf-8') as f:
    u = f.read()
u = u.replace(
    "path('profile/', views.profile, name='profile'),",
    "path('profile/', views.profile, name='profile'),\n    path('profile/edit/', views.edit_profile, name='edit_profile'),\n    path('user/<str:username>/', views.public_profile, name='public_profile'),\n    path('notifications/', views.notifications_view, name='notifications'),"
)
write_file('accounts/urls.py', u)


# ----------------- PLANNER -----------------
planner_views = '''
from .models import StudySession, FlashcardDeck, Flashcard

@login_required
def study_room(request):
    courses = Course.objects.filter(user=request.user)
    return render(request, 'planner/study_room.html', {'courses': courses})

@login_required
@require_POST
def log_study(request):
    duration = int(request.POST.get('duration', 0))
    course_id = request.POST.get('course_id')
    if duration > 0:
        course = Course.objects.filter(id=course_id, user=request.user).first() if course_id else None
        StudySession.objects.create(user=request.user, course=course, duration_minutes=duration)
    return redirect('study_room')

@login_required
def flashcard_hubs(request):
    decks = FlashcardDeck.objects.filter(course__user=request.user)
    return render(request, 'planner/flashcards.html', {'decks': decks})
'''
append_to_file('planner/views.py', planner_views)

with open('planner/urls.py', 'r', encoding='utf-8') as f:
    u = f.read()
u = u.replace(
    "path('timetable/', views.timetable, name='timetable'),",
    "path('timetable/', views.timetable, name='timetable'),\n    path('study/', views.study_room, name='study_room'),\n    path('study/log/', views.log_study, name='log_study'),\n    path('flashcards/', views.flashcard_hubs, name='flashcards'),"
)
write_file('planner/urls.py', u)


# ----------------- COMMUNITY -----------------
community_views = '''
from .models import ThreadVote
from django.contrib.auth import get_user_model
from planner.models import Course

@login_required
def find_buddies(request):
    User = get_user_model()
    my_courses = set(Course.objects.filter(user=request.user).values_list('code', flat=True))
    buddies = []
    if my_courses:
        other_users = User.objects.exclude(id=request.user.id)
        for u in other_users:
            u_courses = set(Course.objects.filter(user=u).values_list('code', flat=True))
            overlap = my_courses.intersection(u_courses)
            if overlap:
                buddies.append({'user': u, 'overlap': overlap})
    return render(request, 'community/find_buddies.html', {'buddies': buddies})

@login_required
@require_POST
def vote_thread(request, pk):
    thread = get_object_or_404(Thread, pk=pk)
    val = int(request.POST.get('value', 1))
    ThreadVote.objects.update_or_create(user=request.user, thread=thread, defaults={'value': val})
    return redirect('thread_detail', pk=pk)
'''
append_to_file('community/views.py', community_views)

with open('community/urls.py', 'r', encoding='utf-8') as f:
    u = f.read()
u = u.replace(
    "path('new/', views.thread_create, name='thread_create'),",
    "path('new/', views.thread_create, name='thread_create'),\n    path('buddies/', views.find_buddies, name='find_buddies'),\n    path('<int:pk>/vote/', views.vote_thread, name='vote_thread'),"
)
write_file('community/urls.py', u)


# ----------------- TEMPLATES -----------------
write_file('templates/accounts/edit_profile.html', """
{% extends 'base.html' %}
{% block title %}Edit Profile{% endblock %}
{% block content %}
<div class="page">
    <h2>Edit Profile</h2>
    <form method="post" class="form section-block">
        {% csrf_token %}
        {{ form.as_p }}
        <button type="submit" class="btn">Save Profile</button>
    </form>
</div>
{% endblock %}
""")

write_file('templates/accounts/public_profile.html', """
{% extends 'base.html' %}
{% block title %}{{ target_user.username }}'s Profile{% endblock %}
{% block content %}
<div class="page">
    <h2>{{ target_user.username }}'s Profile</h2>
    <p class="muted">Bio: {{ profile.bio }}</p>
    <p class="muted">Department: {{ profile.department }}</p>
    <p class="muted">Reading Goal: {{ profile.reading_goal }}</p>
</div>
{% endblock %}
""")

write_file('templates/accounts/notifications.html', """
{% extends 'base.html' %}
{% block title %}Notifications{% endblock %}
{% block content %}
<div class="page">
    <h2>Notifications</h2>
    <ul class="tasks">
    {% for n in notifications %}
        <li class="task"><div class="task-main">{{ n.message }} <span class="muted">- {{ n.created_at|date }}</span></div></li>
    {% empty %}
        <li class="empty">No notifications yet.</li>
    {% endfor %}
    </ul>
</div>
{% endblock %}
""")

write_file('templates/planner/study_room.html', """
{% extends 'base.html' %}
{% block title %}Study Room{% endblock %}
{% block content %}
<div class="page">
    <h2>Pomodoro Timer</h2>
    <div style="font-size: 4rem; margin: 2rem 0; font-family: var(--font-head); font-weight: bold; color: var(--primary);" id="timer">25:00</div>
    <form method="post" action="{% url 'log_study' %}" class="form">
        {% csrf_token %}
        <input type="hidden" name="duration" value="25">
        <div class="field">
            <label>Log time to course (optional)</label>
            <select name="course_id" style="width: 100%; padding: 0.6rem; border-radius: 6px;">
                <option value="">No specific course</option>
                {% for c in courses %}
                <option value="{{ c.id }}">{{ c.code }}</option>
                {% endfor %}
            </select>
        </div>
        <button type="submit" class="btn">Log 25 Minutes</button>
    </form>
</div>
{% endblock %}
""")

write_file('templates/planner/flashcards.html', """
{% extends 'base.html' %}
{% block title %}Flashcards{% endblock %}
{% block content %}
<div class="page">
    <h2>My Flashcard Decks</h2>
    <ul class="courses">
    {% for d in decks %}
        <li class="course"><a href="#">
            <span class="course-name">{{ d.title }}</span>
            <span class="course-code">{{ d.course.code }}</span>
        </a></li>
    {% empty %}
        <li class="empty">No decks yet.</li>
    {% endfor %}
    </ul>
</div>
{% endblock %}
""")

write_file('templates/community/find_buddies.html', """
{% extends 'base.html' %}
{% block title %}Study Buddies{% endblock %}
{% block content %}
<div class="page">
    <h2>Study Buddy Matcher</h2>
    <ul class="tasks">
    {% for b in buddies %}
        <li class="task">
            <div class="task-main">
                <a href="{% url 'public_profile' b.user.username %}" class="task-title" style="color: var(--primary);">{{ b.user.username }}</a>
                <p class="task-course">Shared courses: {{ b.overlap|join:", " }}</p>
            </div>
            <button class="btn ghost">Send Request</button>
        </li>
    {% empty %}
        <li class="empty">No matches found right now. Add more courses!</li>
    {% endfor %}
    </ul>
</div>
{% endblock %}
""")
print('Feature wiring complete.')
