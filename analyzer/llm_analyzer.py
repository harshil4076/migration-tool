"""
LLM Analyzer
=============
Sends scraped HTML to an LLM (Anthropic Claude or OpenAI GPT-4)
and receives a structured JSON specification for migration.

Handles large pages by chunking HTML if it exceeds token limits.
"""

import json
import re
from typing import Optional

from .prompts.page_analysis import (
    PAGE_ANALYSIS_SYSTEM,
    PAGE_ANALYSIS_PROMPT,
    CHUNK_ANALYSIS_PROMPT,
)


class LLMAnalyzer:
    """Analyzes page HTML using an LLM to produce migration specs."""

    # Approximate token limits (conservative, leaving room for response)
    MAX_INPUT_CHARS = {
        "anthropic": 150_000,  # ~37k tokens for Claude
        "openai": 80_000,     # ~20k tokens for GPT-4
        "mock": 999_999,
    }

    def __init__(self, provider: str = "anthropic", api_key: str = "", model: str = ""):
        self.provider = provider.lower()
        self.api_key = api_key
        self.model = model or self._default_model()

    def _default_model(self) -> str:
        return {
            "anthropic": "claude-sonnet-4-20250514",
            "openai": "gpt-4",
            "mock": "mock",
        }.get(self.provider, "claude-sonnet-4-20250514")

    def analyze(self, html: str, metadata: dict = None) -> dict:
        """
        Analyze HTML and return a structured page specification.

        If the HTML is too large, it will be chunked and analyzed
        in parts, then merged.
        """
        if self.provider == "mock":
            return self._mock_analysis(html, metadata)

        max_chars = self.MAX_INPUT_CHARS.get(self.provider, 80_000)

        if len(html) <= max_chars:
            return self._analyze_single(html, metadata)
        else:
            return self._analyze_chunked(html, metadata, max_chars)

    def _analyze_single(self, html: str, metadata: dict) -> dict:
        """Send the full HTML to the LLM in one request."""
        prompt = PAGE_ANALYSIS_PROMPT.replace("{html}", "{__html__}").replace("{metadata}", "{__metadata__}")
        # Escape all remaining braces (JSON examples in the prompt), then restore placeholders
        prompt = prompt.replace("{", "{{").replace("}", "}}")
        prompt = prompt.replace("{{__html__}}", "{html}").replace("{{__metadata__}}", "{metadata}")
        prompt = prompt.format(
            html=html,
            metadata=json.dumps(metadata or {}, indent=2),
        )

        response_text = self._call_llm(prompt)
        return self._parse_json_response(response_text)

    def _analyze_chunked(self, html: str, metadata: dict, max_chars: int) -> dict:
        """Split HTML into chunks and analyze each separately, then merge."""
        chunks = self._split_html(html, max_chars)
        print(f"    Page is large ({len(html)} chars). Splitting into {len(chunks)} chunks.")

        all_sections = []
        base_spec = None

        for i, chunk in enumerate(chunks):
            print(f"    Analyzing chunk {i + 1}/{len(chunks)}...")
            prompt = CHUNK_ANALYSIS_PROMPT.replace("{chunk_num}", "{__cn__}").replace("{total_chunks}", "{__tc__}").replace("{html_chunk}", "{__hc__}")
            prompt = prompt.replace("{", "{{").replace("}", "}}")
            prompt = prompt.replace("{{__cn__}}", "{chunk_num}").replace("{{__tc__}}", "{total_chunks}").replace("{{__hc__}}", "{html_chunk}")
            prompt = prompt.format(
                chunk_num=i + 1,
                total_chunks=len(chunks),
                html_chunk=chunk,
            )

            response_text = self._call_llm(prompt)
            chunk_spec = self._parse_json_response(response_text)

            if base_spec is None:
                base_spec = chunk_spec
            else:
                # Merge sections from this chunk
                all_sections.extend(chunk_spec.get("sections", []))

        if base_spec:
            base_spec["sections"] = base_spec.get("sections", []) + all_sections

        return base_spec or {}

    def _call_llm(self, prompt: str) -> str:
        """Make an API call to the configured LLM provider."""
        if self.provider == "anthropic":
            return self._call_anthropic(prompt)
        elif self.provider == "openai":
            return self._call_openai(prompt)
        else:
            raise ValueError(f"Unknown LLM provider: {self.provider}")

    def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic Claude API."""
        try:
            import anthropic
        except ImportError:
            raise ImportError("Install anthropic SDK: pip install anthropic")

        client = anthropic.Anthropic(api_key=self.api_key)

        message = client.messages.create(
            model=self.model,
            max_tokens=8192,
            system=PAGE_ANALYSIS_SYSTEM,
            messages=[
                {"role": "user", "content": prompt}
            ],
        )

        return message.content[0].text

    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI GPT API."""
        try:
            import openai
        except ImportError:
            raise ImportError("Install openai SDK: pip install openai")

        client = openai.OpenAI(api_key=self.api_key)

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": PAGE_ANALYSIS_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            max_tokens=8192,
            temperature=0.1,
        )

        return response.choices[0].message.content

    def _parse_json_response(self, text: str) -> dict:
        """Parse JSON from LLM response, handling common formatting issues."""
        # Strip markdown code fences
        text = text.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            # Try to find JSON object in the text
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass

            print(f"    ⚠ Failed to parse LLM JSON response: {e}")
            print(f"    Response preview: {text[:200]}...")
            return {"error": "Failed to parse LLM response", "raw": text[:500]}

    def _split_html(self, html: str, max_chars: int) -> list[str]:
        """Split HTML into chunks at logical boundaries."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        body = soup.find("body") or soup

        chunks = []
        current_chunk = ""

        # Split by top-level body children
        for child in body.children:
            child_str = str(child)
            if len(current_chunk) + len(child_str) > max_chars and current_chunk:
                chunks.append(current_chunk)
                current_chunk = child_str
            else:
                current_chunk += child_str

        if current_chunk:
            chunks.append(current_chunk)

        # If we still have chunks that are too large, force-split them
        final_chunks = []
        for chunk in chunks:
            if len(chunk) > max_chars:
                for i in range(0, len(chunk), max_chars):
                    final_chunks.append(chunk[i:i + max_chars])
            else:
                final_chunks.append(chunk)

        return final_chunks

    def _mock_analysis(self, html: str, metadata: dict) -> dict:
        """Return a mock spec for testing without an API key."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        title = soup.find("title")
        h1 = soup.find("h1")

        return {
            "page_title": title.get_text(strip=True) if title else "Untitled Page",
            "page_slug": "migrated-page",
            "seo": metadata.get("seo", {}),
            "tracking": metadata.get("tracking", []),
            "redirects": [],
            "navigation": {"items": []},
            "sections": [
                {
                    "id": "mock-hero",
                    "type": "hero",
                    "layout": "full_width",
                    "background": {"type": "color", "value": "#ffffff"},
                    "children": [
                        {
                            "type": "heading",
                            "elementor_widget": "heading",
                            "content": {
                                "text": h1.get_text(strip=True) if h1 else "Page Heading",
                                "tag": "h1",
                            },
                            "style": {"color": "#000000"},
                            "attributes": {},
                        }
                    ],
                },
                {
                    "id": "mock-content",
                    "type": "content",
                    "layout": "boxed",
                    "background": {"type": "color", "value": "#ffffff"},
                    "children": [
                        {
                            "type": "paragraph",
                            "elementor_widget": "text-editor",
                            "content": {"html": "[Content extracted from page body]"},
                            "style": {},
                            "attributes": {},
                        }
                    ],
                },
            ],
            "global_styles": {
                "primary_color": "#0056b3",
                "secondary_color": "#6c757d",
                "text_color": "#333333",
                "background_color": "#ffffff",
                "heading_font": "Arial",
                "body_font": "Arial",
                "base_font_size": "16px",
            },
            "dependencies": {
                "plugins": ["elementor"],
                "fonts": [],
                "icon_libraries": [],
                "custom_css": "",
                "custom_js": "",
            },
            "_mock": True,
            "_note": "This is a mock analysis. Set LLM_API_KEY for real analysis.",
        }
