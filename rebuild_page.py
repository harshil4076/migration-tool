#!/usr/bin/env python3
"""
Rebuild Mode: Uses LLM to analyze the source page and generate a faithful
WordPress-native HTML/CSS recreation that matches the original design.
"""
import requests
import re
import json
import os
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv('/home/harshil/migration-tool/migration-tool/.env')

SOURCE_URL = "https://www.orangeville.ca"
WP_URL = os.getenv("WP_URL", "http://localhost:8881")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-20250514")

def fetch_page(url):
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text

def call_anthropic(system, prompt, max_tokens=16000):
    import anthropic
    client = anthropic.Anthropic(api_key=LLM_API_KEY)
    message = client.messages.create(
        model=LLM_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text

def extract_design_info(html):
    """Extract key design elements from the source."""
    soup = BeautifulSoup(html, 'html.parser')
    
    # Extract color scheme from CSS
    colors = set()
    for style in soup.find_all('style'):
        if style.string:
            colors.update(re.findall(r'#[0-9a-fA-F]{3,8}', style.string))
    
    # Extract image URLs
    images = {}
    for img in soup.find_all('img'):
        src = img.get('src', '') or img.get('data-src', '')
        alt = img.get('alt', '')
        if src:
            if src.startswith('/'):
                src = f'https://www.orangeville.ca{src}'
            images[alt or src.split('/')[-1]] = src
    
    # Extract background images from inline styles
    bg_images = re.findall(r'background(?:-image)?:\s*url\(["\']?([^"\')\s]+)["\']?\)', html)
    for bg in bg_images:
        if bg.startswith('/'):
            bg = f'https://www.orangeville.ca{bg}'
        images[f'bg_{len(images)}'] = bg
    
    # Extract nav structure
    nav = soup.find('nav', attrs={'aria-label': 'Site Navigation'})
    nav_items = []
    if nav:
        for li in nav.find_all('li', recursive=False) or nav.find_all('a'):
            a = li.find('a') if li.name == 'li' else li
            if a:
                href = a.get('href', '')
                if href.startswith('/'):
                    href = f'https://www.orangeville.ca{href}'
                nav_items.append({'label': a.get_text(strip=True), 'url': href})
    
    # Extract quick links
    quick_links_nav = soup.find('nav', attrs={'aria-label': 'Quick links'})
    quick_links = []
    if quick_links_nav:
        for a in quick_links_nav.find_all('a'):
            href = a.get('href', '')
            if href.startswith('/'):
                href = f'https://www.orangeville.ca{href}'
            quick_links.append({'label': a.get_text(strip=True), 'url': href})
    
    # Extract feature boxes
    feature_section = soup.find('section', attrs={'aria-label': re.compile('Feature', re.I)})
    features = []
    if feature_section:
        for a in feature_section.find_all('a'):
            href = a.get('href', '')
            if href.startswith('/'):
                href = f'https://www.orangeville.ca{href}'
            img = a.find('img')
            img_src = ''
            if img:
                img_src = img.get('src', '') or img.get('data-src', '')
                if img_src.startswith('/'):
                    img_src = f'https://www.orangeville.ca{img_src}'
            p = a.find('p') or a.find('span')
            label = p.get_text(strip=True) if p else a.get_text(strip=True)
            if label and label not in [f['label'] for f in features]:
                features.append({'label': label, 'url': href, 'image': img_src})
    
    # Extract footer info
    footer = soup.find('footer') or soup.find('div', role='contentinfo')
    footer_text = footer.get_text('\n', strip=True) if footer else ''
    
    return {
        'nav_items': nav_items,
        'quick_links': quick_links,
        'features': features,
        'images': images,
        'footer_text': footer_text[:500],
    }

def main():
    print("=" * 60)
    print("REBUILD MODE: LLM-Powered Design Recreation")
    print("=" * 60)
    
    # Step 1: Fetch source
    print("\n1. Fetching source page...")
    html = fetch_page(SOURCE_URL)
    print(f"   Downloaded {len(html)} chars")
    
    # Step 2: Extract design info
    print("\n2. Extracting design information...")
    design = extract_design_info(html)
    print(f"   Nav items: {len(design['nav_items'])}")
    print(f"   Quick links: {len(design['quick_links'])}")
    print(f"   Features: {len(design['features'])}")
    print(f"   Images: {len(design['images'])}")
    
    # Step 3: Send to LLM for recreation
    print("\n3. Generating WordPress-native rebuild with LLM...")
    
    system_prompt = """You are an expert web developer specializing in converting website designs to clean HTML/CSS.
You will receive the HTML of a municipal website and extracted design data. 
Your task is to create a COMPLETE, standalone HTML page that faithfully recreates the visual design.

Rules:
- Use modern CSS (flexbox, grid) for layout
- Include ALL sections from the original
- Use the actual image URLs from the source (absolute URLs)
- Match colors, fonts, spacing as closely as possible
- Make it responsive
- Include the complete CSS inline in a <style> tag
- Output ONLY the complete HTML - no markdown, no explanation
- The page should look professional and match the original design closely
- Use Google Fonts if needed (the original uses 'Open Sans')
- All links should point to the original orangeville.ca URLs"""

    # Truncate HTML to fit in context
    truncated_html = html[:80000]
    
    prompt = f"""Recreate this municipal website as a standalone HTML page with inline CSS.
Match the visual design as closely as possible.

DESIGN DATA:
{json.dumps(design, indent=2)}

SOURCE HTML (truncated):
{truncated_html}

Create a complete HTML page that looks like the original. Include:
1. Header with logo and navigation (Living Here, Things to Do, Doing Business, Town Hall)
2. Hero banner with "Dynamic future. Historic charm." tagline, search bar, and "I Want To" button
3. Quick links bar (6 icons: Agendas, Recreation, Garbage, Transit, Report a Problem, Library)
4. Alert banner section
5. "In the News" section with placeholder cards
6. "Calendar of Events" section with sample events
7. Feature cards (Visit, Job Opportunities, Drop In Programs, Riding with Us)
8. "Stay Connected" newsletter signup banner
9. Complete footer with address, links, social media

Use these actual image URLs from the source:
- Logo: https://www.orangeville.ca/en/resourcesGeneral/images/logo.svg
- Footer logo: https://www.orangeville.ca/en/resourcesGeneral/images/logo_footer.svg  
- Hero banner: use a dark background with the town hall image
- Feature images: {json.dumps({k:v for k,v in design['images'].items() if 'feature' in k.lower() or 'Feature' in k.lower() or 'job' in k.lower()}, indent=2)}

Color scheme from the original:
- Primary orange/gold: #E8912D
- Dark navy: #1B2A4A  
- Dark background: #2C2C2C
- Text: #333333
- White: #FFFFFF
- Green accent: #4CAF50

Output the complete HTML file."""

    result = call_anthropic(system_prompt, prompt, max_tokens=16000)
    
    # Extract HTML from response (strip any markdown fences)
    result = result.strip()
    result = re.sub(r'^```(?:html)?\s*', '', result)
    result = re.sub(r'\s*```$', '', result)
    
    print(f"   Generated {len(result)} chars of HTML")
    
    # Step 4: Save and deploy
    print("\n4. Deploying to WordPress...")
    
    tmp_file = '/tmp/orangeville_rebuild.html'
    with open(tmp_file, 'w', encoding='utf-8') as f:
        f.write(result)
    
    os.system(f"docker cp {tmp_file} migration-tool-wordpress-1:/var/www/html/orangeville-rebuild.html")
    os.system("docker exec migration-tool-wordpress-1 chown www-data:www-data /var/www/html/orangeville-rebuild.html")
    
    print(f"\n{'=' * 60}")
    print("REBUILD MODE COMPLETE")
    print(f"  View at: {WP_URL}/orangeville-rebuild.html")
    print(f"{'=' * 60}")

if __name__ == "__main__":
    main()
