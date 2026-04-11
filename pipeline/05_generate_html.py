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
from pathlib import Path

import re
from jinja2 import Environment, FileSystemLoader, select_autoescape

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import (DIGEST_DIR, LEONARDO_API_KEY, SUPABASE_URL,
                              today_str, read_json)

# ── Template Setup ──────────────────────────────────────────────────────────

TEMPLATE_DIR = DIGEST_DIR / "templates"
REVIEWS_DIR = DIGEST_DIR / "reviews"


def _slugify(text: str) -> str:
    """Convert tool name to URL-safe slug (mirrors 05b logic)."""
    slug = text.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s-]+', '-', slug)
    return slug.strip('-')


def _build_review_slug_map() -> dict[str, str]:
    """Build a map from tool slug -> review relative URL."""
    slug_map: dict[str, str] = {}
    if not REVIEWS_DIR.is_dir():
        return slug_map
    for f in REVIEWS_DIR.glob("20??-??-??-*.html"):
        # filename: 2026-04-10-tool-slug-here.html
        # strip date prefix (11 chars: YYYY-MM-DD-)
        tool_slug = f.stem[11:]
        if tool_slug:
            slug_map[tool_slug] = f"./reviews/{f.name}"
    return slug_map


def _enrich_tools_with_reviews(tools: list[dict]) -> list[dict]:
    """Add review_url to tools that have a Lab Report."""
    slug_map = _build_review_slug_map()
    enriched = []
    for tool in tools:
        tool_copy = dict(tool)
        title = tool_copy.get("title", "")
        slug = _slugify(title)
        if slug in slug_map:
            tool_copy["review_url"] = slug_map[slug]
        enriched.append(tool_copy)
    return enriched


def format_date_label(date_str):
    """Convert YYYY-MM-DD to '28 March 2026' format, always using the --date arg."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%-d %B %Y") if os.name != "nt" else dt.strftime("%#d %B %Y")
    except ValueError:
        return date_str


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


def get_youtube_id(date: str = "") -> str:
    """Read YouTube video ID from youtube-result.json.
    Only returns an ID if it was uploaded on the same date as today's digest.
    Stale IDs from previous days are silently ignored.
    """
    yt_path = DIGEST_DIR / "youtube-result.json"
    if yt_path.exists():
        try:
            with open(yt_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw_id = data.get("video_id", "")
            stamped_date = data.get("date", "")
            # Reject if from a different day
            if date and stamped_date and stamped_date != date:
                print(f"  INFO: youtube-result.json is from {stamped_date}, not {date} — skipping stale video")
                return ""
            if re.fullmatch(r'[A-Za-z0-9_\-]{11}', raw_id):
                return raw_id
            if raw_id:
                print(f"  WARNING: Invalid YouTube ID format: {raw_id!r}")
            return ""
        except Exception as e:
            print(f"  WARNING: Could not read youtube-result.json: {e}")
    return ""


def media_url(filename):
    """Return the public URL for a media file (Supabase if available, relative fallback)."""
    if SUPABASE_URL:
        return f"{SUPABASE_URL}/storage/v1/object/public/koda-media/{filename}"
    return f"./{filename}"


def check_media(date, media_status):
    """Check which media files are available."""
    media = media_status.get("media", {}) if media_status else {}

    podcast_file = DIGEST_DIR / f"podcast-{date}.mp3"
    has_podcast = bool(media.get("podcast")) or podcast_file.exists()

    infographic_file = DIGEST_DIR / f"infographic-{date}.jpg"
    has_infographic = bool(media.get("infographic")) or infographic_file.exists()

    return has_podcast, has_infographic


# ── Hero Image Generation ──────────────────────────────────────────────────

def generate_hero_image(digest, date):
    """Generate a unique hero image using Leonardo.ai Nano Banana based on today's content."""
    import httpx
    import time

    hero_path = DIGEST_DIR / f"hero-{date}.jpg"
    if hero_path.exists():
        print(f"  Hero image already exists: {hero_path.name}")
        return True

    if not LEONARDO_API_KEY:
        print("  WARNING: No LEONARDO_API_KEY, skipping hero image")
        return False

    # Build a visual theme from focus topics, using the date to pick a primary angle
    import hashlib
    topics = digest.get("summary", {}).get("focus_topics", [])
    hook = (digest.get("summary", {}).get("hook", "") or "").lower()
    briefs = digest.get("summary", {}).get("briefs", [])

    # Collect all thematic angles from the day's content
    angles = []
    for topic in topics:
        title = (topic.get("title", "") or "").lower()
        desc = (topic.get("description", "") or "").lower()
        combined = title + " " + desc

        if any(kw in combined for kw in ["ai", "model", "open-source", "neural", "llm", "frontier"]):
            angles.append({
                "subject": "an intricate web of glowing neural pathways branching outward from a central core, electric pulses traveling along crystalline fibers",
                "mood": "awe-inspiring, expansive, luminous",
            })
        if any(kw in combined for kw in ["war", "conflict", "military", "iran", "crisis", "strike", "troops"]):
            angles.append({
                "subject": "a massive storm system seen from above with lightning illuminating fractured tectonic plates, dark volcanic energy",
                "mood": "ominous, turbulent, raw power",
            })
        if any(kw in combined for kw in ["market", "stock", "oil", "dow", "economy", "crash", "freefall"]):
            angles.append({
                "subject": "abstract geometric shards falling through space like a collapsing structure, streaks of red and amber light through dark void",
                "mood": "dramatic, kinetic, tension",
            })
        if any(kw in combined for kw in ["open-source", "release", "launch", "commodit"]):
            angles.append({
                "subject": "thousands of luminous orbs spreading outward from a singularity in a dark ocean, ripple patterns in light",
                "mood": "expansive, democratizing, hopeful energy",
            })
        if any(kw in combined for kw in ["regulation", "policy", "govern", "law", "compliance"]):
            angles.append({
                "subject": "towering crystalline pillars forming a structured grid against a stormy sky, order emerging from chaos",
                "mood": "authoritative, structured, imposing",
            })
        if any(kw in combined for kw in ["energy", "climate", "sustain", "green", "carbon"]):
            angles.append({
                "subject": "swirling aurora-like energy ribbons wrapping around a dark sphere, organic meets digital",
                "mood": "elemental, powerful, natural force",
            })

    if not angles:
        angles.append({
            "subject": "abstract data streams flowing through a dark crystalline landscape, nodes of light pulsing at intersections",
            "mood": "futuristic, contemplative",
        })

    # Use the day number to rotate through angles (guarantees different visual each day)
    day_num = int(date.split("-")[-1])
    primary = angles[day_num % len(angles)]

    image_prompt = (
        f"Cinematic digital art: {primary['subject']}. "
        f"Mood: {primary['mood']}. "
        f"Dark moody atmosphere, deep shadows, volumetric lighting, rich contrast. "
        f"Color palette: deep navy, electric blue, violet purple, subtle cyan accents. "
        f"Wide composition, no people, no faces, no bodies, no hands. "
        f"Absolutely NO text, NO words, NO labels, NO numbers, NO letters, NO typography anywhere. "
        f"Clean abstract visual only. Photorealistic 3D render, dramatic cinematic lighting."
    )

    print(f"  Generating hero image via Leonardo.ai Nano Banana...")
    print(f"    Prompt: {image_prompt[:120]}...")

    headers = {
        "authorization": f"Bearer {LEONARDO_API_KEY}",
        "Content-Type": "application/json",
        "accept": "application/json",
    }

    # v2 endpoint for Nano Banana generation
    payload = {
        "model": "gemini-2.5-flash-image",
        "parameters": {
            "width": 1024,
            "height": 1024,
            "prompt": image_prompt,
            "quantity": 1,
            "style_ids": ["111dc692-d470-4eec-b791-3475abac4c46"],  # Dynamic style
            "prompt_enhance": "OFF",
        },
        "public": False,
    }

    try:
        # Submit generation request via v2
        resp = httpx.post(
            "https://cloud.leonardo.ai/api/rest/v2/generations",
            json=payload, headers=headers, timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        generation_id = result.get("generate", {}).get("generationId")

        if not generation_id:
            print(f"  WARNING: No generation ID returned: {result}")
            return False

        print(f"    Generation ID: {generation_id}")

        # Poll for completion via v1 endpoint
        poll_url = f"https://cloud.leonardo.ai/api/rest/v1/generations/{generation_id}"
        for attempt in range(30):  # up to 90 seconds
            time.sleep(3)
            status_resp = httpx.get(poll_url, headers=headers, timeout=15)
            status_resp.raise_for_status()
            gen = status_resp.json().get("generations_by_pk", {})
            state = gen.get("status", "")

            if state == "COMPLETE":
                images = gen.get("generated_images", [])
                if not images:
                    print("  WARNING: Generation complete but no images returned")
                    return False

                image_url = images[0].get("url", "")
                if not image_url:
                    print("  WARNING: No image URL in response")
                    return False

                # Download the generated image
                print(f"    Downloading generated image...")
                img_resp = httpx.get(image_url, timeout=30)
                img_resp.raise_for_status()
                with open(hero_path, "wb") as f:
                    f.write(img_resp.content)

                size_kb = hero_path.stat().st_size // 1024
                print(f"  Saved hero image: {hero_path.name} ({size_kb}KB)")
                return True

            elif state == "FAILED":
                print(f"  WARNING: Leonardo generation failed")
                return False

            if attempt % 5 == 4:
                print(f"    Still generating... ({(attempt + 1) * 3}s)")

        print("  WARNING: Leonardo generation timed out after 90s")
        return False

    except Exception as e:
        print(f"  WARNING: Leonardo hero image generation failed: {e}")
        if hero_path.exists():
            hero_path.unlink()
        return False


# ── Main Assembly ───────────────────────────────────────────────────────────

def safe_url(value):
    """Return URL only if it starts with http(s)://."""
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        return value
    return "#"


def strip_em_dash(value):
    """Replace em dashes with commas for cleaner copy."""
    if isinstance(value, str):
        return value.replace("\u2014", ",").replace("\u2013", ",")
    return value


def sparkline_svg(points, color="var(--emerald)", width=80, height=24):
    """Generate an inline SVG sparkline from a list of numeric values."""
    if not points or len(points) < 2:
        return ""
    lo, hi = min(points), max(points)
    span = hi - lo if hi != lo else 1
    pad = 2
    usable_h = height - pad * 2
    coords = []
    for i, v in enumerate(points):
        x = round(i / (len(points) - 1) * width, 1)
        y = round(pad + usable_h - ((v - lo) / span) * usable_h, 1)
        coords.append(f"{x},{y}")
    poly = " ".join(coords)
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'style="display:block;margin:8px auto 0" aria-hidden="true">'
        f'<polyline points="{poly}" fill="none" stroke="{color}" '
        f'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
        f'</svg>'
    )


def generate_html(digest, media_status, date):
    """Render the Jinja2 template with digest data."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["safe_url"] = safe_url
    env.filters["no_em_dash"] = strip_em_dash
    env.filters["sparkline"] = sparkline_svg
    template = env.get_template("briefing.html")

    has_podcast, has_infographic = check_media(date, media_status)
    has_hero_image = generate_hero_image(digest, date)
    editorial_status = read_json("editorial-status.json")

    context = {
        # Metadata
        "date": date,
        "date_label": format_date_label(date),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "year": datetime.now().year,
        "youtube_id": get_youtube_id(date),

        # Media availability and URLs
        "has_podcast": has_podcast,
        "has_infographic": has_infographic,
        "has_hero_image": has_hero_image,
        "podcast_url": media_url(f"podcast-{date}.mp3"),
        "infographic_url": media_url(f"infographic-{date}.jpg"),

        # Focus hero image (email sketch-note infographic from Supabase)
        "focus_hero_url": media_url(f"email-hero-{date}.jpg"),

        # Editorial (from step 04E — only set if it ran successfully today)
        "editorial": editorial_status if (
            editorial_status
            and editorial_status.get("success")
            and editorial_status.get("date") == date
        ) else None,

        # Editorial hero image URL (for Deep Dive card)
        "editorial_hero_url": (
            editorial_status.get("hero_url", "")
            if editorial_status and editorial_status.get("success")
            and editorial_status.get("date") == date
            else ""
        ),

        # Content sections (passed directly from JSON)
        "summary": digest.get("summary", {}),
        "ai_news": digest.get("ai_news", []),
        "world_news": digest.get("world_news", []),
        "markets": digest.get("markets", {}),
        "newsletters": digest.get("newsletters", []),
        "competitive": digest.get("competitive", []),
        "tools": _enrich_tools_with_reviews(digest.get("tools", [])),

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

    # Export latest markets for landing page
    markets = digest.get("markets", {})
    if markets:
        markets_path = DIGEST_DIR / "latest-markets.json"
        with open(markets_path, "w", encoding="utf-8") as f:
            json.dump({"date": args.date, "markets": markets}, f)
        print(f"  Saved: {markets_path}")


if __name__ == "__main__":
    main()
