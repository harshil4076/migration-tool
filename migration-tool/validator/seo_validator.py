"""
SEO Validator
=============
Validates that SEO metadata was correctly migrated to the
WordPress page: meta titles, descriptions, OG tags, canonical
URLs, and structured data.
"""

import requests
from bs4 import BeautifulSoup


class SEOValidator:
    """Validates SEO metadata on the migrated page."""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "CMS-Migration-SEOValidator/1.0"
        })

    def validate(self, page_url: str, expected_seo: dict) -> list[dict]:
        """
        Fetch the migrated page and compare its SEO metadata
        against the expected values from the source.

        Args:
            page_url: URL of the migrated WordPress page
            expected_seo: dict with expected meta_title, meta_description, etc.

        Returns:
            list of check results, each with:
                - check: name of the check
                - ok: bool
                - expected: expected value
                - actual: actual value found
                - message: description
        """
        if not page_url:
            return [{"check": "page_url", "ok": False, "expected": "URL",
                      "actual": None, "message": "No page URL provided"}]

        results = []

        try:
            response = self.session.get(page_url, timeout=self.timeout)
            response.raise_for_status()
        except Exception as e:
            return [{"check": "page_fetch", "ok": False, "expected": "200",
                      "actual": None, "message": f"Could not fetch page: {e}"}]

        soup = BeautifulSoup(response.text, "html.parser")

        # ── Title Tag ──
        title_tag = soup.find("title")
        actual_title = title_tag.get_text(strip=True) if title_tag else ""
        expected_title = expected_seo.get("meta_title", "")
        if expected_title:
            results.append({
                "check": "meta_title",
                "ok": expected_title.lower() in actual_title.lower() if expected_title else True,
                "expected": expected_title,
                "actual": actual_title,
                "message": "Title tag present and matches" if expected_title.lower() in actual_title.lower()
                           else "Title tag mismatch",
            })
        else:
            results.append({
                "check": "meta_title",
                "ok": bool(actual_title),
                "expected": "(any)",
                "actual": actual_title,
                "message": "Title tag present" if actual_title else "Title tag missing",
            })

        # ── Meta Description ──
        meta_desc = soup.find("meta", attrs={"name": "description"})
        actual_desc = meta_desc.get("content", "") if meta_desc else ""
        expected_desc = expected_seo.get("meta_description", "")
        results.append({
            "check": "meta_description",
            "ok": bool(actual_desc),
            "expected": expected_desc or "(any)",
            "actual": actual_desc,
            "message": "Meta description present" if actual_desc else "Meta description missing",
        })

        # ── Canonical URL ──
        canonical = soup.find("link", rel="canonical")
        actual_canonical = canonical.get("href", "") if canonical else ""
        expected_canonical = expected_seo.get("canonical_url", "")
        results.append({
            "check": "canonical_url",
            "ok": bool(actual_canonical),
            "expected": expected_canonical or "(any)",
            "actual": actual_canonical,
            "message": "Canonical URL present" if actual_canonical else "Canonical URL missing",
        })

        # ── Open Graph Tags ──
        og_checks = {
            "og:title": expected_seo.get("og_title", ""),
            "og:description": expected_seo.get("og_description", ""),
            "og:image": expected_seo.get("og_image", ""),
            "og:url": expected_seo.get("og_url", ""),
            "og:type": expected_seo.get("og_type", ""),
        }

        for og_prop, expected_val in og_checks.items():
            tag = soup.find("meta", attrs={"property": og_prop})
            actual_val = tag.get("content", "") if tag else ""
            results.append({
                "check": og_prop,
                "ok": bool(actual_val) or not expected_val,
                "expected": expected_val or "(optional)",
                "actual": actual_val,
                "message": f"{og_prop} present" if actual_val else f"{og_prop} missing",
            })

        # ── Twitter Card Tags ──
        twitter_card = soup.find("meta", attrs={"name": "twitter:card"})
        results.append({
            "check": "twitter:card",
            "ok": bool(twitter_card),
            "expected": expected_seo.get("twitter_card", "(optional)"),
            "actual": twitter_card.get("content", "") if twitter_card else "",
            "message": "Twitter card present" if twitter_card else "Twitter card missing",
        })

        # ── Robots Meta ──
        robots = soup.find("meta", attrs={"name": "robots"})
        actual_robots = robots.get("content", "") if robots else ""
        results.append({
            "check": "robots",
            "ok": "noindex" not in actual_robots.lower(),
            "expected": "index, follow (or empty)",
            "actual": actual_robots or "(not set)",
            "message": "Page is indexable" if "noindex" not in actual_robots.lower()
                       else "WARNING: Page is set to noindex",
        })

        # ── Structured Data (JSON-LD) ──
        json_ld_scripts = soup.find_all("script", type="application/ld+json")
        expected_schema = expected_seo.get("schema_markup", [])
        results.append({
            "check": "structured_data",
            "ok": bool(json_ld_scripts) or not expected_schema,
            "expected": f"{len(expected_schema)} schema blocks" if expected_schema else "(optional)",
            "actual": f"{len(json_ld_scripts)} schema blocks found",
            "message": "Structured data present" if json_ld_scripts else "No structured data found",
        })

        # ── Heading Structure ──
        h1_tags = soup.find_all("h1")
        results.append({
            "check": "h1_tag",
            "ok": len(h1_tags) == 1,
            "expected": "Exactly 1 H1 tag",
            "actual": f"{len(h1_tags)} H1 tags found",
            "message": "Single H1 tag present" if len(h1_tags) == 1
                       else f"Expected 1 H1, found {len(h1_tags)}",
        })

        # ── Image Alt Text ──
        images = soup.find_all("img")
        images_without_alt = [img for img in images if not img.get("alt")]
        results.append({
            "check": "image_alt_text",
            "ok": len(images_without_alt) == 0,
            "expected": "All images have alt text",
            "actual": f"{len(images_without_alt)} of {len(images)} images missing alt text",
            "message": "All images have alt text" if not images_without_alt
                       else f"{len(images_without_alt)} images missing alt text",
        })

        # ── Viewport Meta ──
        viewport = soup.find("meta", attrs={"name": "viewport"})
        results.append({
            "check": "viewport",
            "ok": bool(viewport),
            "expected": "viewport meta tag present",
            "actual": viewport.get("content", "") if viewport else "(missing)",
            "message": "Viewport meta present (mobile-friendly)" if viewport
                       else "Viewport meta missing (mobile issues likely)",
        })

        return results

    def generate_report(self, results: list) -> str:
        """Generate a human-readable SEO validation report."""
        lines = ["SEO Validation Report", "=" * 40, ""]

        passed = sum(1 for r in results if r["ok"])
        total = len(results)
        lines.append(f"Score: {passed}/{total} checks passed\n")

        for r in results:
            icon = "✓" if r["ok"] else "✗"
            lines.append(f"  {icon} {r['check']}: {r['message']}")
            if not r["ok"]:
                lines.append(f"    Expected: {r['expected']}")
                lines.append(f"    Actual:   {r['actual']}")

        return "\n".join(lines)
