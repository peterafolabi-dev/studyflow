import os

study_room_html = '''{% extends 'base.html' %}
{% block title %}Lo-Fi Study Room · StudyFlow{% endblock %}
{% block content %}
<div class="relative overflow-hidden rounded-3xl border border-brand-200 dark:border-slate-800 shadow-2xl mb-8 min-h-[75vh] flex items-center justify-center fade-in-up">
    
    <!-- Background YouTube Video (Lo-Fi Girl Live Stream) -->
    <div class="absolute inset-0 w-full h-full pointer-events-none opacity-80 dark:opacity-40">
        <iframe class="w-full h-full scale-[1.3]" 
                src="https://www.youtube.com/embed/jfKfPfyJRdk?autoplay=1&mute=0&controls=0&showinfo=0&rel=0&loop=1&playlist=jfKfPfyJRdk" 
                frameborder="0" 
                allow="autoplay; encrypted-media" 
                allowfullscreen>
        </iframe>
    </div>

    <!-- Glassmorphism Overlay Timer -->
    <div class="relative z-10 bg-white/60 dark:bg-slate-900/60 backdrop-blur-md border border-white/40 dark:border-slate-700/50 p-8 rounded-3xl shadow-xl max-w-sm w-full mx-4 text-center">
        <h2 class="font-display text-2xl font-bold text-slate-800 dark:text-white mb-1">Study Room 🎧</h2>
        <p class="text-slate-600 dark:text-slate-300 text-sm mb-6">Focus with live lo-fi beats.</p>

        <div class="text-6xl font-display font-bold text-brand-700 dark:text-brand-400 mb-6 tracking-tight" style="font-variant-numeric: tabular-nums;" id="timer-display">
            25:00
        </div>

        <div class="flex justify-center gap-3 mb-8">
            <button id="start-btn" class="bg-brand-600 hover:bg-brand-700 text-white px-6 py-2 rounded-full font-medium transition-colors shadow-lg shadow-brand-500/30">
                Start Focus
            </button>
            <button id="reset-btn" class="bg-slate-200 dark:bg-slate-700 hover:bg-slate-300 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200 px-6 py-2 rounded-full font-medium transition-colors hidden">
                Reset
            </button>
        </div>

        <hr class="border-slate-300/50 dark:border-slate-700/50 mb-6">

        <form method="post" action="{% url 'log_study' %}" id="log-form">
            {% csrf_token %}
            <input type="hidden" name="duration" id="duration-input" value="25">
            <div class="text-left mb-4">
                <label class="block text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-2">Log to Course</label>
                <select name="course_id" class="w-full bg-white/50 dark:bg-slate-800/50 border border-slate-300 dark:border-slate-600 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-brand-500 focus:outline-none backdrop-blur-sm">
                    <option value="">General Study</option>
                    {% for c in courses %}
                    <option value="{{ c.id }}">{{ c.code }}</option>
                    {% endfor %}
                </select>
            </div>
            <button type="submit" class="w-full bg-emerald-500 hover:bg-emerald-600 text-white px-4 py-2.5 rounded-xl font-medium transition-colors shadow-lg shadow-emerald-500/20" id="log-btn">
                Save Session (25m)
            </button>
        </form>
    </div>
</div>

<script>
    let timeLeft = 25 * 60;
    let timerId = null;
    let isRunning = false;
    
    const display = document.getElementById('timer-display');
    const startBtn = document.getElementById('start-btn');
    const resetBtn = document.getElementById('reset-btn');
    const logBtn = document.getElementById('log-btn');
    const durationInput = document.getElementById('duration-input');

    function updateDisplay() {
        const m = Math.floor(timeLeft / 60);
        const s = timeLeft % 60;
        display.textContent = `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }

    startBtn.addEventListener('click', () => {
        if (!isRunning) {
            isRunning = true;
            startBtn.textContent = 'Pause';
            startBtn.classList.replace('bg-brand-600', 'bg-amber-500');
            startBtn.classList.replace('hover:bg-brand-700', 'hover:bg-amber-600');
            resetBtn.classList.remove('hidden');
            
            timerId = setInterval(() => {
                if (timeLeft > 0) {
                    timeLeft--;
                    updateDisplay();
                } else {
                    clearInterval(timerId);
                    isRunning = false;
                    startBtn.textContent = 'Done!';
                    alert('Focus session complete! Great job.');
                }
            }, 1000);
        } else {
            isRunning = false;
            clearInterval(timerId);
            startBtn.textContent = 'Resume';
            startBtn.classList.replace('bg-amber-500', 'bg-brand-600');
            startBtn.classList.replace('hover:bg-amber-600', 'hover:bg-brand-700');
        }
    });

    resetBtn.addEventListener('click', () => {
        isRunning = false;
        clearInterval(timerId);
        timeLeft = 25 * 60;
        updateDisplay();
        startBtn.textContent = 'Start Focus';
        startBtn.classList.replace('bg-amber-500', 'bg-brand-600');
        startBtn.classList.replace('hover:bg-amber-600', 'hover:bg-brand-700');
        resetBtn.classList.add('hidden');
    });
</script>
{% endblock %}'''

with open('templates/planner/study_room.html', 'w', encoding='utf-8') as f:
    f.write(study_room_html)
print('Built Lo-Fi Study Room!')
