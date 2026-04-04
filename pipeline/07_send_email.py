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


SUBJECT_EMOJIS: dict[str, str] = {
    "Model Release": "\U0001f680",  # rocket
    "Benchmark": "\U0001f4ca",      # bar chart
    "Agents": "\U0001f916",         # robot
    "Hardware": "\U0001f4bb",       # laptop
    "Enterprise": "\U0001f3e2",     # office
    "Policy": "\U0001f4dc",         # scroll
    "Open Source": "\U0001f513",    # unlock
    "China": "\U0001f30f",          # globe
    "Biotech": "\U0001f9ec",        # DNA
    "Conflict": "\u26a1",           # zap
    "Economy": "\U0001f4b0",        # money bag
    "Trend": "\U0001f525",          # fire
    "Diplomacy": "\U0001f91d",      # handshake
    "Technology": "\U0001f4a1",     # light bulb
}


def build_email_subject(digest: dict) -> str:
    """Generate emoji + hook subject line matching Rundown AI / TLDR style."""
    summary = digest.get("summary", {})
    hook = summary.get("hook", "Your daily AI intelligence briefing is ready.")
    # Pick emoji from top story category
    ai_news = digest.get("ai_news", [])
    top_cat = ai_news[0].get("category", "") if ai_news else ""
    emoji = SUBJECT_EMOJIS.get(top_cat, "\U0001f4a1")
    # Trim hook to ~65 chars to leave room for emoji
    if len(hook) > 65:
        hook = hook[:62] + "..."
    return f"{emoji} {hook}"


def build_email_preheader(digest: dict) -> str:
    """Generate hidden preview text from stories 2-3 (shown in inbox preview)."""
    ai_news = digest.get("ai_news", [])
    world_news = digest.get("world_news", [])
    titles = []
    for s in (ai_news[1:3] + world_news[:1]):
        t = s.get("title", "")
        if t:
            titles.append(t)
    if titles:
        return "PLUS: " + " | ".join(titles)
    return "AI developments, markets, tools, and more"


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
    """Gradient accent bar divider between email sections."""
    return """<tr><td style="padding:12px 24px"><table width="100%" cellpadding="0" cellspacing="0"><tr>
    <td style="height:3px;background:linear-gradient(90deg,#3B82F6,#8B5CF6,#EC4899);border-radius:2px"></td></tr></table></td></tr>"""


def _section_header(title: str) -> str:
    """Named section header with branded styling."""
    return f"""<tr><td style="padding:20px 24px 8px">
    <p style="margin:0;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:2px;color:#6366F1">{title}</p>
  </td></tr>"""


def _cat_badge(cat: str) -> str:
    """Render a category as a filled pill badge."""
    color = CAT_COLORS.get(cat, "#3B82F6")
    return f'<span style="display:inline-block;background:{color};color:white;padding:2px 10px;border-radius:12px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px">{cat}</span>'


def _fetch_live_markets() -> dict:
    """Fetch live market data from free APIs when digest markets are empty."""
    result: dict = {}
    try:
        # Yahoo Finance v8 API (no key needed)
        symbols = {
            "^GSPC": "sp500",
            "^IXIC": "nasdaq",
            "BTC-USD": "btc",
            "CL=F": "oil",
        }
        for symbol, key in symbols.items():
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1d&interval=1d"
                resp = httpx.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200:
                    data = resp.json()
                    meta = data["chart"]["result"][0]["meta"]
                    price = meta["regularMarketPrice"]
                    prev = meta.get("chartPreviousClose", meta.get("previousClose", price))
                    pct = ((price - prev) / prev * 100) if prev else 0
                    direction = "up" if pct > 0 else "down" if pct < 0 else "neutral"
                    # Format price
                    if key == "btc":
                        price_str = f"${price:,.0f}"
                    elif key == "oil":
                        price_str = f"${price:.2f}"
                    else:
                        price_str = f"{price:,.2f}"
                    result[key] = {
                        "price": price_str,
                        "change": f"{pct:+.2f}%",
                        "direction": direction,
                    }
            except Exception:
                pass

        # Fear & Greed Index
        try:
            fg_resp = httpx.get("https://api.alternative.me/fng/?limit=1", timeout=5)
            if fg_resp.status_code == 200:
                fg = fg_resp.json()["data"][0]
                val = int(fg["value"])
                label = fg["value_classification"]
                direction = "up" if val > 50 else "down"
                result["sentiment"] = {"value": str(val), "label": label, "direction": direction}
        except Exception:
            pass

        if result:
            print(f"  Live market data fetched: {list(result.keys())}")
    except Exception as e:
        print(f"  WARNING: Live market fetch failed: {e}")
    return result


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
    """Generate best-in-class light-mode newsletter inspired by Rundown AI, TLDR, Superhuman."""
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
    preheader = build_email_preheader(digest)

    # --- TODAY'S RUNDOWN (TOC with emoji markers) ---
    category_emojis = {
        "Model Release": "&#129302;", "Benchmark": "&#128202;", "Agents": "&#129302;",
        "Hardware": "&#128187;", "Enterprise": "&#127970;", "Policy": "&#128220;",
        "Open Source": "&#128275;", "China": "&#127464;&#127475;", "Biotech": "&#129516;",
        "Conflict": "&#9889;", "Diplomacy": "&#129309;", "Economy": "&#128176;",
        "Trend": "&#128293;", "Technology": "&#128161;",
    }
    toc_html = ""
    for i, story in enumerate((ai_news[:3] + world_news[:2])[:5]):
        emoji = category_emojis.get(story.get("category", ""), "&#128313;")
        toc_html += f'<tr><td style="padding:3px 0;font-size:14px;color:#334155;line-height:1.5">{emoji} {story.get("title", "")}</td></tr>\n'

    # --- HERO IMAGE ---
    # Fixed-height img with object-fit:cover crops the square infographic to a
    # landscape banner. object-fit is supported in Apple Mail, Gmail app, Yahoo
    # app, and all modern webmail. Outlook desktop ignores it but still shows
    # the image (just uncropped). The height values give a clean 16:9ish crop
    # that works at any width.
    hero_html = ""
    if hero_url:
        hero_html = (
            f'<tr><td style="padding:16px 24px 0;line-height:0;font-size:0">'
            f'<img class="hero-img" src="{hero_url}" alt="Today\'s AI digest visual" width="552" height="240" '
            f'style="width:100%;max-width:552px;height:240px;object-fit:cover;object-position:top center;'
            f'display:block;border-radius:10px;border:1px solid #E2E8F0">'
            f'</td></tr>'
        )

    # --- AI FRONTLINE (main stories, tight format: lead + max 3 bullets) ---
    main_stories = ai_news[:3] + world_news[:2]
    stories_html = ""
    for i, story in enumerate(main_stories):
        cat = story.get("category", "")
        title = story.get("title", "")
        body = story.get("body", "")
        source_name = story.get("source_name", "")
        source_url = story.get("source_url", "")
        color = CAT_COLORS.get(cat, "#3B82F6")

        # Insert hero before first story
        if i == 0:
            stories_html += hero_html

        # Source link
        source_link = ""
        if source_url and source_name:
            source_link = f'<p style="margin:8px 0 0"><a href="{source_url}" style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;text-decoration:none;color:{color}" target="_blank">{source_name} &#8594;</a></p>'

        # Tight format: 1 lead sentence + max 3 bullet points (no "why it matters" block)
        sentences = [s.strip() for s in body.split(". ") if s.strip()]
        if len(sentences) >= 3:
            lead = sentences[0] + "."
            bullets = ""
            for s in sentences[1:4]:  # max 3 bullets
                clean = s.rstrip(".")
                bullets += f'<li style="margin:0 0 3px;font-size:13px;color:#475569;line-height:1.5">{clean}.</li>'
            body_html = (
                f'<p style="margin:8px 0 6px;font-size:14px;color:#334155;line-height:1.55">{lead}</p>'
                f'<ul style="margin:0;padding-left:18px">{bullets}</ul>'
            )
        elif len(sentences) == 2:
            body_html = f'<p style="margin:8px 0 0;font-size:14px;color:#334155;line-height:1.55">{sentences[0]}. {sentences[1]}.</p>'
        else:
            body_html = f'<p style="margin:8px 0 0;font-size:14px;color:#475569;line-height:1.55">{body}</p>'

        # Separator between stories (not before first)
        sep = '<tr><td style="padding:0 24px"><table width="100%" cellpadding="0" cellspacing="0"><tr><td style="height:1px;background:#E2E8F0"></td></tr></table></td></tr>' if i > 0 else ""

        stories_html += f"""{sep}<tr><td style="padding:16px 24px 0">
          {_cat_badge(cat)}
          <p style="margin:8px 0 0;font-size:17px;font-weight:800;color:#0F172A;line-height:1.3">{title}</p>
          {body_html}
          {source_link}
        </td></tr>"""

    # --- MARKET PULSE (compact row, light background) ---
    # If markets dict is empty, try to fetch live data
    if not markets:
        markets = _fetch_live_markets()

    ticker_map = {"sp500": "S&P", "nasdaq": "NDX", "btc": "BTC", "oil": "Oil", "sentiment": "Mood"}
    market_cells = ""
    for key, label in ticker_map.items():
        data = markets.get(key, {})
        if isinstance(data, dict) and data:
            price = data.get("price", data.get("value", "N/A"))
            change = data.get("change", data.get("label", ""))
            direction = data.get("direction", "neutral")
            color = "#10B981" if direction == "up" else "#EF4444" if direction == "down" else "#F59E0B"
            market_cells += f"""<td style="padding:8px 2px;text-align:center;width:20%;background:#F1F5F9;border-radius:6px">
              <span style="display:block;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#64748B">{label}</span>
              <span style="display:block;font-size:12px;font-weight:700;color:#0F172A;font-family:'Courier New',monospace">{price}</span>
              <span style="display:block;font-size:10px;font-family:'Courier New',monospace;color:{color}">{change}</span>
            </td>"""

    # --- SPEED ROUND (remaining stories, brief) ---
    quick_hit_stories = ai_news[3:7] + world_news[2:4]
    quick_hits_html = ""
    for story in quick_hit_stories[:5]:
        cat = story.get("category", "")
        color = CAT_COLORS.get(cat, "#3B82F6")
        title = story.get("title", "")
        body = story.get("body", "")
        source_name = story.get("source_name", "")
        source_url = story.get("source_url", "")
        # First sentence only for speed round
        short_body = body.split(". ")[0] + "." if ". " in body else body

        src = ""
        if source_url and source_name:
            src = f' <a href="{source_url}" style="font-size:11px;font-weight:700;text-decoration:none;color:{color}" target="_blank">{source_name} &#8594;</a>'

        quick_hits_html += f"""<tr><td style="padding:10px 0;border-bottom:1px solid #E2E8F0">
          {_cat_badge(cat)}
          <p style="margin:6px 0 0;font-size:15px;font-weight:700;color:#0F172A;line-height:1.3">{title}</p>
          <p style="margin:4px 0 0;font-size:13px;color:#475569;line-height:1.5">{short_body}{src}</p>
        </td></tr>"""

    # --- TOOL DROP (emoji + name + description + Lab Report link) ---
    tool_emojis = ["&#128640;", "&#9889;", "&#128161;", "&#128295;", "&#127775;"]
    tools_html = ""
    for i, tool in enumerate(tools[:3]):
        name = tool.get("title", "")
        desc = tool.get("body", "")
        url = tool.get("url", "")
        review_url = tool.get("review_url", "")
        emoji = tool_emojis[i % len(tool_emojis)]
        # Use first two sentences instead of one
        sentences = desc.split(". ")
        short_desc = ". ".join(sentences[:2]) + "." if len(sentences) > 1 else desc
        name_html = f'<a href="{url}" style="color:#0F172A;text-decoration:underline;font-weight:700" target="_blank">{name}</a>' if url else f'<strong style="color:#0F172A">{name}</strong>'
        review_link = ""
        if review_url:
            full_review_url = f"https://www.koda.community{review_url}"
            review_link = f' <a href="{full_review_url}" style="color:#6366F1;font-size:12px;font-weight:600;text-decoration:underline" target="_blank">Lab Report &rarr;</a>'
        tools_html += f"""<tr><td style="padding:8px 0">
          <p style="margin:0;font-size:14px;color:#475569;line-height:1.5">{emoji} {name_html} -- {short_desc}</p>
          {f'<p style="margin:4px 0 0">{review_link}</p>' if review_link else ''}
        </td></tr>"""

    # --- LISTEN & WATCH (media section) ---
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
        video_cell = ""
        podcast_cell = ""

        if yt_url and yt_video_id:
            yt_thumb = f"https://img.youtube.com/vi/{yt_video_id}/maxresdefault.jpg"
            video_cell = f"""<td style="padding:0 4px 0 0;width:50%;vertical-align:top">
              <table width="100%" cellpadding="0" cellspacing="0" style="border-radius:10px;overflow:hidden;border:1px solid #E2E8F0">
                <tr><td style="height:140px;background:#F1F5F9;padding:0;vertical-align:middle;text-align:center">
                  <a href="{yt_url}" target="_blank"><img src="{yt_thumb}" alt="Watch video" width="264" style="width:100%;height:140px;object-fit:cover;display:block"></a>
                </td></tr>
                <tr><td style="padding:0">
                  <a href="{yt_url}" style="display:block;padding:12px 8px;background:linear-gradient(135deg,#EC4899,#8B5CF6);color:white;text-decoration:none;text-align:center;font-weight:700;font-size:12px" target="_blank">&#9654; Watch Video</a>
                </td></tr>
              </table>
            </td>"""

        if podcast_url:
            podcast_cell = f"""<td style="padding:0 0 0 4px;width:50%;vertical-align:top">
              <table width="100%" cellpadding="0" cellspacing="0" style="border-radius:10px;overflow:hidden;border:1px solid #E2E8F0">
                <tr><td style="height:140px;background:#F1F5F9;padding:0;text-align:center;vertical-align:middle">
                  <p style="margin:0 0 8px;font-size:36px;line-height:1">&#127911;</p>
                  <p style="margin:0 0 4px;font-size:14px;font-weight:800;color:#0F172A">Daily Podcast</p>
                  <p style="margin:0;font-size:11px;color:#64748B">~22 min deep dive</p>
                </td></tr>
                <tr><td style="padding:0">
                  <a href="{podcast_url}" style="display:block;padding:12px 8px;background:linear-gradient(135deg,#6366F1,#3B82F6);color:white;text-decoration:none;text-align:center;font-weight:700;font-size:12px" target="_blank">&#9654; Listen Now</a>
                </td></tr>
              </table>
            </td>"""

        if video_cell and podcast_cell:
            cells = video_cell + podcast_cell
        elif video_cell:
            cells = video_cell.replace("width:50%", "width:100%")
        else:
            cells = podcast_cell.replace("width:50%", "width:100%")

        media_html = f"""{_section_header("Listen & Watch")}
        <tr><td style="padding:0 24px">
          <table width="100%" cellpadding="0" cellspacing="0"><tr>{cells}</tr></table>
        </td></tr>"""

    # --- DEEP DIVE (editorial teaser) ---
    editorial = _get_editorial_teaser(date)
    editorial_html = ""

    # --- DEEP DIVE MEDIA (editorial audio + anime video) ---
    editorial_media_status = read_json("editorial-media-status.json")
    editorial_media_html = ""
    if editorial:
        editorial_hero_img = ""
        editorial_hero_url = f"{SUPABASE_URL}/storage/v1/object/public/koda-media/editorial-hero-{date}.jpg" if SUPABASE_URL else ""
        editorial_hero_local = Path(__file__).parent.parent / "editorial" / f"editorial-hero-{date}.jpg"
        if editorial_hero_local.exists() and editorial_hero_url:
            editorial_hero_img = f'<a href="{editorial["url"]}" target="_blank"><img src="{editorial_hero_url}" alt="" width="520" style="width:100%;max-width:520px;height:140px;object-fit:cover;display:block;border-radius:10px 10px 0 0"></a>'

        editorial_html = f"""
    {_section_header("Deep Dive")}
    <tr><td style="padding:0 24px">
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;overflow:hidden">
        <tr><td style="padding:0">{editorial_hero_img}</td></tr>
        <tr><td style="padding:16px">
          <p style="margin:0 0 6px;font-size:16px;font-weight:800;color:#0F172A;line-height:1.3">{editorial['title']}</p>
          <p style="margin:0 0 12px;font-size:13px;color:#64748B;line-height:1.5">{editorial['description']}</p>
          <a href="{editorial['url']}" style="color:#6366F1;font-size:13px;font-weight:700;text-decoration:none" target="_blank">Read the full analysis &#8594;</a>
        </td></tr>
      </table>
    </td></tr>"""

    # Build Deep Dive Media strip if editorial media was generated
    if editorial_media_status:
        ed_audio = editorial_media_status.get("editorial_audio", {})
        ed_video = editorial_media_status.get("editorial_video", {})
        ed_audio_url = ed_audio.get("path", "") if isinstance(ed_audio, dict) else ""
        ed_yt_id = ed_video.get("youtube_id", "") if isinstance(ed_video, dict) else ""

        has_ed_media = bool(ed_audio_url) or bool(ed_yt_id)
        if has_ed_media:
            ed_audio_cell = ""
            ed_video_cell = ""

            if ed_audio_url:
                ed_audio_cell = f"""<td style="padding:0 4px 0 0;width:50%;vertical-align:top">
                  <table width="100%" cellpadding="0" cellspacing="0" style="border-radius:10px;overflow:hidden;border:1px solid #E2E8F0">
                    <tr><td style="height:100px;background:#F1F5F9;padding:0;text-align:center;vertical-align:middle">
                      <p style="margin:0 0 4px;font-size:28px;line-height:1">&#127911;</p>
                      <p style="margin:0 0 4px;font-size:13px;font-weight:800;color:#0F172A">Deep Dive Audio</p>
                      <p style="margin:0;font-size:10px;color:#64748B">~5 min brief</p>
                    </td></tr>
                    <tr><td style="padding:0">
                      <a href="{ed_audio_url}" style="display:block;padding:10px 8px;background:linear-gradient(135deg,#6366F1,#3B82F6);color:white;text-decoration:none;text-align:center;font-weight:700;font-size:11px" target="_blank">&#9654; Listen Now</a>
                    </td></tr>
                  </table>
                </td>"""

            if ed_yt_id:
                ed_video_cell = f"""<td style="padding:0 0 0 4px;width:50%;vertical-align:top">
                  <table width="100%" cellpadding="0" cellspacing="0" style="border-radius:10px;overflow:hidden;border:1px solid #E2E8F0">
                    <tr><td style="height:100px;background:#F1F5F9;padding:0;text-align:center;vertical-align:middle">
                      <p style="margin:0 0 4px;font-size:28px;line-height:1">&#127916;</p>
                      <p style="margin:0 0 4px;font-size:13px;font-weight:800;color:#0F172A">Anime Brief</p>
                      <p style="margin:0;font-size:10px;color:#64748B">~2 min visual dive</p>
                    </td></tr>
                    <tr><td style="padding:0">
                      <a href="https://www.youtube.com/watch?v={ed_yt_id}" style="display:block;padding:10px 8px;background:linear-gradient(135deg,#EC4899,#8B5CF6);color:white;text-decoration:none;text-align:center;font-weight:700;font-size:11px" target="_blank">&#9654; Watch Video</a>
                    </td></tr>
                  </table>
                </td>"""

            if ed_audio_cell and ed_video_cell:
                ed_cells = ed_audio_cell + ed_video_cell
            elif ed_audio_cell:
                ed_cells = ed_audio_cell.replace("width:50%", "width:100%")
            else:
                ed_cells = ed_video_cell.replace("width:50%", "width:100%")

            editorial_media_html = f"""<tr><td style="padding:16px 24px 0">
      <p style="margin:0 0 12px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;color:#8B5CF6">DEEP DIVE MEDIA</p>
    </td></tr>
    <tr><td style="padding:0 24px">
      <table width="100%" cellpadding="0" cellspacing="0"><tr>{ed_cells}</tr></table>
    </td></tr>"""

    # --- RATE THIS ISSUE (1-click emoji poll) ---
    rate_base = f"{digest_url}?utm_source=email&utm_medium=rating&rating="
    rating_html = f"""<tr><td style="padding:24px 24px 0;text-align:center">
      <p style="margin:0 0 10px;font-size:13px;font-weight:700;color:#334155">How was today's digest?</p>
      <table cellpadding="0" cellspacing="0" style="margin:0 auto"><tr>
        <td style="padding:0 12px"><a href="{rate_base}great" style="text-decoration:none;font-size:28px" target="_blank">&#128293;</a><br><span style="font-size:11px;color:#64748B">Great</span></td>
        <td style="padding:0 12px"><a href="{rate_base}good" style="text-decoration:none;font-size:28px" target="_blank">&#128077;</a><br><span style="font-size:11px;color:#64748B">Good</span></td>
        <td style="padding:0 12px"><a href="{rate_base}meh" style="text-decoration:none;font-size:28px" target="_blank">&#128528;</a><br><span style="font-size:11px;color:#64748B">Meh</span></td>
      </tr></table>
    </td></tr>"""

    # ========== ASSEMBLE EMAIL ==========
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta name="color-scheme" content="light dark"><meta name="supported-color-schemes" content="light dark">
<title>Koda Daily Digest | {date_label}</title>
<style>
@media screen and (max-width:480px){{.hero-img{{height:180px!important}}}}
@media (prefers-color-scheme:dark){{.email-body{{background:#1a1a2e!important}}.email-container{{background:#16213e!important}}.text-primary{{color:#E2E8F0!important}}.text-secondary{{color:#94A3B8!important}}.market-cell{{background:#1E293B!important}}.card-bg{{background:#1E293B!important;border-color:#334155!important}}}}
</style>
</head>
<body style="margin:0;padding:0;background:#F8FAFC;font-family:Arial,Helvetica,sans-serif;-webkit-font-smoothing:antialiased">
<!--[if mso]><style>table{{border-collapse:collapse}}</style><![endif]-->
<!-- Preheader text (hidden, shows in inbox preview) -->
<div style="display:none;max-height:0;overflow:hidden;mso-hide:all">{preheader}</div>
<div style="display:none;max-height:0;overflow:hidden;mso-hide:all">&#8199;&#65279;&#847; &#8199;&#65279;&#847; &#8199;&#65279;&#847; &#8199;&#65279;&#847; &#8199;&#65279;&#847; &#8199;&#65279;&#847; &#8199;&#65279;&#847; &#8199;&#65279;&#847;</div>

<table width="100%" cellpadding="0" cellspacing="0" class="email-body" style="background:#F8FAFC">
<tr><td align="center" style="padding:16px 12px">

<table width="600" cellpadding="0" cellspacing="0" class="email-container" style="max-width:600px;width:100%;background:#FFFFFF;border-radius:12px;overflow:hidden;border:1px solid #E2E8F0">

  <!-- Header: gradient bar + logo + date -->
  <tr><td style="padding:0"><table width="100%" cellpadding="0" cellspacing="0"><tr>
    <td style="height:4px;background:linear-gradient(90deg,#3B82F6,#8B5CF6,#EC4899)"></td>
  </tr></table></td></tr>
  <tr><td style="padding:24px 24px 20px">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td style="vertical-align:middle">
        <table cellpadding="0" cellspacing="0"><tr>
          <td style="width:40px;height:40px;background:linear-gradient(135deg,#3B82F6,#8B5CF6);border-radius:10px;text-align:center;line-height:40px;color:white;font-weight:900;font-size:18px">K</td>
          <td style="padding-left:12px">
            <p style="margin:0;font-size:18px;font-weight:800;color:#0F172A;letter-spacing:-0.3px">Koda Daily</p>
          </td>
        </tr></table>
      </td>
      <td style="text-align:right;vertical-align:middle">
        <p style="margin:0;font-size:12px;color:#94A3B8;text-transform:uppercase;letter-spacing:1.5px">{date_label}</p>
      </td>
    </tr></table>
  </td></tr>

  <!-- THE SIGNAL: Opening hook -->
  <tr><td style="padding:0 24px 20px">
    <p class="text-primary" style="margin:0;color:#0F172A;font-size:20px;font-weight:800;line-height:1.35">{hook}</p>
  </td></tr>

  <!-- TODAY'S RUNDOWN (TOC) -->
  <tr><td style="padding:0 24px 16px">
    <p style="margin:0 0 8px;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:2px;color:#6366F1">Today's Rundown</p>
    <table width="100%" cellpadding="0" cellspacing="0">
      {toc_html}
    </table>
  </td></tr>

  {_section_divider() if market_cells else ""}

  {"" if not market_cells else _section_header("Market Pulse") + '''
  <tr><td style="padding:0 24px">
    <table width="100%" cellpadding="0" cellspacing="4" style="border-spacing:4px">
      <tr>''' + market_cells + '''</tr>
    </table>
  </td></tr>'''}

  {_section_divider()}

  <!-- AI FRONTLINE + BEYOND AI -->
  {_section_header("AI Frontline")}
  {stories_html}

  {_section_divider()}

  <!-- SPEED ROUND -->
  {_section_header("Speed Round")}
  <tr><td style="padding:0 24px">
    <table width="100%" cellpadding="0" cellspacing="0">
      {quick_hits_html}
    </table>
  </td></tr>

  {_section_divider()}

  <!-- TOOL DROP -->
  {_section_header("Tool Drop")}
  <tr><td style="padding:0 24px">
    <table width="100%" cellpadding="0" cellspacing="0">
      {tools_html}
    </table>
  </td></tr>

  <!-- LISTEN & WATCH -->
  {media_html}

  <!-- DEEP DIVE (editorial) -->
  {editorial_html}

  <!-- DEEP DIVE MEDIA (editorial audio + anime video) -->
  {editorial_media_html}

  {_section_divider()}

  <!-- CTA -->
  <tr><td style="padding:24px 24px 0;text-align:center">
    <a href="{digest_url}"
      style="display:inline-block;padding:16px 40px;background:linear-gradient(135deg,#3B82F6,#6366F1);color:white;text-decoration:none;font-weight:800;font-size:15px;letter-spacing:0.5px;border-radius:8px" target="_blank">READ THE FULL DIGEST</a>
    <p style="margin:10px 0 0;font-size:12px;color:#94A3B8">Competitive landscape, newsletter intel, changelog, and more</p>
  </td></tr>

  <!-- RATE THIS ISSUE -->
  {rating_html}

  <!-- FOOTER -->
  <tr><td style="padding:24px;border-top:1px solid #E2E8F0;text-align:center">
    <p style="margin:0 0 8px;font-size:13px;color:#334155">Until tomorrow -- the <strong>Koda Intelligence</strong> team</p>
    <p style="margin:0 0 12px;font-size:12px;color:#94A3B8">
      <a href="https://www.koda.community" style="color:#6366F1;text-decoration:none;font-weight:600" target="_blank">koda.community</a> &nbsp;&#183;&nbsp;
      <a href="https://www.koda.community/archive/" style="color:#6366F1;text-decoration:none;font-weight:600" target="_blank">The Vault</a> &nbsp;&#183;&nbsp;
      <a href="https://www.koda.community/editorial/" style="color:#6366F1;text-decoration:none;font-weight:600" target="_blank">Deep Dive</a>
    </p>
    <p style="margin:0;font-size:10px;color:#94A3B8">
      <a href="{{{{UNSUBSCRIBE_URL}}}}" style="color:#94A3B8;text-decoration:underline">Unsubscribe</a> &nbsp;&#183;&nbsp;
      Delivered by Koda Intelligence
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
