#!/usr/bin/env python3
"""
Clone Mode: Creates a WordPress page that is an exact HTML/CSS copy of the source.
Inlines all CSS, rewrites asset URLs to point to the original source.
"""
import requests
import re
import json
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import os

load_dotenv('/home/harshil/migration-tool/migration-tool/.env')

SOURCE_URL = "https://www.orangeville.ca"
WP_URL = os.getenv("WP_URL", "http://localhost:8881")
WP_USER = os.getenv("WP_USERNAME", "admin")
WP_PASS = os.getenv("WP_APP_PASSWORD", "")

def fetch_page(url):
    """Fetch the full HTML of a page."""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text

def fetch_css(css_urls):
    """Download and concatenate all CSS files."""
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
            all_css.append(f"/* Source: {url} */\n{css_text}")
        except Exception as e:
            print(f"  Warning: Could not fetch CSS {url}: {e}")
    return "\n".join(all_css)

def extract_body_and_css(html):
    """Extract body content and all CSS from the HTML."""
    soup = BeautifulSoup(html, 'html.parser')
    
    # Collect external CSS links
    css_links = []
    for link in soup.find_all('link', rel='stylesheet'):
        href = link.get('href', '')
        if href:
            if href.startswith('/'):
                href = f'https://www.orangeville.ca{href}'
            elif not href.startswith('http'):
                href = f'https://www.orangeville.ca/{href}'
            css_links.append(href)
    
    # Collect inline styles
    inline_styles = []
    for style in soup.find_all('style'):
        inline_styles.append(style.string or '')
    
    # Get body content
    body = soup.find('body')
    if body:
        body_html = str(body)
        # Remove the body tags themselves
        body_html = re.sub(r'^<body[^>]*>', '', body_html)
        body_html = re.sub(r'</body>$', '', body_html)
    else:
        body_html = str(soup)
    
    # Rewrite relative URLs in body HTML to absolute
    body_html = re.sub(
        r'(src|href|data-src)="(/[^"]*)"',
        r'\1="https://www.orangeville.ca\2"',
        body_html
    )
    
    # Also get body classes
    body_classes = body.get('class', []) if body else []
    
    return body_html, css_links, inline_styles, body_classes

def create_wp_page(title, html_content, slug):
    """Create a WordPress page with custom HTML content."""
    auth = (WP_USER, WP_PASS)
    
    page_data = {
        "title": title,
        "slug": slug,
        "content": html_content,
        "status": "publish",
    }
    
    resp = requests.post(
        f"{WP_URL}/wp-json/wp/v2/pages",
        auth=auth,
        json=page_data,
        timeout=30
    )
    resp.raise_for_status()
    result = resp.json()
    return result['id'], result['link']

def main():
    print("=" * 60)
    print("CLONE MODE: Exact HTML/CSS Copy")
    print("=" * 60)
    
    # Step 1: Fetch source page
    print("\n1. Fetching source page...")
    html = fetch_page(SOURCE_URL)
    print(f"   Downloaded {len(html)} chars")
    
    # Step 2: Extract body and CSS
    print("\n2. Extracting body content and CSS...")
    body_html, css_links, inline_styles, body_classes = extract_body_and_css(html)
    print(f"   Found {len(css_links)} external stylesheets")
    print(f"   Found {len(inline_styles)} inline style blocks")
    print(f"   Body classes: {' '.join(body_classes[:5])}...")
    
    # Step 3: Fetch all external CSS
    print("\n3. Downloading external CSS...")
    external_css = fetch_css(css_links)
    print(f"   Total CSS: {len(external_css)} chars")
    
    # Step 4: Build the complete page HTML
    print("\n4. Building clone page...")
    
    all_inline_css = "\n".join(inline_styles)
    
    clone_html = f"""
<!-- CLONE MODE: Exact copy of {SOURCE_URL} -->
<style>
/* Reset WordPress theme interference */
.entry-content {{ max-width: none !important; padding: 0 !important; margin: 0 !important; }}
.wp-site-blocks {{ padding: 0 !important; max-width: none !important; }}
article {{ max-width: none !important; padding: 0 !important; }}

/* External CSS from source */
{external_css}

/* Inline CSS from source */
{all_inline_css}
</style>

<div class="cloned-page {' '.join(body_classes)}">
{body_html}
</div>

<script>
// Fix any relative links that were missed
document.querySelectorAll('.cloned-page a[href^="/"]').forEach(function(a) {{
    a.href = 'https://www.orangeville.ca' + a.getAttribute('href');
}});
document.querySelectorAll('.cloned-page img[src^="/"]').forEach(function(img) {{
    img.src = 'https://www.orangeville.ca' + img.getAttribute('src');
}});
</script>
"""
    
    # Step 5: Create WordPress page
    print("\n5. Creating WordPress page...")
    page_id, page_link = create_wp_page(
        "Orangeville - Clone Mode",
        clone_html,
        "orangeville-clone"
    )
    print(f"   Page created! ID: {page_id}")
    print(f"   URL: {page_link}")
    
    print("\n" + "=" * 60)
    print("CLONE MODE COMPLETE")
    print(f"  View at: {WP_URL}/?page_id={page_id}")
    print("=" * 60)

if __name__ == "__main__":
    main()
