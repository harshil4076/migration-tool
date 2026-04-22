# CMS-to-WordPress Migration Tool (MVP)

An LLM-powered tool that automates migrating web pages from any vendor CMS to a self-hosted WordPress site with Elementor.

## How It Works

```
Source Page (Vendor CMS)
        │
        ▼
  ┌─────────────┐
  │  1. Scrape   │  Fetch HTML, download images/videos/docs/fonts
  └──────┬───────┘
         ▼
  ┌─────────────┐
  │ 2. Analyze   │  LLM reads HTML → outputs structured JSON spec
  └──────┬───────┘
         ▼
  ┌─────────────┐
  │  3. Map      │  JSON spec → Elementor widget data structure
  └──────┬───────┘
         ▼
  ┌─────────────┐
  │ 4. Generate  │  Create WP page via REST API + upload assets
  └──────┬───────┘
         ▼
  ┌─────────────┐
  │ 5. Validate  │  Check links, images, SEO metadata
  └──────────────┘
```

## Prerequisites

1. **Python 3.10+**
2. **Local WordPress instance** (see setup below)
3. **LLM API key** — Anthropic (Claude) or OpenAI (GPT-4)

## Quick Start

### 1. Clone and install dependencies

```bash
cd migration-tool
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set up local WordPress

The easiest way is [LocalWP](https://localwp.com/) (free):

1. Download and install LocalWP
2. Click "Create a new site"
3. Name it (e.g., "migration-test"), use default settings
4. Once running, note the site URL (e.g., `http://migration-test.local`)

Then install required plugins in WordPress Admin → Plugins → Add New:
- **Elementor** (page builder)
- **WPForms Lite** (forms)
- **Yoast SEO** (SEO metadata)
- **Redirection** (URL redirects)

### 3. Create a WordPress Application Password

1. Go to WordPress Admin → Users → Your Profile
2. Scroll to "Application Passwords"
3. Enter a name (e.g., "migration-tool") and click "Add New"
4. Copy the generated password

### 4. Configure the tool

Option A — Environment variables:
```bash
cp .env.example .env
# Edit .env with your values
```

Option B — Config file:
```bash
cp config/settings.json.example config/settings.json
# Edit config/settings.json with your values
```

### 5. Run a dry run (no WordPress changes)

```bash
python main.py --url https://example.com --dry-run
```

This will:
- Scrape the page and download all assets
- Run LLM analysis (or mock analysis if no API key)
- Save all output files to `./output/` for review

### 6. Run the full migration

```bash
python main.py --url https://example.com/landing-page
```

Or with a config file:
```bash
python main.py --url https://example.com/landing-page --config config/settings.json
```

## Project Structure

```
migration-tool/
├── main.py                     # Entry point — orchestrates the pipeline
├── scraper/
│   ├── crawl.py                # Fetches source page HTML
│   ├── extract_assets.py       # Downloads images, videos, docs, fonts
│   └── extract_metadata.py     # Extracts SEO, tracking, structured data
├── analyzer/
│   ├── llm_analyzer.py         # Sends HTML to LLM, gets structured JSON
│   ├── element_mapper.py       # Maps JSON spec to Elementor data format
│   └── prompts/
│       └── page_analysis.py    # LLM prompt templates
├── generator/
│   ├── wp_client.py            # WordPress REST API client
│   ├── media_uploader.py       # Uploads assets to WP Media Library
│   ├── elementor_builder.py    # Creates WP pages with Elementor layout
│   └── plugin_configurator.py  # Configures SEO, redirects, tracking
├── validator/
│   ├── link_checker.py         # Checks for broken links/images
│   └── seo_validator.py        # Validates SEO metadata migration
├── config/
│   └── settings.json.example   # Example config file
├── .env.example                # Example environment variables
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Output Files

After running, the `./output/` directory will contain:

| File | Description |
|------|-------------|
| `scraped/index.html` | Raw HTML from source page |
| `scraped/assets/` | Downloaded images, videos, docs, fonts |
| `scraped/manifest.json` | Full inventory of scraped data |
| `page_spec.json` | LLM's structured analysis of the page |
| `elementor_spec.json` | Elementor-ready widget data |
| `validation_report.json` | Link check and SEO validation results |
| `tracking_config.json` | Analytics/tracking code snippets |
| `redirects.json` | URL redirect rules |
| `redirects.htaccess` | Apache redirect rules |

## Configuration Reference

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `WP_URL` | WordPress site URL | `http://localhost:8881` |
| `WP_USERNAME` | WordPress admin username | `admin` |
| `WP_APP_PASSWORD` | Application Password (not login pw) | — |
| `LLM_PROVIDER` | `anthropic` or `openai` | `anthropic` |
| `LLM_API_KEY` | API key for the LLM provider | — |
| `LLM_MODEL` | Model name | `claude-sonnet-4-20250514` |
| `OUTPUT_DIR` | Where to save output files | `./output` |

## What Gets Migrated

The tool handles these page elements:

- **Content**: Headings, paragraphs, lists, text blocks
- **Images**: Downloads, uploads to WP Media Library, rewrites URLs. Handles srcset and CSS backgrounds
- **Videos**: Self-hosted (uploaded) and embeds (YouTube, Vimeo)
- **Forms**: Contact forms mapped to WPForms fields
- **Documents**: PDFs, Word docs, spreadsheets (as downloads)
- **Navigation**: Menu structure and hierarchy
- **SEO**: Meta title, description, canonical, OG tags, Twitter cards, schema markup
- **Tracking**: Google Analytics, GTM, Facebook Pixel, LinkedIn Insight
- **Fonts**: Custom fonts detected and cataloged
- **UI Components**: Accordions, tabs, sliders, carousels, counters
- **Redirects**: Old-to-new URL redirect rules
- **Styles**: Colors, typography, spacing, backgrounds

## Troubleshooting

**"WordPress application password not set"**
→ Create one in WP Admin → Users → Profile → Application Passwords

**"Selenium not installed" warning**
→ Only needed for JavaScript-rendered pages. Install with `pip install selenium` if your source site uses heavy JS rendering.

**Elementor data not showing in page editor**
→ The REST API may not support custom meta fields. Check `output/elementor_data_page_*.json` for wp-cli commands to import manually.

**LLM analysis returns empty or malformed JSON**
→ Very large pages may need chunking. The tool handles this automatically but check `output/page_spec.json` for any errors.

## Next Steps (Post-MVP)

- Full site crawl (batch processing hundreds of pages)
- Visual screenshot comparison (original vs migrated)
- Template pattern detection (reuse layouts across similar pages)
- WordPress theme generation from source design
- Progress dashboard with migration status
- Rollback support
