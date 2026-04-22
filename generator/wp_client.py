"""
WordPress Client
================
Handles all communication with the WordPress REST API.
Supports authentication via Application Passwords.
"""

import mimetypes
from pathlib import Path
from urllib.parse import urljoin

import requests


class WordPressClient:
    """REST API client for WordPress."""

    def __init__(self, url: str, username: str, password: str):
        """
        Initialize the WordPress client.

        Args:
            url: WordPress site URL (e.g., http://localhost:8881)
            username: WordPress admin username
            password: Application Password (not the login password)
        """
        self.base_url = url.rstrip("/")
        self.api_url = f"{self.base_url}/wp-json/wp/v2"
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.headers.update({
            "User-Agent": "CMS-Migration-Tool/1.0",
        })

    def test_connection(self) -> bool:
        """Test if we can connect to the WordPress API."""
        try:
            response = self.session.get(f"{self.api_url}/users/me")
            return response.status_code == 200
        except Exception:
            return False

    # ── Pages ──

    def create_page(self, title: str, content: str = "", slug: str = "",
                    status: str = "draft", meta: dict = None) -> dict:
        """Create a new WordPress page."""
        data = {
            "title": title,
            "content": content,
            "status": status,
            "type": "page",
        }
        if slug:
            data["slug"] = slug
        if meta:
            data["meta"] = meta

        response = self.session.post(f"{self.api_url}/pages", json=data)
        response.raise_for_status()
        return response.json()

    def update_page(self, page_id: int, data: dict) -> dict:
        """Update an existing page."""
        response = self.session.post(f"{self.api_url}/pages/{page_id}", json=data)
        response.raise_for_status()
        return response.json()

    def get_page(self, page_id: int) -> dict:
        """Get a page by ID."""
        response = self.session.get(f"{self.api_url}/pages/{page_id}")
        response.raise_for_status()
        return response.json()

    # ── Media ──

    def upload_media(self, file_path: str, alt_text: str = "",
                     caption: str = "", title: str = "") -> dict:
        """Upload a file to the WordPress Media Library."""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        mime_type, _ = mimetypes.guess_type(str(file_path))
        mime_type = mime_type or "application/octet-stream"

        headers = {
            "Content-Disposition": f'attachment; filename="{file_path.name}"',
            "Content-Type": mime_type,
        }

        with open(file_path, "rb") as f:
            response = self.session.post(
                f"{self.api_url}/media",
                headers=headers,
                data=f,
            )

        response.raise_for_status()
        media = response.json()

        # Update alt text, caption, title if provided
        update_data = {}
        if alt_text:
            update_data["alt_text"] = alt_text
        if caption:
            update_data["caption"] = caption
        if title:
            update_data["title"] = title

        if update_data:
            self.session.post(f"{self.api_url}/media/{media['id']}", json=update_data)

        return media

    def get_media(self, media_id: int) -> dict:
        """Get media item by ID."""
        response = self.session.get(f"{self.api_url}/media/{media_id}")
        response.raise_for_status()
        return response.json()

    # ── Post Meta (for Elementor data) ──

    def update_post_meta(self, post_id: int, meta_key: str, meta_value) -> dict:
        """
        Update post meta via the WordPress REST API.
        For Elementor data, we use the custom endpoint.
        """
        data = {"meta": {meta_key: meta_value}}
        response = self.session.post(f"{self.api_url}/pages/{post_id}", json=data)
        response.raise_for_status()
        return response.json()

    # ── Navigation Menus ──

    def create_menu(self, name: str, locations: list = None) -> dict:
        """Create a navigation menu (requires WP REST API Menus plugin or WP 5.9+)."""
        data = {"name": name}
        if locations:
            data["locations"] = locations

        # Try the built-in navigation endpoint (WP 5.9+)
        response = self.session.post(
            f"{self.base_url}/wp-json/wp/v2/navigation",
            json={"title": name, "status": "publish", "content": ""},
        )

        if response.status_code in (200, 201):
            return response.json()

        # Fallback: menu creation may need to be done via
        # wp-cli or a custom plugin endpoint
        print(f"    ⚠ Could not create menu via REST API. Create '{name}' manually in WordPress.")
        return {"name": name, "id": None, "error": "Manual creation needed"}

    # ── Options / Settings ──

    def get_option(self, option_name: str) -> str | None:
        """Get a WordPress option value (requires custom endpoint or wp-cli)."""
        response = self.session.get(f"{self.base_url}/wp-json/wp/v2/settings")
        if response.status_code == 200:
            settings = response.json()
            return settings.get(option_name)
        return None

    # ── Plugin-specific endpoints ──

    def yoast_update(self, post_id: int, seo_data: dict) -> bool:
        """
        Update Yoast SEO metadata for a post.
        Yoast exposes its data via the standard post meta.
        """
        meta = {}
        if seo_data.get("meta_title"):
            meta["_yoast_wpseo_title"] = seo_data["meta_title"]
        if seo_data.get("meta_description"):
            meta["_yoast_wpseo_metadesc"] = seo_data["meta_description"]
        if seo_data.get("canonical_url"):
            meta["_yoast_wpseo_canonical"] = seo_data["canonical_url"]
        if seo_data.get("og_title"):
            meta["_yoast_wpseo_opengraph-title"] = seo_data["og_title"]
        if seo_data.get("og_description"):
            meta["_yoast_wpseo_opengraph-description"] = seo_data["og_description"]
        if seo_data.get("og_image"):
            meta["_yoast_wpseo_opengraph-image"] = seo_data["og_image"]

        if meta:
            try:
                self.update_post_meta(post_id, "_yoast_wpseo_title", meta.get("_yoast_wpseo_title", ""))
                # Update all meta through the page endpoint
                self.update_page(post_id, {"meta": meta})
                return True
            except Exception as e:
                print(f"    ⚠ Yoast update failed: {e}")
                return False
        return True

    # ── Utility ──

    def get_site_info(self) -> dict:
        """Get basic site information."""
        response = self.session.get(f"{self.base_url}/wp-json")
        response.raise_for_status()
        return response.json()
