"""
Step 05B: Generate AI tool deep reviews via Firecrawl.

Selects top 3 tools from today's digest, deep-scrapes each tool's website
(pricing, features, branding), and generates standalone review HTML pages.

Input:  pipeline/data/digest-content.json (reads tools array)
Output: reviews/{slug}.html (one per reviewed tool)
        pipeline/data/review-status.json (tracking)

Non-critical step: pipeline continues if this fails.
"""

import argparse
import json
import os
import re
import sys
import time
import httpx
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import (
    DIGEST_DIR, FIRECRAWL_API_KEY, OPENROUTER_API_KEY,
    today_str, write_json, read_json, ensure_data_dir,
)
from nav_component import NAV_CSS_V2, build_nav_v2

# Escape CSS braces for f-string usage
NAV_CSS_V2_ESCAPED = NAV_CSS_V2.replace("{", "{{").replace("}", "}}")

# ── Config ─────────────────────────────────────────────────────────────────

FIRECRAWL_API_URL = "https://api.firecrawl.dev/v1"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
LLM_MODEL = "anthropic/claude-opus-4-6"
REVIEWS_DIR = DIGEST_DIR / "reviews"
MAX_REVIEWS_PER_DAY = 3

WELL_KNOWN_TOOLS = {
    "chatgpt", "claude", "gemini", "copilot", "github copilot", "cursor",
    "zapier", "notion", "manus", "perplexity", "midjourney", "dall-e",
    "stable diffusion", "hugging face", "replicate", "vercel", "supabase",
}

def _extract_verdict(html: str) -> str:
    """Extract the first sentence from the verdict-card section of a review HTML."""
    match = re.search(r'class="verdict-card"[^>]*>(.*?)</(?:div|section)', html, re.DOTALL)
    if match:
        text = re.sub(r'<[^>]+>', ' ', match.group(1)).strip()
        # Remove leading emoji/icon names like "gavel Verdict"
        text = re.sub(r'^[\w\s]{0,20}Verdict\s*', '', text, flags=re.IGNORECASE).strip()
        sentences = [s.strip() for s in text.split('. ') if len(s.strip()) > 20]
        if sentences:
            return sentences[0].rstrip('.') + '.'
    # Fallback: search for any paragraph after "verdict" heading
    match2 = re.search(r'(?:verdict|Verdict).*?<p[^>]*>(.*?)</p>', html, re.DOTALL | re.IGNORECASE)
    if match2:
        text = re.sub(r'<[^>]+>', '', match2.group(1)).strip()
        first = text.split('. ')[0].rstrip('.') + '.'
        if len(first) > 20:
            return first
    return ""


def _extract_pricing(html: str) -> str:
    """Extract a short pricing summary from review HTML (e.g. 'Free', 'From $10/mo')."""
    text = re.sub(r'<[^>]+>', ' ', html)
    # Prefer specific dollar amounts over "free" (tools may have both free + paid tiers)
    price_match = re.search(r'\$\d+(?:\.\d{2})?(?:/mo(?:nth)?|/yr|/year|/user)', text, re.IGNORECASE)
    if price_match:
        return f"From {price_match.group(0)}"
    price_match2 = re.search(r'\$\d+(?:\.\d{2})?\s*/\s*(?:mo|month|year|yr)', text, re.IGNORECASE)
    if price_match2:
        return f"From {price_match2.group(0)}"
    # Simple "$X" near "pricing" or "plan"
    pricing_section = re.search(r'(?:pric|plan|cost).*?\$(\d+)', text, re.IGNORECASE)
    if pricing_section:
        return f"From ${pricing_section.group(1)}/mo"
    # Check for "open source"
    if re.search(r'\bopen[- ]source\b', text, re.IGNORECASE):
        return "Free / Open Source"
    # Only fall back to "Free" if no paid pricing found
    if re.search(r'\bfree\s+(?:plan|tier|forever|to use)\b', text, re.IGNORECASE):
        return "Free"
    return ""


REVIEW_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Product name"},
        "tagline": {"type": "string", "description": "One-line description"},
        "company": {"type": "string", "description": "Company or creator name"},
        "pricing": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "plan": {"type": "string"},
                    "price": {"type": "string"},
                    "features": {"type": "array", "items": {"type": "string"}},
                },
            },
            "description": "Pricing tiers (Free, Pro, Enterprise, etc.)",
        },
        "key_features": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Top 5-8 features",
        },
        "use_cases": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Primary use cases or target audiences",
        },
        "integrations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Notable integrations or platforms supported",
        },
        "limitations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Known limitations or missing features",
        },
    },
}


# ── Firecrawl Helpers ──────────────────────────────────────────────────────

def firecrawl_scrape(url: str, formats: list[str], json_schema: dict | None = None,
                     json_prompt: str = "", max_retries: int = 2) -> dict | None:
    """Scrape a URL with Firecrawl. Returns the full data dict."""
    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "url": url,
        "formats": formats,
        "timeout": 20000,
    }
    if json_schema and "json" in formats:
        json_options: dict[str, Any] = {"schema": json_schema}
        if json_prompt:
            json_options["prompt"] = json_prompt
        payload["jsonOptions"] = json_options

    for attempt in range(max_retries + 1):
        try:
            resp = httpx.post(
                f"{FIRECRAWL_API_URL}/scrape",
                json=payload, headers=headers, timeout=35,
            )
            resp.raise_for_status()
            return resp.json().get("data", {})
        except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
            print(f"    Firecrawl scrape error for {url} (attempt {attempt + 1}): {e}")
            if attempt < max_retries:
                time.sleep(2 ** attempt)
        except Exception as e:
            print(f"    Firecrawl unexpected error for {url}: {e}")
            return None
    return None


# ── LLM ────────────────────────────────────────────────────────────────────

def llm_call(prompt: str, system: str = "", max_tokens: int = 8000,
             max_retries: int = 2) -> str | None:
    """Call OpenRouter and return text response."""
    if not OPENROUTER_API_KEY:
        return None

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://koda.community",
        "X-Title": "Koda Digest Reviews",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }

    for attempt in range(max_retries + 1):
        try:
            resp = httpx.post(OPENROUTER_URL, json=payload, headers=headers, timeout=120)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
            print(f"    LLM error (attempt {attempt + 1}): {e}")
            if attempt < max_retries:
                time.sleep(2 ** attempt)
            else:
                return None
        except Exception as e:
            print(f"    LLM unexpected error: {e}")
            return None
    return None


# ── Tool Selection ─────────────────────────────────────────────────────────

def select_tools_for_review(tools: list[dict]) -> list[dict]:
    """Pick the top N tools from today's digest for deep review.

    Selection criteria:
    - Has a working URL
    - Not a well-known tool
    - Prioritize tools with richer descriptions
    """
    candidates = []
    for tool in tools:
        url = tool.get("url", "").strip()
        title = tool.get("title", "").strip()
        if not url or not url.startswith("http"):
            continue
        if not title:
            continue
        if any(known in title.lower() for known in WELL_KNOWN_TOOLS):
            continue
        candidates.append(tool)

    # Sort by body length (richer descriptions first) as a proxy for quality
    candidates.sort(key=lambda t: len(t.get("body", "")), reverse=True)
    return candidates[:MAX_REVIEWS_PER_DAY]


def slugify(text: str) -> str:
    """Convert tool name to URL-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s-]+', '-', slug)
    return slug.strip('-')


# ── Review Generation ──────────────────────────────────────────────────────

def deep_scrape_tool(url: str, tool_name: str) -> dict:
    """Deep-scrape a tool's website using Firecrawl with JSON + branding extraction."""
    print(f"    Scraping {tool_name} ({url})...")

    # Primary scrape: structured data + branding
    data = firecrawl_scrape(
        url,
        formats=["json", "branding", "screenshot"],
        json_schema=REVIEW_EXTRACTION_SCHEMA,
        json_prompt=(
            "Extract the product name, pricing tiers with features, "
            "key features, use cases, integrations, and limitations "
            "from this product/tool landing page."
        ),
    )

    result: dict[str, Any] = {
        "url": url,
        "name": tool_name,
        "structured": {},
        "branding": {},
        "screenshot_url": "",
    }

    if not data:
        print(f"      Primary scrape failed")
        return result

    result["structured"] = data.get("json", {})
    result["branding"] = data.get("branding", {})
    result["screenshot_url"] = data.get("screenshot", "")

    if result["screenshot_url"]:
        print(f"      Screenshot captured")

    structured = result["structured"]
    feature_count = len(structured.get("key_features", []))
    pricing_count = len(structured.get("pricing", []))
    print(f"      Extracted: {feature_count} features, {pricing_count} pricing tiers")

    return result


REVIEW_SYSTEM_PROMPT = """You are the editor of Koda Intelligence Briefing (koda.community), writing a tool deep review.
Write in a direct, analytical voice. Be specific with pricing, features, and comparisons.
Do NOT use em dashes. Use commas, semicolons, or periods instead.
The review should be genuinely useful to someone deciding whether to use this tool."""


def generate_review_html(tool: dict, scrape_data: dict, date: str) -> str | None:
    """Generate a complete self-contained review HTML page via LLM."""
    structured = scrape_data.get("structured", {})
    branding = scrape_data.get("branding", {})
    hero_url = scrape_data.get("hero_url", "")

    context_parts = [
        f"Tool: {tool.get('title', '')}",
        f"URL: {tool.get('url', '')}",
        f"From digest: {tool.get('body', '')}",
    ]
    if hero_url:
        context_parts.append(f"Hero image URL (screenshot of the tool): {hero_url}")

    if structured:
        context_parts.append(f"\nStructured data from website:\n{json.dumps(structured, indent=2)}")
    if branding:
        context_parts.append(f"\nBranding data:\n{json.dumps(branding, indent=2)}")

    context = "\n".join(context_parts)

    prompt = f"""Generate a complete, self-contained HTML review page for this AI tool.

{context}

Date: {date}

DESIGN SYSTEM (must match exactly):
- Font: Inter (300-900) + JetBrains Mono (400,500,700) via Google Fonts
- Icon font: Material Symbols Outlined via Google Fonts
- Background: #0b1326
- Card backgrounds: rgba(23,31,51,0.4) with border: 1px solid rgba(255,255,255,0.06), border-radius: 12px
- Text: #dae2fd (body), #dae2fd (headings), #c2c6d6 (secondary), #8c909f (muted)
- Accent: #8B5CF6 (purple, primary for The Lab), #3B82F6 (blue, secondary)
- Links: #3B82F6
- Gradients: linear-gradient(135deg, #3B82F6, #8B5CF6) for buttons and brand icon

TOPBAR (fixed, 56px height):
- Background: rgba(11,19,38,0.8) with backdrop-filter: blur(20px)
- Left: brand link to ../index.html with 32x32 gradient "K" icon + "Koda Intelligence" text (14px, 700, color #3B82F6) + sub-text "The Lab" (10px, color #8c909f)
- Right: ALL 7 nav links in JetBrains Mono 10px/700 (gap 4px):
  bolt "The Signal" -> ../morning-briefing-koda.html
  explore "Deep Dive" -> ../editorial/
  monitoring "Token Tracker" -> ../pricing/
  trophy "Leaderboard" -> ../benchmarks/
  science "The Lab" -> ../reviews/ (ACTIVE: highlighted with color #3B82F6 and blue bg)
  pulse_alert "Pulse" -> ../changelog/
  lock_open "The Vault" -> ../archive/
  Home button (gradient) -> ../index.html
- On mobile (@media max-width:768px): hide all except active link + Home

PAGE STRUCTURE:
1. Hero: purple badge "Lab Report", tool name as gradient h1 (clamp 28px-48px), tagline, prominent "Try It" CTA button linking to {tool.get('url', '')}. If a hero image URL is provided in the context, render it below the hero text as: <img src="HERO_URL" alt="Tool screenshot" style="max-width:800px;width:100%;border-radius:12px;border:1px solid rgba(255,255,255,0.08);margin:24px auto 0;display:block" loading="eager">
2. Verdict: 2-3 sentence editorial verdict in a highlighted card (who is this for, is it worth it)
3. Pricing table: all tiers with features using the scraped data. Use a grid on desktop, stack on mobile.
4. Key Features: 2-column grid of feature cards (5-8 features) with material icon per card
5. Use Cases: who should use this and why
6. Limitations: honest assessment of gaps (be direct, not mean)
7. Bottom CTA: "Try It" button + "Back to The Lab" link to ../reviews/ + "Back to The Signal" link to ../morning-briefing-koda.html

FOOTER:
- Background: #060e20, border-top: 1px solid rgba(255,255,255,0.06)
- "Koda Intelligence" + date + nav links (Home, The Signal, The Lab)
- Flex column on mobile, row on desktop

CRITICAL RULES:
- NO em dashes. Use commas, semicolons, or periods.
- Mobile-first: all grids collapse to single column below 768px
- All external links: target="_blank" rel="noopener"
- IntersectionObserver animations: .animate-in class (opacity 0->1, translateY 24px->0)
- Scroll progress bar at top (3px gradient #3B82F6 to #8B5CF6)
- scroll-margin-top: 80px on sections
- Self-contained: all CSS inline in <style> tag

Return ONLY the complete HTML document. No markdown code fences. No explanation text."""

    return llm_call(prompt, REVIEW_SYSTEM_PROMPT, max_tokens=12000)


# ── Archive Index ──────────────────────────────────────────────────────────

def update_review_index(reviews_dir: Path) -> None:
    """Regenerate reviews/index.html from all review files."""
    review_files = sorted(reviews_dir.glob("*.html"), reverse=True)
    review_files = [f for f in review_files if f.name != "index.html"]

    # Extract metadata from filenames (YYYY-MM-DD-slug.html)
    entries = []
    for f in review_files:
        name = f.stem  # e.g. "2026-04-04-fabricate"
        parts = name.split("-", 3)
        if len(parts) >= 4:
            date_str = f"{parts[0]}-{parts[1]}-{parts[2]}"
            slug = parts[3]
            display_name = slug.replace("-", " ").title()
        else:
            date_str = ""
            display_name = name.replace("-", " ").title()
        entries.append({
            "file": f.name,
            "date": date_str,
            "name": display_name,
        })

    # Read the template approach from editorial index
    html = _build_review_index_html(entries)
    index_path = reviews_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    print(f"    Updated review index: {len(entries)} reviews")


def _build_review_index_html(entries: list[dict]) -> str:
    """Build the reviews archive index page matching site design system."""
    _css, reviews_nav_html, reviews_nav_js = build_nav_v2(
        current_page="reviews",
        url_prefix="../",
        page_subtitle="The Lab",
        page_icon="science",
        share_url="https://www.koda.community/reviews/",
    )
    cards = ""
    for e in entries:
        cards += f"""
        <a href="./{e['file']}" class="review-card animate-in" style="text-decoration:none">
            <div style="display:flex;justify-content:space-between;align-items:center">
                <div style="min-width:0">
                    <div style="font-size:17px;font-weight:700;color:#dae2fd;margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{e['name']}</div>
                    <div style="font-size:12px;color:#8c909f">{e['date']}</div>
                </div>
                <span style="color:#8B5CF6;font-size:13px;font-weight:600;white-space:nowrap;margin-left:16px" class="material-symbols-outlined" title="Read">arrow_forward</span>
            </div>
        </a>"""

    if not cards:
        cards = '<div class="empty-state animate-in"><span class="material-symbols-outlined" style="font-size:48px;color:#3B82F6;margin-bottom:16px;display:block">science</span><p style="color:#8c909f;font-size:15px">No lab reports yet. First reviews drop with tomorrow\'s digest.</p></div>'

    review_count = len(entries)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>The Lab | Koda Intelligence</title>
<meta name="description" content="Hands-on AI tool deep dives with pricing, features, and honest verdicts from the Koda Intelligence team.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Inter',sans-serif;background:#0b1326;color:#dae2fd;min-height:100vh;overflow-x:hidden}}
.material-symbols-outlined{{font-variation-settings:'FILL' 0,'wght' 400,'GRAD' 0,'opsz' 24;display:inline-block;vertical-align:middle}}
.scroll-progress{{position:fixed;top:0;left:0;width:0%;height:3px;background:linear-gradient(90deg,#3B82F6,#8B5CF6);z-index:1001;transition:width 0.1s linear;pointer-events:none}}
{NAV_CSS_V2_ESCAPED}
/* -- End Koda Nav V2 -- */
.hero{{padding:100px 24px 40px;text-align:center;background:radial-gradient(ellipse 80% 50% at 20% 60%,rgba(139,92,246,0.12) 0%,transparent 100%),radial-gradient(ellipse 60% 40% at 80% 30%,rgba(59,130,246,0.08) 0%,transparent 100%)}}
.hero h1{{font-size:clamp(28px,5vw,48px);font-weight:900;background:linear-gradient(135deg,#8B5CF6 0%,#3B82F6 50%,#EC4899 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:8px;letter-spacing:-0.02em}}
.hero p{{color:#c2c6d6;font-size:15px;max-width:600px;margin:0 auto}}
.hero .badge{{display:inline-block;padding:4px 14px;border-radius:9999px;border:1px solid rgba(139,92,246,0.2);background:rgba(139,92,246,0.05);color:#a78bfa;font-size:10px;text-transform:uppercase;letter-spacing:0.2em;font-weight:700;margin-bottom:16px}}
.stats{{display:flex;gap:16px;justify-content:center;flex-wrap:wrap;padding:0 24px;margin-bottom:32px}}
.stat{{background:rgba(23,31,51,0.4);backdrop-filter:blur(20px);border:1px solid rgba(173,198,255,0.1);border-radius:12px;padding:16px 24px;text-align:center;min-width:120px}}
.stat-value{{font-size:24px;font-weight:800;color:#dae2fd}}
.stat-label{{font-size:11px;color:#8c909f;margin-top:2px;text-transform:uppercase;letter-spacing:0.05em}}
.container{{max-width:900px;margin:0 auto;padding:0 24px 64px}}
.review-card{{display:block;background:rgba(23,31,51,0.4);border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:18px 20px;margin-bottom:10px;transition:all 0.2s}}
.review-card:hover{{background:rgba(23,31,51,0.7);border-color:rgba(139,92,246,0.3)}}
.empty-state{{text-align:center;padding:60px 24px}}
footer{{background:#060e20;border-top:1px solid rgba(255,255,255,0.06);margin-top:auto}}
footer .inner{{max-width:1280px;margin:0 auto;display:flex;flex-direction:column;align-items:center;padding:32px 24px;gap:12px;text-align:center}}
@media(min-width:768px){{footer .inner{{flex-direction:row;justify-content:space-between;text-align:left}}}}
.animate-in{{opacity:0;transform:translateY(24px);transition:opacity 0.7s cubic-bezier(0.16,1,0.3,1),transform 0.7s cubic-bezier(0.16,1,0.3,1)}}
.animate-in.visible{{opacity:1;transform:translateY(0)}}
</style>
</head>
<body>
<div class="scroll-progress" id="scrollProgress"></div>
{reviews_nav_html}
<section class="hero animate-in">
    <div class="badge">Hands-On Tool Intelligence</div>
    <h1>The Lab</h1>
    <p>We scrape, test, and break down the AI tools everyone is talking about. Pricing, features, and honest verdicts so you do not have to guess.</p>
</section>
<div class="stats animate-in">
    <div class="stat"><div class="stat-value">{review_count}</div><div class="stat-label">Lab Reports</div></div>
    <div class="stat"><div class="stat-value">3</div><div class="stat-label">New Per Day</div></div>
</div>
<div class="container">
    {cards}
</div>
<footer>
    <div class="inner">
        <div>
            <div style="font-weight:700;font-size:14px;color:#dae2fd;margin-bottom:4px">Koda Intelligence</div>
            <div style="font-size:12px;color:#8c909f">AI-powered daily intelligence for builders and operators.</div>
        </div>
        <div style="display:flex;gap:16px;align-items:center">
            <a href="../index.html" style="color:#8c909f;text-decoration:none;font-size:12px">Home</a>
            <a href="../morning-briefing-koda.html" style="color:#8c909f;text-decoration:none;font-size:12px">The Signal</a>
            <a href="../editorial/" style="color:#8c909f;text-decoration:none;font-size:12px">Deep Dive</a>
        </div>
    </div>
</footer>
<script>
// Scroll progress
window.addEventListener('scroll',function(){{var p=document.getElementById('scrollProgress');if(p){{var h=document.documentElement.scrollHeight-window.innerHeight;p.style.width=h>0?(window.scrollY/h*100)+'%':'0%'}}}});
// Animate in
var obs=new IntersectionObserver(function(e){{e.forEach(function(en){{if(en.isIntersecting)en.target.classList.add('visible')}});}},{{threshold:0.1}});
document.querySelectorAll('.animate-in').forEach(function(el){{obs.observe(el)}});
</script>
{reviews_nav_js}
</body>
</html>"""


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Step 05B: Generate tool deep reviews")
    parser.add_argument("--date", default=today_str(), help="Date (YYYY-MM-DD)")
    args = parser.parse_args()

    ensure_data_dir()
    REVIEWS_DIR.mkdir(exist_ok=True)

    # Load today's tools from digest
    digest = read_json("digest-content.json")
    if not digest:
        print("  No digest-content.json found. Skipping reviews.")
        sys.exit(0)

    tools = digest.get("tools", [])
    if not tools:
        print("  No tools in digest. Skipping reviews.")
        sys.exit(0)

    # Check API keys
    if not FIRECRAWL_API_KEY:
        print("  WARNING: No FIRECRAWL_API_KEY. Skipping reviews.")
        sys.exit(0)
    if not OPENROUTER_API_KEY:
        print("  WARNING: No OPENROUTER_API_KEY. Skipping reviews.")
        sys.exit(0)

    # Select tools for review
    selected = select_tools_for_review(tools)
    if not selected:
        print("  No eligible tools for review. Skipping.")
        sys.exit(0)

    print(f"  Selected {len(selected)} tools for deep review:")
    for t in selected:
        print(f"    - {t.get('title', '?')} ({t.get('url', '?')})")

    # Generate reviews
    review_results = []
    for tool in selected:
        title = tool.get("title", "Unknown Tool")
        url = tool.get("url", "")
        slug = slugify(title)
        filename = f"{args.date}-{slug}.html"
        filepath = REVIEWS_DIR / filename

        print(f"\n  Reviewing: {title}")

        # Deep scrape
        scrape_data = deep_scrape_tool(url, title)

        # Download screenshot and upload to Supabase
        hero_url = ""
        screenshot_src = scrape_data.get("screenshot_url", "")
        if screenshot_src:
            try:
                print(f"    Downloading screenshot...")
                img_resp = httpx.get(screenshot_src, timeout=20, follow_redirects=True)
                img_resp.raise_for_status()
                hero_filename = f"review-hero-{args.date}-{slug}.jpg"
                hero_path = REVIEWS_DIR / hero_filename
                hero_path.write_bytes(img_resp.content)
                print(f"    Saved: reviews/{hero_filename} ({len(img_resp.content) // 1024}KB)")

                # Upload to Supabase if keys available
                from pipeline.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
                if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
                    from supabase_upload import upload_file
                    hero_url = upload_file(str(hero_path), SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
                    print(f"    Uploaded to Supabase: {hero_url}")
                else:
                    # Fallback: serve from relative path via Vercel
                    hero_url = f"./reviews/{hero_filename}"
                    print(f"    No Supabase keys; using relative path")
            except Exception as e:
                print(f"    Screenshot download/upload failed (non-critical): {e}")

        scrape_data["hero_url"] = hero_url

        # Generate HTML
        print(f"    Generating review HTML...")
        html = generate_review_html(tool, scrape_data, args.date)

        if not html:
            print(f"    Failed to generate review HTML. Skipping {title}.")
            review_results.append({"tool": title, "success": False, "reason": "LLM generation failed"})
            continue

        # Strip markdown fences if present
        html = html.strip()
        if html.startswith("```"):
            html = re.sub(r'^```\w*\n?', '', html)
            html = re.sub(r'\n?```$', '', html)

        filepath.write_text(html, encoding="utf-8")
        print(f"    Saved: reviews/{filename}")

        # Extract verdict + pricing from generated HTML for email enrichment
        review_verdict = _extract_verdict(html)
        review_pricing = _extract_pricing(html)
        review_hero_url = scrape_data.get("hero_url", "")

        review_results.append({
            "tool": title,
            "slug": slug,
            "url": url,
            "file": filename,
            "review_url": f"/reviews/{filename}",
            "review_verdict": review_verdict,
            "review_pricing": review_pricing,
            "review_hero_url": review_hero_url,
            "success": True,
        })

    # Update archive index
    print(f"\n  Updating review archive index...")
    update_review_index(REVIEWS_DIR)

    # Inject review metadata back into digest-content.json so email can render rich cards
    successful_reviews = {
        r["tool"]: {
            "review_url": r["review_url"],
            "review_verdict": r.get("review_verdict", ""),
            "review_pricing": r.get("review_pricing", ""),
            "review_hero_url": r.get("review_hero_url", ""),
        }
        for r in review_results if r.get("success")
    }
    if successful_reviews:
        updated_tools = [
            {**t, **successful_reviews[t.get("title", "")]}
            if t.get("title", "") in successful_reviews else t
            for t in digest.get("tools", [])
        ]
        updated_digest = {**digest, "tools": updated_tools}
        write_json("digest-content.json", updated_digest)
        print(f"    Injected {len(successful_reviews)} review URLs + metadata into digest-content.json")

    # Save status
    status = {
        "date": args.date,
        "generated_at": datetime.now().isoformat(),
        "reviews": review_results,
        "total": len(review_results),
        "successful": sum(1 for r in review_results if r.get("success")),
    }
    write_json("review-status.json", status)
    print(f"\n  Reviews complete: {status['successful']}/{status['total']} succeeded")


if __name__ == "__main__":
    main()
