"""
Asset Extractor
===============
Finds and downloads all assets referenced by the source page:
images, videos, documents (PDFs, etc.), fonts, and external stylesheets.
"""

import os
import re
import mimetypes
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

import requests
from bs4 import BeautifulSoup


class AssetExtractor:
    """Extracts and downloads all assets from a page's HTML."""

    # File extensions by category
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico", ".bmp", ".avif"}
    VIDEO_EXTENSIONS = {".mp4", ".webm", ".ogg", ".mov", ".avi"}
    DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".txt"}
    FONT_EXTENSIONS = {".woff", ".woff2", ".ttf", ".otf", ".eot"}

    def __init__(self, output_dir: str | Path, base_url: str):
        self.output_dir = Path(output_dir)
        self.base_url = base_url
        self.parsed_base = urlparse(base_url)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            )
        })

        # Create subdirectories
        for subdir in ["images", "videos", "documents", "fonts", "css", "js"]:
            (self.output_dir / subdir).mkdir(parents=True, exist_ok=True)

    def extract_and_download(self, html: str) -> dict:
        """
        Parse HTML, find all asset URLs, download them.

        Returns:
            dict with keys: images, videos, documents, fonts, stylesheets, scripts
            Each is a list of dicts with 'url', 'local_path', 'filename'.
        """
        soup = BeautifulSoup(html, "html.parser")

        assets = {
            "images": [],
            "videos": [],
            "documents": [],
            "fonts": [],
            "stylesheets": [],
            "scripts": [],
        }

        # ── Images ──
        image_urls = set()

        # <img> tags
        for img in soup.find_all("img"):
            src = img.get("src")
            if src:
                image_urls.add(src)
            # srcset for responsive images
            srcset = img.get("srcset", "")
            for entry in srcset.split(","):
                parts = entry.strip().split()
                if parts:
                    image_urls.add(parts[0])

        # <picture> <source> tags
        for source in soup.find_all("source"):
            srcset = source.get("srcset", "")
            for entry in srcset.split(","):
                parts = entry.strip().split()
                if parts:
                    image_urls.add(parts[0])

        # CSS background images (inline styles)
        bg_pattern = re.compile(r'url\(["\']?([^"\')\s]+)["\']?\)')
        for tag in soup.find_all(style=True):
            matches = bg_pattern.findall(tag["style"])
            for url in matches:
                if self._get_extension(url) in self.IMAGE_EXTENSIONS:
                    image_urls.add(url)

        # <style> block background images
        for style_tag in soup.find_all("style"):
            if style_tag.string:
                matches = bg_pattern.findall(style_tag.string)
                for url in matches:
                    if self._get_extension(url) in self.IMAGE_EXTENSIONS:
                        image_urls.add(url)

        # OG and meta images
        for meta in soup.find_all("meta"):
            content = meta.get("content", "")
            if meta.get("property") in ("og:image", "twitter:image") and content:
                image_urls.add(content)

        for url in image_urls:
            result = self._download_asset(url, "images")
            if result:
                assets["images"].append(result)

        # ── Videos ──
        video_urls = set()

        for video in soup.find_all("video"):
            src = video.get("src")
            if src:
                video_urls.add(src)
            for source in video.find_all("source"):
                src = source.get("src")
                if src:
                    video_urls.add(src)

        # Detect embedded iframes (YouTube, Vimeo)
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src", "")
            if any(host in src for host in ["youtube.com", "vimeo.com", "youtu.be"]):
                assets["videos"].append({
                    "url": src,
                    "local_path": None,
                    "filename": None,
                    "type": "embed",
                    "embed_html": str(iframe),
                })

        for url in video_urls:
            result = self._download_asset(url, "videos")
            if result:
                result["type"] = "file"
                assets["videos"].append(result)

        # ── Documents (PDFs, etc.) ──
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if self._get_extension(href) in self.DOCUMENT_EXTENSIONS:
                result = self._download_asset(href, "documents")
                if result:
                    result["link_text"] = a_tag.get_text(strip=True)
                    assets["documents"].append(result)

        # ── Fonts (from CSS @font-face in inline styles) ──
        font_pattern = re.compile(r'url\(["\']?([^"\')\s]+\.(?:woff2?|ttf|otf|eot))["\']?\)')
        for style_tag in soup.find_all("style"):
            if style_tag.string:
                matches = font_pattern.findall(style_tag.string)
                for url in matches:
                    result = self._download_asset(url, "fonts")
                    if result:
                        assets["fonts"].append(result)

        # ── External Stylesheets ──
        for link in soup.find_all("link", rel="stylesheet"):
            href = link.get("href")
            if href:
                result = self._download_asset(href, "css")
                if result:
                    assets["stylesheets"].append(result)
                    # Also extract font URLs from downloaded CSS
                    self._extract_fonts_from_css(result["local_path"], assets["fonts"])

        # ── External Scripts ──
        for script in soup.find_all("script", src=True):
            src = script["src"]
            result = self._download_asset(src, "js")
            if result:
                assets["scripts"].append(result)

        return assets

    def _download_asset(self, url: str, category: str) -> dict | None:
        """Download a single asset and return its metadata."""
        # Skip data URIs
        if url.startswith("data:"):
            return None

        # Resolve relative URLs
        absolute_url = urljoin(self.base_url, url)

        # Generate local filename
        parsed = urlparse(absolute_url)
        filename = os.path.basename(unquote(parsed.path)) or "unknown"
        # Clean filename
        filename = re.sub(r'[^\w.\-]', '_', filename)
        if not filename or filename == "unknown":
            filename = f"asset_{hash(absolute_url) % 100000}"

        local_path = self.output_dir / category / filename

        # Skip if already downloaded
        if local_path.exists():
            return {
                "url": absolute_url,
                "original_url": url,
                "local_path": str(local_path),
                "filename": filename,
            }

        try:
            response = self.session.get(absolute_url, timeout=15, stream=True)
            response.raise_for_status()

            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return {
                "url": absolute_url,
                "original_url": url,
                "local_path": str(local_path),
                "filename": filename,
            }
        except Exception as e:
            print(f"    ⚠ Failed to download {absolute_url}: {e}")
            return None

    def _extract_fonts_from_css(self, css_path: str, fonts_list: list):
        """Parse a downloaded CSS file for @font-face declarations."""
        try:
            with open(css_path, "r", encoding="utf-8", errors="ignore") as f:
                css_content = f.read()

            font_pattern = re.compile(r'url\(["\']?([^"\')\s]+\.(?:woff2?|ttf|otf|eot))["\']?\)')
            matches = font_pattern.findall(css_content)
            for url in matches:
                result = self._download_asset(url, "fonts")
                if result and result not in fonts_list:
                    fonts_list.append(result)
        except Exception:
            pass

    def _get_extension(self, url: str) -> str:
        """Extract file extension from a URL."""
        parsed = urlparse(url)
        path = parsed.path.lower()
        _, ext = os.path.splitext(path)
        return ext
