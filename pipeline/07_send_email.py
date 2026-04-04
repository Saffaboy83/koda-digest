"""
Step 07: Send the daily newsletter email.

Fetches active subscribers from Beehiiv, then sends via Gmail API using BCC
so recipients don't see each other's email addresses.
Includes a per-subscriber unsubscribe link that removes them from Beehiiv.

Input:  pipeline/data/digest-content.json, pipeline/data/media-status.json
Output: Gmail email to all Beehiiv subscribers (BCC)
"""

import argparse
import base64
import hashlib
import hmac
import json
import sys
import os
import httpx
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import (EMAIL_RECIPIENTS, DIGEST_DIR, SUPABASE_URL,
                              BEEHIIV_API_KEY, BEEHIIV_PUBLICATION_ID,
                              today_str, write_json, read_json)

UNSUBSCRIBE_SECRET = os.environ.get("UNSUBSCRIBE_SECRET", BEEHIIV_API_KEY[:16] if BEEHIIV_API_KEY else "koda-unsub-key")

GMAIL_TOKEN_PATH = DIGEST_DIR / ".gmail_token.json"
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]


NOTEBOOK_ID = "f928d89b-2520-4180-a71a-d93a75a5487c"


def generate_email_hero(digest: dict, date: str) -> str | None:
    """Generate a concise sketch-note infographic via NotebookLM for the email hero.
    Uses the permanent notebook (sources already loaded by step 04).
    Returns the Supabase public URL if successful, None otherwise."""
    import asyncio

    hero_path = DIGEST_DIR / "pipeline" / "data" / f"email-hero-{date}.jpg"
    if hero_path.exists():
        print(f"  Email sketch-note already exists: {hero_path.name}")
        return _upload_hero_to_supabase(hero_path, date)

    try:
        from notebooklm import NotebookLMClient, InfographicOrientation, InfographicDetail
    except ImportError:
        print("  WARNING: notebooklm-py not installed, skipping email hero")
        return None

    # Build instructions from the day's top stories
    hook = digest.get("summary", {}).get("hook", "AI intelligence briefing")
    top_titles = []
    for s in digest.get("ai_news", [])[:3]:
        top_titles.append(s.get("title", ""))
    for s in digest.get("world_news", [])[:2]:
        top_titles.append(s.get("title", ""))
    stories_summary = "; ".join(t for t in top_titles if t)

    instructions = (
        f'Create a concise sketch-note style square infographic for "Koda Daily AI Digest" ({date}). '
        f"Today's theme: {hook}. Key stories: {stories_summary}. "
        f"Style: Hand-drawn sketch-note aesthetic with simple icons, arrows, and visual metaphors. "
        f"Clean white/cream background with bold black outlines. Use color sparingly for emphasis "
        f"(blue for AI/tech, red for conflict/world, green for markets/growth). "
        f"Layout: 4 quadrant layout with a bold headline at top connecting the day's themes. "
        f"Each quadrant has a simple icon, bold sub-headline, and 1-2 key facts. "
        f"Keep it scannable and visually engaging. "
        f"STRICT: No recognizable political figures or heads of state."
    )

    async def _generate():
        client_cm = await NotebookLMClient.from_storage()
        client = await client_cm.__aenter__()
        try:
            print("  Generating sketch-note infographic via NotebookLM (square, concise)...")
            status = await client.artifacts.generate_infographic(
                NOTEBOOK_ID,
                instructions=instructions,
                orientation=InfographicOrientation.SQUARE,
                detail_level=InfographicDetail.CONCISE,
            )
            print(f"  Infographic generation started (task: {status.task_id})")

            await client.artifacts.wait_for_completion(
                NOTEBOOK_ID, status.task_id, timeout=120.0
            )

            # Download the infographic
            png_path = hero_path.with_suffix(".png")
            await client.artifacts.download_infographic(NOTEBOOK_ID, str(png_path))
            print(f"  Downloaded infographic PNG: {png_path.stat().st_size // 1024}KB")

            # Convert PNG to JPG for smaller size
            try:
                from PIL import Image
                with Image.open(png_path) as img:
                    rgb = img.convert("RGB")
                    rgb.save(str(hero_path), "JPEG", quality=90)
                png_path.unlink(missing_ok=True)
                print(f"  Converted to JPG: {hero_path.stat().st_size // 1024}KB")
            except ImportError:
                # No PIL, just rename
                png_path.rename(hero_path)
        finally:
            await client_cm.__aexit__(None, None, None)

    try:
        asyncio.run(_generate())
        return _upload_hero_to_supabase(hero_path, date)
    except Exception as e:
        print(f"  WARNING: NotebookLM sketch-note generation failed: {e}")
        return None


def _upload_hero_to_supabase(hero_path: Path, date: str) -> str | None:
    """Upload the email hero to Supabase and return the public URL."""
    if not SUPABASE_URL:
        return None

    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not service_key:
        # Return direct URL assuming it was already uploaded
        return f"{SUPABASE_URL}/storage/v1/object/public/koda-media/email-hero-{date}.jpg"

    filename = f"email-hero-{date}.jpg"
    upload_url = f"{SUPABASE_URL}/storage/v1/object/koda-media/{filename}"

    try:
        with open(hero_path, "rb") as f:
            img_bytes = f.read()

        resp = httpx.put(
            upload_url,
            content=img_bytes,
            headers={
                "Authorization": f"Bearer {service_key}",
                "Content-Type": "image/jpeg",
                "x-upsert": "true",
            },
            timeout=30,
        )
        if resp.status_code in (200, 201):
            public_url = f"{SUPABASE_URL}/storage/v1/object/public/koda-media/{filename}"
            print(f"  Email hero uploaded to Supabase: {filename}")
            return public_url
        else:
            print(f"  WARNING: Supabase upload failed ({resp.status_code}): {resp.text[:200]}")
    except Exception as e:
        print(f"  WARNING: Supabase upload error: {e}")

    return f"{SUPABASE_URL}/storage/v1/object/public/koda-media/{filename}"


def build_email_subject(digest: dict) -> str:
    """Generate a hook-only email subject line. Brand comes from sender name."""
    summary = digest.get("summary", {})
    hook = summary.get("hook", "Your daily AI intelligence briefing is ready.")
    # Keep it punchy -- trim to ~80 chars for mobile preview
    if len(hook) > 80:
        hook = hook[:77] + "..."
    return hook


def _get_editorial_teaser(date: str) -> dict | None:
    """Find today's editorial and extract title + description from HTML meta."""
    import re
    editorial_dir = Path(__file__).parent.parent / "editorial"
    matches = sorted(editorial_dir.glob(f"{date}-*.html"))
    if not matches:
        return None
    try:
        content = matches[0].read_text(encoding="utf-8")[:4000]
        title_m = re.search(r'"headline":\s*"([^"]+)"', content)
        desc_m = re.search(r'og:description"\s+content="([^"]+)"', content)
        url_m = re.search(r'og:url"\s+content="([^"]+)"', content)
        if title_m:
            return {
                "title": title_m.group(1),
                "description": desc_m.group(1) if desc_m else "",
                "url": url_m.group(1) if url_m else f"https://www.koda.community/editorial/{matches[0].name}",
            }
    except Exception:
        pass
    return None


def _section_divider() -> str:
    """Thin line divider between email sections."""
    return """<tr><td style="padding:0 24px"><table width="100%" cellpadding="0" cellspacing="0"><tr>
    <td style="height:1px;background:#1E293B"></td></tr></table></td></tr>"""


CAT_COLORS = {
    "Model Release": "#3B82F6", "Benchmark": "#8B5CF6", "Agents": "#6366F1",
    "Hardware": "#F59E0B", "Enterprise": "#10B981", "Policy": "#EF4444",
    "Open Source": "#8B5CF6", "China": "#EF4444", "Biotech": "#10B981",
    "Design": "#EC4899", "Trend": "#06B6D4", "Consolidation": "#F59E0B",
    "Conflict": "#EF4444", "Diplomacy": "#3B82F6", "Economy": "#10B981",
    "Humanitarian": "#F59E0B", "Infrastructure": "#6366F1", "Climate": "#10B981",
    "Technology": "#3B82F6",
}


def build_email_html(digest: dict, media_status: dict | None, hero_url: str | None = None, send_date: str | None = None) -> str:
    """Generate Rundown AI-inspired newsletter: full stories, not a dashboard teaser."""
    date_label = digest.get("date_label", digest["date"])
    date = send_date or digest.get("date", "")
    summary = digest.get("summary", {})
    hook = summary.get("hook", "Your daily AI intelligence briefing is ready.")
    markets = digest.get("markets", {})
    media = media_status.get("media", {}) if media_status else {}
    ai_news = digest.get("ai_news", [])
    world_news = digest.get("world_news", [])
    tools = digest.get("tools", [])
    digest_url = f"https://www.koda.community/morning-briefing-koda-{date}.html"

    # --- Preview bullets from top stories ---
    preview_items = []
    category_emojis = {
        "Model Release": "&#129302;", "Benchmark": "&#128202;", "Agents": "&#129302;",
        "Hardware": "&#128187;", "Enterprise": "&#127970;", "Policy": "&#128220;",
        "Open Source": "&#128275;", "China": "&#127464;&#127475;", "Biotech": "&#129516;",
        "Conflict": "&#127988;", "Diplomacy": "&#129309;", "Economy": "&#128176;",
    }
    for story in (ai_news[:3] + world_news[:2]):
        emoji = category_emojis.get(story.get("category", ""), "&#128313;")
        preview_items.append(f"{emoji} {story.get('title', '')}")

    preview_html = ""
    for item in preview_items[:5]:
        preview_html += f'<tr><td style="padding:2px 0;font-size:14px;color:#C2C6D6;line-height:1.5">{item}</td></tr>\n'

    # --- Lead story hero image (passed in from generate_email_hero) ---
    lead_hero_html = ""
    if hero_url:
        lead_hero_html = (
            f'<tr><td style="padding:16px 24px 0">'
            f'<div style="max-width:552px;margin:0 auto;overflow:hidden;border-radius:8px;border:1px solid #1E293B">'
            f'<img src="{hero_url}" alt="" width="552" style="width:100%;height:auto;display:block">'
            f'</div></td></tr>'
        )

    # --- Main stories (full body, Rundown format) ---
    main_stories = ai_news[:3] + world_news[:2]
    stories_html = ""
    for i, story in enumerate(main_stories):
        cat = story.get("category", "")
        color = CAT_COLORS.get(cat, "#3B82F6")
        title = story.get("title", "")
        body = story.get("body", "")
        source_name = story.get("source_name", "")
        source_url = story.get("source_url", "")

        source_link = ""
        if source_url and source_name:
            source_link = f"""<p style="margin:8px 0 0"><a href="{source_url}" style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;text-decoration:none;color:{color}" target="_blank">Source: {source_name} &rarr;</a></p>"""
        elif source_name:
            source_link = f'<p style="margin:8px 0 0;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#64748B">Source: {source_name}</p>'

        # Insert lead hero image before the first story
        hero_insert = lead_hero_html if i == 0 else ""

        stories_html += f"""{hero_insert}<tr><td style="padding:20px 24px 0">
          <span style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;color:{color}">{cat}</span>
          <p style="margin:8px 0 0;font-size:17px;font-weight:800;color:#E2E8F0;line-height:1.3">{title}</p>
          <p style="margin:12px 0 0;font-size:14px;color:#C2C6D6;line-height:1.65">{body}</p>
          {source_link}
        </td></tr>"""

    # --- Market snapshot (compact single row) ---
    ticker_map = {"sp500": "S&P", "nasdaq": "NDX", "btc": "BTC", "oil": "Oil", "sentiment": "Mood"}
    market_cells = ""
    for key, label in ticker_map.items():
        data = markets.get(key, {})
        if isinstance(data, dict):
            price = data.get("price", data.get("value", "N/A"))
            change = data.get("change", data.get("label", ""))
            direction = data.get("direction", "neutral")
            color = "#10B981" if direction == "up" else "#EF4444" if direction == "down" else "#F59E0B"
            market_cells += f"""<td style="padding:8px 2px;text-align:center;width:20%;background:#131B2E">
              <span style="display:block;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#8C909F">{label}</span>
              <span style="display:block;font-size:12px;font-weight:700;color:#E2E8F0;font-family:'Courier New',monospace">{price}</span>
              <span style="display:block;font-size:10px;font-family:'Courier New',monospace;color:{color}">{change}</span>
            </td>"""

    # --- Quick hits (remaining stories, fuller summaries) ---
    quick_hit_stories = ai_news[3:7] + world_news[2:4]
    quick_hits_html = ""
    for story in quick_hit_stories[:5]:
        cat = story.get("category", "")
        color = CAT_COLORS.get(cat, "#3B82F6")
        title = story.get("title", "")
        body = story.get("body", "")
        source_name = story.get("source_name", "")
        source_url = story.get("source_url", "")

        src = ""
        if source_url and source_name:
            src = f' <a href="{source_url}" style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;text-decoration:none;color:{color}" target="_blank">Source: {source_name} &rarr;</a>'
        elif source_name:
            src = f' <span style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#64748B">Source: {source_name}</span>'

        quick_hits_html += f"""<tr><td style="padding:10px 0;border-bottom:1px solid #1a2235">
          <span style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;color:{color}">{cat}</span>
          <p style="margin:4px 0 0;font-size:15px;font-weight:700;color:#E2E8F0;line-height:1.3">{title}</p>
          <p style="margin:6px 0 0;font-size:13px;color:#C2C6D6;line-height:1.55">{body}</p>
          <p style="margin:6px 0 0">{src}</p>
        </td></tr>"""

    # --- Tool spotlight ---
    tools_html = ""
    for tool in tools[:3]:
        name = tool.get("title", "")
        desc = tool.get("body", "")
        url = tool.get("url", "")
        cat = tool.get("category", "")
        cat_label = f'<span style="color:#8B5CF6;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px">{cat}</span><br>' if cat else ""
        name_html = f'<a href="{url}" style="color:#E2E8F0;text-decoration:underline;font-weight:700" target="_blank">{name}</a>' if url else f'<span style="color:#E2E8F0;font-weight:700">{name}</span>'
        # First sentence of description
        short_desc = desc.split(". ")[0] + "." if ". " in desc else desc
        tools_html += f"""<tr><td style="padding:6px 0">
          <p style="margin:0;font-size:14px;color:#C2C6D6;line-height:1.5">{cat_label}{name_html} -- {short_desc}</p>
        </td></tr>"""

    # --- Media section (video thumbnail, podcast button, infographic thumbnail) ---
    podcast_url = ""
    yt_url = ""
    yt_video_id = ""
    if media.get("podcast"):
        podcast_url = f"{SUPABASE_URL}/storage/v1/object/public/koda-media/podcast-{date}.mp3" if SUPABASE_URL else f"https://www.koda.community/podcast-{date}.mp3"

    video_result_path = Path(__file__).parent.parent / "youtube-result.json"
    if video_result_path.exists():
        try:
            vr = json.loads(video_result_path.read_text(encoding="utf-8"))
            stamped_date = vr.get("date", "")
            # Only use video if it was uploaded today (prevent stale embeds)
            if date and (not stamped_date or stamped_date != date):
                print(f"  INFO: youtube-result.json is from {stamped_date or 'unknown'}, not {date} -- skipping stale video in email")
            else:
                yt_url = vr.get("url", "")
                yt_video_id = vr.get("video_id", "")
        except Exception:
            pass

    media_html = ""
    has_media = podcast_url or (yt_url and yt_video_id)

    if has_media:
        # Side-by-side layout: video thumbnail left, podcast button right
        video_cell = ""
        podcast_cell = ""

        if yt_url and yt_video_id:
            yt_thumb = f"https://img.youtube.com/vi/{yt_video_id}/maxresdefault.jpg"
            video_cell = f"""<td style="padding:0 4px 0 0;width:50%;vertical-align:top">
              <table width="100%" cellpadding="0" cellspacing="0" style="border-radius:8px;overflow:hidden;border:1px solid #1E293B">
                <tr><td style="height:140px;background:#131B2E;padding:0;vertical-align:middle;text-align:center">
                  <a href="{yt_url}" target="_blank"><img src="{yt_thumb}" alt="Watch video" width="264" style="width:100%;height:140px;object-fit:cover;display:block"></a>
                </td></tr>
                <tr><td style="padding:0">
                  <a href="{yt_url}" style="display:block;padding:12px 8px;background:#EC4899;color:white;text-decoration:none;text-align:center;font-weight:700;font-size:12px" target="_blank">&#9654; Watch Video</a>
                </td></tr>
              </table>
            </td>"""

        if podcast_url:
            podcast_cell = f"""<td style="padding:0 0 0 4px;width:50%;vertical-align:top">
              <table width="100%" cellpadding="0" cellspacing="0" style="border-radius:8px;overflow:hidden;border:1px solid #1E293B">
                <tr><td style="height:140px;background:#131B2E;padding:0;text-align:center;vertical-align:middle">
                  <p style="margin:0 0 8px;font-size:36px;line-height:1">&#127911;</p>
                  <p style="margin:0 0 4px;font-size:14px;font-weight:800;color:#E2E8F0">Daily Podcast</p>
                  <p style="margin:0;font-size:11px;color:#94A3B8">~22 min deep dive</p>
                </td></tr>
                <tr><td style="padding:0">
                  <a href="{podcast_url}" style="display:block;padding:12px 8px;background:#6366F1;color:white;text-decoration:none;text-align:center;font-weight:700;font-size:12px" target="_blank">&#9654; Listen Now</a>
                </td></tr>
              </table>
            </td>"""

        # If only one is available, it gets full width
        if video_cell and podcast_cell:
            cells = video_cell + podcast_cell
        elif video_cell:
            cells = video_cell.replace("width:50%", "width:100%")
        else:
            cells = podcast_cell.replace("width:50%", "width:100%")

        media_html = f"""<tr><td style="padding:20px 24px 0">
          <p style="margin:0 0 12px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:2px;color:#8C909F">Today's Media</p>
          <table width="100%" cellpadding="0" cellspacing="0"><tr>{cells}</tr></table>
        </td></tr>"""

    # --- Editorial teaser with hero image ---
    editorial = _get_editorial_teaser(date)
    editorial_html = ""
    if editorial:
        # Try to find the editorial hero image on Supabase
        editorial_hero_img = ""
        editorial_hero_url = f"{SUPABASE_URL}/storage/v1/object/public/koda-media/editorial-hero-{date}.jpg" if SUPABASE_URL else ""
        editorial_hero_local = Path(__file__).parent.parent / "editorial" / f"editorial-hero-{date}.jpg"
        if editorial_hero_local.exists() and editorial_hero_url:
            editorial_hero_img = f'<a href="{editorial["url"]}" target="_blank"><img src="{editorial_hero_url}" alt="" width="520" style="width:100%;max-width:520px;height:140px;object-fit:cover;display:block;border-radius:6px 6px 0 0;border:1px solid #1E293B;border-bottom:none"></a>'

        editorial_html = f"""
    {_section_divider()}
    <tr><td style="padding:20px 24px">
      <p style="margin:0 0 10px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:2px;color:#8C909F">Today's Editorial</p>
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#131B2E;border-left:3px solid #6366F1">
        <tr><td style="padding:0">{editorial_hero_img}</td></tr>
        <tr><td style="padding:16px">
          <p style="margin:0 0 6px;font-size:16px;font-weight:800;color:#E2E8F0;line-height:1.3">{editorial['title']}</p>
          <p style="margin:0 0 12px;font-size:13px;color:#94A3B8;line-height:1.5">{editorial['description']}</p>
          <a href="{editorial['url']}" style="color:#6366F1;font-size:13px;font-weight:700;text-decoration:none" target="_blank">Read the full analysis &#8594;</a>
        </td></tr>
      </table>
    </td></tr>"""

    # ========== ASSEMBLE EMAIL ==========
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta name="color-scheme" content="dark"><meta name="supported-color-schemes" content="dark">
<title>Koda Daily Digest | {date_label}</title></head>
<body style="margin:0;padding:0;background:#0B1326;font-family:Arial,Helvetica,sans-serif;-webkit-font-smoothing:antialiased">

<table width="100%" cellpadding="0" cellspacing="0" style="background:#0B1326">
<tr><td align="center" style="padding:16px 12px">

<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#0F172A">

  <!-- Header -->
  <tr><td style="padding:28px 24px 24px;text-align:center;background:linear-gradient(135deg,#1E293B 0%,#312E81 50%,#1E293B 100%)">
    <table cellpadding="0" cellspacing="0" style="margin:0 auto 12px"><tr>
      <td style="width:36px;height:36px;background:linear-gradient(135deg,#3B82F6,#8B5CF6);text-align:center;line-height:36px;color:white;font-weight:900;font-size:16px">K</td>
    </tr></table>
    <h1 style="margin:0;color:white;font-size:22px;font-weight:800;letter-spacing:-0.5px">Koda Daily Digest</h1>
    <p style="margin:6px 0 0;color:#94A3B8;font-size:12px;text-transform:uppercase;letter-spacing:2px">{date_label}</p>
  </td></tr>

  <!-- Accent line -->
  <tr><td style="padding:0"><table width="100%" cellpadding="0" cellspacing="0"><tr>
    <td style="height:2px;background:linear-gradient(90deg,#3B82F6,#8B5CF6,#EC4899)"></td>
  </tr></table></td></tr>

  <!-- Opening hook -->
  <tr><td style="padding:24px 24px 0">
    <p style="margin:0 0 16px;color:#E2E8F0;font-size:18px;font-weight:800;line-height:1.35">{hook}</p>
  </td></tr>

  <!-- In today's digest -->
  <tr><td style="padding:0 24px 20px">
    <p style="margin:0 0 8px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;color:#64748B">In today's digest:</p>
    <table width="100%" cellpadding="0" cellspacing="0">
      {preview_html}
    </table>
  </td></tr>

  <!-- Market snapshot -->
  <tr><td style="padding:16px 24px 0">
    <p style="margin:0 0 10px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:2px;color:#8C909F">Market Snapshot</p>
    <table width="100%" cellpadding="0" cellspacing="4" style="border-spacing:4px">
      <tr>{market_cells}</tr>
    </table>
  </td></tr>

  {_section_divider()}

  <!-- Main stories -->
  {stories_html}

  {_section_divider()}

  <!-- Quick hits -->
  <tr><td style="padding:20px 24px 0">
    <p style="margin:0 0 10px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:2px;color:#8C909F">Everything Else in AI Today</p>
    <table width="100%" cellpadding="0" cellspacing="0">
      {quick_hits_html}
    </table>
  </td></tr>

  {_section_divider()}

  <!-- Tool spotlight -->
  <tr><td style="padding:20px 24px 0">
    <p style="margin:0 0 10px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:2px;color:#8C909F">Tools Worth Trying</p>
    <table width="100%" cellpadding="0" cellspacing="0">
      {tools_html}
    </table>
  </td></tr>

  <!-- Media buttons -->
  {media_html}

  <!-- Editorial teaser -->
  {editorial_html}

  {_section_divider()}

  <!-- CTA -->
  <tr><td style="padding:24px 24px 28px;text-align:center">
    <a href="{digest_url}"
      style="display:inline-block;padding:16px 40px;background:#3B82F6;color:white;text-decoration:none;font-weight:800;font-size:15px;letter-spacing:0.5px;border-radius:4px" target="_blank">READ THE FULL DIGEST</a>
    <p style="margin:12px 0 0;font-size:12px;color:#64748B">Includes competitive landscape, newsletter intelligence, and more</p>
  </td></tr>

  <!-- Footer -->
  <tr><td style="padding:20px 24px;border-top:1px solid #1E293B;text-align:center">
    <p style="margin:0 0 6px;font-size:12px;font-weight:700;color:#3B82F6">Koda Intelligence</p>
    <p style="margin:0 0 8px;font-size:11px;color:#64748B">
      <a href="https://www.koda.community" style="color:#64748B;text-decoration:none">koda.community</a>
    </p>
    <p style="margin:0;font-size:10px;color:#475569">
      <a href="{{{{UNSUBSCRIBE_URL}}}}" style="color:#475569;text-decoration:underline">Unsubscribe</a>
    </p>
  </td></tr>

</table>
</td></tr>
</table>
</body></html>"""

    return html


def generate_unsubscribe_token(email: str) -> str:
    """Generate an HMAC token for a given email to prevent unauthorized unsubscribes."""
    return hmac.new(
        UNSUBSCRIBE_SECRET.encode(), email.lower().encode(), hashlib.sha256
    ).hexdigest()[:32]


def build_unsubscribe_url(email: str) -> str:
    """Build a personalized unsubscribe URL for a subscriber."""
    from urllib.parse import quote
    token = generate_unsubscribe_token(email)
    return f"https://www.koda.community/api/unsubscribe?email={quote(email, safe='')}&token={token}"


def fetch_beehiiv_subscribers() -> list[str]:
    """Fetch active subscriber emails from Beehiiv. Returns list of emails."""
    if not BEEHIIV_API_KEY or not BEEHIIV_PUBLICATION_ID:
        print("  Beehiiv: not configured (missing API key or publication ID)")
        return []

    pub_id = BEEHIIV_PUBLICATION_ID
    if not pub_id.startswith("pub_"):
        pub_id = f"pub_{pub_id}"

    all_emails = []
    page = None

    try:
        while True:
            params = {"limit": 100}
            if page:
                params["page"] = page

            resp = httpx.get(
                f"https://api.beehiiv.com/v2/publications/{pub_id}/subscriptions",
                headers={"Authorization": f"Bearer {BEEHIIV_API_KEY}"},
                params=params,
                timeout=15,
            )

            if resp.status_code != 200:
                print(f"  Beehiiv: failed to fetch subscribers ({resp.status_code})")
                break

            data = resp.json()
            subs = data.get("data", [])
            for sub in subs:
                if sub.get("status") == "active":
                    all_emails.append(sub["email"])

            # Pagination
            next_page = data.get("next_page")
            if not next_page:
                break
            page = next_page

        print(f"  Beehiiv: fetched {len(all_emails)} active subscribers")
        return all_emails

    except Exception as e:
        print(f"  Beehiiv: error fetching subscribers: {e}")
        return []


def get_gmail_credentials():
    """Get Gmail API credentials, reusing YouTube OAuth client."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("  WARNING: google-auth packages not installed.")
        print("  Run: pip install google-auth google-auth-oauthlib google-api-python-client")
        return None

    creds = None

    # Try loading existing Gmail token
    if GMAIL_TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(GMAIL_TOKEN_PATH), GMAIL_SCOPES)

    # Refresh or get new token
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(GMAIL_TOKEN_PATH, "w") as f:
                f.write(creds.to_json())
        except Exception as e:
            print(f"  Token refresh failed: {e}")
            print("  This usually means the refresh token was revoked. Re-authorize locally.")
            creds = None

    if not creds or not creds.valid:
        # Detect headless/CI environments where interactive OAuth would hang
        is_headless = (
            os.environ.get("RAILWAY_ENVIRONMENT")
            or os.environ.get("CI")
            or (not os.environ.get("DISPLAY") and sys.platform != "win32")
        )
        if is_headless:
            print("  ERROR: Gmail token expired/invalid and interactive OAuth not available in headless env.")
            print("  ACTION: Refresh .gmail_token.json locally, re-encode to GMAIL_TOKEN_B64, update Railway env var.")
            return None

        # Reuse the YouTube OAuth client credentials (local dev only)
        yt_token_path = DIGEST_DIR / ".youtube_token.json"
        if not yt_token_path.exists():
            print("  No YouTube token found to extract OAuth client from.")
            return None

        with open(yt_token_path) as f:
            yt_data = json.load(f)

        client_config = {
            "installed": {
                "client_id": yt_data["client_id"],
                "client_secret": yt_data["client_secret"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": yt_data["token_uri"],
                "redirect_uris": ["http://localhost"],
            }
        }

        flow = InstalledAppFlow.from_client_config(client_config, GMAIL_SCOPES)
        creds = flow.run_local_server(port=0)

        with open(GMAIL_TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
        print(f"  Gmail token saved to {GMAIL_TOKEN_PATH}")

    return creds


def send_email_gmail_api(subject, html_template, recipients, sender_email="saffaboyjm@gmail.com"):
    """Send individual emails via Gmail API. Each recipient gets a personalized
    unsubscribe link and cannot see other recipients' addresses."""
    creds = get_gmail_credentials()
    if not creds:
        return False

    try:
        from googleapiclient.discovery import build
    except ImportError:
        print("  WARNING: google-api-python-client not installed.")
        return False

    service = build("gmail", "v1", credentials=creds)
    sent_count = 0

    for recipient in recipients:
        # Personalize unsubscribe link for this recipient
        unsub_url = build_unsubscribe_url(recipient)
        html_body = html_template.replace("{{UNSUBSCRIBE_URL}}", unsub_url)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Koda Digest <{sender_email}>"
        msg["To"] = recipient
        msg.attach(MIMEText(html_body, "html"))

        try:
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            service.users().messages().send(
                userId="me", body={"raw": raw}
            ).execute()
            sent_count += 1
        except Exception as e:
            print(f"  Failed to send to {recipient}: {e}")

    print(f"  Sent to {sent_count}/{len(recipients)} recipients")
    return sent_count > 0


def main():
    parser = argparse.ArgumentParser(description="Step 07: Send newsletter email")
    parser.add_argument("--date", default=today_str(), help="Date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Generate email but don't send")
    args = parser.parse_args()

    print(f"[07] Preparing newsletter email for {args.date}")

    digest = read_json("digest-content.json")
    media_status = read_json("media-status.json")

    if not digest:
        print("  ERROR: digest-content.json not found. Run 03_synthesize_content.py first.")
        sys.exit(1)

    digest_date = digest.get("date", "")
    if digest_date != args.date:
        print(f"  ERROR: digest-content.json date={digest_date} but --date={args.date}. Stale content, aborting.")
        sys.exit(1)

    # Generate fresh hero image for the email
    print("  Generating email hero image...")
    hero_url = generate_email_hero(digest, args.date)

    subject = build_email_subject(digest)
    html_body = build_email_html(digest, media_status, hero_url=hero_url, send_date=args.date)

    # Fetch subscribers from Beehiiv (dynamic list)
    print("  Fetching subscriber list from Beehiiv...")
    subscribers = fetch_beehiiv_subscribers()
    if not subscribers:
        print("  No Beehiiv subscribers found, using static fallback list")
        subscribers = EMAIL_RECIPIENTS

    print(f"  Subject: {subject}")
    print(f"  Recipients: {len(subscribers)} (via BCC)")
    print(f"  HTML body: {len(html_body)} chars")

    # Save email for reference
    email_data = {
        "date": args.date,
        "subject": subject,
        "recipients": subscribers,
        "html_body": html_body,
        "generated_at": datetime.now().isoformat(),
    }
    path = write_json("email-draft.json", email_data)
    print(f"  Saved draft to {path}")

    if args.dry_run:
        print("  DRY RUN | email not sent")
        preview_path = os.path.join(os.path.dirname(str(path)), "email-preview.html")
        with open(preview_path, "w", encoding="utf-8") as f:
            f.write(html_body)
        print(f"  Preview: {preview_path}")
        return

    # Send via Gmail API with BCC (recipients can't see each other)
    print("  Sending via Gmail API (BCC)...")
    gmail_sent = send_email_gmail_api(subject, html_body, subscribers)
    if not gmail_sent:
        print("  Gmail send failed | draft saved to email-draft.json")


if __name__ == "__main__":
    main()
