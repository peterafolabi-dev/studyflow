import os
import django
import json
from unittest.mock import MagicMock, patch

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'studyflow.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from planner.views import ai_chat_api

User = get_user_model()
user = User.objects.first()

rf = RequestFactory()

test_conversation = [
    ('hi', 'Step into the arena, athlete! What subject are we conquering today? ⚔️ Challenge: Name your target topic right now.'),
    ('i want to read', 'Good rep ahead. Which arena are we hitting? 1) Course lecture notes, 2) Catalogue textbook, or 3) Past questions? 🔥 Pick your rep.'),
    ('yes', 'Target locked. Fire up a 25-minute Pomodoro session in the Study Room right now. 🏆 Challenge: Start the timer and lock in.'),
    ('give me study tips', 'Three reps for victory: 1) Active recall using Flashcards for 15 mins. 2) 25-min Pomodoro reps with Lo-Fi or Deep Focus. 3) Log your study session to track your streak. ⚔️ Challenge: Create 5 flashcards for your hardest topic today!')
]

history = []
with patch.dict(os.environ, {'GROQ_API_KEY': 'dummy_key'}):
    with patch('groq.Groq') as mock_groq_class:
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client
        
        for msg, simulated_reply in test_conversation:
            mock_completion = MagicMock()
            mock_choice = MagicMock()
            mock_choice.message.content = simulated_reply
            mock_completion.choices = [mock_choice]
            mock_client.chat.completions.create.return_value = mock_completion
            
            req = rf.post('/ai-chat/', data=json.dumps({
                'message': msg,
                'history': history
            }), content_type='application/json')
            req.user = user
            
            resp = ai_chat_api(req)
            data = json.loads(resp.content.decode('utf-8'))
            
            call_kwargs = mock_client.chat.completions.create.call_args[1]
            print(f'=== Turn: "{msg}" ===')
            print('Model used:', call_kwargs['model'])
            print('Number of messages sent to Groq:', len(call_kwargs['messages']))
            print('Roles sequence:', [m['role'] for m in call_kwargs['messages']])
            print('Reply:', data['reply'])
            print()
            
            history.append({'role': 'user', 'content': msg})
            history.append({'role': 'assistant', 'content': data['reply']})
