#!/usr/bin/env python3
"""
CMS-to-WordPress Migration Tool (MVP)
======================================
Automates migrating a single landing page from a vendor CMS to WordPress
using LLM-powered content analysis and the WordPress REST API + Elementor.

Usage:
    python main.py --url https://example.com/landing-page
    python main.py --url https://example.com --config config/settings.json
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from scraper.crawl import PageCrawler
from scraper.extract_assets import AssetExtractor
from scraper.extract_metadata import MetadataExtractor
from analyzer.llm_analyzer import LLMAnalyzer
from analyzer.element_mapper import ElementMapper
from generator.wp_client import WordPressClient
from generator.media_uploader import MediaUploader
from generator.elementor_builder import ElementorBuilder
from generator.plugin_configurator import PluginConfigurator
from validator.link_checker import LinkChecker
from validator.seo_validator import SEOValidator


def load_config(config_path: str = None) -> dict:
    """Load configuration from file or environment variables."""
    config = {
        "wordpress": {
            "url": os.getenv("WP_URL", "http://localhost:8881"),
            "username": os.getenv("WP_USERNAME", "admin"),
            "password": os.getenv("WP_APP_PASSWORD", ""),
        },
        "llm": {
            "provider": os.getenv("LLM_PROVIDER", "anthropic"),
            "api_key": os.getenv("LLM_API_KEY", ""),
            "model": os.getenv("LLM_MODEL", "claude-sonnet-4-20250514"),
        },
        "output_dir": os.getenv("OUTPUT_DIR", "./output"),
    }

    if config_path and os.path.exists(config_path):
        with open(config_path, "r") as f:
            file_config = json.load(f)
        # Deep merge file config into defaults
        for section in file_config:
            if isinstance(file_config[section], dict) and section in config:
                config[section].update(file_config[section])
            else:
                config[section] = file_config[section]

    return config


def validate_config(config: dict) -> list[str]:
    """Validate that all required config values are present."""
    errors = []
    if not config["wordpress"]["password"]:
        errors.append("WordPress application password not set. Set WP_APP_PASSWORD env var or add to config.")
    if not config["llm"]["api_key"]:
        errors.append("LLM API key not set. Set LLM_API_KEY env var or add to config.")
    return errors


def run_migration(source_url: str, config: dict, dry_run: bool = False):
    """Execute the full migration pipeline."""
    output_dir = Path(config["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("CMS-to-WordPress Migration Tool (MVP)")
    print("=" * 60)
    print(f"\nSource URL : {source_url}")
    print(f"Target WP  : {config['wordpress']['url']}")
    print(f"LLM        : {config['llm']['provider']} / {config['llm']['model']}")
    print(f"Output Dir : {output_dir}")
    print(f"Dry Run    : {dry_run}")
    print()

    # ─── Step 1: Scrape the Source Page ───────────────────────
    print("─" * 60)
    print("STEP 1: Scraping source page...")
    print("─" * 60)

    crawler = PageCrawler(output_dir=output_dir / "scraped")
    page_data = crawler.crawl(source_url)
    print(f"  ✓ Page HTML downloaded ({len(page_data['html'])} chars)")

    asset_extractor = AssetExtractor(
        output_dir=output_dir / "scraped" / "assets",
        base_url=source_url,
    )
    assets = asset_extractor.extract_and_download(page_data["html"])
    print(f"  ✓ Assets downloaded: {len(assets['images'])} images, "
          f"{len(assets['documents'])} docs, {len(assets['videos'])} videos, "
          f"{len(assets['fonts'])} fonts")

    metadata_extractor = MetadataExtractor()
    metadata = metadata_extractor.extract(page_data["html"], source_url)
    print(f"  ✓ Metadata extracted: title='{metadata.get('title', 'N/A')}'")

    # Save scraped data
    scraped_manifest = {
        "source_url": source_url,
        "html_file": str(output_dir / "scraped" / "index.html"),
        "assets": assets,
        "metadata": metadata,
    }
    with open(output_dir / "scraped" / "manifest.json", "w") as f:
        json.dump(scraped_manifest, f, indent=2)
    print(f"  ✓ Manifest saved to {output_dir / 'scraped' / 'manifest.json'}")

    # ─── Step 2: LLM Analysis ────────────────────────────────
    print()
    print("─" * 60)
    print("STEP 2: Analyzing page with LLM...")
    print("─" * 60)

    analyzer = LLMAnalyzer(
        provider=config["llm"]["provider"],
        api_key=config["llm"]["api_key"],
        model=config["llm"]["model"],
    )
    page_spec = analyzer.analyze(page_data["html"], metadata)
    print(f"  ✓ LLM analysis complete: {len(page_spec.get('sections', []))} sections identified")

    # Save the spec
    with open(output_dir / "page_spec.json", "w") as f:
        json.dump(page_spec, f, indent=2)
    print(f"  ✓ Page spec saved to {output_dir / 'page_spec.json'}")

    # ─── Step 3: Map to Elementor Components ──────────────────
    print()
    print("─" * 60)
    print("STEP 3: Mapping to Elementor components...")
    print("─" * 60)

    mapper = ElementMapper()
    elementor_spec = mapper.map(page_spec)
    print(f"  ✓ Mapped {len(elementor_spec.get('elements', []))} Elementor elements")

    with open(output_dir / "elementor_spec.json", "w") as f:
        json.dump(elementor_spec, f, indent=2)

    if dry_run:
        print("\n🏁 DRY RUN complete. Review output files in:", output_dir)
        print("   - scraped/manifest.json  (scraped data)")
        print("   - page_spec.json         (LLM analysis)")
        print("   - elementor_spec.json    (Elementor mapping)")
        return

    # ─── Step 4: Upload Assets to WordPress ───────────────────
    print()
    print("─" * 60)
    print("STEP 4: Uploading assets to WordPress...")
    print("─" * 60)

    wp_client = WordPressClient(
        url=config["wordpress"]["url"],
        username=config["wordpress"]["username"],
        password=config["wordpress"]["password"],
    )

    uploader = MediaUploader(wp_client=wp_client)
    media_map = uploader.upload_assets(assets)
    print(f"  ✓ Uploaded {len(media_map)} assets to WordPress Media Library")

    # ─── Step 5: Generate WordPress Page ──────────────────────
    print()
    print("─" * 60)
    print("STEP 5: Creating WordPress page...")
    print("─" * 60)

    builder = ElementorBuilder(wp_client=wp_client, media_map=media_map)
    page_result = builder.create_page(page_spec, elementor_spec)
    print(f"  ✓ Page created: {page_result.get('link', 'N/A')}")
    print(f"    Page ID: {page_result.get('id', 'N/A')}")

    # Configure plugins (SEO, redirects, tracking)
    configurator = PluginConfigurator(wp_client=wp_client)
    configurator.configure_seo(page_result["id"], page_spec.get("seo", {}))
    configurator.configure_redirects(page_spec.get("redirects", []))
    configurator.configure_tracking(page_spec.get("tracking", []))
    print("  ✓ Plugins configured (SEO, redirects, tracking)")

    # ─── Step 6: Validation ───────────────────────────────────
    print()
    print("─" * 60)
    print("STEP 6: Running validation checks...")
    print("─" * 60)

    page_url = page_result.get("link", "")

    link_checker = LinkChecker()
    link_results = link_checker.check(page_url)
    broken = [r for r in link_results if not r["ok"]]
    print(f"  {'✓' if not broken else '✗'} Link check: {len(link_results)} links, {len(broken)} broken")

    seo_validator = SEOValidator()
    seo_results = seo_validator.validate(page_url, page_spec.get("seo", {}))
    seo_issues = [r for r in seo_results if not r["ok"]]
    print(f"  {'✓' if not seo_issues else '✗'} SEO check: {len(seo_results)} checks, {len(seo_issues)} issues")

    # Save validation report
    validation_report = {
        "page_url": page_url,
        "page_id": page_result.get("id"),
        "links": link_results,
        "seo": seo_results,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(output_dir / "validation_report.json", "w") as f:
        json.dump(validation_report, f, indent=2)

    # ─── Summary ──────────────────────────────────────────────
    print()
    print("=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
    print(f"  Source    : {source_url}")
    print(f"  WordPress : {page_result.get('link', 'N/A')}")
    print(f"  Page ID   : {page_result.get('id', 'N/A')}")
    print(f"  Issues    : {len(broken)} broken links, {len(seo_issues)} SEO issues")
    print(f"  Report    : {output_dir / 'validation_report.json'}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="CMS-to-WordPress Migration Tool (MVP)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic migration
  python main.py --url https://example.com/landing-page

  # Dry run (scrape + analyze only, no WordPress changes)
  python main.py --url https://example.com --dry-run

  # With custom config file
  python main.py --url https://example.com --config config/settings.json
        """,
    )
    parser.add_argument("--url", required=True, help="URL of the source page to migrate")
    parser.add_argument("--config", default=None, help="Path to config JSON file")
    parser.add_argument("--dry-run", action="store_true", help="Scrape and analyze only, don't create WordPress page")

    args = parser.parse_args()

    config = load_config(args.config)
    errors = validate_config(config)

    if errors and not args.dry_run:
        print("Configuration errors:")
        for e in errors:
            print(f"  ✗ {e}")
        print("\nUse --dry-run to test scraping/analysis without WordPress.")
        sys.exit(1)

    # Allow dry run without full config
    if args.dry_run:
        if not config["llm"]["api_key"]:
            print("Warning: No LLM API key set. Using mock analyzer for dry run.")
            config["llm"]["provider"] = "mock"

    try:
        run_migration(args.url, config, dry_run=args.dry_run)
    except KeyboardInterrupt:
        print("\n\nMigration cancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        raise


if __name__ == "__main__":
    main()
