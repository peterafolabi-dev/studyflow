import os

# 1. Update Models
with open('community/models.py', 'r', encoding='utf-8') as f:
    models = f.read()

if 'room = models.CharField' not in models:
    models = models.replace('class ChatMessage(models.Model):', 'class ChatMessage(models.Model):\n    room = models.CharField(max_length=50, default="global")')
    with open('community/models.py', 'w', encoding='utf-8') as f:
        f.write(models)

# 2. Update Views
with open('community/views.py', 'r', encoding='utf-8') as f:
    views = f.read()

# Completely rewrite chat_api
import re
views = re.sub(r'@login_required\ndef chat_api.*?return JsonResponse\(\{.*?\}\)', '''@login_required
def chat_api(request):
    room = request.GET.get('room', 'global')
    if request.method == 'POST':
        data = json.loads(request.body)
        text = data.get('text', '').strip()
        room = data.get('room', 'global')
        if text:
            ChatMessage.objects.create(user=request.user, text=text, room=room)
            return JsonResponse({'status': 'ok'})
        return JsonResponse({'status': 'error'}, status=400)
    
    messages = ChatMessage.objects.filter(room=room)[:50]
    data = []
    for msg in reversed(messages):
        data.append({
            'username': msg.user.username,
            'text': msg.text,
            'time': msg.created_at.strftime("%H:%M"),
            'is_me': msg.user == request.user
        })
    return JsonResponse({'messages': data})''', views, flags=re.DOTALL)

with open('community/views.py', 'w', encoding='utf-8') as f:
    f.write(views)

# 3. Rewrite global_chat.html to include Tabs and Optimistic UI Update
chat_html = '''{% extends 'base.html' %}
{% block title %}Campus Chat · StudyFlow{% endblock %}
{% block content %}
<div class="mb-6 fade-in-up">
  <h1 class="font-display text-4xl font-bold tracking-tight text-slate-900 dark:text-white mb-2">StudyFlow Chat 💬</h1>
  <p class="text-slate-500 dark:text-slate-400 mt-1">Connect with students worldwide or locally at FUT Minna.</p>
</div>

<div class="bg-white/60 dark:bg-slate-900/60 backdrop-blur-xl border border-white/50 dark:border-slate-700/50 rounded-3xl shadow-xl overflow-hidden flex flex-col md:flex-row fade-in-up h-[600px]">
    
    <!-- Sidebar / Room Switcher -->
    <div class="w-full md:w-64 bg-slate-50 dark:bg-slate-900 border-b md:border-b-0 md:border-r border-slate-200 dark:border-slate-800 p-4 flex flex-col gap-2">
        <h3 class="font-bold text-xs uppercase tracking-wider text-slate-500 mb-2 px-2">Chat Rooms</h3>
        
        <button onclick="switchRoom('global')" id="btn-global" class="room-btn w-full flex items-center gap-3 px-4 py-3 rounded-xl bg-brand-100 dark:bg-brand-900/40 text-brand-700 dark:text-brand-300 font-medium transition-all text-left">
            <span class="text-xl">🌍</span> Global
        </button>
        
        <button onclick="switchRoom('futminna')" id="btn-futminna" class="room-btn w-full flex items-center gap-3 px-4 py-3 rounded-xl hover:bg-slate-200 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 font-medium transition-all text-left">
            <span class="text-xl">🏫</span> FUT Minna
        </button>
    </div>

    <!-- Main Chat Area -->
    <div class="flex-1 flex flex-col relative">
        <div class="bg-brand-600 px-6 py-4 border-b border-brand-700 flex justify-between items-center">
            <div class="flex items-center gap-3">
                <span class="relative flex h-3 w-3">
                  <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span class="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                </span>
                <h2 id="room-title" class="font-bold text-white font-display text-lg">🌍 Global Chat</h2>
            </div>
            <span class="text-brand-200 text-xs font-medium bg-brand-800/50 px-2 py-1 rounded-md">Live</span>
        </div>

        <!-- Messages Area -->
        <div id="chat-messages" class="flex-1 p-6 overflow-y-auto flex flex-col gap-4 bg-slate-50/50 dark:bg-slate-950/30 pb-24">
            <!-- JS will populate -->
        </div>

        <!-- Input Area -->
        <div class="absolute bottom-0 left-0 right-0 p-4 bg-white/90 dark:bg-slate-900/90 backdrop-blur-md border-t border-slate-200 dark:border-slate-800">
            <form id="chat-form" class="flex gap-3">
                {% csrf_token %}
                <input type="text" id="chat-input" class="flex-1 bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl px-4 py-3 text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500 focus:outline-none transition-all" placeholder="Type your message..." autocomplete="off">
                <button type="submit" class="bg-brand-600 hover:bg-brand-700 text-white p-3 rounded-2xl transition-transform hover:scale-105 shadow-md shadow-brand-500/20">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
                </button>
            </form>
        </div>
    </div>
</div>

<script>
    const chatMessages = document.getElementById('chat-messages');
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const roomTitle = document.getElementById('room-title');
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    let currentRoom = 'global';
    let isScrolledToBottom = true;

    function switchRoom(room) {
        currentRoom = room;
        
        // Update UI Tabs
        document.querySelectorAll('.room-btn').forEach(btn => {
            btn.className = 'room-btn w-full flex items-center gap-3 px-4 py-3 rounded-xl hover:bg-slate-200 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 font-medium transition-all text-left';
        });
        const activeBtn = document.getElementById('btn-' + room);
        activeBtn.className = 'room-btn w-full flex items-center gap-3 px-4 py-3 rounded-xl bg-brand-100 dark:bg-brand-900/40 text-brand-700 dark:text-brand-300 font-medium transition-all text-left';
        
        // Update Title
        roomTitle.innerHTML = room === 'global' ? '🌍 Global Chat' : '🏫 FUT Minna Chat';
        
        chatMessages.innerHTML = '<div class="text-center text-slate-400 text-sm mt-10">Loading messages...</div>';
        fetchMessages();
    }

    chatMessages.addEventListener('scroll', () => {
        isScrolledToBottom = chatMessages.scrollHeight - chatMessages.clientHeight <= chatMessages.scrollTop + 20;
    });

    async function fetchMessages() {
        try {
            const res = await fetch(`{% url 'chat_api' %}?room=${currentRoom}`);
            const data = await res.json();
            
            chatMessages.innerHTML = data.messages.map(msg => `
                <div class="flex flex-col max-w-[75%] ${msg.is_me ? 'self-end items-end' : 'self-start items-start'}">
                    <span class="text-[10px] font-medium text-slate-400 mb-1 px-1">${msg.is_me ? 'You' : msg.username} • ${msg.time}</span>
                    <div class="${msg.is_me ? 'bg-brand-600 text-white rounded-tl-2xl rounded-tr-sm rounded-b-2xl' : 'bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 rounded-tr-2xl rounded-tl-sm rounded-b-2xl'} px-4 py-2.5 text-sm shadow-sm">
                        ${msg.text}
                    </div>
                </div>
            `).join('');

            if(isScrolledToBottom) {
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }
        } catch (e) { console.error(e); }
    }

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const text = chatInput.value.trim();
        if(!text) return;
        
        // Optimistic UI Update (Makes it feel instant!)
        const now = new Date();
        const timeString = now.getHours().toString().padStart(2, '0') + ':' + now.getMinutes().toString().padStart(2, '0');
        
        chatMessages.innerHTML += `
            <div class="flex flex-col max-w-[75%] self-end items-end opacity-70 transition-opacity" id="temp-msg">
                <span class="text-[10px] font-medium text-slate-400 mb-1 px-1">You • ${timeString}</span>
                <div class="bg-brand-600 text-white rounded-tl-2xl rounded-tr-sm rounded-b-2xl px-4 py-2.5 text-sm shadow-sm">
                    ${text}
                </div>
            </div>
        `;
        chatMessages.scrollTop = chatMessages.scrollHeight;
        chatInput.value = '';
        
        try {
            await fetch("{% url 'chat_api' %}", {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ text: text, room: currentRoom })
            });
            isScrolledToBottom = true;
            fetchMessages(); // Pull real state from server
        } catch (e) { console.error(e); }
    });

    // Poll every 3 seconds
    fetchMessages();
    setInterval(fetchMessages, 3000);
</script>
{% endblock %}'''

with open('templates/community/global_chat.html', 'w', encoding='utf-8') as f:
    f.write(chat_html)

print('Updated Chat functionality!')
