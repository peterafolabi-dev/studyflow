import os

with open('templates/base.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Add view transition meta tag
meta_tag = '<meta name="view-transition" content="same-origin">'
if meta_tag not in html:
    html = html.replace('<head>', f'<head>\n  {meta_tag}')

# Add JS polyfill for sibling-index
js_script = '''
  <script>
    document.addEventListener('DOMContentLoaded', function() {
      if(!CSS.supports('animation-delay: calc(sibling-index() * 0.1s)')) {
        document.querySelectorAll('.grid, .tasks, .flex.gap-3').forEach(container => {
          [...container.children].forEach((el, index) => el.style.setProperty('--sibling-index', index + 1));
        });
      }
    });
  </script>
'''
if 'sibling-index' not in html:
    html = html.replace('</body>', f'{js_script}\n</body>')

with open('templates/base.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Added View Transitions and Polyfill to base.html!')
