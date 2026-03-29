"""
Step 04E (08): Generate Daily Editorial.

Picks the strongest angle from today's digest, researches it via Perplexity,
drafts a 1200-1800 word article using Koda voice, applies fact-checking,
generates a hero image, and renders HTML from the editorial template.

Input:  pipeline/data/digest-content.json
        editorial/koda-voice-guide.md
        editorial/fact-check-framework.md
        editorial/template-editorial.html
Output: editorial/YYYY-MM-DD-slug.html
        pipeline/data/editorial-status.json

Usage:
    python -m pipeline.08_generate_editorial --date 2026-03-29
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import DIGEST_DIR, today_str, read_json, write_json

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPUS_MODEL = "anthropic/claude-opus-4-6"
SONNET_MODEL = "anthropic/claude-sonnet-4-6"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"
PERPLEXITY_MODEL = "sonar-pro"
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "")

LEONARDO_API_KEY = os.environ.get("LEONARDO_API_KEY", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

EXPERT_ROUTING = {
    "tools": "Jack Roberts",
    "automation": "Jack Roberts",
    "agents": "Jack Roberts",
    "apis": "Jack Roberts",
    "monetization": "Paul J Lipsky",
    "business model": "Paul J Lipsky",
    "side hustle": "Paul J Lipsky",
    "scaling": "Dan Martell",
    "leadership": "Dan Martell",
    "saas": "Dan Martell",
    "hiring": "Dan Martell",
    "strategy": "theMITmonk",
    "career": "theMITmonk",
    "investing": "theMITmonk",
    "content creation": "Sabrina Ramonov",
    "personal brand": "Sabrina Ramonov",
    "sales": "Alex Hormozi",
    "pricing": "Alex Hormozi",
    "marketing": "Alex Hormozi",
    "open-source": "theMITmonk",
    "open-weight": "theMITmonk",
    "model release": "Jack Roberts",
    "benchmark": "Jack Roberts",
    "geopolitics": "theMITmonk",
    "regulation": "theMITmonk",
}


def _llm_call(prompt: str, system: str = "", model: str = OPUS_MODEL,
              max_tokens: int = 4000, temperature: float = 0.6) -> str | None:
    """Make an LLM call via OpenRouter. Returns text or None."""
    if not OPENROUTER_API_KEY:
        print("  ERROR: OPENROUTER_API_KEY not set")
        return None
    try:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = httpx.post(
            OPENROUTER_URL,
            json={"model": model, "messages": messages,
                  "max_tokens": max_tokens, "temperature": temperature},
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://koda.community",
                "X-Title": "Koda Editorial Pipeline",
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"  ERROR: LLM call failed: {type(e).__name__}: {e}")
        return None


def _perplexity_call(query: str) -> dict | None:
    """Make a Perplexity search call. Returns content + citations or None."""
    if not PERPLEXITY_API_KEY:
        print("  WARNING: PERPLEXITY_API_KEY not set, skipping research")
        return None
    try:
        resp = httpx.post(
            PERPLEXITY_URL,
            json={
                "model": PERPLEXITY_MODEL,
                "messages": [
                    {"role": "system", "content": "Provide detailed, factual information with specific numbers, dates, and source names. Include contrarian perspectives where relevant."},
                    {"role": "user", "content": query},
                ],
                "max_tokens": 2000,
                "temperature": 0.1,
                "return_citations": True,
            },
            headers={
                "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "content": data["choices"][0]["message"]["content"],
            "citations": data.get("citations", []),
        }
    except Exception as e:
        print(f"  WARNING: Perplexity call failed: {type(e).__name__}: {e}")
        return None


# ── Step 01E: Topic Selection ────────────────────────────────────────────────

def select_topic(digest: dict) -> dict | None:
    """Score stories and select the best editorial topic."""
    stories = []
    for story in digest.get("ai_news", []):
        stories.append({"title": story["title"], "body": story.get("body", ""), "section": "AI"})
    for story in digest.get("world_news", []):
        stories.append({"title": story["title"], "body": story.get("body", ""), "section": "World"})
    for story in digest.get("competitive", []):
        title = story.get("title") or f"{story.get('name', '')} — {story.get('status', '')}".strip(" —")
        stories.append({"title": title, "body": story.get("body", ""), "section": "Competitive"})

    if not stories:
        return None

    story_list = "\n".join(
        f"- [{s['section']}] {s['title']}: {s['body'][:200]}" for s in stories[:15]
    )

    prompt = f"""You are selecting a topic for the Koda daily editorial -- a 1,200-1,800 word analysis piece.

Score each story on these 5 criteria (1-5 each):
1. Counterintuitive angle? (surprising, challenges assumptions)
2. Affects builders? (actionable for developers, founders, product people)
3. Quantitative data available? (specific numbers to anchor the argument)
4. Framework potential? (can you name a principle around it?)
5. Shareable? (would a reader forward this to a colleague?)

Today's stories:
{story_list}

Output ONLY valid JSON (no markdown):
{{"topic": "one sentence topic statement", "story_title": "which story this came from", "expert_overlay": "name from routing table", "data_points": ["point 1", "point 2", "point 3"], "score": total_score, "tag": "one word category tag like Strategy, Tools, Markets, etc"}}

Expert routing table:
- Tools/automation/APIs/agents -> Jack Roberts
- Monetization/business models -> Paul J Lipsky
- Scaling/leadership/SaaS -> Dan Martell
- Strategy/career/investing/open-source -> theMITmonk
- Content creation/personal brand -> Sabrina Ramonov
- Sales/pricing/marketing -> Alex Hormozi"""

    result = _llm_call(prompt, model=SONNET_MODEL, max_tokens=500, temperature=0.3)
    if not result:
        return None

    try:
        # Strip markdown code fences if present
        cleaned = re.sub(r'^```(?:json)?\s*', '', result.strip())
        cleaned = re.sub(r'\s*```$', '', cleaned)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"  WARNING: Could not parse topic selection: {result[:200]}")
        # Fallback: use the first AI story
        first = stories[0]
        return {
            "topic": first["title"],
            "story_title": first["title"],
            "expert_overlay": "theMITmonk",
            "data_points": [first["body"][:150]],
            "score": 15,
            "tag": "Strategy",
        }


# ── Step 02E: Deep Research ──────────────────────────────────────────────────

def research_topic(topic: dict) -> dict:
    """Research the selected topic via Perplexity."""
    research: dict[str, Any] = {"primary": None, "contrarian": None, "data": None}

    topic_text = topic["topic"]
    print(f"  Researching: {topic_text}")

    # Primary research
    primary = _perplexity_call(
        f"Detailed analysis of: {topic_text}. Include specific numbers, dates, company names, and market data. March 2026."
    )
    if primary:
        research["primary"] = primary
        print(f"    Primary: {len(primary['content'])} chars, {len(primary['citations'])} citations")

    # Contrarian perspective
    contrarian = _perplexity_call(
        f"What are the strongest counterarguments or risks to: {topic_text}? What could go wrong? Who disagrees?"
    )
    if contrarian:
        research["contrarian"] = contrarian
        print(f"    Contrarian: {len(contrarian['content'])} chars")

    # Additional data points
    data = _perplexity_call(
        f"Key statistics, benchmark numbers, market sizes, and adoption rates related to: {topic_text}. March 2026."
    )
    if data:
        research["data"] = data
        print(f"    Data: {len(data['content'])} chars")

    return research


# ── Step 03E: Draft Article ──────────────────────────────────────────────────

def draft_article(topic: dict, research: dict, voice_guide: str, digest: dict) -> str | None:
    """Draft the editorial using the Koda voice system."""
    # Build research context
    research_text = ""
    if research.get("primary"):
        research_text += f"\n\nPRIMARY RESEARCH:\n{research['primary']['content']}"
    if research.get("contrarian"):
        research_text += f"\n\nCONTRARIAN PERSPECTIVES:\n{research['contrarian']['content']}"
    if research.get("data"):
        research_text += f"\n\nADDITIONAL DATA:\n{research['data']['content']}"

    # Build digest context (tools for the "Build" section)
    tools_text = ""
    for tool in digest.get("tools", [])[:4]:
        tools_text += f"- {tool['title']}: {tool.get('body', '')[:100]}\n"

    expert = topic.get("expert_overlay", "theMITmonk")
    tag = topic.get("tag", "Strategy")

    system_prompt = f"""You are writing a Koda editorial article. Follow the voice guide EXACTLY.

{voice_guide}

EXPERT OVERLAY FOR THIS ARTICLE: {expert}
The deep dive section (section 3) should use {expert}'s vocabulary and teaching style.

MANDATORY CONSTRAINTS:
- Zero em dashes (use commas, periods, or "and" instead)
- No banned phrases: "dive into", "game-changer", "buckle up", "let's unpack", "In today's rapidly evolving"
- No paragraph longer than 4 sentences
- No sentence over 30 words
- Every section has at least one specific number, name, or date
- At least one editorial opinion ("I think..." or "My read on this...")
- At least one hedge ("It is unclear whether..." or "The data is mixed on...")
- Word count: 1,200-1,800 words total
- Do NOT include a Sources or References section at the end"""

    user_prompt = f"""Write a Koda editorial article on this topic:

TOPIC: {topic['topic']}
TAG: {tag}
KEY DATA POINTS: {json.dumps(topic.get('data_points', []))}

RESEARCH:{research_text}

TOOLS FROM TODAY'S DIGEST (reference in the Build section):
{tools_text}

Write the article with these exact 5 sections using ## headings:

## [Framework Name] (section 2 - name it something memorable)
## [Deep Dive Heading] (section 3)
## [Year - e.g., 2031] (section 4 - the zoom out)
## What to Build This Weekend (section 5)

The hook (section 1) has no heading -- it is the opening paragraphs before the first ##.

Output the article as clean text with ## headings. No markdown code fences. No metadata."""

    return _llm_call(user_prompt, system=system_prompt, model=OPUS_MODEL,
                     max_tokens=4000, temperature=0.6)


# ── Step 04F: Fact-Check ─────────────────────────────────────────────────────

def fact_check_article(article: str) -> tuple[str, list[dict]]:
    """Extract and verify key claims. Returns corrected article + verification log."""
    log: list[dict] = []

    # Extract specific numbers and claims
    claims = re.findall(
        r'(?:(?:\d+(?:\.\d+)?[%BMK]?\s+(?:percent|billion|million|parameter|release|model|percent))|'
        r'(?:\$[\d,.]+\s*(?:billion|million)?)|'
        r'(?:\d+(?:\.\d+)?x\s+\w+)|'
        r'(?:(?:GPQA|MMLU|HumanEval|MATH|Arena)\s+(?:score\s+(?:of\s+)?)?\d+\.?\d*%?))',
        article, re.IGNORECASE
    )

    if not claims:
        print("  No specific claims to verify")
        return article, log

    print(f"  Found {len(claims)} claims to verify")

    # Verify the most impactful claims (max 5 to keep pipeline fast)
    corrected = article
    for claim in claims[:5]:
        result = _perplexity_call(
            f"Verify this specific claim (March 2026): \"{claim}\". Is this number accurate? Reply in one sentence."
        )
        if result:
            content = result["content"].upper()
            verdict = "PLAUSIBLE"
            if "INACCURATE" in content or "INCORRECT" in content or "FALSE" in content or "WRONG" in content:
                verdict = "INACCURATE"
            elif "CONFIRMED" in content or "ACCURATE" in content or "CORRECT" in content or "VERIFIED" in content:
                verdict = "VERIFIED"

            log.append({"claim": claim, "verdict": verdict, "detail": result["content"][:200]})
            print(f"    {verdict}: {claim}")

            if verdict == "INACCURATE":
                # Hedge the claim
                corrected = corrected.replace(claim, f"approximately {claim}")
        else:
            log.append({"claim": claim, "verdict": "UNVERIFIABLE", "detail": "Perplexity unavailable"})

    return corrected, log


# ── Step 05E: Hero Image ─────────────────────────────────────────────────────

_TAG_SUBJECTS: dict[str, str] = {
    "strategy":   "a cathedral of crystalline data pillars rising into deep space, one beam of violet light cutting through the darkness",
    "tools":      "an intricate network of glowing API nodes and data pipelines converging at a single supernova-bright point",
    "automation": "streams of light-coded instructions flowing through a dark geometric lattice, executing in perfect parallel",
    "markets":    "cascading golden data particles falling through dark angular architecture like a digital waterfall",
    "ai":         "a fractal neural network branching outward from a luminous core, each node pulsing with violet energy",
    "leadership": "towering abstract structures ascending through dark volumetric fog toward a single point of light",
    "saas":       "interconnected orbital rings of data spinning around a glowing infrastructure core in deep space",
    "content":    "flowing luminescent ribbons of light weaving through a dark infinite canvas",
    "sales":      "bold geometric forms erupting from darkness with amber and blue light, conveying momentum and impact",
    "investing":  "long-exposure light trails tracing upward arcs through a dark mathematical landscape",
}


def generate_editorial_hero(topic: dict, date: str) -> str | None:
    """Generate a hero image for the editorial via Leonardo.ai. Returns URL or None."""
    import time

    hero_filename = f"editorial-hero-{date}.jpg"
    hero_path = DIGEST_DIR / hero_filename

    if not LEONARDO_API_KEY:
        print("  WARNING: No LEONARDO_API_KEY, skipping hero image")
        return None

    if hero_path.exists():
        print(f"  Hero image already exists: {hero_filename}")
    else:
        tag = (topic.get("tag", "") or "").lower()
        subject = _TAG_SUBJECTS.get(tag)

        # Fall back to keyword scan of the topic text
        if not subject:
            topic_text = (topic.get("topic", "") or "").lower()
            for key, subj in _TAG_SUBJECTS.items():
                if key in topic_text:
                    subject = subj
                    break
        if not subject:
            subject = _TAG_SUBJECTS["ai"]

        image_prompt = (
            f"Cinematic digital art: {subject}. "
            f"Dark moody atmosphere, deep shadows, volumetric lighting, rich contrast. "
            f"Color palette: deep navy, electric blue, violet purple, subtle cyan accents. "
            f"Wide composition, no people, no faces, no bodies, no hands. "
            f"Absolutely NO text, NO words, NO labels, NO numbers, NO letters, NO typography anywhere. "
            f"Clean abstract visual only. Photorealistic 3D render, dramatic cinematic lighting."
        )

        print(f"  Generating editorial hero via Leonardo.ai...")

        headers = {
            "authorization": f"Bearer {LEONARDO_API_KEY}",
            "Content-Type": "application/json",
            "accept": "application/json",
        }
        payload = {
            "model": "gemini-2.5-flash-image",
            "parameters": {
                "width": 1024,
                "height": 576,
                "prompt": image_prompt,
                "quantity": 1,
                "style_ids": ["111dc692-d470-4eec-b791-3475abac4c46"],
                "prompt_enhance": "OFF",
            },
            "public": False,
        }

        try:
            resp = httpx.post(
                "https://cloud.leonardo.ai/api/rest/v2/generations",
                json=payload, headers=headers, timeout=30,
            )
            resp.raise_for_status()
            generation_id = resp.json().get("generate", {}).get("generationId")
            if not generation_id:
                print(f"  WARNING: No generation ID returned: {resp.json()}")
                return None

            poll_url = f"https://cloud.leonardo.ai/api/rest/v1/generations/{generation_id}"
            for attempt in range(30):
                time.sleep(3)
                poll = httpx.get(poll_url, headers=headers, timeout=15)
                poll.raise_for_status()
                gen = poll.json().get("generations_by_pk", {})
                state = gen.get("status", "")

                if state == "COMPLETE":
                    images = gen.get("generated_images", [])
                    if not images:
                        print("  WARNING: Generation complete but no images returned")
                        return None
                    img_data = httpx.get(images[0]["url"], timeout=30)
                    img_data.raise_for_status()
                    with open(hero_path, "wb") as f:
                        f.write(img_data.content)
                    size_kb = hero_path.stat().st_size // 1024
                    print(f"  Hero image saved: {hero_filename} ({size_kb}KB)")
                    break
                elif state == "FAILED":
                    print("  WARNING: Leonardo generation failed")
                    return None
                if attempt % 5 == 4:
                    print(f"    Still generating... ({(attempt + 1) * 3}s)")
            else:
                print("  WARNING: Leonardo generation timed out after 90s")
                return None

        except Exception as e:
            print(f"  WARNING: Hero image generation failed: {e}")
            if hero_path.exists():
                hero_path.unlink()
            return None

    # Upload to Supabase
    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and hero_path.exists():
        try:
            upload_url = f"{SUPABASE_URL}/storage/v1/object/koda-media/{hero_filename}"
            with open(hero_path, "rb") as f:
                img_bytes = f.read()
            upload_resp = httpx.put(
                upload_url,
                content=img_bytes,
                headers={
                    "apikey": SUPABASE_SERVICE_ROLE_KEY,
                    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                    "Content-Type": "image/jpeg",
                    "x-upsert": "true",
                },
                timeout=30,
            )
            upload_resp.raise_for_status()
            public_url = f"{SUPABASE_URL}/storage/v1/object/public/koda-media/{hero_filename}"
            print(f"  Uploaded to Supabase: {public_url}")
            return public_url
        except Exception as e:
            print(f"  WARNING: Supabase upload failed: {e}")

    # Relative fallback (served by Vercel)
    if hero_path.exists():
        return f"../{hero_filename}"

    return None


# ── Step 06E: Render HTML ────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    slug = text.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s-]+', '-', slug).strip('-')
    return slug[:60]


def render_html(article: str, topic: dict, date: str, hero_url: str | None = None) -> str:
    """Render editorial HTML from the article text."""
    tag = topic.get("tag", "Strategy")
    expert = topic.get("expert_overlay", "theMITmonk")

    # Parse article into sections
    # Hook is everything before the first ##
    sections = re.split(r'\n##\s+', article)
    hook = sections[0].strip() if sections else ""
    named_sections = sections[1:] if len(sections) > 1 else []

    # Extract title from first strong claim in hook
    first_line = hook.split('\n')[0].strip()
    # Generate a proper title from the topic
    title = topic.get("topic", first_line)[:80]

    # Build subtitle from hook
    hook_sentences = re.split(r'(?<=[.!?])\s+', hook)
    subtitle = ' '.join(hook_sentences[:2])[:200] if hook_sentences else ""

    # Format date
    dt = datetime.strptime(date, "%Y-%m-%d")
    date_display = dt.strftime("%d %B %Y")

    # Word count
    word_count = len(article.split())
    read_time = max(1, word_count // 250)

    # Build body HTML
    body_html = ""

    # Hook paragraphs
    for para in hook.split('\n\n'):
        para = para.strip()
        if para:
            body_html += f"    <p>{para}</p>\n"

    # Named sections
    for sec in named_sections:
        lines = sec.strip().split('\n', 1)
        heading = lines[0].strip()
        content = lines[1].strip() if len(lines) > 1 else ""

        body_html += f"\n    <h2>{heading}</h2>\n"
        for para in content.split('\n\n'):
            para = para.strip()
            if not para:
                continue
            # Check if it's a pull quote (starts with >)
            if para.startswith('>'):
                quote_text = para.lstrip('> ').strip()
                body_html += f'    <blockquote class="pull-quote fade-in">{quote_text}</blockquote>\n'
            else:
                body_html += f"    <p>{para}</p>\n"

    # Hero image
    hero_img_html = ""
    if hero_url:
        hero_img_html = f'''    <div class="hero-image fade-in">
        <img src="{hero_url}" alt="Abstract digital art for {tag}" loading="eager" style="width:100%;height:auto;display:block;border-radius:16px;">
    </div>'''

    slug = slugify(title)
    url = f"https://www.koda.community/editorial/{date}-{slug}.html"

    # Read the existing editorial as a template reference for CSS/structure
    template_path = DIGEST_DIR / "editorial" / "template-editorial.html"
    if not template_path.exists():
        print("  ERROR: editorial/template-editorial.html not found")
        return ""

    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    # Build the full HTML by modifying the template approach
    # We'll generate a self-contained HTML based on the existing editorial's structure
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} | Koda Editorial</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet">
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect rx='20' width='100' height='100' fill='%236366F1'/><text x='50' y='68' font-size='55' text-anchor='middle' fill='white' font-family='system-ui' font-weight='800'>K</text></svg>">
    <meta property="og:title" content="{title} | Koda Editorial">
    <meta property="og:description" content="{subtitle}">
    <meta property="og:type" content="article">
    <meta property="og:url" content="{url}">
    <meta property="og:site_name" content="Koda Digest">
    <meta name="description" content="{subtitle}">
    <script type="application/ld+json">
    {{
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "{title}",
        "datePublished": "{date}",
        "description": "{subtitle}",
        "author": {{"@type": "Organization", "name": "Koda Editorial"}},
        "publisher": {{"@type": "Organization", "name": "Koda Intelligence", "url": "https://www.koda.community"}},
        "mainEntityOfPage": "{url}",
        "wordCount": "{word_count}",
        "timeRequired": "PT{read_time}M"
    }}
    </script>"""

    # Extract CSS from template (between <style> tags)
    css_match = re.search(r'<style>(.*?)</style>', template, re.DOTALL)
    css = css_match.group(1) if css_match else ""

    html += f"\n    <style>\n{css}\n    </style>\n</head>\n<body class=\"dark\">\n"

    # Scroll progress bar
    html += '<div class="scroll-progress" id="scrollProgress"></div>\n'

    # Topbar
    html += f"""
<header class="fixed top-0 w-full z-50 bg-[#0b1326]/80 backdrop-blur-xl border-b border-white/[0.06]" style="position:fixed;top:0;left:0;right:0;z-index:1000;background:rgba(11,19,38,0.8);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border-bottom:1px solid rgba(255,255,255,0.06);">
    <div style="max-width:1280px;margin:0 auto;padding:0 24px;height:56px;display:flex;align-items:center;justify-content:space-between;">
        <a href="../index.html" style="display:flex;align-items:center;gap:12px;text-decoration:none;color:inherit;">
            <div style="width:32px;height:32px;border-radius:8px;background:linear-gradient(135deg,#3B82F6,#8B5CF6);display:flex;align-items:center;justify-content:center;color:white;font-weight:800;font-size:14px;">K</div>
            <div>
                <div style="font-size:14px;font-weight:700;color:#3B82F6;">Koda Editorial</div>
                <div style="font-size:10px;color:#8c909f;">Daily Analysis</div>
            </div>
        </a>
        <div style="display:flex;align-items:center;gap:8px;">
            <button id="topbarSearchBtn" style="width:32px;height:32px;border-radius:8px;background:rgba(255,255,255,0.05);border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;color:#8c909f;transition:all 0.2s;" title="Search (Ctrl+K)">
                <span class="material-symbols-outlined" style="font-size:18px;">search</span>
            </button>
            <a class="topbar-nav-text" href="../archive/" style="font-size:11px;font-family:'JetBrains Mono',monospace;font-weight:600;padding:6px 12px;border-radius:6px;background:rgba(255,255,255,0.05);color:#8c909f;text-decoration:none;">Archive</a>
            <a class="topbar-nav-text" href="../morning-briefing-koda.html" style="font-size:11px;font-family:'JetBrains Mono',monospace;font-weight:600;padding:6px 12px;border-radius:6px;background:rgba(255,255,255,0.05);color:#8c909f;text-decoration:none;">Today's Digest</a>
            <a href="../index.html" style="font-size:11px;font-family:'JetBrains Mono',monospace;font-weight:700;padding:6px 12px;border-radius:8px;background:linear-gradient(135deg,#3B82F6,#6366F1);color:white;text-decoration:none;">&larr; Home</a>
        </div>
    </div>
</header>

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

    # Search overlay (same as other editorial pages)
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
.topbar-nav-text { }
@media (max-width: 640px) { .topbar-nav-text { display: none !important; } }
</style>
<script>
(function(){
    var overlay=document.getElementById('searchOverlay'),input=document.getElementById('globalSearchInput'),results=document.getElementById('globalSearchResults'),idx=null,timer=null;
    function open(){overlay.style.display='block';input.value='';results.innerHTML='';setTimeout(function(){input.focus();},50);}
    function close(){overlay.style.display='none';}
    document.getElementById('topbarSearchBtn').addEventListener('click',open);
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
            h+='<a href="'+href+'" class="koda-sr-item"><div class="koda-sr-meta"><span class="koda-sr-badge '+rs.type+'">'+(rs.type==='editorial'?'Editorial':'Digest')+'</span><span class="koda-sr-date">'+fmtDate(rs.date)+'</span><span class="koda-sr-section">'+esc(rs.section)+'</span></div><div class="koda-sr-headline">'+hilight(esc(rs.headline),terms)+'</div><div class="koda-sr-snippet">'+hilight(sn,terms)+'</div></a>';}
        results.innerHTML=h;
    }
    function snippet(t,tm,c){if(!t)return '';var l=t.toLowerCase(),i=l.indexOf(tm.toLowerCase());if(i===-1)return t.substring(0,c*2);var s=Math.max(0,i-c),e=Math.min(t.length,i+tm.length+c),r=t.substring(s,e);if(s>0)r='...'+r;if(e<t.length)r+='...';return r;}
    function hilight(t,terms){for(var i=0;i<terms.length;i++){t=t.replace(new RegExp('('+terms[i].replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&')+')','gi'),'<mark>$1</mark>');}return t;}
    function slug(t){return t.toLowerCase().replace(/['']/g,'').replace(/[^a-z0-9]+/g,'-').replace(/(^-|-$)/g,'');}
    function fmtDate(d){var p=d.split('-'),m=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];return m[parseInt(p[1])-1]+' '+parseInt(p[2])+', '+p[0];}
    function esc(s){return s?s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'):'';}
})();
</script>
</body>
</html>"""

    return html


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Daily Editorial")
    parser.add_argument("--date", default=today_str())
    parser.add_argument("--dry-run", action="store_true", help="Don't save files")
    args = parser.parse_args()

    print(f"[04E] Generating editorial for {args.date}")

    # Load digest content
    digest = read_json("digest-content.json")
    if not digest:
        print("  ERROR: digest-content.json not found. Run step 03 first.")
        sys.exit(1)

    # Load voice guide
    voice_path = DIGEST_DIR / "editorial" / "koda-voice-guide.md"
    if not voice_path.exists():
        print("  ERROR: editorial/koda-voice-guide.md not found.")
        sys.exit(1)
    with open(voice_path, "r", encoding="utf-8") as f:
        voice_guide = f.read()

    # Step 01E: Topic selection
    print("\n  Step 01E: Selecting topic...")
    topic = select_topic(digest)
    if not topic:
        print("  ERROR: Topic selection failed")
        write_json("editorial-status.json", {"date": args.date, "success": False, "error": "topic_selection_failed"})
        sys.exit(1)
    print(f"  Topic: {topic['topic']}")
    print(f"  Expert overlay: {topic.get('expert_overlay', 'unknown')}")
    print(f"  Tag: {topic.get('tag', 'unknown')}")

    # Step 02E: Research
    print("\n  Step 02E: Researching topic...")
    research = research_topic(topic)
    research_count = sum(1 for v in research.values() if v is not None)
    print(f"  Research sources: {research_count}/3")

    # Step 03E: Draft article
    print("\n  Step 03E: Drafting article...")
    article = draft_article(topic, research, voice_guide, digest)
    if not article:
        print("  ERROR: Article draft failed")
        write_json("editorial-status.json", {"date": args.date, "success": False, "error": "draft_failed"})
        sys.exit(1)
    word_count = len(article.split())
    print(f"  Draft: {word_count} words")

    # Step 04F: Fact-check
    print("\n  Step 04F: Fact-checking...")
    article, fact_log = fact_check_article(article)
    verified = sum(1 for f in fact_log if f["verdict"] == "VERIFIED")
    print(f"  Checked {len(fact_log)} claims, {verified} verified")

    # Step 05E: Hero image
    print("\n  Step 05E: Generating hero image...")
    hero_url = generate_editorial_hero(topic, args.date)
    if hero_url:
        print(f"  Hero URL: {hero_url}")
    else:
        print("  No hero image (skipped or failed)")

    # Step 06E: Render HTML
    print("\n  Step 06E: Rendering HTML...")
    slug = slugify(topic.get("topic", "editorial"))
    filename = f"{args.date}-{slug}.html"
    html = render_html(article, topic, args.date, hero_url=hero_url)

    if not html:
        print("  ERROR: HTML rendering failed")
        write_json("editorial-status.json", {"date": args.date, "success": False, "error": "render_failed"})
        sys.exit(1)

    if args.dry_run:
        print(f"  DRY RUN: would save editorial/{filename} ({len(html)} chars)")
    else:
        output_path = DIGEST_DIR / "editorial" / filename
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  Saved: editorial/{filename} ({len(html)} chars, {word_count} words)")

    # Save status
    status = {
        "date": args.date,
        "success": True,
        "filename": filename,
        "filepath": f"editorial/{filename}",
        "topic": topic.get("topic", ""),
        "tag": topic.get("tag", ""),
        "expert_overlay": topic.get("expert_overlay", ""),
        "word_count": word_count,
        "hero_url": hero_url or "",
        "fact_check": {"claims_checked": len(fact_log), "verified": verified},
    }
    write_json("editorial-status.json", status)
    print(f"\n  Editorial generation complete!")


if __name__ == "__main__":
    main()
