"""
Plugin Configurator
===================
Configures WordPress plugins after page creation:
- Yoast SEO / RankMath (SEO metadata)
- Redirection plugin (URL redirects)
- Tracking codes (GA, GTM, FB Pixel via Insert Headers & Footers)
"""

import json


class PluginConfigurator:
    """Configures WordPress plugins for the migrated page."""

    def __init__(self, wp_client):
        self.wp = wp_client

    def configure_seo(self, page_id: int, seo_data: dict):
        """
        Set SEO metadata for a page using Yoast SEO or RankMath.

        Args:
            page_id: WordPress page ID
            seo_data: dict with meta_title, meta_description, og_*, canonical_url, etc.
        """
        if not seo_data:
            return

        # Try Yoast SEO first
        yoast_meta = {}
        if seo_data.get("meta_title"):
            yoast_meta["_yoast_wpseo_title"] = seo_data["meta_title"]
        if seo_data.get("meta_description"):
            yoast_meta["_yoast_wpseo_metadesc"] = seo_data["meta_description"]
        if seo_data.get("canonical_url"):
            yoast_meta["_yoast_wpseo_canonical"] = seo_data["canonical_url"]
        if seo_data.get("og_title"):
            yoast_meta["_yoast_wpseo_opengraph-title"] = seo_data["og_title"]
        if seo_data.get("og_description"):
            yoast_meta["_yoast_wpseo_opengraph-description"] = seo_data["og_description"]
        if seo_data.get("og_image"):
            yoast_meta["_yoast_wpseo_opengraph-image"] = seo_data["og_image"]

        # Also try RankMath meta keys
        rankmath_meta = {}
        if seo_data.get("meta_title"):
            rankmath_meta["rank_math_title"] = seo_data["meta_title"]
        if seo_data.get("meta_description"):
            rankmath_meta["rank_math_description"] = seo_data["meta_description"]
        if seo_data.get("canonical_url"):
            rankmath_meta["rank_math_canonical_url"] = seo_data["canonical_url"]

        # Try to set via REST API
        try:
            all_meta = {**yoast_meta, **rankmath_meta}
            self.wp.update_page(page_id, {"meta": all_meta})
            print(f"    ✓ SEO metadata set for page {page_id}")
        except Exception as e:
            print(f"    ⚠ Could not set SEO meta via API: {e}")
            self._save_seo_config(page_id, seo_data)

        # Handle schema/structured data
        schema = seo_data.get("schema_markup", [])
        if schema:
            self._set_schema_markup(page_id, schema)

    def configure_redirects(self, redirects: list):
        """
        Set up URL redirects using the Redirection plugin.

        Args:
            redirects: list of dicts with 'from', 'to', 'type' (301/302)
        """
        if not redirects:
            return

        # The Redirection plugin has a REST API at /wp-json/redirection/v1/
        for redirect in redirects:
            try:
                response = self.wp.session.post(
                    f"{self.wp.base_url}/wp-json/redirection/v1/redirect",
                    json={
                        "url": redirect.get("from", ""),
                        "action_data": {"url": redirect.get("to", "")},
                        "action_type": "url",
                        "action_code": redirect.get("type", 301),
                        "match_type": "url",
                        "group_id": 1,  # Default group
                    },
                )
                if response.status_code in (200, 201):
                    print(f"    ✓ Redirect: {redirect['from']} → {redirect['to']}")
                else:
                    print(f"    ⚠ Redirect API returned {response.status_code}")
            except Exception as e:
                print(f"    ⚠ Could not create redirect: {e}")

        # If API fails, save redirect rules for manual import
        if redirects:
            self._save_redirect_config(redirects)

    def configure_tracking(self, tracking_codes: list):
        """
        Set up analytics and tracking codes.

        Args:
            tracking_codes: list of dicts with 'type' and 'id'
        """
        if not tracking_codes:
            return

        header_scripts = []
        body_scripts = []

        for tracker in tracking_codes:
            tracker_type = tracker.get("type", "")
            tracker_id = tracker.get("id", "")

            if not tracker_id:
                continue

            if tracker_type == "google_analytics":
                if tracker_id.startswith("G-"):
                    # GA4
                    header_scripts.append(
                        f'<script async src="https://www.googletagmanager.com/gtag/js?id={tracker_id}"></script>\n'
                        f'<script>\n'
                        f'  window.dataLayer = window.dataLayer || [];\n'
                        f'  function gtag(){{dataLayer.push(arguments);}}\n'
                        f'  gtag("js", new Date());\n'
                        f'  gtag("config", "{tracker_id}");\n'
                        f'</script>'
                    )
                else:
                    # Universal Analytics
                    header_scripts.append(
                        f'<script async src="https://www.google-analytics.com/analytics.js"></script>\n'
                        f'<script>\n'
                        f'  window.ga=window.ga||function(){{(ga.q=ga.q||[]).push(arguments)}};ga.l=+new Date;\n'
                        f'  ga("create", "{tracker_id}", "auto");\n'
                        f'  ga("send", "pageview");\n'
                        f'</script>'
                    )

            elif tracker_type == "google_tag_manager":
                header_scripts.append(
                    f'<script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{"gtm.start":\n'
                    f'new Date().getTime(),event:"gtm.js"}});var f=d.getElementsByTagName(s)[0],\n'
                    f'j=d.createElement(s),dl=l!="dataLayer"?"&l="+l:"";j.async=true;j.src=\n'
                    f'"https://www.googletagmanager.com/gtm.js?id="+i+dl;f.parentNode.insertBefore(j,f);\n'
                    f'}})(window,document,"script","dataLayer","{tracker_id}");</script>'
                )
                body_scripts.append(
                    f'<noscript><iframe src="https://www.googletagmanager.com/ns.html?id={tracker_id}"\n'
                    f'height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>'
                )

            elif tracker_type == "facebook_pixel":
                header_scripts.append(
                    f'<script>\n'
                    f'  !function(f,b,e,v,n,t,s){{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?\n'
                    f'  n.callMethod.apply(n,arguments):n.queue.push(arguments)}};if(!f._fbq)f._fbq=n;\n'
                    f'  n.push=n;n.loaded=!0;n.version="2.0";n.queue=[];t=b.createElement(e);t.async=!0;\n'
                    f'  t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}}\n'
                    f'  (window,document,"script","https://connect.facebook.net/en_US/fbevents.js");\n'
                    f'  fbq("init", "{tracker_id}");\n'
                    f'  fbq("track", "PageView");\n'
                    f'</script>'
                )

            elif tracker.get("script_snippet"):
                header_scripts.append(tracker["script_snippet"])

        # Try to set via Insert Headers and Footers plugin or similar
        tracking_config = {
            "header_scripts": "\n".join(header_scripts),
            "body_scripts": "\n".join(body_scripts),
            "trackers": tracking_codes,
        }

        self._save_tracking_config(tracking_config)
        print(f"    ✓ Tracking config saved ({len(tracking_codes)} trackers)")

    def _set_schema_markup(self, page_id: int, schema: list):
        """Add schema/structured data markup."""
        schema_json = json.dumps(schema, indent=2)
        # Save as a reference file
        with open(f"output/schema_page_{page_id}.json", "w") as f:
            f.write(schema_json)
        print(f"    ✓ Schema markup saved for page {page_id}")

    def _save_seo_config(self, page_id: int, seo_data: dict):
        """Save SEO config for manual import."""
        with open(f"output/seo_config_page_{page_id}.json", "w") as f:
            json.dump(seo_data, f, indent=2)

    def _save_redirect_config(self, redirects: list):
        """Save redirect rules for manual import."""
        # Save as Redirection plugin import format
        with open("output/redirects.json", "w") as f:
            json.dump({"redirects": redirects}, f, indent=2)

        # Also save as .htaccess rules
        htaccess_rules = ["# Generated redirect rules"]
        for r in redirects:
            code = r.get("type", 301)
            htaccess_rules.append(
                f"Redirect {code} {r.get('from', '')} {r.get('to', '')}"
            )
        with open("output/redirects.htaccess", "w") as f:
            f.write("\n".join(htaccess_rules))

        print("    ✓ Redirect config saved to output/redirects.json and output/redirects.htaccess")

    def _save_tracking_config(self, config: dict):
        """Save tracking code config for manual insertion."""
        with open("output/tracking_config.json", "w") as f:
            json.dump(config, f, indent=2)
