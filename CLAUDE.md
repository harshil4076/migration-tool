# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
cd migration-tool
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure credentials
cp .env.example .env   # then fill in WP_APP_PASSWORD and LLM_API_KEY

# Dry run — scrape + LLM analysis only, no WordPress changes
python main.py --url https://example.com --dry-run

# Full migration
python main.py --url https://example.com/landing-page

# Full migration with config file
python main.py --url https://example.com/landing-page --config config/settings.json
```

No test suite or linter is configured.

## Architecture

This is a single-page CMS → WordPress migration tool. `main.py` drives a linear 5-step pipeline; each step is a thin orchestration call to a class in its own module.

**Pipeline:**

```
1. scraper/crawl.py          PageCrawler        → fetch HTML (Selenium fallback for JS pages)
2. scraper/extract_assets.py  AssetExtractor     → download images/videos/fonts/docs to output/scraped/assets/
3. scraper/extract_metadata.py MetadataExtractor → extract SEO tags, tracking IDs
4. analyzer/llm_analyzer.py   LLMAnalyzer        → POST HTML to Claude/GPT-4, get structured JSON (page_spec.json)
5. analyzer/element_mapper.py ElementMapper      → translate page_spec → Elementor's _elementor_data format (elementor_spec.json)
6. generator/wp_client.py     WordPressClient    → thin wrapper around WordPress REST API (/wp-json/wp/v2/)
7. generator/media_uploader.py MediaUploader     → upload downloaded assets, return old→new URL map
8. generator/elementor_builder.py ElementorBuilder → create WP page, rewrite asset URLs, set _elementor_data post meta
9. generator/plugin_configurator.py PluginConfigurator → set Yoast/RankMath SEO meta, Redirection plugin rules, tracking snippets
10. validator/link_checker.py  LinkChecker       → concurrent HEAD requests on all links/images
11. validator/seo_validator.py SEOValidator       → compare migrated page SEO against expected values
```

**The critical data contracts between steps:**

- `page_spec.json` — LLM output. Schema: `{page_title, page_slug, seo, tracking, redirects, navigation, sections[], global_styles, dependencies}`. Each section has `{id, type, layout, background, children[]}` where each child has `{type, elementor_widget, content, style, attributes}`.
- `elementor_spec.json` — Elementor input. Schema: `{elements[], settings, custom_css}` where elements are Elementor sections → columns → widgets in Elementor's native nested format.
- `output/scraped/manifest.json` — asset inventory linking original URLs to local file paths.

**Key design decisions:**

- The LLM prompt (in `analyzer/prompts/page_analysis.py`) dictates the `page_spec.json` schema. If you change the schema, update both the prompt and `element_mapper.py`.
- `ElementMapper.WIDGET_MAP` is the authoritative mapping from semantic element types (e.g. `"paragraph"`) to Elementor widget types (e.g. `"text-editor"`). Unknown types fall back to `html` widget.
- Large HTML (>150k chars for Claude, >80k for GPT-4) is split at top-level body children in `_analyze_chunked`, with sections merged across chunk results.
- WordPress auth uses Application Passwords (not login credentials). `WP_APP_PASSWORD` must be generated in WP Admin → Users → Profile.
- Elementor data is set via `_elementor_data` post meta. If the REST API rejects meta writes, the builder falls back to saving JSON to `output/elementor_data_page_*.json` with wp-cli import instructions.
- `--dry-run` stops after Step 3 (no WordPress interaction). With no `LLM_API_KEY`, dry-run uses `MockAnalyzer` which parses the page title/H1 but skips real analysis.

**Root-level scripts** (`clone_page.py`, `clone_page_v2.py`, `rebuild_page.py`) are standalone alternatives to the main pipeline — not integrated into it.

## Configuration

All config flows through `load_config()` in `main.py`: `.env` sets defaults, a JSON config file (via `--config`) deep-merges on top.

| Variable | Default |
|---|---|
| `WP_URL` | `http://localhost:8881` |
| `WP_USERNAME` | `admin` |
| `WP_APP_PASSWORD` | *(required for full run)* |
| `LLM_PROVIDER` | `anthropic` |
| `LLM_API_KEY` | *(required for real analysis)* |
| `LLM_MODEL` | `claude-sonnet-4-20250514` |
| `OUTPUT_DIR` | `./output` |

Required WordPress plugins: **Elementor**, **WPForms Lite**, **Yoast SEO**, **Redirection**. Local development uses [LocalWP](https://localwp.com/).
