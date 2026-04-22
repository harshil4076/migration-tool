"""
Media Uploader
==============
Uploads all scraped assets (images, videos, documents) to the
WordPress Media Library and maintains a mapping of old URLs to new URLs.
"""

import os
from pathlib import Path


class MediaUploader:
    """Uploads assets to WordPress Media Library."""

    def __init__(self, wp_client):
        self.wp = wp_client

    def upload_assets(self, assets: dict) -> dict:
        """
        Upload all local assets to WordPress Media Library.

        Args:
            assets: dict from AssetExtractor with images, videos, documents, fonts

        Returns:
            dict mapping original URLs to WordPress media URLs
            e.g., {"https://old-site.com/img/hero.jpg": "https://wp-site.com/wp-content/uploads/hero.jpg"}
        """
        media_map = {}

        # Upload images
        for asset in assets.get("images", []):
            result = self._upload_single(asset, "image")
            if result:
                media_map[asset["url"]] = result
                if asset.get("original_url"):
                    media_map[asset["original_url"]] = result

        # Upload documents
        for asset in assets.get("documents", []):
            result = self._upload_single(asset, "document")
            if result:
                media_map[asset["url"]] = result
                if asset.get("original_url"):
                    media_map[asset["original_url"]] = result

        # Upload self-hosted videos (skip embeds)
        for asset in assets.get("videos", []):
            if asset.get("type") == "embed":
                # Keep embed URLs as-is
                media_map[asset["url"]] = {
                    "url": asset["url"],
                    "type": "embed",
                    "embed_html": asset.get("embed_html", ""),
                }
                continue

            result = self._upload_single(asset, "video")
            if result:
                media_map[asset["url"]] = result
                if asset.get("original_url"):
                    media_map[asset["original_url"]] = result

        # Upload fonts (as regular media files)
        for asset in assets.get("fonts", []):
            result = self._upload_single(asset, "font")
            if result:
                media_map[asset["url"]] = result

        return media_map

    def _upload_single(self, asset: dict, asset_type: str) -> dict | None:
        """Upload a single asset to WordPress."""
        local_path = asset.get("local_path")
        if not local_path or not os.path.exists(local_path):
            print(f"    ⚠ Skipping {asset_type}: file not found at {local_path}")
            return None

        try:
            result = self.wp.upload_media(
                file_path=local_path,
                alt_text=asset.get("alt", ""),
                title=Path(local_path).stem,
            )

            wp_url = result.get("source_url", "")
            media_id = result.get("id")

            print(f"    ✓ Uploaded {asset_type}: {asset.get('filename', 'unknown')} → ID {media_id}")

            return {
                "url": wp_url,
                "id": media_id,
                "type": asset_type,
                "original_url": asset.get("url", ""),
            }
        except Exception as e:
            print(f"    ✗ Failed to upload {asset.get('filename', 'unknown')}: {e}")
            return None

    def rewrite_urls(self, content: str, media_map: dict) -> str:
        """
        Replace all old asset URLs in content with new WordPress URLs.

        Args:
            content: HTML string with old URLs
            media_map: mapping from old URLs to new media info

        Returns:
            content string with URLs replaced
        """
        for old_url, new_info in media_map.items():
            if isinstance(new_info, dict):
                new_url = new_info.get("url", "")
            else:
                new_url = str(new_info)

            if old_url and new_url:
                content = content.replace(old_url, new_url)

        return content
