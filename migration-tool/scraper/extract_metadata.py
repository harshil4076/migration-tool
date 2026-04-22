"""
Metadata Extractor
==================
Extracts SEO metadata, Open Graph tags, tracking codes,
structured data, and other page-level information.
"""

import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup


class MetadataExtractor:
    """Extracts all page-level metadata from HTML."""

    # Known analytics/tracking patterns
    TRACKING_PATTERNS = {
        "google_analytics": [
            re.compile(r'UA-\d{4,10}-\d{1,4}'),
            re.compile(r'G-[A-Z0-9]{10,}'),
            re.compile(r'gtag\s*\(\s*["\']config["\']\s*,\s*["\']([^"\']+)["\']'),
        ],
        "google_tag_manager": [
            re.compile(r'GTM-[A-Z0-9]{4,8}'),
        ],
        "facebook_pixel": [
            re.compile(r'fbq\s*\(\s*["\']init["\']\s*,\s*["\'](\d+)["\']'),
        ],
        "linkedin_insight": [
            re.compile(r'_linkedin_partner_id\s*=\s*["\'](\d+)["\']'),
        ],
        "hotjar": [
            re.compile(r'hjid\s*:\s*(\d+)'),
            re.compile(r'h\._hjSettings\s*=\s*\{hjid\s*:\s*(\d+)'),
        ],
    }

    def extract(self, html: str, source_url: str) -> dict:
        """
        Extract all metadata from HTML.

        Returns:
            dict with: title, seo, open_graph, twitter_card, tracking,
                       structured_data, canonical, favicon, language, redirects
        """
        soup = BeautifulSoup(html, "html.parser")

        metadata = {
            "title": self._extract_title(soup),
            "seo": self._extract_seo(soup),
            "open_graph": self._extract_open_graph(soup),
            "twitter_card": self._extract_twitter_card(soup),
            "tracking": self._extract_tracking(html),
            "structured_data": self._extract_structured_data(soup),
            "canonical": self._extract_canonical(soup),
            "favicon": self._extract_favicon(soup, source_url),
            "language": self._extract_language(soup),
            "custom_fonts": self._extract_font_references(soup, html),
            "external_scripts": self._extract_external_scripts(soup),
        }

        return metadata

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract page title."""
        title_tag = soup.find("title")
        return title_tag.get_text(strip=True) if title_tag else ""

    def _extract_seo(self, soup: BeautifulSoup) -> dict:
        """Extract SEO-relevant meta tags."""
        seo = {}

        meta_mappings = {
            "description": "meta_description",
            "keywords": "meta_keywords",
            "robots": "robots",
            "author": "author",
            "viewport": "viewport",
        }

        for name, key in meta_mappings.items():
            tag = soup.find("meta", attrs={"name": name})
            if tag and tag.get("content"):
                seo[key] = tag["content"]

        return seo

    def _extract_open_graph(self, soup: BeautifulSoup) -> dict:
        """Extract Open Graph meta tags."""
        og = {}
        for tag in soup.find_all("meta", attrs={"property": re.compile(r"^og:")}):
            prop = tag.get("property", "").replace("og:", "")
            content = tag.get("content", "")
            if prop and content:
                og[prop] = content
        return og

    def _extract_twitter_card(self, soup: BeautifulSoup) -> dict:
        """Extract Twitter Card meta tags."""
        twitter = {}
        for tag in soup.find_all("meta", attrs={"name": re.compile(r"^twitter:")}):
            name = tag.get("name", "").replace("twitter:", "")
            content = tag.get("content", "")
            if name and content:
                twitter[name] = content
        return twitter

    def _extract_tracking(self, html: str) -> list:
        """Detect analytics and tracking codes in the HTML."""
        found = []

        for tracker_type, patterns in self.TRACKING_PATTERNS.items():
            for pattern in patterns:
                matches = pattern.findall(html)
                for match in matches:
                    entry = {"type": tracker_type, "id": match}
                    if entry not in found:
                        found.append(entry)

        return found

    def _extract_structured_data(self, soup: BeautifulSoup) -> list:
        """Extract JSON-LD structured data."""
        structured = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                structured.append(data)
            except (json.JSONDecodeError, TypeError):
                pass
        return structured

    def _extract_canonical(self, soup: BeautifulSoup) -> str:
        """Extract canonical URL."""
        link = soup.find("link", rel="canonical")
        return link["href"] if link and link.get("href") else ""

    def _extract_favicon(self, soup: BeautifulSoup, base_url: str) -> str:
        """Extract favicon URL."""
        for rel in ["icon", "shortcut icon"]:
            link = soup.find("link", rel=rel)
            if link and link.get("href"):
                return urljoin(base_url, link["href"])
        return ""

    def _extract_language(self, soup: BeautifulSoup) -> str:
        """Extract page language."""
        html_tag = soup.find("html")
        if html_tag:
            return html_tag.get("lang", "")
        return ""

    def _extract_font_references(self, soup: BeautifulSoup, html: str) -> list:
        """Detect custom font references (Google Fonts, Adobe Fonts, etc.)."""
        fonts = []

        # Google Fonts
        for link in soup.find_all("link"):
            href = link.get("href", "")
            if "fonts.googleapis.com" in href:
                fonts.append({"type": "google_fonts", "url": href})
            elif "use.typekit.net" in href:
                fonts.append({"type": "adobe_fonts", "url": href})

        # @font-face in inline styles
        font_face_pattern = re.compile(
            r"font-family\s*:\s*['\"]?([^;'\"]+)['\"]?",
            re.IGNORECASE,
        )
        for style in soup.find_all("style"):
            if style.string and "@font-face" in style.string:
                families = font_face_pattern.findall(style.string)
                for family in families:
                    fonts.append({"type": "custom", "family": family.strip()})

        return fonts

    def _extract_external_scripts(self, soup: BeautifulSoup) -> list:
        """Catalog all external script sources."""
        scripts = []
        for script in soup.find_all("script", src=True):
            src = script["src"]
            script_info = {"url": src}

            # Classify known scripts
            if "google" in src:
                script_info["category"] = "analytics"
            elif "facebook" in src or "fbevents" in src:
                script_info["category"] = "tracking"
            elif "jquery" in src.lower():
                script_info["category"] = "library"
            elif "bootstrap" in src.lower():
                script_info["category"] = "framework"
            else:
                script_info["category"] = "other"

            scripts.append(script_info)

        return scripts
