import re

with open('static/index.html', 'r') as f:
    html = f.read()

# Remove sidebar
html = re.sub(r'<aside class="sidebar">.*?</aside>', '', html, flags=re.DOTALL)
# Remove top header
html = re.sub(r'<header class="top-header">.*?</header>', '', html, flags=re.DOTALL)
# Add fullscreen-mode to body
html = html.replace('<div class="app-container">', '<div class="app-container fullscreen-mode">')

# Extract tabs
dashboard = re.search(r'(<section id="tab-dashboard".*?</section>)', html, flags=re.DOTALL).group(1)
register = re.search(r'(<section id="tab-register".*?</section>)', html, flags=re.DOTALL).group(1)
kiosk = re.search(r'(<section id="tab-kiosk".*?</section>)', html, flags=re.DOTALL).group(1)
history = re.search(r'(<section id="tab-history".*?</section>)', html, flags=re.DOTALL).group(1)

def build_page(target_tab_id, out_file):
    page = html.replace(dashboard, '').replace(history, '')
    if target_tab_id == 'tab-register':
        page = page.replace(kiosk, '')
        page = page.replace('<section id="tab-register" class="tab-content">', '<section id="tab-register" class="tab-content active">')
    elif target_tab_id == 'tab-kiosk':
        page = page.replace(register, '')
        page = page.replace('<section id="tab-kiosk" class="tab-content">', '<section id="tab-kiosk" class="tab-content active">')
    
    with open(f'static/{out_file}', 'w') as f:
        f.write(page)

build_page('tab-register', 'face_registration.html')
build_page('tab-kiosk', 'face_attendance.html')

print("Created standalone pages successfully.")
