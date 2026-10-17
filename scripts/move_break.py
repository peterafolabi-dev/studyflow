import os

with open('planner/views.py', 'r', encoding='utf-8') as f:
    views = f.read()

# Remove the old one if it exists
views = views.replace("('Break Room', '🎮', 'break_room'),\n        ", "")
views = views.replace("('Break Room', '🎮', 'break_room'),", "")

# Add it to the very front of the quick_links list
views = views.replace("'quick_links': [", "'quick_links': [\n            ('Break Room', '🎮', 'break_room'),")

with open('planner/views.py', 'w', encoding='utf-8') as f:
    f.write(views)
print('Moved Break Room to front!')
