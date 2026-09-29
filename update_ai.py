import os
import re

with open('planner/views.py', 'r', encoding='utf-8') as f:
    text = f.read()

new_api = '''def ai_chat_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '')
            
            api_key = os.environ.get('GEMINI_API_KEY')
            if not api_key:
                return JsonResponse({'reply': 'I am ready to go! To activate me, add GEMINI_API_KEY to the .env file.'})
            
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = f"""You are a highly intelligent, friendly AI study assistant inside a university app called StudyFlow. 
You help students with their homework, explain complex topics, and give study advice. 
Keep your answers concise, encouraging, and formatted with HTML tags (like <b>, <i>, <br>, <ul>, <li>) so it looks good in a chat bubble. Do not use markdown backticks or markdown headers, just use raw text and simple HTML tags.
Student's message: {user_message}"""

            response = model.generate_content(prompt)
            
            return JsonResponse({'reply': response.text})
        except Exception as e:
            return JsonResponse({'reply': 'Oops, I encountered an error connecting to Gemini! Check your API key. Error: ' + str(e)}, status=500)
    return JsonResponse({'error': 'Invalid method'}, status=405)
'''

text = re.sub(r'def ai_chat_api.*?return JsonResponse\(\{\'error\': \'Invalid method\'\}, status=405\)', new_api, text, flags=re.DOTALL)

with open('planner/views.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Updated AI logic!')
