"""
Step 05: Generate HTML dashboard from digest content.

Reads digest-content.json + media-status.json and renders the Jinja2
template. Saves both dated archive and current shortcut.

Input:  pipeline/data/digest-content.json, pipeline/data/media-status.json
Output: morning-briefing-koda.html, morning-briefing-koda-{date}.html
"""

import argparse
import json
import sys
import os
from datetime import datetime

import re
from jinja2 import Environment, FileSystemLoader, select_autoescape

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import DIGEST_DIR, today_str, read_json

# ── Template Setup ──────────────────────────────────────────────────────────

TEMPLATE_DIR = DIGEST_DIR / "templates"


def load_css():
    """Load CSS from templates/briefing.css."""
    css_path = TEMPLATE_DIR / "briefing.css"
    if css_path.exists():
        return css_path.read_text(encoding="utf-8")
    return "*{margin:0;padding:0;box-sizing:border-box;}body{font-family:sans-serif;}"


def load_js():
    """Load JS from templates/briefing.js."""
    js_path = TEMPLATE_DIR / "briefing.js"
    if js_path.exists():
        return js_path.read_text(encoding="utf-8")
    return ""


def get_youtube_id():
    """Read YouTube video ID from youtube-result.json."""
    yt_path = DIGEST_DIR / "youtube-result.json"
    if yt_path.exists():
        try:
            with open(yt_path, "r", encoding="utf-8") as f:
                raw_id = json.load(f).get("video_id", "")
            if re.fullmatch(r'[A-Za-z0-9_\-]{11}', raw_id):
                return raw_id
            if raw_id:
                print(f"  WARNING: Invalid YouTube ID format: {raw_id!r}")
            return ""
        except Exception as e:
            print(f"  WARNING: Could not read youtube-result.json: {e}")
    return ""


def check_media(date, media_status):
    """Check which media files are available."""
    media = media_status.get("media", {}) if media_status else {}

    podcast_file = DIGEST_DIR / f"podcast-{date}.mp3"
    has_podcast = bool(media.get("podcast")) or podcast_file.exists()

    infographic_file = DIGEST_DIR / f"infographic-{date}.jpg"
    has_infographic = bool(media.get("infographic")) or infographic_file.exists()

    return has_podcast, has_infographic


# ── Main Assembly ───────────────────────────────────────────────────────────

def safe_url(value):
    """Return URL only if it starts with http(s)://."""
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        return value
    return "#"


def generate_html(digest, media_status, date):
    """Render the Jinja2 template with digest data."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["safe_url"] = safe_url
    template = env.get_template("briefing.html")

    has_podcast, has_infographic = check_media(date, media_status)

    context = {
        # Metadata
        "date": date,
        "date_label": digest.get("date_label", date),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "year": datetime.now().year,
        "youtube_id": get_youtube_id(),

        # Media availability
        "has_podcast": has_podcast,
        "has_infographic": has_infographic,

        # Content sections (passed directly from JSON)
        "summary": digest.get("summary", {}),
        "ai_news": digest.get("ai_news", []),
        "world_news": digest.get("world_news", []),
        "markets": digest.get("markets", {}),
        "newsletters": digest.get("newsletters", []),
        "competitive": digest.get("competitive", []),
        "tools": digest.get("tools", []),

        # Inline assets
        "css": load_css(),
        "js": load_js(),
    }

    return template.render(**context)


def main():
    parser = argparse.ArgumentParser(description="Step 05: Generate HTML dashboard")
    parser.add_argument("--date", default=today_str(), help="Date (YYYY-MM-DD)")
    args = parser.parse_args()

    print(f"[05] Generating HTML for {args.date}")

    digest = read_json("digest-content.json")
    media_status = read_json("media-status.json")

    if not digest:
        print("  ERROR: digest-content.json not found. Run 03_synthesize_content.py first.")
        sys.exit(1)

    html = generate_html(digest, media_status, args.date)
    print(f"  Generated {len(html)} chars of HTML")

    # Save dated archive
    dated_path = DIGEST_DIR / f"morning-briefing-koda-{args.date}.html"
    with open(dated_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Saved: {dated_path}")

    # Save current shortcut
    current_path = DIGEST_DIR / "morning-briefing-koda.html"
    with open(current_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Saved: {current_path}")


if __name__ == "__main__":
    main()
