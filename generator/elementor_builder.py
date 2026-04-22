"""
Elementor Builder
=================
Creates WordPress pages and populates them with Elementor's
internal data structure (_elementor_data post meta).

Elementor stores its page layout as serialized JSON in post meta,
which we construct from the ElementMapper output.
"""

import json


class ElementorBuilder:
    """Creates WordPress pages with Elementor layout data."""

    def __init__(self, wp_client, media_map: dict = None):
        self.wp = wp_client
        self.media_map = media_map or {}

    def create_page(self, page_spec: dict, elementor_spec: dict) -> dict:
        """
        Create a WordPress page and set its Elementor data.

        Args:
            page_spec: the LLM-generated page specification
            elementor_spec: the Elementor-mapped specification from ElementMapper

        Returns:
            dict with page creation result (id, link, etc.)
        """
        # Step 1: Rewrite asset URLs in the Elementor data
        elements = elementor_spec.get("elements", [])
        elements = self._rewrite_asset_urls(elements)

        # Step 2: Create the WordPress page
        page_title = page_spec.get("page_title", "Migrated Page")
        page_slug = page_spec.get("page_slug", "")

        # Build a basic HTML fallback content (for non-Elementor viewing)
        fallback_content = self._build_fallback_content(page_spec)

        page = self.wp.create_page(
            title=page_title,
            content=fallback_content,
            slug=page_slug,
            status="draft",
        )

        page_id = page.get("id")
        if not page_id:
            raise RuntimeError(f"Failed to create page. Response: {page}")

        print(f"    Page created with ID: {page_id}")

        # Step 3: Set Elementor data via post meta
        self._set_elementor_data(page_id, elements, elementor_spec.get("settings", {}))

        # Step 4: Set custom CSS if any
        custom_css = elementor_spec.get("custom_css", "")
        if custom_css:
            self._set_custom_css(page_id, custom_css)

        # Step 5: Set the page template to Elementor's full-width template
        self._set_page_template(page_id)

        return page

    def _set_elementor_data(self, page_id: int, elements: list, settings: dict):
        """
        Set the _elementor_data post meta which defines the page layout.

        Elementor stores layout as a JSON array in _elementor_data.
        It also needs _elementor_edit_mode and _elementor_template_type.
        """
        elementor_data = json.dumps(elements)

        # We need to update these meta fields for Elementor to recognize the page
        meta_updates = {
            "_elementor_data": elementor_data,
            "_elementor_edit_mode": "builder",
            "_elementor_template_type": "wp-page",
            "_elementor_version": "3.18.0",  # Minimum compatible version
        }

        try:
            # Update via the pages endpoint with meta
            self.wp.update_page(page_id, {"meta": meta_updates})
            print("    ✓ Elementor data set via REST API")
        except Exception as e:
            # If REST API doesn't allow meta updates, save to file for manual import
            print(f"    ⚠ Could not set Elementor meta via API: {e}")
            print("    Saving Elementor data to file for manual import...")
            self._save_elementor_data_file(page_id, meta_updates)

    def _save_elementor_data_file(self, page_id: int, meta: dict):
        """Save Elementor data to a JSON file for manual import via wp-cli or DB."""
        import os
        output_path = os.path.join("output", f"elementor_data_page_{page_id}.json")
        with open(output_path, "w") as f:
            json.dump({
                "page_id": page_id,
                "meta": meta,
                "wp_cli_commands": [
                    f"wp post meta update {page_id} _elementor_data '{meta['_elementor_data']}'",
                    f"wp post meta update {page_id} _elementor_edit_mode builder",
                    f"wp post meta update {page_id} _elementor_template_type wp-page",
                ],
            }, f, indent=2)
        print(f"    Saved to: {output_path}")
        print("    Run the wp-cli commands to import manually.")

    def _set_custom_css(self, page_id: int, css: str):
        """Set custom CSS for the page."""
        try:
            self.wp.update_page(page_id, {
                "meta": {"_elementor_css": css}
            })
        except Exception:
            print(f"    ⚠ Could not set custom CSS via API. Add manually in Elementor.")

    def _set_page_template(self, page_id: int):
        """Set the page template to Elementor's full-width canvas."""
        try:
            self.wp.update_page(page_id, {
                "template": "elementor_header_footer",
            })
        except Exception:
            print("    ⚠ Could not set page template. Set to 'Elementor Full Width' manually.")

    def _rewrite_asset_urls(self, elements: list) -> list:
        """Recursively rewrite old asset URLs in Elementor element data."""
        if not self.media_map:
            return elements

        elements_json = json.dumps(elements)

        for old_url, new_info in self.media_map.items():
            if isinstance(new_info, dict):
                new_url = new_info.get("url", "")
            else:
                new_url = str(new_info)

            if old_url and new_url:
                elements_json = elements_json.replace(old_url, new_url)

        return json.loads(elements_json)

    def _build_fallback_content(self, page_spec: dict) -> str:
        """
        Build basic HTML content as a fallback for when the page
        is viewed without Elementor active.
        """
        parts = []

        for section in page_spec.get("sections", []):
            for child in section.get("children", []):
                content = child.get("content", {})
                elem_type = child.get("type", "")

                if elem_type == "heading":
                    tag = content.get("tag", "h2")
                    text = content.get("text", "")
                    parts.append(f"<{tag}>{text}</{tag}>")

                elif elem_type in ("paragraph", "text"):
                    html = content.get("html", content.get("text", ""))
                    parts.append(f"<p>{html}</p>")

                elif elem_type == "image":
                    src = content.get("src", content.get("url", ""))
                    alt = content.get("alt", "")
                    parts.append(f'<img src="{src}" alt="{alt}" />')

                elif elem_type == "button":
                    text = content.get("text", "")
                    link = content.get("link", content.get("url", "#"))
                    parts.append(f'<a href="{link}" class="button">{text}</a>')

        return "\n".join(parts) if parts else "<p>This page was migrated. Edit with Elementor.</p>"
