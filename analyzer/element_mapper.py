"""
Element Mapper
==============
Takes the structured JSON from the LLM analyzer and maps it
to Elementor's internal data format (_elementor_data).

Elementor stores page data as a nested JSON structure of
sections → columns → widgets. This module builds that structure.
"""

import random


class ElementMapper:
    """Maps LLM page spec to Elementor's internal data structure."""

    # Mapping from our element types to Elementor widget types
    WIDGET_MAP = {
        "heading": "heading",
        "paragraph": "text-editor",
        "text": "text-editor",
        "image": "image",
        "button": "button",
        "video": "video",
        "form": "form",
        "accordion": "accordion",
        "tabs": "tabs",
        "slider": "image-carousel",
        "icon": "icon",
        "icon_list": "icon-list",
        "list": "icon-list",
        "social_embed": "html",
        "html_block": "html",
        "spacer": "spacer",
        "divider": "divider",
        "counter": "counter",
        "testimonial": "testimonial",
        "map": "google_maps",
        "nav": "nav-menu",
    }

    def map(self, page_spec: dict) -> dict:
        """
        Convert the LLM page spec into Elementor's _elementor_data format.

        Returns:
            dict with:
                - elements: list of Elementor section elements
                - settings: global page settings
                - custom_css: any additional CSS
        """
        elementor_data = {
            "elements": [],
            "settings": self._build_page_settings(page_spec),
            "custom_css": page_spec.get("dependencies", {}).get("custom_css", ""),
        }

        for section in page_spec.get("sections", []):
            elementor_section = self._build_section(section)
            elementor_data["elements"].append(elementor_section)

        return elementor_data

    def _build_page_settings(self, page_spec: dict) -> dict:
        """Build Elementor page-level settings."""
        global_styles = page_spec.get("global_styles", {})

        return {
            "template": "elementor_header_footer",  # Full-width Elementor template
            "post_title": page_spec.get("page_title", "Migrated Page"),
            "post_status": "draft",  # Create as draft for review
        }

    def _build_section(self, section: dict) -> dict:
        """Build an Elementor section element."""
        section_settings = {
            "layout": "full_width" if section.get("layout") == "full_width" else "boxed",
            "content_width": {"unit": "px", "size": 1140},
        }

        # Background
        bg = section.get("background", {})
        if bg.get("type") == "color":
            section_settings["background_background"] = "classic"
            section_settings["background_color"] = bg.get("value", "")
        elif bg.get("type") == "image":
            section_settings["background_background"] = "classic"
            section_settings["background_image"] = {"url": bg.get("value", "")}
        elif bg.get("type") == "video":
            section_settings["background_background"] = "video"
            section_settings["background_video_link"] = bg.get("value", "")
        elif bg.get("type") == "gradient":
            section_settings["background_background"] = "gradient"
            section_settings["background_color"] = bg.get("value", "")

        # Overlay
        if bg.get("overlay"):
            section_settings["background_overlay_background"] = "classic"
            section_settings["background_overlay_color"] = bg["overlay"]

        # Build columns based on layout
        columns = self._build_columns(section)

        return {
            "id": self._generate_id(),
            "elType": "section",
            "settings": section_settings,
            "elements": columns,
        }

    def _build_columns(self, section: dict) -> list:
        """Build column elements within a section."""
        layout = section.get("layout", "full_width")
        children = section.get("children", [])

        if layout == "two_column":
            mid = len(children) // 2
            return [
                self._build_column(children[:mid], width=50),
                self._build_column(children[mid:], width=50),
            ]
        elif layout == "three_column":
            third = len(children) // 3
            return [
                self._build_column(children[:third], width=33),
                self._build_column(children[third:2*third], width=33),
                self._build_column(children[2*third:], width=34),
            ]
        else:
            # Single column (full width or boxed)
            return [self._build_column(children, width=100)]

    def _build_column(self, children: list, width: int = 100) -> dict:
        """Build a column element with its child widgets."""
        widgets = []
        for child in children:
            widget = self._build_widget(child)
            if widget:
                widgets.append(widget)

        return {
            "id": self._generate_id(),
            "elType": "column",
            "settings": {"_column_size": width},
            "elements": widgets,
        }

    def _build_widget(self, element: dict) -> dict | None:
        """Build an Elementor widget from a page element."""
        elem_type = element.get("type", "")
        widget_type = element.get("elementor_widget") or self.WIDGET_MAP.get(elem_type, "text-editor")
        content = element.get("content", {})
        style = element.get("style", {})

        settings = {}

        # ── Heading ──
        if widget_type == "heading":
            settings["title"] = content.get("text", "")
            settings["header_size"] = content.get("tag", "h2")
            if style.get("color"):
                settings["title_color"] = style["color"]
            if style.get("font_size"):
                settings["typography_font_size"] = {"unit": "px", "size": int(style["font_size"].replace("px", ""))}
            settings["align"] = style.get("align", "left")

        # ── Text Editor (paragraph) ──
        elif widget_type == "text-editor":
            settings["editor"] = content.get("html", content.get("text", ""))
            if style.get("color"):
                settings["text_color"] = style["color"]

        # ── Image ──
        elif widget_type == "image":
            settings["image"] = {
                "url": content.get("src", content.get("url", "")),
                "alt": content.get("alt", ""),
            }
            if content.get("link"):
                settings["link"] = {"url": content["link"]}
            settings["align"] = style.get("align", "center")
            if style.get("width"):
                settings["image_size"] = "custom"
                settings["image_custom_dimension"] = {
                    "width": int(style["width"].replace("px", "")) if "px" in str(style["width"]) else style["width"]
                }

        # ── Button ──
        elif widget_type == "button":
            settings["text"] = content.get("text", "Click Here")
            settings["link"] = {"url": content.get("link", content.get("url", "#"))}
            if style.get("bg_color"):
                settings["button_background_color"] = style["bg_color"]
            if style.get("color"):
                settings["button_text_color"] = style["color"]
            settings["align"] = style.get("align", "center")
            if style.get("size"):
                settings["size"] = style["size"]  # sm, md, lg, xl

        # ── Video ──
        elif widget_type == "video":
            video_type = content.get("type", "youtube")
            if "youtube" in str(content.get("src", "")):
                settings["video_type"] = "youtube"
                settings["youtube_url"] = content.get("src", "")
            elif "vimeo" in str(content.get("src", "")):
                settings["video_type"] = "vimeo"
                settings["vimeo_url"] = content.get("src", "")
            else:
                settings["video_type"] = "hosted"
                settings["hosted_url"] = {"url": content.get("src", "")}

            if content.get("autoplay"):
                settings["autoplay"] = "yes"
            if content.get("mute"):
                settings["mute"] = "yes"
            if content.get("loop"):
                settings["loop"] = "yes"

        # ── Form ──
        elif widget_type == "form":
            settings["form_name"] = content.get("name", "Contact Form")
            settings["form_fields"] = []
            for field in content.get("fields", []):
                settings["form_fields"].append({
                    "_id": self._generate_id(),
                    "field_type": self._map_form_field_type(field.get("type", "text")),
                    "field_label": field.get("label", ""),
                    "required": "yes" if field.get("required") else "",
                    "placeholder": field.get("placeholder", ""),
                })
            settings["submit_text"] = content.get("submit_text", "Submit")
            settings["email_to"] = content.get("submit_target", "")

        # ── Accordion ──
        elif widget_type == "accordion":
            settings["tabs"] = []
            for item in content.get("items", []):
                settings["tabs"].append({
                    "_id": self._generate_id(),
                    "tab_title": item.get("title", ""),
                    "tab_content": item.get("content", ""),
                })

        # ── Tabs ──
        elif widget_type == "tabs":
            settings["tabs"] = []
            for item in content.get("items", []):
                settings["tabs"].append({
                    "_id": self._generate_id(),
                    "tab_title": item.get("title", ""),
                    "tab_content": item.get("content", ""),
                })

        # ── Image Carousel ──
        elif widget_type == "image-carousel":
            settings["carousel"] = []
            for slide in content.get("slides", []):
                settings["carousel"].append({
                    "_id": self._generate_id(),
                    "image": {"url": slide.get("src", "")},
                    "caption": slide.get("caption", ""),
                })
            settings["slides_to_show"] = str(content.get("slides_to_show", 1))
            settings["autoplay"] = "yes" if content.get("autoplay") else "no"

        # ── HTML Block ──
        elif widget_type == "html":
            settings["html"] = content.get("html", content.get("embed_code", ""))

        # ── Counter ──
        elif widget_type == "counter":
            settings["starting_number"] = content.get("start", 0)
            settings["ending_number"] = content.get("end", 100)
            settings["prefix"] = content.get("prefix", "")
            settings["suffix"] = content.get("suffix", "")
            settings["title"] = content.get("label", "")

        # ── Google Maps ──
        elif widget_type == "google_maps":
            settings["address"] = content.get("address", "")
            settings["zoom"] = {"unit": "px", "size": content.get("zoom", 14)}

        # ── Spacer ──
        elif widget_type == "spacer":
            settings["space"] = {
                "unit": "px",
                "size": style.get("height", 50),
            }

        # ── Divider ──
        elif widget_type == "divider":
            settings["style"] = style.get("border_style", "solid")
            settings["color"] = style.get("color", "#e0e0e0")

        else:
            # Fallback: render as HTML block
            settings["html"] = content.get("html", str(content))

        return {
            "id": self._generate_id(),
            "elType": "widget",
            "widgetType": widget_type,
            "settings": settings,
            "elements": [],
        }

    def _map_form_field_type(self, field_type: str) -> str:
        """Map HTML form field types to Elementor form field types."""
        mapping = {
            "text": "text",
            "email": "email",
            "tel": "tel",
            "phone": "tel",
            "textarea": "textarea",
            "select": "select",
            "dropdown": "select",
            "checkbox": "checkbox",
            "radio": "radio",
            "file": "upload",
            "date": "date",
            "time": "time",
            "number": "number",
            "url": "url",
            "hidden": "hidden",
            "password": "password",
        }
        return mapping.get(field_type.lower(), "text")

    @staticmethod
    def _generate_id() -> str:
        """Generate a random Elementor-style element ID (7 hex chars)."""
        return ''.join(random.choices('0123456789abcdef', k=7))
