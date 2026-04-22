"""
Link Checker
=============
Validates all links on the migrated WordPress page:
- Internal links resolve correctly
- External links are reachable
- Image sources load
- Document download links work
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed


class LinkChecker:
    """Checks all links on a migrated page for broken references."""

    def __init__(self, timeout: int = 10, max_workers: int = 5):
        self.timeout = timeout
        self.max_workers = max_workers
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "CMS-Migration-LinkChecker/1.0"
        })

    def check(self, page_url: str) -> list[dict]:
        """
        Fetch a page and check all links on it.

        Returns:
            list of dicts, each with:
                - url: the link URL
                - type: 'link' | 'image' | 'script' | 'stylesheet'
                - ok: bool
                - status_code: int or None
                - error: str or None
        """
        if not page_url:
            return []

        try:
            response = self.session.get(page_url, timeout=self.timeout)
            response.raise_for_status()
        except Exception as e:
            return [{"url": page_url, "type": "page", "ok": False, "status_code": None, "error": str(e)}]

        soup = BeautifulSoup(response.text, "html.parser")
        urls_to_check = []

        # Collect all URLs to check
        # Links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
                continue
            urls_to_check.append({
                "url": urljoin(page_url, href),
                "type": "link",
                "text": a.get_text(strip=True)[:50],
            })

        # Images
        for img in soup.find_all("img", src=True):
            urls_to_check.append({
                "url": urljoin(page_url, img["src"]),
                "type": "image",
                "text": img.get("alt", ""),
            })

        # Scripts
        for script in soup.find_all("script", src=True):
            urls_to_check.append({
                "url": urljoin(page_url, script["src"]),
                "type": "script",
                "text": "",
            })

        # Stylesheets
        for link in soup.find_all("link", rel="stylesheet"):
            if link.get("href"):
                urls_to_check.append({
                    "url": urljoin(page_url, link["href"]),
                    "type": "stylesheet",
                    "text": "",
                })

        # Check all URLs concurrently
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_url = {
                executor.submit(self._check_url, item["url"]): item
                for item in urls_to_check
            }
            for future in as_completed(future_to_url):
                item = future_to_url[future]
                status_code, error = future.result()
                results.append({
                    "url": item["url"],
                    "type": item["type"],
                    "text": item.get("text", ""),
                    "ok": error is None and status_code and status_code < 400,
                    "status_code": status_code,
                    "error": error,
                })

        return results

    def _check_url(self, url: str) -> tuple:
        """
        Check if a URL is reachable.

        Returns:
            (status_code, error_string) — error is None if OK
        """
        try:
            response = self.session.head(url, timeout=self.timeout, allow_redirects=True)
            if response.status_code == 405:
                # HEAD not allowed, try GET
                response = self.session.get(url, timeout=self.timeout, stream=True)
                response.close()
            return (response.status_code, None)
        except requests.Timeout:
            return (None, "Timeout")
        except requests.ConnectionError:
            return (None, "Connection failed")
        except Exception as e:
            return (None, str(e))
