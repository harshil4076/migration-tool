#!/usr/bin/env python3
"""
Clone Mode v2: Creates a WordPress page with exact HTML/CSS from source.
Saves directly via WP-CLI to bypass content filtering.
"""
import requests
import re
import json
import subprocess
import tempfile
import os
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv('/home/harshil/migration-tool/migration-tool/.env')

SOURCE_URL = "https://www.orangeville.ca"
WP_URL = os.getenv("WP_URL", "http://localhost:8881")

def fetch_page(url):
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text

def fetch_css(css_urls):
    all_css = []
    for url in css_urls:
        try:
            resp = requests.get(url, timeout=15)
            css_text = resp.text
            # Rewrite relative URLs in CSS to absolute
            css_text = re.sub(
                r'url\(["\']?(?!data:|http|//)(/?[^"\')\s]+)["\']?\)',
                lambda m: f'url("https://www.orangeville.ca{m.group(1) if m.group(1).startswith("/") else "/" + m.group(1)}")',
                css_text
            )
            all_css.append(css_text)
        except Exception as e:
            print(f"  Warning: Could not fetch CSS {url}: {e}")
    return "\n".join(all_css)

def main():
    print("=" * 60)
    print("CLONE MODE v2: Exact HTML/CSS Copy (Direct DB)")
    print("=" * 60)
    
    # Fetch source
    print("\n1. Fetching source page...")
    html = fetch_page(SOURCE_URL)
    soup = BeautifulSoup(html, 'html.parser')
    print(f"   Downloaded {len(html)} chars")
    
    # Extract CSS links
    css_links = []
    for link in soup.find_all('link', rel='stylesheet'):
        href = link.get('href', '')
        if href:
            if href.startswith('/'):
                href = f'https://www.orangeville.ca{href}'
            elif not href.startswith('http'):
                href = f'https://www.orangeville.ca/{href}'
            css_links.append(href)
    
    # Get inline styles
    inline_styles = []
    for style in soup.find_all('style'):
        if style.string:
            inline_styles.append(style.string)
    
    # Get inline scripts (for functionality like carousels, etc.)
    scripts = []
    for script in soup.find_all('script'):
        src = script.get('src', '')
        if src:
            if src.startswith('/'):
                src = f'https://www.orangeville.ca{src}'
            scripts.append(f'<script src="{src}"></script>')
        elif script.string:
            scripts.append(f'<script>{script.string}</script>')
    
    print(f"   Found {len(css_links)} stylesheets, {len(scripts)} scripts")
    
    # Fetch external CSS
    print("\n2. Downloading CSS...")
    external_css = fetch_css(css_links)
    print(f"   Total CSS: {len(external_css)} chars")
    
    # Get the full head section for meta tags, etc.
    head = soup.find('head')
    meta_tags = ""
    if head:
        for meta in head.find_all('meta'):
            meta_tags += str(meta) + "\n"
    
    # Get body
    body = soup.find('body')
    body_classes = ' '.join(body.get('class', [])) if body else ''
    body_html = ''.join(str(c) for c in body.children) if body else str(soup)
    
    # Rewrite relative URLs to absolute
    body_html = re.sub(
        r'(src|href|data-src|data-bg|action)="(/[^"]*)"',
        r'\1="https://www.orangeville.ca\2"',
        body_html
    )
    
    # Also handle srcset
    body_html = re.sub(
        r'(srcset=")(/[^"]*)"',
        lambda m: m.group(1) + re.sub(r'(/[^\s,]+)', r'https://www.orangeville.ca\1', m.group(2)) + '"',
        body_html
    )

    # Build complete standalone HTML page
    all_inline_css = "\n".join(inline_styles)
    
    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Orangeville - Clone Mode</title>
{meta_tags}
<style>
/* Reset */
* {{ margin: 0; padding: 0; }}
body {{ font-family: inherit; }}

/* External CSS from source */
{external_css}

/* Inline CSS from source */
{all_inline_css}
</style>
</head>
<body class="{body_classes}">
{body_html}

{''.join(scripts)}

<script>
// Fix any remaining relative links
document.querySelectorAll('a[href^="/"]').forEach(function(a) {{
    a.href = 'https://www.orangeville.ca' + a.getAttribute('href');
}});
document.querySelectorAll('img[src^="/"]').forEach(function(img) {{
    img.src = 'https://www.orangeville.ca' + img.getAttribute('src');
}});
</script>
</body>
</html>"""
    
    # Save as a static HTML file that WordPress serves
    tmp_file = '/tmp/orangeville_clone.html'
    with open(tmp_file, 'w', encoding='utf-8') as f:
        f.write(full_html)
    
    print(f"\n3. Full page built ({len(full_html)} chars)")
    
    # Copy to WordPress container as a standalone HTML file
    print("\n4. Deploying to WordPress...")
    os.system(f"docker cp {tmp_file} migration-tool-wordpress-1:/var/www/html/orangeville-clone.html")
    os.system("docker exec migration-tool-wordpress-1 chown www-data:www-data /var/www/html/orangeville-clone.html")
    
    print(f"\n{'=' * 60}")
    print("CLONE MODE v2 COMPLETE")
    print(f"  View at: {WP_URL}/orangeville-clone.html")
    print(f"{'=' * 60}")

if __name__ == "__main__":
    main()
