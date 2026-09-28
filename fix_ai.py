import os
import re

with open('templates/base.html', 'r', encoding='utf-8') as f:
    text = f.read()

new_script = '''
    const chatBtn = document.getElementById('ai-chat-btn');
    const chatModal = document.getElementById('ai-chat-modal');
    const chatClose = document.getElementById('ai-chat-close');
    const chatForm = document.getElementById('ai-chat-form');
    const chatInput = document.getElementById('ai-chat-input');
    const chatMessages = document.getElementById('ai-chat-messages');

    if(chatBtn && chatModal) {
        chatBtn.addEventListener('click', () => {
            chatModal.classList.remove('hidden');
            chatBtn.classList.add('hidden');
            if(chatInput) chatInput.focus();
        });

        chatClose.addEventListener('click', () => {
            chatModal.classList.add('hidden');
            chatBtn.classList.remove('hidden');
        });

        if(chatForm) {
            chatForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const msg = chatInput.value.trim();
                if(!msg) return;

                chatMessages.innerHTML += `
                    <div class="bg-brand-600 text-white rounded-xl rounded-tr-none p-3 text-sm self-end max-w-[85%] shadow-sm">
                        ${msg}
                    </div>
                `;
                chatInput.value = '';
                chatMessages.scrollTop = chatMessages.scrollHeight;

                const typingId = 'typing-' + Date.now();
                chatMessages.innerHTML += `
                    <div id="${typingId}" class="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl rounded-tl-none p-3 text-sm text-slate-500 self-start max-w-[85%] shadow-sm">
                        Thinking...
                    </div>
                `;
                chatMessages.scrollTop = chatMessages.scrollHeight;

                try {
                    let csrf = '';
                    const tokenEl = document.querySelector('[name=csrfmiddlewaretoken]');
                    if (tokenEl) csrf = tokenEl.value;

                    const response = await fetch('/ai-chat/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrf
                        },
                        body: JSON.stringify({ message: msg })
                    });
                    const data = await response.json();
                    
                    const t = document.getElementById(typingId);
                    if (t) t.remove();
                    
                    chatMessages.innerHTML += `
                        <div class="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl rounded-tl-none p-3 text-sm text-slate-800 dark:text-slate-200 self-start max-w-[85%] shadow-sm">
                            ${data.reply}
                        </div>
                    `;
                    chatMessages.scrollTop = chatMessages.scrollHeight;
                } catch (error) {
                    const t = document.getElementById(typingId);
                    if (t) t.innerHTML = "Sorry, I'm offline right now! Did you set the API key in .env?";
                }
            });
        }
    }
</script>'''

text = re.sub(r'const chatBtn = document.getElementById.*?<\/script>', new_script, text, flags=re.DOTALL)

with open('templates/base.html', 'w', encoding='utf-8') as f:
    f.write(text)
print('Fixed AI chat JS')
