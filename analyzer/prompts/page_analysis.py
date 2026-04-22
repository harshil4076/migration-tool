"""
LLM Prompt Templates
====================
Structured prompts for the LLM to analyze source pages
and produce migration specifications.
"""

PAGE_ANALYSIS_SYSTEM = """You are an expert web developer and CMS migration specialist. 
Your job is to analyze HTML source code from a website and produce a detailed, structured 
JSON specification that maps every element on the page to WordPress/Elementor components.

You must respond ONLY with valid JSON — no markdown, no code fences, no explanation text.
Just the raw JSON object."""

PAGE_ANALYSIS_PROMPT = """Analyze the following HTML page and produce a structured JSON migration specification.

For each section and element on the page, identify:
1. What type of element it is (heading, paragraph, image, form, video, button, nav, etc.)
2. Its content (text, URLs, alt text, labels)
3. Its styling (colors, fonts, spacing, layout — extract from inline styles and class names)
4. Its behavior (links, animations, conditional display, interactions)
5. The recommended Elementor widget to recreate it
6. Any WordPress plugin dependencies

Also extract:
- SEO metadata (title, description, OG tags, schema markup)
- Tracking/analytics codes (GA, GTM, Facebook Pixel, etc.)
- Form configurations (fields, validation, submission actions)
- Navigation structure (menu items, hierarchy, dropdowns)
- Any redirect rules or canonical URLs
- Custom fonts and icon libraries used
- Accessibility attributes (ARIA labels, roles)

Respond with this JSON structure:
{
  "page_title": "string",
  "page_slug": "suggested-url-slug",
  "seo": {
    "meta_title": "string",
    "meta_description": "string",
    "canonical_url": "string",
    "og_title": "string",
    "og_description": "string",
    "og_image": "url or null",
    "twitter_card": "summary_large_image",
    "schema_markup": [] 
  },
  "tracking": [
    {"type": "google_analytics|google_tag_manager|facebook_pixel|other", "id": "string", "script_snippet": "string if custom"}
  ],
  "redirects": [
    {"from": "/old-path", "to": "/new-path", "type": 301}
  ],
  "navigation": {
    "items": [
      {"label": "string", "url": "string", "children": []}
    ]
  },
  "sections": [
    {
      "id": "unique-section-id",
      "type": "hero|content|features|cta|form|footer|testimonials|gallery|faq|stats|contact|custom",
      "layout": "full_width|boxed|two_column|three_column|sidebar",
      "background": {
        "type": "color|image|video|gradient",
        "value": "string (hex color, url, or gradient CSS)",
        "overlay": "rgba string or null"
      },
      "children": [
        {
          "type": "heading|paragraph|image|button|form|video|icon|list|accordion|tabs|slider|social_embed|html_block|spacer|divider|icon_list|counter|testimonial|map",
          "elementor_widget": "heading|text-editor|image|button|form|video|icon|icon-list|accordion|tabs|image-carousel|html|spacer|divider|counter|testimonial|google_maps",
          "content": {},
          "style": {},
          "attributes": {}
        }
      ]
    }
  ],
  "global_styles": {
    "primary_color": "#hex",
    "secondary_color": "#hex",
    "text_color": "#hex",
    "background_color": "#hex",
    "heading_font": "font name",
    "body_font": "font name",
    "base_font_size": "16px"
  },
  "dependencies": {
    "plugins": ["plugin-slug"],
    "fonts": ["font-name"],
    "icon_libraries": ["library-name"],
    "custom_css": "string of custom CSS needed",
    "custom_js": "string of custom JS needed"
  }
}

Here is the HTML to analyze:

---PAGE HTML START---
{html}
---PAGE HTML END---

Here is the extracted metadata for additional context:
{metadata}

Respond ONLY with the JSON object. No other text."""


CHUNK_ANALYSIS_PROMPT = """The full HTML was too large to analyze at once. 
Here is section {chunk_num} of {total_chunks}.

Analyze this HTML fragment and return the same JSON structure, but only for 
the sections/elements present in this chunk.

---HTML CHUNK START---
{html_chunk}
---HTML CHUNK END---

Respond ONLY with the JSON object. No other text."""
