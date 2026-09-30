import re
import json

with open('planner/views.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Remove Campus Chat from quick links
text = re.sub(r"\s*\('Campus Chat'.*?'global_chat'\),", "", text)

groq_api = '''import logging
logger = logging.getLogger('django.request')

@login_required
@require_POST
def ai_chat_api(request):
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        if not user_message:
            return JsonResponse({'reply': 'Ask me something!'})
            
        api_key = os.environ.get('GROQ_API_KEY')
        if not api_key:
            return JsonResponse({'reply': 'I am ready to go! To activate me, add GROQ_API_KEY to your Render environment variables.'})
            
        from groq import Groq
        client = Groq(api_key=api_key)
        
        system_prompt = """You are the legendary AI study assistant inside StudyFlow, a comprehensive student app built for FUT Minna students.
You know everything about StudyFlow:
- Users can manage Courses and Tasks on the Dashboard.
- Users can view and add to the Catalogue (a global library).
- IBB Library allows users to reserve and return physical books.
- Study Groups are for specific courses.
- Break Room has mini-games.
- Study Room has a Pomodoro Timer (with Deep Focus and Lo-Fi Spotify playlists) and logs study sessions.
- Flashcards let users quiz themselves.
- GPA Calculator helps them track their grades.
- Resources section holds Past Questions, Notes, Theses, and Lecture Slides.

Your personality: Friendly, highly intelligent, encouraging, and legendary.
Respond in PLAIN TEXT ONLY. Do not use Markdown, HTML tags, or code blocks. Keep it concise."""

        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            model="llama3-8b-8192",
        )
        reply = chat_completion.choices[0].message.content
        return JsonResponse({'reply': reply})
    except Exception as e:
        logger.error('AI chat error: %s', e, exc_info=True)
        return JsonResponse({'reply': 'Oops, I encountered an error. Check if your API key is correct!'}, status=500)
'''

text = re.sub(r'import logging\s+logger = logging\.getLogger.*?status=500\)', groq_api.strip(), text, flags=re.DOTALL)

with open('planner/views.py', 'w', encoding='utf-8') as f:
    f.write(text)

with open('templates/base.html', 'r', encoding='utf-8') as f:
    base_html = f.read()

base_html = re.sub(r'<a href="\{\% url \'global_chat\' \%\}"[^>]*>.*?Campus Chat.*?</a>', '', base_html, flags=re.DOTALL)
base_html = re.sub(r'GEMINI_API_KEY', 'GROQ_API_KEY', base_html)

with open('templates/base.html', 'w', encoding='utf-8') as f:
    f.write(base_html)

print('Updated successfully!')
