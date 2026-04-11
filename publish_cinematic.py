"""
Publish Cinematic Content Studio output as a Koda Deep Dive editorial.

Takes a cinematic output folder (blog post, YouTube videos, audio, quotes)
and renders a fully self-contained editorial HTML page that is visually
identical to existing Daily Deep Dive articles.

Usage:
    python publish_cinematic.py --folder ~/Desktop/cinematic-claude-mythos-2026-04-11
    python publish_cinematic.py --folder ~/Desktop/cinematic-foo-2026-04-12 --tag "Strategy"
    python publish_cinematic.py --folder ~/Desktop/cinematic-foo-2026-04-12 --dry-run

This is a standalone on-demand script, NOT part of the daily pipeline.
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ── Setup paths ─────────────────────────────────────────────────────────────

DIGEST_DIR = Path(__file__).parent
sys.path.insert(0, str(DIGEST_DIR))
sys.path.insert(0, str(DIGEST_DIR / "pipeline"))

from pipeline.config import (
    DIGEST_DIR as CFG_DIGEST_DIR,
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY,
    og_media_url,
    OG_FALLBACK_IMAGE,
)
from nav_component import NAV_CSS_V2, build_nav_v2
from supabase_upload import upload_file

# ── Reuse editorial utilities ───────────────────────────────────────────────


def slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    slug = text.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s-]+', '-', slug).strip('-')
    return slug[:60]


def inline_md(text: str) -> str:
    """Convert inline markdown to HTML. Order matters: bold before italic."""
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    return text


def _truncate_title(text: str, max_len: int = 120) -> str:
    """Truncate text at the last word boundary before max_len."""
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    last_break = max(truncated.rfind(' '), truncated.rfind('-'))
    if last_break > max_len // 2:
        return truncated[:last_break].rstrip(' -')
    return truncated.rstrip()


def _clean_em_dashes(text: str) -> str:
    """Replace em dashes with spaced hyphens (Koda house style: zero em dashes)."""
    return text.replace("\u2014", " -").replace("\u2013", "-")


def _excerpt(article_text: str, max_chars: int = 150) -> str:
    """Extract a clean excerpt from the article hook (first paragraph)."""
    paragraphs = [p.strip() for p in article_text.split('\n\n') if p.strip()]
    raw = paragraphs[0] if paragraphs else ""
    raw = re.sub(r'\*+', '', raw)
    return raw[:max_chars].rstrip(' .,') + ("..." if len(raw) > max_chars else "")


def _format_date_display(date_str: str) -> str:
    """Format YYYY-MM-DD as '11 April 2026'."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{dt.day} {dt.strftime('%B %Y')}"


# ── Step 1: Parse cinematic folder ──────────────────────────────────────────


def parse_cinematic_folder(folder: Path) -> dict:
    """Parse a cinematic output folder and return a structured dict of all assets."""
    assets: dict = {"folder": folder, "errors": []}

    # Find blog markdown
    blog_files = list(folder.glob("cinematic-blog-*.md"))
    if not blog_files:
        assets["errors"].append("No cinematic-blog-*.md found")
        return assets
    assets["blog_path"] = blog_files[0]

    # Extract slug and date from blog filename
    m = re.search(r'cinematic-blog-(.+?)-(\d{4}-\d{2}-\d{2})\.md', blog_files[0].name)
    if m:
        assets["slug"] = m.group(1)
        assets["date"] = m.group(2)
    else:
        assets["slug"] = folder.name.replace("cinematic-", "")
        assets["date"] = datetime.now().strftime("%Y-%m-%d")

    # YouTube master result
    yt_master = folder / f"cinematic-master-youtube-result.json"
    if yt_master.exists():
        with open(yt_master, "r", encoding="utf-8") as f:
            assets["youtube_master"] = json.load(f)
    else:
        assets["youtube_master"] = None
        assets["errors"].append("No YouTube master result JSON")

    # YouTube shorts result
    yt_shorts = folder / f"cinematic-shorts-youtube-result.json"
    if yt_shorts.exists():
        with open(yt_shorts, "r", encoding="utf-8") as f:
            assets["youtube_shorts"] = json.load(f)

    # Audio MP3
    audio_files = list(folder.glob("cinematic-audio-*.mp3"))
    assets["audio_path"] = audio_files[0] if audio_files else None

    # Quote card HTML files (contain quote text in prompt)
    quote_htmls = sorted(folder.glob("cinematic-quote-*-*.html"))
    assets["quote_htmls"] = quote_htmls

    # Quote card PNGs
    quote_pngs = sorted(folder.glob("cinematic-quote-*-*.png"))
    assets["quote_pngs"] = quote_pngs

    # Thumbnail
    thumb_files = list(folder.glob("cinematic-thumb-*.png"))
    assets["thumb_path"] = thumb_files[0] if thumb_files else None

    # Script markdown
    script_files = list(folder.glob("cinematic-script-*.md"))
    assets["script_path"] = script_files[0] if script_files else None

    return assets


# ── Step 2: Extract quotes ──────────────────────────────────────────────────


def extract_quotes(assets: dict) -> list[str]:
    """Extract quote text from cinematic quote card HTML files."""
    quotes: list[str] = []
    for html_path in assets.get("quote_htmls", []):
        try:
            content = html_path.read_text(encoding="utf-8")
            # Quote is inside the prompt box: 'The quote text reads: "..."'
            m = re.search(r'The quote text reads:\s*"([^"]+)"', content)
            if m:
                quotes.append(m.group(1))
        except Exception:
            continue
    return quotes


# ── Step 3: Prepare blog markdown ───────────────────────────────────────────


def prepare_blog(assets: dict, quotes: list[str], hero_quote_idx: int = 1) -> dict:
    """Read blog markdown, inject pull quotes, extract metadata.

    Returns dict with: title, subtitle, body (with pull quotes), word_count, read_time
    """
    blog_text = assets["blog_path"].read_text(encoding="utf-8")
    blog_text = _clean_em_dashes(blog_text)

    # Extract title from first # line
    original_title = ""
    lines = blog_text.split('\n')
    body_start = 0
    for i, line in enumerate(lines):
        if line.startswith('# '):
            original_title = line.lstrip('# ').strip()
            body_start = i + 1
            break

    # Use selected quote as hero title (or fall back to original)
    if 0 <= hero_quote_idx < len(quotes):
        title = quotes[hero_quote_idx]
    else:
        title = original_title or assets["slug"].replace("-", " ").title()

    # Rebuild body without the H1 title line
    body = '\n'.join(lines[body_start:]).strip()

    # Remove horizontal rules (---) that the cinematic blog uses
    body = re.sub(r'\n---+\n', '\n', body)

    # Split into sections for pull quote injection
    sections = re.split(r'\n(## .+)', body)

    # Inject quotes at ~1/3 and ~2/3 through sections
    usable_quotes = [q for i, q in enumerate(quotes) if i != hero_quote_idx]
    if sections and usable_quotes:
        # Count the section boundaries (## headings)
        heading_indices = [i for i, s in enumerate(sections) if s.strip().startswith('## ')]
        total_headings = len(heading_indices)

        if total_headings >= 2 and len(usable_quotes) >= 1:
            # Insert first quote after ~1/3
            insert_at_1 = heading_indices[total_headings // 3] if total_headings >= 3 else heading_indices[0]
            quote_block_1 = f'\n\n> "{usable_quotes[0]}"\n'
            sections.insert(insert_at_1 + 2, quote_block_1)

        if total_headings >= 4 and len(usable_quotes) >= 2:
            # Recalculate after first insertion
            heading_indices_2 = [i for i, s in enumerate(sections) if s.strip().startswith('## ')]
            insert_at_2 = heading_indices_2[len(heading_indices_2) * 2 // 3]
            quote_block_2 = f'\n\n> "{usable_quotes[1]}"\n'
            sections.insert(insert_at_2 + 2, quote_block_2)

    body = '\n'.join(sections)

    # Extract subtitle from first paragraph
    paragraphs = [p.strip() for p in body.split('\n\n') if p.strip() and not p.strip().startswith('#')]
    subtitle = paragraphs[0][:200] if paragraphs else ""
    subtitle = re.sub(r'\*+', '', subtitle)

    word_count = len(body.split())
    read_time = max(1, word_count // 250)

    return {
        "title": title,
        "original_title": original_title,
        "subtitle": subtitle,
        "body": body,
        "word_count": word_count,
        "read_time": read_time,
    }


# ── Step 4: Generate hero image ────────────────────────────────────────────


def generate_hero(blog_data: dict, assets: dict, output_path: Path) -> bool:
    """Generate a Gemini Imagen hero image. Falls back to thumbnail if Gemini fails."""
    api_key = os.environ.get("GEMINI_API_KEY")
    gemini_script = DIGEST_DIR / "gemini_image.py"

    if not api_key or not gemini_script.exists():
        print("  WARNING: GEMINI_API_KEY or gemini_image.py not available")
        # Fallback: use thumbnail
        if assets.get("thumb_path") and assets["thumb_path"].exists():
            import shutil
            shutil.copy2(str(assets["thumb_path"]), str(output_path))
            print(f"  Fallback: using cinematic thumbnail as hero")
            return True
        return False

    # Generate content-aware image prompt via OpenRouter
    article_text = blog_data["body"][:3000]
    title = blog_data["original_title"] or blog_data["title"]

    prompt = f"""You are an art director for Koda, a premium AI intelligence publication.
Read this editorial article and generate a single image prompt for a hero image.

ARTICLE TITLE: {title}
FIRST PARAGRAPH: {blog_data['subtitle'][:500]}

ARTICLE TEXT:
{article_text}

REQUIREMENTS:
1. FIRST: identify the ONE most concrete visual subject in this article
2. The image MUST depict that specific subject -- not a generic "tech" or "AI" visual
3. Dark moody atmosphere with deep shadows and volumetric lighting
4. Color palette: deep navy, electric blue, violet purple, subtle cyan accents
5. Cinematic composition, photorealistic 3D render
6. ABSOLUTELY NO text, words, labels, numbers, letters, or typography
7. NO people, faces, bodies, or hands
8. NO political figures or identifiable persons

Output ONLY the image prompt (150-200 words). No preamble, no explanation."""

    # Call Opus via OpenRouter for the prompt
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
    image_prompt = None
    if openrouter_key:
        try:
            import httpx
            resp = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json={
                    "model": "anthropic/claude-opus-4-6",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 500,
                    "temperature": 0.5,
                },
                headers={"Authorization": f"Bearer {openrouter_key}",
                         "Content-Type": "application/json"},
                timeout=60,
            )
            resp.raise_for_status()
            image_prompt = resp.json()["choices"][0]["message"]["content"].strip()
            image_prompt = re.sub(r'^```\w*\s*', '', image_prompt)
            image_prompt = re.sub(r'\s*```$', '', image_prompt).strip()
            print(f"  Hero prompt ({len(image_prompt)} chars): {image_prompt[:150]}...")
        except Exception as e:
            print(f"  WARNING: LLM prompt generation failed: {e}")

    if not image_prompt:
        image_prompt = (
            "Dark moody server room, deep navy and electric blue lighting, "
            "rows of glowing servers, digital shield barrier, volumetric fog, "
            "cinematic composition, photorealistic 3D render, no text, no people"
        )

    # Call Gemini via subprocess
    print("  Generating hero image via Gemini Imagen...")
    try:
        result = subprocess.run(
            [sys.executable, str(gemini_script),
             "--prompt", image_prompt,
             "--output", str(output_path)],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        if result.returncode == 0 and output_path.exists():
            size_kb = output_path.stat().st_size // 1024
            print(f"  Hero image saved: {output_path.name} ({size_kb}KB)")
            return True
        else:
            print(f"  WARNING: Gemini failed (exit {result.returncode})")
            if result.stderr:
                print(f"    {result.stderr.strip()[:200]}")
    except subprocess.TimeoutExpired:
        print("  WARNING: Gemini image gen timed out")
    except Exception as e:
        print(f"  WARNING: Gemini image gen error: {e}")

    # Fallback: use thumbnail
    if assets.get("thumb_path") and assets["thumb_path"].exists():
        import shutil
        shutil.copy2(str(assets["thumb_path"]), str(output_path))
        print(f"  Fallback: using cinematic thumbnail as hero")
        return True
    return False


# ── Step 5: Upload media to Supabase ────────────────────────────────────────


def upload_media(hero_path: Path, audio_path: Path | None, date: str) -> dict:
    """Upload hero image and audio to Supabase. Returns dict of URLs."""
    urls: dict = {"hero": None, "audio": None}

    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        print("  WARNING: Supabase credentials not set, using local paths")
        if hero_path.exists():
            urls["hero"] = f"./{hero_path.name}"
        if audio_path and audio_path.exists():
            urls["audio"] = f"./{audio_path.name}"
        return urls

    # Upload hero
    if hero_path.exists():
        hero_filename = f"editorial-hero-{date}.jpg"
        hero_upload = hero_path
        # If PNG, convert to JPG
        if hero_path.suffix.lower() == ".png":
            try:
                from PIL import Image
                jpg_path = hero_path.with_suffix(".jpg")
                Image.open(hero_path).convert("RGB").save(str(jpg_path), "JPEG", quality=85)
                hero_upload = jpg_path
            except ImportError:
                hero_filename = f"editorial-hero-{date}.png"

        print(f"  Uploading hero image to Supabase...")
        try:
            # Rename to standard naming
            import shutil
            temp_hero = hero_path.parent / hero_filename
            shutil.copy2(str(hero_upload), str(temp_hero))
            url = upload_file(str(temp_hero), SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
            urls["hero"] = url
            print(f"  OK: {url}")
        except Exception as e:
            print(f"  FAILED: {e}")
            urls["hero"] = f"./{hero_path.name}"

    # Upload audio
    if audio_path and audio_path.exists():
        print(f"  Uploading audio to Supabase...")
        audio_filename = f"editorial-podcast-{date}.mp3"
        try:
            import shutil
            temp_audio = audio_path.parent / audio_filename
            shutil.copy2(str(audio_path), str(temp_audio))
            url = upload_file(str(temp_audio), SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
            urls["audio"] = url
            print(f"  OK: {url}")
        except Exception as e:
            print(f"  FAILED: {e}")

    return urls


# ── Step 5b: Generate OG card ───────────────────────────────────────────────


def generate_og_card(hero_path: Path, title: str, subtitle: str,
                     date: str, output_dir: Path) -> str | None:
    """Generate a branded 1200x630 OG card and upload to Supabase."""
    try:
        from pipeline.generate_og_card import create_og_card
    except ImportError:
        print("  WARNING: generate_og_card not importable, skipping OG card")
        return None

    og_filename = f"og-editorial-v2-{date}.jpg"
    og_path = output_dir / og_filename

    print("  Generating branded OG card...")
    ok = create_og_card(
        hero_path=str(hero_path),
        title=title,
        section="editorial",
        output_path=str(og_path),
        subtitle=subtitle[:150],
    )

    if not ok or not og_path.exists():
        print("  WARNING: OG card generation failed")
        return None

    size_kb = og_path.stat().st_size // 1024
    print(f"  OG card: {og_filename} ({size_kb}KB)")

    # Upload to Supabase
    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
        try:
            url = upload_file(str(og_path), SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
            print(f"  OG card uploaded: {url}")
            return og_media_url(og_filename)
        except Exception as e:
            print(f"  WARNING: OG card upload failed: {e}")

    return og_media_url(og_filename)


# ── Step 6: Render HTML ─────────────────────────────────────────────────────


def render_editorial_html(
    blog_data: dict,
    assets: dict,
    media_urls: dict,
    og_image_url: str,
    tag: str,
) -> str:
    """Render the full self-contained editorial HTML page."""
    title = blog_data["title"]
    subtitle = blog_data["subtitle"]
    date = assets["date"]
    body = blog_data["body"]
    word_count = blog_data["word_count"]
    read_time = blog_data["read_time"]

    dt = datetime.strptime(date, "%Y-%m-%d")
    date_display = dt.strftime("%d %B %Y")

    slug = slugify(blog_data.get("original_title") or title)
    filename = f"{date}-{slug}.html"
    url = f"https://www.koda.community/editorial/{filename}"

    hero_url = media_urls.get("hero", "")
    hero_proxy = ""
    if hero_url and "/koda-media/" in hero_url:
        hero_fname = hero_url.split("/koda-media/")[-1]
        hero_proxy = og_media_url(hero_fname)
    elif hero_url:
        hero_proxy = hero_url

    if not og_image_url:
        og_image_url = OG_FALLBACK_IMAGE

    # Build body HTML from markdown
    body_html = ""
    sections = re.split(r'\n##\s+', body)
    hook = sections[0].strip() if sections else ""
    named_sections = sections[1:] if len(sections) > 1 else []

    for para in hook.split('\n\n'):
        para = para.strip()
        if para:
            if para.startswith('>'):
                quote_text = para.lstrip('> ').strip().strip('"')
                body_html += f'    <blockquote class="pull-quote fade-in">{inline_md(quote_text)}</blockquote>\n'
            else:
                body_html += f"    <p>{inline_md(para)}</p>\n"

    for sec in named_sections:
        lines = sec.strip().split('\n', 1)
        heading = lines[0].strip()
        content = lines[1].strip() if len(lines) > 1 else ""

        body_html += f"\n    <h2>{heading}</h2>\n"
        for para in content.split('\n\n'):
            para = para.strip()
            if not para:
                continue
            if para.startswith('>'):
                quote_text = para.lstrip('> ').strip().strip('"')
                body_html += f'    <blockquote class="pull-quote fade-in">{inline_md(quote_text)}</blockquote>\n'
            else:
                body_html += f"    <p>{inline_md(para)}</p>\n"

    # Hero image HTML
    hero_img_html = ""
    if hero_proxy:
        hero_img_html = f'''    <div class="hero-image fade-in" style="max-width:800px;margin:32px auto 0;border-radius:16px;overflow:hidden;">
        <img src="{hero_proxy}" alt="{title}" loading="eager" style="width:100%;height:auto;display:block;border-radius:16px;">
    </div>'''

    # Read CSS from template
    template_path = DIGEST_DIR / "editorial" / "template-editorial.html"
    css = ""
    if template_path.exists():
        template = template_path.read_text(encoding="utf-8")
        css_match = re.search(r'<style>(.*?)</style>', template, re.DOTALL)
        css = css_match.group(1) if css_match else ""

    # Build nav
    _nav_css, nav_html, _nav_js = build_nav_v2(
        current_page="editorial",
        url_prefix="../",
        page_subtitle="Deep Dive",
        page_icon="explore",
        share_url="https://www.koda.community/editorial/",
    )

    # Assemble full HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{_truncate_title(title, 90)} | Koda Deep Dive</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet">
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect rx='20' width='100' height='100' fill='%236366F1'/><text x='50' y='68' font-size='55' text-anchor='middle' fill='white' font-family='system-ui' font-weight='800'>K</text></svg>">
    <meta property="og:title" content="{_truncate_title(title, 90)} | Koda Deep Dive">
    <meta property="og:description" content="{subtitle[:160]} Daily analysis of what matters in AI, written for builders.">
    <meta property="og:type" content="article">
    <meta property="og:url" content="{url}">
    <meta property="og:site_name" content="Koda Digest">
    <meta property="og:image" content="{og_image_url}">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{_truncate_title(title, 90)} | Koda Deep Dive">
    <meta name="twitter:description" content="{subtitle[:160]} Daily analysis of what matters in AI, written for builders.">
    <meta name="twitter:image" content="{og_image_url}">
    <meta name="description" content="{subtitle[:160]}">
    <script type="application/ld+json">
    {{
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "{_truncate_title(title, 110)}",
        "datePublished": "{date}",
        "description": "{subtitle[:160]}",
        "author": {{"@type": "Organization", "name": "Koda Deep Dive"}},
        "publisher": {{"@type": "Organization", "name": "Koda Intelligence", "url": "https://www.koda.community"}},
        "mainEntityOfPage": "{url}",
        "wordCount": "{word_count}",
        "timeRequired": "PT{read_time}M"
    }}
    </script>"""

    html += f"\n    <style>\n{css}\n    </style>\n</head>\n<body class=\"dark\">\n"
    html += '<div class="scroll-progress" id="scrollProgress"></div>\n'
    html += nav_html

    html += f"""
<header class="hero-section">
    <div class="hero-inner">
        <div class="hero-meta">
            <span class="tag">{tag}</span>
            <span>{date_display}</span>
            <span>{read_time} min read</span>
        </div>
        <h1 class="hero-title">{title}</h1>
        <p class="hero-subtitle">{subtitle}</p>
    </div>
{hero_img_html}
</header>

<article class="article-body">
{body_html}
</article>
"""

    # Subscribe CTA
    html += """
<section style="max-width:48rem;margin:0 auto;padding:64px 24px 16px;text-align:center;">
    <div style="background:rgba(11,19,38,0.6);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.06);border-radius:16px;padding:32px 40px;position:relative;overflow:hidden;">
        <div style="position:absolute;top:0;left:50%;transform:translateX(-50%);width:128px;height:4px;background:linear-gradient(90deg,#3B82F6,#8B5CF6,#EC4899);border-radius:0 0 4px 4px;"></div>
        <h3 style="font-size:20px;font-weight:700;color:white;margin-bottom:8px;">Want this every morning?</h3>
        <p style="color:#c2c6d6;font-size:14px;margin-bottom:24px;">AI analysis, world news, markets, and tools. One briefing, delivered free.</p>
        <form style="display:flex;gap:8px;max-width:28rem;margin:0 auto;padding:6px;border-radius:9999px;background:#171f33;border:1px solid rgba(255,255,255,0.06);" onsubmit="return kodaSubscribe(this)">
            <input type="email" name="email" required style="background:transparent;border:none;outline:none;color:white;padding:0 20px;width:100%;font-size:14px;font-family:'Inter',system-ui,sans-serif;" placeholder="your@email.com">
            <button type="submit" style="background:linear-gradient(135deg,#3B82F6,#6366F1);color:white;padding:12px 24px;border-radius:9999px;font-weight:700;font-size:14px;white-space:nowrap;border:none;cursor:pointer;">Subscribe</button>
        </form>
        <p style="font-size:10px;color:#8c909f;margin-top:12px;">One email per day. No spam. Unsubscribe anytime.</p>
    </div>
</section>
"""

    # Subscribe JS
    html += """
<script>
function kodaSubscribe(form) {
    var btn = form.querySelector('button');
    var email = form.querySelector('input[name="email"]').value;
    btn.textContent = 'Subscribing...'; btn.disabled = true;
    fetch('/api/subscribe', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({email:email}) })
    .then(function(r) { btn.textContent = r.ok ? 'Subscribed!' : 'Try again'; btn.disabled = false; })
    .catch(function() { btn.textContent = 'Try again'; btn.disabled = false; });
    return false;
}
</script>
"""

    # Scroll progress + fade-in JS
    html += """
<script>
window.addEventListener('scroll', function() {
    var h = document.documentElement.scrollHeight - window.innerHeight;
    var pct = h > 0 ? (window.scrollY / h) * 100 : 0;
    document.getElementById('scrollProgress').style.width = pct + '%';
});
const observer = new IntersectionObserver(entries => {
    entries.forEach(e => { if (e.isIntersecting) e.target.classList.add('visible'); });
}, { threshold: 0.1 });
document.querySelectorAll('.fade-in').forEach(el => observer.observe(el));
</script>
"""

    # Search overlay
    html += """
<div id="searchOverlay" style="position:fixed;inset:0;z-index:2000;display:none;background:rgba(0,0,0,0.6);backdrop-filter:blur(4px);">
    <div style="max-width:640px;margin:80px auto 0;padding:0 16px;">
        <div style="background:#171f33;border:1px solid rgba(66,71,84,0.4);border-radius:16px;box-shadow:0 25px 50px rgba(0,0,0,0.5);overflow:hidden;">
            <div style="display:flex;align-items:center;gap:12px;padding:16px 20px;border-bottom:1px solid rgba(255,255,255,0.05);">
                <span class="material-symbols-outlined" style="color:#adc6ff;font-size:20px;">search</span>
                <input type="text" id="globalSearchInput" autocomplete="off" placeholder="Search digests and editorials..." style="flex:1;background:transparent;border:none;outline:none;font-size:16px;color:#dae2fd;font-family:Inter,system-ui,sans-serif;">
                <kbd style="font-size:10px;font-family:'JetBrains Mono',monospace;color:#64748b;border:1px solid #475569;border-radius:4px;padding:2px 6px;">ESC</kbd>
            </div>
            <div id="globalSearchResults" style="max-height:60vh;overflow-y:auto;"></div>
        </div>
    </div>
</div>
<style>
.koda-sr-item{padding:14px 18px;border-bottom:1px solid rgba(173,198,255,0.05);cursor:pointer;transition:background 0.15s;text-decoration:none;display:block;color:inherit;}
.koda-sr-item:hover{background:rgba(99,102,241,0.1);}
.koda-sr-meta{display:flex;align-items:center;gap:8px;margin-bottom:6px;}
.koda-sr-date{font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700;color:#adc6ff;padding:2px 8px;background:rgba(173,198,255,0.12);border-radius:4px;}
.koda-sr-section{font-size:11px;color:#c2c6d6;text-transform:uppercase;letter-spacing:0.5px;}
.koda-sr-headline{font-size:14px;font-weight:600;color:#dae2fd;margin-bottom:4px;}
.koda-sr-snippet{font-size:13px;color:#c2c6d6;line-height:1.5;}
.koda-sr-snippet mark{background:rgba(173,198,255,0.25);color:#dae2fd;border-radius:2px;padding:0 2px;}
.koda-sr-badge{display:inline-flex;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;padding:2px 7px;border-radius:4px;}
.koda-sr-badge.digest{background:rgba(59,130,246,0.12);color:#60a5fa;}
.koda-sr-badge.editorial{background:rgba(139,92,246,0.12);color:#a78bfa;}
.koda-sr-empty{padding:20px;text-align:center;color:#c2c6d6;font-size:14px;}
"""
    html += NAV_CSS_V2
    html += """/* -- End Koda Nav V2 -- */
</style>
<script>
(function(){
    var overlay=document.getElementById('searchOverlay'),input=document.getElementById('globalSearchInput'),results=document.getElementById('globalSearchResults'),idx=null,timer=null;
    function open(){overlay.style.display='block';input.value='';results.innerHTML='';setTimeout(function(){input.focus();},50);}
    function close(){overlay.style.display='none';}
    var tsb=document.getElementById('topbarSearchBtn')||document.getElementById('knSearchBtn');if(tsb)tsb.addEventListener('click',open);
    overlay.addEventListener('click',function(e){if(e.target===overlay)close();});
    document.addEventListener('keydown',function(e){if((e.ctrlKey||e.metaKey)&&e.key==='k'){e.preventDefault();open();}if(e.key==='Escape'&&overlay.style.display!=='none')close();});
    input.addEventListener('input',function(){clearTimeout(timer);var q=input.value.trim();if(q.length<2){results.innerHTML='';return;}timer=setTimeout(function(){search(q);},200);});
    function search(q){if(!idx){fetch('../search-index.json').then(function(r){return r.json();}).then(function(d){idx=d;run(q);}).catch(function(){results.innerHTML='<div class="koda-sr-empty">Search unavailable.</div>';});}else run(q);}
    function run(q){
        var terms=q.toLowerCase().split(/\\s+/).filter(function(t){return t.length>0;});if(!terms.length){results.innerHTML='';return;}
        var hits=[],entries=idx.entries||idx.days||[];
        for(var i=0;i<entries.length;i++){var en=entries[i],tp=en.type||'digest',fl=en.file||('morning-briefing-koda-'+en.date+'.html'),secs=en.sections||[];
            for(var j=0;j<secs.length;j++){var sec=secs[j],items=sec.items||[];
                for(var k=0;k<items.length;k++){var it=items[k],hl=(it.headline||'').toLowerCase(),bt=(it.text||'').toLowerCase(),ft=hl+' '+bt,sc=0,mt=0;
                    for(var t=0;t<terms.length;t++){var tm=terms[t];if(ft.indexOf(tm)!==-1){mt++;sc+=10;if(hl.indexOf(tm)!==-1)sc+=15;}else{var ws=ft.split(/[\\s,.\\-\\/]+/);for(var w=0;w<ws.length;w++){if(ws[w].indexOf(tm)===0&&tm.length>=3){mt++;sc+=5;break;}}}}
                    if(mt>0){if(mt===terms.length)sc+=20;sc-=i*2;hits.push({date:en.date,type:tp,section:sec.title,headline:it.headline,text:it.text,file:fl,score:sc});}
                }}}
        hits.sort(function(a,b){return a.date<b.date?1:a.date>b.date?-1:b.score-a.score;});hits=hits.slice(0,20);
        if(!hits.length){results.innerHTML='<div class="koda-sr-empty">No results for "'+esc(q)+'"</div>';return;}
        var h='';for(var r=0;r<hits.length;r++){var rs=hits[r],sn=snippet(rs.text,terms[0],80),sa=rs.type==='editorial'?'':slug(rs.section),href='../'+rs.file+(sa?'#'+sa:'');
            h+='<a href="'+href+'" class="koda-sr-item"><div class="koda-sr-meta"><span class="koda-sr-badge '+rs.type+'">'+(rs.type==='editorial'?'Deep Dive':'The Signal')+'</span><span class="koda-sr-date">'+fmtDate(rs.date)+'</span><span class="koda-sr-section">'+esc(rs.section)+'</span></div><div class="koda-sr-headline">'+hilight(esc(rs.headline),terms)+'</div><div class="koda-sr-snippet">'+hilight(sn,terms)+'</div></a>';}
        results.innerHTML=h;
    }
    function snippet(t,tm,c){if(!t)return '';var l=t.toLowerCase(),i=l.indexOf(tm.toLowerCase());if(i===-1)return t.substring(0,c*2);var s=Math.max(0,i-c),e=Math.min(t.length,i+tm.length+c),r=t.substring(s,e);if(s>0)r='...'+r;if(e<t.length)r+='...';return r;}
    function hilight(t,terms){for(var i=0;i<terms.length;i++){t=t.replace(new RegExp('('+terms[i].replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&')+')','gi'),'<mark>$1</mark>');}return t;}
    function slug(t){return t.toLowerCase().replace(/['']/g,'').replace(/[^a-z0-9]+/g,'-').replace(/(^-|-$)/g,'');}
    function fmtDate(d){var p=d.split('-'),m=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];return m[parseInt(p[1])-1]+' '+parseInt(p[2])+', '+p[0];}
    function esc(s){return s?s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'):'';}
})();
</script>
"""
    html += _nav_js
    html += "\n</body>\n</html>"

    return html, filename


# ── Step 7: Inject media strip ──────────────────────────────────────────────


def inject_media_strip(html: str, media_urls: dict, assets: dict) -> str:
    """Inject audio + video media strip into the editorial HTML."""
    audio_url = media_urls.get("audio", "")
    if audio_url and "/koda-media/" in audio_url:
        audio_fname = audio_url.split("/koda-media/")[-1]
        audio_url = og_media_url(audio_fname)

    yt = assets.get("youtube_master") or {}
    youtube_id = yt.get("video_id", "")
    youtube_url = yt.get("url", f"https://www.youtube.com/watch?v={youtube_id}" if youtube_id else "")

    if not audio_url and not youtube_id:
        return html

    cards = []
    if audio_url:
        cards.append(f"""    <div class="media-card media-card--audio">
      <span class="material-symbols-outlined media-card__icon media-card__icon--audio">headphones</span>
      <div class="media-card__title">Deep Dive Audio</div>
      <div class="media-card__subtitle">Full cinematic narration</div>
      <button class="media-btn media-btn--podcast" id="edPodBtn" onclick="toggleEditorialPodcast()" aria-expanded="false" aria-controls="editorialPodcastPlayer">&#9654; Listen Now</button>
      <div class="ed-podcast-wrap" id="editorialPodcastPlayer">
        <audio controls preload="none"><source src="{audio_url}" type="audio/mpeg"></audio>
      </div>
    </div>""")

    if youtube_id:
        cards.append(f"""    <div class="media-card media-card--video">
      <span class="material-symbols-outlined media-card__icon media-card__icon--video">smart_display</span>
      <div class="media-card__title">Visual Narrative</div>
      <div class="media-card__subtitle">Cinematic story breakdown</div>
      <button class="media-btn media-btn--video" onclick="toggleVideo()">&#9654; Play Video</button>
      <a href="{youtube_url}" target="_blank" rel="noopener" class="media-yt-link">or watch on YouTube &rarr;</a>
      <div class="video-overlay" id="videoOverlay" role="dialog" aria-modal="true" aria-label="Video player" onclick="if(event.target===this)toggleVideo()">
        <div class="video-overlay-inner">
          <button class="video-overlay-close" onclick="toggleVideo()" aria-label="Close video">&times;</button>
          <iframe id="videoFrame" width="100%" style="aspect-ratio:16/9;border:none;border-radius:12px" allowfullscreen title="Cinematic video"></iframe>
        </div>
      </div>
    </div>""")

    strip_html = (
        '\n<!-- MEDIA_STRIP_START -->\n'
        '<section class="media-strip fade-in">\n'
        '  <div class="media-strip-grid">\n'
        + '\n'.join(cards) + '\n'
        '  </div>\n'
        '</section>\n'
        '<!-- MEDIA_STRIP_END -->\n'
    )

    media_js = """
<script>
function toggleEditorialPodcast() {
    var player = document.getElementById('editorialPodcastPlayer');
    var btn = document.getElementById('edPodBtn');
    if (!player || !btn) return;
    if (player.classList.contains('active')) {
        player.classList.remove('active');
        btn.innerHTML = '&#9654; Listen Now';
        btn.setAttribute('aria-expanded', 'false');
        var audio = player.querySelector('audio');
        if (audio) audio.pause();
    } else {
        player.classList.add('active');
        btn.innerHTML = '&#9646;&#9646; Pause';
        btn.setAttribute('aria-expanded', 'true');
        var audio = player.querySelector('audio');
        if (audio) audio.play();
    }
}
function toggleVideo() {
    var o = document.getElementById('videoOverlay'), f = document.getElementById('videoFrame');
    if (!o || !f) return;
    if (o.classList.contains('active')) {
        o.classList.remove('active');
        f.src = '';
        document.body.style.overflow = '';
    } else {
        f.src = 'https://www.youtube.com/embed/""" + youtube_id + """?autoplay=1&rel=0';
        o.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}
</script>
"""

    # Inject after <article class="article-body">
    marker = '<article class="article-body">'
    idx = html.find(marker)
    if idx != -1:
        insert_at = idx + len(marker)
        html = html[:insert_at] + "\n" + strip_html + html[insert_at:]
        print(f"  Injected media strip (audio={bool(audio_url)}, video={bool(youtube_id)})")

    # Inject media JS before </body>
    body_end = html.rfind("</body>")
    if body_end != -1:
        html = html[:body_end] + media_js + html[body_end:]

    return html


# ── Step 8-9: Write + update archives ───────────────────────────────────────


def update_editorial_archive(title: str, filename: str, tag: str,
                             date: str, word_count: int, article_text: str) -> None:
    """Prepend a card to editorial/index.html."""
    archive_path = DIGEST_DIR / "editorial" / "index.html"
    if not archive_path.exists():
        print("  WARNING: editorial/index.html not found, skipping archive update")
        return

    content = archive_path.read_text(encoding="utf-8")
    date_display = _format_date_display(date)
    read_min = max(1, word_count // 250)
    excerpt = _excerpt(article_text)

    new_card = f'''    <a href="./{filename}" class="article-card">
        <div class="article-meta">
            <span class="tag">{tag}</span>
            <span class="date">{date_display}</span>
        </div>
        <h2>{_truncate_title(title, 100)}</h2>
        <p>{excerpt}</p>
        <div class="read-time">{read_min} min read</div>
    </a>
'''

    marker = '<div class="grid">'
    if marker in content:
        updated = content.replace(marker, marker + "\n" + new_card, 1)
        archive_path.write_text(updated, encoding="utf-8")
        print(f"  Updated editorial/index.html with card")
    else:
        print("  WARNING: could not find grid marker in editorial/index.html")


def update_landing_page(title: str, filename: str, tag: str,
                        date: str, word_count: int, article_text: str) -> None:
    """Replace the featured editorial card in index.html."""
    landing_path = DIGEST_DIR / "index.html"
    if not landing_path.exists():
        print("  WARNING: index.html not found, skipping landing page update")
        return

    content = landing_path.read_text(encoding="utf-8")
    date_display = _format_date_display(date)
    read_min = max(1, word_count // 250)
    excerpt = _excerpt(article_text, max_chars=120)

    start_marker = "<!-- EDITORIAL-CARD-START -->"
    end_marker = "<!-- EDITORIAL-CARD-END -->"

    if start_marker not in content or end_marker not in content:
        print("  WARNING: EDITORIAL-CARD markers not found in index.html, skipping")
        return

    new_card = f"""<!-- EDITORIAL-CARD-START -->
        <a href="./editorial/{filename}" class="block no-underline group">
            <div class="bg-surface-container border border-outline-variant/20 rounded-2xl p-8 md:p-10 transition-all group-hover:border-[#6366F1]/30 group-hover:-translate-y-1" style="background:linear-gradient(135deg, rgba(99,102,241,0.06), rgba(139,92,246,0.04));">
                <div class="flex items-center gap-3 mb-4">
                    <span style="display:inline-block;padding:4px 12px;border-radius:20px;font-size:10px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;background:rgba(99,102,241,0.15);color:#a5b4fc;">{tag}</span>
                    <span class="text-xs font-mono text-on-surface-variant/50">{date_display}</span>
                    <span class="text-xs font-mono text-on-surface-variant/40">{read_min} min read</span>
                </div>
                <h3 class="text-xl md:text-2xl font-extrabold text-on-surface tracking-tight mb-3 group-hover:text-[#a5b4fc] transition-colors">{_truncate_title(title, 100)}</h3>
                <p class="text-sm text-on-surface-variant/70 leading-relaxed max-w-2xl">{excerpt}</p>
            </div>
        </a>
<!-- EDITORIAL-CARD-END -->"""

    pattern = re.compile(
        re.escape(start_marker) + r".*?" + re.escape(end_marker),
        re.DOTALL
    )
    updated = pattern.sub(new_card, content)

    if updated != content:
        landing_path.write_text(updated, encoding="utf-8")
        print(f"  Updated index.html editorial card")
    else:
        print("  WARNING: landing page editorial card replacement had no effect")


def rebuild_search_index() -> None:
    """Run build-index.py to rebuild manifest.json and search-index.json."""
    build_script = DIGEST_DIR / "build-index.py"
    if not build_script.exists():
        print("  WARNING: build-index.py not found, skipping index rebuild")
        return

    print("  Rebuilding manifest.json + search-index.json...")
    try:
        result = subprocess.run(
            [sys.executable, str(build_script)],
            cwd=str(DIGEST_DIR),
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            print("  Search index rebuilt OK")
        else:
            print(f"  WARNING: build-index.py failed (exit {result.returncode})")
            if result.stderr:
                print(f"    {result.stderr.strip()[:200]}")
    except Exception as e:
        print(f"  WARNING: build-index.py error: {e}")


# ── Main ────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publish cinematic content as a Koda Deep Dive editorial"
    )
    parser.add_argument("--folder", required=True, help="Path to cinematic output folder")
    parser.add_argument("--tag", default="", help="Editorial tag (auto-detected if empty)")
    parser.add_argument("--date", default="", help="Override date (YYYY-MM-DD)")
    parser.add_argument("--quote-idx", type=int, default=1,
                        help="Which quote to use as hero title (0-indexed, default: 1)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing files")
    args = parser.parse_args()

    folder = Path(args.folder).expanduser().resolve()
    if not folder.is_dir():
        print(f"ERROR: Folder not found: {folder}")
        sys.exit(1)

    print(f"[publish-cinematic] Parsing: {folder.name}")

    # Step 1: Parse folder
    assets = parse_cinematic_folder(folder)
    if assets.get("errors"):
        for err in assets["errors"]:
            print(f"  WARNING: {err}")
    if "blog_path" not in assets:
        print("ERROR: No blog post found in folder")
        sys.exit(1)

    if args.date:
        assets["date"] = args.date

    date = assets["date"]
    slug = assets["slug"]
    print(f"  Slug: {slug}")
    print(f"  Date: {date}")

    # Step 2: Extract quotes
    quotes = extract_quotes(assets)
    print(f"  Quotes found: {len(quotes)}")
    for i, q in enumerate(quotes):
        marker = " <-- HERO" if i == args.quote_idx else ""
        print(f"    [{i}] \"{q[:80]}...\"{marker}" if len(q) > 80 else f"    [{i}] \"{q}\"{marker}")

    # Step 3: Prepare blog
    blog_data = prepare_blog(assets, quotes, hero_quote_idx=args.quote_idx)
    print(f"  Title: {blog_data['title']}")
    print(f"  Words: {blog_data['word_count']}, Read time: {blog_data['read_time']} min")

    # Auto-detect tag (scan title + subtitle + first 1500 chars of body for keywords)
    tag = args.tag
    if not tag:
        scan_text = (
            blog_data["original_title"] + " " +
            blog_data["subtitle"] + " " +
            blog_data["body"][:1500]
        ).lower()
        if any(w in scan_text for w in ["security", "cyber", "hack", "vulnerability", "exploit", "breach"]):
            tag = "Cybersecurity"
        elif any(w in scan_text for w in ["business", "revenue", "pricing", "monetiz"]):
            tag = "Business"
        elif any(w in scan_text for w in ["tool", "agent", "api", "automat"]):
            tag = "Tools"
        elif any(w in scan_text for w in ["model", "benchmark", "training", "inference"]):
            tag = "AI Models"
        else:
            tag = "Strategy"
    print(f"  Tag: {tag}")

    if args.dry_run:
        print("\n  [DRY RUN] Skipping hero generation, uploads, and file writes")
        blog_data_html, filename = render_editorial_html(
            blog_data, assets, {"hero": "", "audio": ""}, OG_FALLBACK_IMAGE, tag
        )
        print(f"  Would write: editorial/{filename}")
        print(f"  HTML size: {len(blog_data_html):,} bytes")
        print(f"  YouTube master: {assets.get('youtube_master', {}).get('video_id', 'none')}")
        print(f"  Audio: {'yes' if assets.get('audio_path') else 'no'}")
        print("\n  Done (dry run)")
        return

    # Step 4: Generate hero image
    hero_path = DIGEST_DIR / "pipeline" / "data" / f"editorial-hero-{date}.jpg"
    hero_path.parent.mkdir(parents=True, exist_ok=True)
    print("\n  Step 4: Generating hero image...")
    hero_ok = generate_hero(blog_data, assets, hero_path)
    if not hero_ok:
        print("  WARNING: No hero image generated, continuing without")

    # Step 4b: Upload media
    print("\n  Step 4b: Uploading media to Supabase...")
    media_urls = upload_media(hero_path, assets.get("audio_path"), date)

    # Step 5: Generate OG card
    print("\n  Step 5: Generating OG card...")
    og_image_url = None
    if hero_path.exists():
        og_image_url = generate_og_card(
            hero_path, blog_data["title"], blog_data["subtitle"],
            date, DIGEST_DIR / "pipeline" / "data"
        )
    if not og_image_url:
        og_image_url = OG_FALLBACK_IMAGE

    # Step 6: Render HTML
    print("\n  Step 6: Rendering editorial HTML...")
    html, filename = render_editorial_html(
        blog_data, assets, media_urls, og_image_url, tag
    )

    # Step 7: Inject media strip
    print("\n  Step 7: Injecting media strip...")
    html = inject_media_strip(html, media_urls, assets)

    # Step 8: Write output
    # Check for existing same-date editorial
    editorial_dir = DIGEST_DIR / "editorial"
    output_path = editorial_dir / filename
    if output_path.exists():
        # Append -cinematic to avoid collision
        base = filename.rsplit('.html', 1)[0]
        filename = f"{base}-cinematic.html"
        output_path = editorial_dir / filename
        print(f"  Same-date editorial exists, using: {filename}")

    print(f"\n  Step 8: Writing {filename}...")
    output_path.write_text(html, encoding="utf-8")
    size_kb = output_path.stat().st_size // 1024
    print(f"  Written: editorial/{filename} ({size_kb}KB)")

    # Step 9: Update archives
    print("\n  Step 9: Updating archives and search index...")
    update_editorial_archive(
        blog_data["title"], filename, tag, date,
        blog_data["word_count"], blog_data["body"]
    )
    update_landing_page(
        blog_data["title"], filename, tag, date,
        blog_data["word_count"], blog_data["body"]
    )
    rebuild_search_index()

    # Summary
    print(f"\n  Done! Published: editorial/{filename}")
    print(f"  Live URL: https://www.koda.community/editorial/{filename}")
    print(f"  (git commit + push to deploy to Vercel)")


if __name__ == "__main__":
    main()
