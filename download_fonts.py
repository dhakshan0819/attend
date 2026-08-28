import urllib.request
import os
import re

font_url = "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap"
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

req = urllib.request.Request(font_url, headers=headers)
with urllib.request.urlopen(req) as response:
    css_content = response.read().decode('utf-8')

os.makedirs('/home/neko/attendance/static/fonts', exist_ok=True)

# Find all url(...) in css_content
urls = re.findall(r'url\((https://[^)]+)\)', css_content)

for i, url in enumerate(set(urls)):
    filename = f"inter-{i}.woff2"
    filepath = f"/home/neko/attendance/static/fonts/{filename}"
    print(f"Downloading {url} to {filepath}")
    urllib.request.urlretrieve(url, filepath)
    # The css will be in /static/fonts/, so it should just refer to the filename
    css_content = css_content.replace(url, filename)

with open('/home/neko/attendance/static/fonts/inter.css', 'w') as f:
    f.write(css_content)
    
print("Fonts downloaded and CSS updated.")
