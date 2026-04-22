"""
Page Crawler
============
Fetches the source page HTML and saves it locally.
Handles JavaScript-rendered pages via optional Selenium fallback.
"""

import os
import re
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


class PageCrawler:
    """Crawls a single page and saves the raw HTML."""

    def __init__(self, output_dir: str | Path = "./output/scraped"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        })

    def crawl(self, url: str) -> dict:
        """
        Fetch a page and return its data.

        Returns:
            dict with keys:
                - html: raw HTML string
                - url: the fetched URL
                - status_code: HTTP status code
                - headers: response headers
                - soup: BeautifulSoup parsed object
        """
        print(f"  Fetching: {url}")
        response = self.session.get(url, timeout=30)
        response.raise_for_status()

        html = response.text
        soup = BeautifulSoup(html, "html.parser")

        # Check if page is mostly JS-rendered (very little text content)
        text_content = soup.get_text(strip=True)
        if len(text_content) < 100:
            print("  ⚠ Page appears to be JavaScript-rendered. Attempting Selenium fallback...")
            html = self._crawl_with_selenium(url) or html
            soup = BeautifulSoup(html, "html.parser")

        # Save raw HTML
        html_path = self.output_dir / "index.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

        # Also save any inline stylesheets and scripts
        self._save_inline_resources(soup)

        return {
            "html": html,
            "url": url,
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "soup": soup,
        }

    def _crawl_with_selenium(self, url: str) -> str | None:
        """Fallback: use Selenium for JS-rendered pages."""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.support.ui import WebDriverWait

            options = Options()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")

            driver = webdriver.Chrome(options=options)
            driver.get(url)

            # Wait for page to load
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )

            # Extra wait for dynamic content
            import time
            time.sleep(3)

            html = driver.page_source
            driver.quit()
            print("  ✓ Selenium fallback succeeded")
            return html

        except ImportError:
            print("  ⚠ Selenium not installed. Install with: pip install selenium")
            return None
        except Exception as e:
            print(f"  ⚠ Selenium fallback failed: {e}")
            return None

    def _save_inline_resources(self, soup: BeautifulSoup):
        """Extract and save inline <style> and <script> blocks."""
        styles_dir = self.output_dir / "css"
        scripts_dir = self.output_dir / "js"
        styles_dir.mkdir(exist_ok=True)
        scripts_dir.mkdir(exist_ok=True)

        # Save inline styles
        for i, style_tag in enumerate(soup.find_all("style")):
            if style_tag.string:
                with open(styles_dir / f"inline_{i}.css", "w", encoding="utf-8") as f:
                    f.write(style_tag.string)

        # Save inline scripts
        for i, script_tag in enumerate(soup.find_all("script")):
            if script_tag.string and not script_tag.get("src"):
                with open(scripts_dir / f"inline_{i}.js", "w", encoding="utf-8") as f:
                    f.write(script_tag.string)
