import os

def apply_animations(filepath):
    if not os.path.exists(filepath):
        return
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Generic replacements for common layout blocks
    content = content.replace('<section class="mb-8">', '<section class="mb-8 fade-in-up">')
    content = content.replace('<section class="section-block">', '<section class="section-block fade-in-up">')
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

apply_animations('templates/library/catalogue.html')
apply_animations('templates/resources/research.html')
apply_animations('templates/planner/course_detail.html')
print("Applied global animations")
