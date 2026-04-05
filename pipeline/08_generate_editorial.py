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

import subprocess

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import DIGEST_DIR, today_str, read_json, write_json
from nav_component import NAV_CSS_V2, build_nav_v2

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPUS_MODEL = "anthropic/claude-opus-4-6"
SONNET_MODEL = "anthropic/claude-sonnet-4-6"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"
PERPLEXITY_MODEL = "sonar-pro"
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "")

FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
FIRECRAWL_API_URL = "https://api.firecrawl.dev/v1"

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


# ── Firecrawl Deep Research ─────────────────────────────────────────────────

NOISE_DOMAINS = {
    "google.com", "youtube.com", "twitter.com", "x.com", "reddit.com",
    "facebook.com", "instagram.com", "linkedin.com", "wikipedia.org",
    "tiktok.com", "pinterest.com", "medium.com", "github.com",
}
MAX_SOURCE_TEXT = 3000


def _firecrawl_scrape(url: str, timeout: int = 20) -> str | None:
    """Scrape a URL with Firecrawl and return clean markdown content."""
    if not FIRECRAWL_API_KEY:
        return None
    try:
        resp = httpx.post(
            f"{FIRECRAWL_API_URL}/scrape",
            json={"url": url, "formats": ["markdown"], "onlyMainContent": True, "timeout": 15000},
            headers={"Authorization": f"Bearer {FIRECRAWL_API_KEY}", "Content-Type": "application/json"},
            timeout=timeout,
        )
        resp.raise_for_status()
        markdown = resp.json().get("data", {}).get("markdown", "")
        return markdown[:MAX_SOURCE_TEXT] if markdown else None
    except Exception as e:
        print(f"      Firecrawl scrape failed for {url}: {e}")
        return None


def _firecrawl_search(query: str, limit: int = 6) -> list[dict]:
    """Search via Firecrawl. Returns list of {url, title, description}."""
    if not FIRECRAWL_API_KEY:
        return []
    try:
        resp = httpx.post(
            f"{FIRECRAWL_API_URL}/search",
            json={"query": query, "limit": limit},
            headers={"Authorization": f"Bearer {FIRECRAWL_API_KEY}", "Content-Type": "application/json"},
            timeout=20,
        )
        resp.raise_for_status()
        return [
            {"title": r.get("title", ""), "url": r.get("url", ""), "description": r.get("description", "")}
            for r in resp.json().get("data", [])
            if r.get("title")
        ]
    except Exception as e:
        print(f"      Firecrawl search failed: {e}")
        return []


def _enrich_research_with_firecrawl(research: dict[str, Any], topic_text: str) -> None:
    """Enrich editorial research by scraping Perplexity citations + independent Firecrawl search.

    Adds research["sources"] (scraped citations) and research["firecrawl_sources"] (independent search).
    Modifies research dict in place. Non-critical: failures are logged and skipped.
    """
    if not FIRECRAWL_API_KEY:
        print("    Firecrawl enrichment skipped (no FIRECRAWL_API_KEY)")
        return

    from urllib.parse import urlparse

    print("    Enriching research via Firecrawl...")

    # Step A: Scrape Perplexity citation URLs
    all_citations: list[str] = []
    for key in ("primary", "contrarian", "data"):
        entry = research.get(key)
        if entry and isinstance(entry, dict):
            all_citations.extend(entry.get("citations", []))

    # Deduplicate and filter
    seen: set[str] = set()
    filtered_urls: list[str] = []
    for url in all_citations:
        if url in seen:
            continue
        seen.add(url)
        domain = urlparse(url).netloc.lower().replace("www.", "")
        if domain in NOISE_DOMAINS:
            continue
        path = urlparse(url).path.strip("/")
        if not path or (path.count("/") == 0 and len(path) < 5):
            continue
        filtered_urls.append(url)

    sources: list[dict] = []
    for url in filtered_urls[:6]:
        text = _firecrawl_scrape(url)
        if text and len(text) > 200:
            domain = urlparse(url).netloc.lower().replace("www.", "")
            sources.append({"url": url, "text": text})
            print(f"      Citation: {domain} ({len(text)} chars)")
    research["sources"] = sources
    print(f"    Scraped {len(sources)} citation sources")

    # Step B: Independent Firecrawl search for the topic
    search_results = _firecrawl_search(topic_text)
    firecrawl_sources: list[dict] = []
    for r in search_results:
        url = r.get("url", "")
        if url in seen:
            continue
        seen.add(url)
        domain = urlparse(url).netloc.lower().replace("www.", "")
        if domain in NOISE_DOMAINS:
            continue
        text = _firecrawl_scrape(url)
        if text and len(text) > 200:
            firecrawl_sources.append({"url": url, "title": r.get("title", ""), "text": text})
            print(f"      Search: {domain} ({len(text)} chars)")
        if len(firecrawl_sources) >= 3:
            break
    research["firecrawl_sources"] = firecrawl_sources
    print(f"    Found {len(firecrawl_sources)} additional sources via search")


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
        f"Detailed analysis of: {topic_text}. Include specific numbers, dates, company names, and market data. {datetime.now().strftime('%B %Y')}."
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
        f"Key statistics, benchmark numbers, market sizes, and adoption rates related to: {topic_text}. {datetime.now().strftime('%B %Y')}."
    )
    if data:
        research["data"] = data
        print(f"    Data: {len(data['content'])} chars")

    # Firecrawl deep research: scrape citations + independent search
    try:
        _enrich_research_with_firecrawl(research, topic_text)
    except Exception as e:
        print(f"    WARNING: Firecrawl enrichment failed (non-critical): {e}")

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

    # Add Firecrawl-scraped primary sources (actual article text)
    source_lines = []
    for src in research.get("sources", []):
        url = src.get("url", "")
        text = src.get("text", "")[:2000]
        if text:
            source_lines.append(f"  [{url}]\n  {text}\n")
    for src in research.get("firecrawl_sources", []):
        url = src.get("url", "")
        title = src.get("title", "")
        text = src.get("text", "")[:2000]
        if text:
            source_lines.append(f"  [{title}] {url}\n  {text}\n")
    if source_lines:
        research_text += (
            "\n\nPRIMARY SOURCE ARTICLES (scraped directly, not AI-summarized):\n"
            + "\n".join(source_lines[:8])
            + "\nUse these for specific quotes, stats, and details. "
            "Prefer primary source text over summaries when they conflict.\n"
        )

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
    """
    Multi-pass fact checker.
    Pass 1: Opus extracts all verifiable claims as structured JSON.
    Pass 2: Perplexity verifies each claim individually.
    Pass 3: Sentences containing LOW/DISPUTED claims are removed from the article.
    Returns corrected article + verification log.
    """
    log: list[dict] = []

    # ── Pass 1: LLM extracts all verifiable claims ───────────────────────────
    extraction_prompt = (
        "Extract every verifiable factual claim from this article as a JSON array. "
        "Include: statistics, benchmark scores, AI model names and versions, product features, "
        "prices, source attributions, and quoted figures. "
        'For each claim output: {"claim": "exact quote", "type": "stat|model|feature|price|attribution|benchmark"}\n'
        "Return ONLY a raw JSON array. No prose. No markdown fences.\n\nARTICLE:\n" + article[:6000]
    )
    raw = _llm_call(extraction_prompt, model=OPUS_MODEL, max_tokens=1500, temperature=0.1)
    try:
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip(), flags=re.MULTILINE)
        claims_list: list[dict] = json.loads(cleaned)
    except Exception:
        print("  WARNING: Claim extraction parse failed, using regex fallback")
        claims_list = [{"claim": m, "type": "stat"} for m in re.findall(r"[\$\d][\d,.]+[%BMKx]?\b", article)]

    if not claims_list:
        print("  No claims extracted to verify")
        return article, log

    print(f"  Extracted {len(claims_list)} claims — verifying with Perplexity...")

    # ── Pass 2: Perplexity verifies each claim ───────────────────────────────
    corrected = article
    bad_sentences: list[str] = []

    # Prioritise highest-risk claim types first
    priority = ["benchmark", "model", "feature", "attribution", "price", "stat"]
    claims_list.sort(key=lambda c: priority.index(c.get("type", "stat"))
                     if c.get("type", "stat") in priority else 99)

    for item in claims_list[:12]:  # cap at 12 to keep step fast
        claim = item.get("claim", "").strip()
        ctype = item.get("type", "stat")
        if not claim or len(claim) < 6:
            continue

        result = _perplexity_call(
            f'Fact-check this claim from a {datetime.now().strftime("%B %Y")} AI article: "{claim}". '
            f"Is it accurate? If wrong, state the correct value. Reply in 2 sentences max."
        )
        if not result:
            log.append({"claim": claim, "type": ctype, "verdict": "UNVERIFIABLE", "detail": "no response"})
            continue

        content = result["content"]
        upper = content.upper()

        if any(w in upper for w in ("INACCURATE", "INCORRECT", "FALSE", "WRONG",
                                     "DOES NOT EXIST", "NOT FOUND", "NO EVIDENCE",
                                     "FABRICATED", "MISATTRIBUTED", "CANNOT CONFIRM",
                                     "NOT CONFIRMED", "UNVERIFIABLE")):
            verdict = "LOW"
        elif any(w in upper for w in ("DISPUTED", "CONTRADICTS", "CONFLICT")):
            verdict = "DISPUTED"
        elif any(w in upper for w in ("CONFIRMED", "ACCURATE", "CORRECT",
                                       "VERIFIED", "MATCHES", "IS CORRECT")):
            verdict = "VERIFIED"
        else:
            verdict = "MODERATE"

        log.append({"claim": claim, "type": ctype, "verdict": verdict, "detail": content[:300]})
        print(f"    {verdict} [{ctype}]: {claim[:80]}")

        # ── Pass 3: Flag sentences with LOW or DISPUTED claims ───────────────
        if verdict in ("LOW", "DISPUTED"):
            for sentence in re.split(r"(?<=[.!?])\s+", article):
                key = claim[:50]
                if key in sentence and sentence not in bad_sentences:
                    bad_sentences.append(sentence)

    # Remove problematic sentences
    if bad_sentences:
        print(f"  Removing {len(bad_sentences)} sentence(s) with LOW/DISPUTED claims")
        for bad in bad_sentences:
            corrected = corrected.replace(bad, "")
        corrected = re.sub(r"  +", " ", corrected)
        corrected = re.sub(r"\n{3,}", "\n\n", corrected)

    verified = sum(1 for e in log if e["verdict"] == "VERIFIED")
    low = sum(1 for e in log if e["verdict"] in ("LOW", "DISPUTED"))
    print(f"  Fact-check: {verified} verified, {low} removed of {len(log)} checked")

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


def _generate_hero_prompt(article_text: str, topic: dict) -> str | None:
    """Use Opus to generate a content-aware image prompt from the drafted article."""
    tag = (topic.get("tag", "") or "").lower()
    topic_stmt = (topic.get("topic", "") or "")[:200]

    # Extract first paragraph for additional grounding
    first_para = ""
    paragraphs = [p.strip() for p in article_text.split("\n\n") if p.strip() and not p.strip().startswith("#")]
    if paragraphs:
        first_para = paragraphs[0][:500]

    prompt = f"""You are an art director for Koda, a premium AI intelligence publication.
Read this editorial article and generate a single image prompt for a hero image.

ARTICLE TITLE: {topic_stmt}
ARTICLE TAG: {tag}
FIRST PARAGRAPH: {first_para}

ARTICLE TEXT:
{article_text[:3000]}

REQUIREMENTS:
1. FIRST: identify the ONE most concrete visual subject in this article (a specific technology, device, phenomenon, or metaphorical object)
2. The image MUST depict that specific subject -- not a generic "tech" or "AI" visual
3. Examples: If the article is about aircraft, show aircraft. If about semiconductor chips, show chip structures. If about a company's new product, show something representing THAT product specifically.
4. Dark moody atmosphere with deep shadows and volumetric lighting
5. Color palette: deep navy, electric blue, violet purple, subtle cyan accents
6. Cinematic composition, photorealistic 3D render
7. ABSOLUTELY NO text, words, labels, numbers, letters, or typography
8. NO people, faces, bodies, or hands
9. NO political figures or identifiable persons

SELF-CHECK: Before outputting, verify your prompt references a SPECIFIC visual element from the article, not just "glowing nodes" or "abstract data streams."

Output ONLY the image prompt (150-200 words). No preamble, no explanation."""

    result = _llm_call(prompt, max_tokens=500, temperature=0.5)
    if result:
        # Strip any markdown fencing
        cleaned = re.sub(r'^```\w*\s*', '', result.strip())
        cleaned = re.sub(r'\s*```$', '', cleaned).strip()
        print(f"  LLM hero prompt ({len(cleaned)} chars): {cleaned[:200]}...")
        return cleaned
    print("  WARNING: LLM hero prompt generation failed")
    return None


def _generate_hero_via_openrouter(image_prompt: str, hero_path: Path) -> bool:
    """Fallback: generate hero image via OpenRouter (DALL-E 3). Returns True on success."""
    if not OPENROUTER_API_KEY:
        return False
    try:
        print("  Trying DALL-E 3 via OpenRouter as fallback...")
        resp = httpx.post(
            "https://openrouter.ai/api/v1/images/generations",
            json={
                "model": "openai/dall-e-3",
                "prompt": image_prompt,
                "n": 1,
                "size": "1024x1024",
                "quality": "standard",
                "response_format": "url",
            },
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=60,
        )
        resp.raise_for_status()
        img_url = resp.json()["data"][0]["url"]
        img_data = httpx.get(img_url, timeout=30)
        img_data.raise_for_status()
        with open(hero_path, "wb") as f:
            f.write(img_data.content)
        print(f"  DALL-E fallback hero saved ({hero_path.stat().st_size // 1024}KB)")
        return True
    except Exception as e:
        print(f"  WARNING: DALL-E fallback also failed: {e}")
        return False


def generate_editorial_hero(topic: dict, date: str, article_text: str | None = None) -> str | None:
    """Generate a hero image for the editorial. Primary: Leonardo.ai. Fallback: DALL-E via OpenRouter."""
    import time

    hero_filename = f"editorial-hero-{date}.jpg"
    # Save inside editorial/ so Vercel serves it and git tracks it
    hero_path = DIGEST_DIR / "editorial" / hero_filename

    if not LEONARDO_API_KEY and not OPENROUTER_API_KEY:
        print("  WARNING: No image API keys available, skipping hero image")
        return None

    if hero_path.exists():
        print(f"  Hero image already exists: {hero_filename}")
    else:
        # Primary: LLM-generated content-aware prompt from the article
        image_prompt = None
        if article_text:
            image_prompt = _generate_hero_prompt(article_text, topic)
            # Validate: check if prompt references something specific from the article
            if image_prompt:
                topic_words = set((topic.get("topic", "") or "").lower().split())
                topic_words -= {"the", "of", "and", "a", "an", "in", "to", "for", "is", "on",
                                "at", "by", "with", "how", "why", "what", "this", "that", "its"}
                prompt_lower = image_prompt.lower()
                matches = sum(1 for w in topic_words if len(w) > 3 and re.search(rf'\b{re.escape(w)}\b', prompt_lower))
                if matches < 2:
                    print(f"  WARNING: Hero prompt may not match article (only {matches} topic words found) -- regenerating")
                    retry_prompt = _generate_hero_prompt(article_text, topic)
                    if retry_prompt:
                        image_prompt = retry_prompt

        # Fallback: tag-based prompt, but still article-aware
        if not image_prompt:
            print("  Falling back to tag-based hero prompt (LLM prompt failed)")
            tag = (topic.get("tag", "") or "").lower()
            subject = _TAG_SUBJECTS.get(tag)

            if not subject:
                topic_lower = (topic.get("topic", "") or "").lower()
                for key, subj in _TAG_SUBJECTS.items():
                    if key in topic_lower:
                        subject = subj
                        break
            if not subject:
                subject = _TAG_SUBJECTS["ai"]

            topic_text = (topic.get("topic", "") or "")[:120]
            # Include article context even in fallback for better relevance
            article_hint = ""
            if article_text:
                article_hint = f" The article discusses: {article_text[:200].strip()}."

            image_prompt = (
                f"Cinematic digital art inspired by: {topic_text}.{article_hint} "
                f"Visual approach: {subject}. "
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
                "height": 1024,
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
            submit_body = resp.json()
            if not isinstance(submit_body, dict):
                print(f"  WARNING: Unexpected submit response: {str(submit_body)[:200]}")
                return None
            generation_id = submit_body.get("generate", {}).get("generationId")
            if not generation_id:
                print(f"  WARNING: No generation ID returned: {submit_body}")
                return None

            poll_url = f"https://cloud.leonardo.ai/api/rest/v1/generations/{generation_id}"
            for attempt in range(30):
                time.sleep(3)
                poll = httpx.get(poll_url, headers=headers, timeout=15)
                poll.raise_for_status()
                poll_body = poll.json()
                if not isinstance(poll_body, dict):
                    print(f"  WARNING: Unexpected poll response: {str(poll_body)[:200]}")
                    return None
                gen = poll_body.get("generations_by_pk", {})
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
            print(f"  WARNING: Leonardo hero generation failed: {e}")
            if hero_path.exists():
                hero_path.unlink()
            # Try DALL-E fallback
            if not _generate_hero_via_openrouter(image_prompt, hero_path):
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

    # Relative fallback: hero is in editorial/ alongside the article HTML
    if hero_path.exists():
        return f"./{hero_filename}"

    return None


# ── Step 06E: Render HTML ────────────────────────────────────────────────────

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
    # Find last space or dash before the limit
    truncated = text[:max_len]
    last_break = max(truncated.rfind(' '), truncated.rfind('—'), truncated.rfind('-'))
    if last_break > max_len // 2:
        return truncated[:last_break].rstrip(' —-')
    return truncated.rstrip()


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
    # Generate a proper title from the topic (truncate at word boundary)
    raw_title = topic.get("topic", first_line)
    title = _truncate_title(raw_title, max_len=120)

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
            body_html += f"    <p>{inline_md(para)}</p>\n"

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
                body_html += f'    <blockquote class="pull-quote fade-in">{inline_md(quote_text)}</blockquote>\n'
            else:
                body_html += f"    <p>{inline_md(para)}</p>\n"

    # Hero image
    hero_img_html = ""
    if hero_url:
        hero_img_html = f'''    <div class="hero-image fade-in" style="max-width:800px;max-height:420px;margin:32px auto 0;border-radius:16px;overflow:hidden;">
        <img src="{hero_url}" alt="{title}" loading="eager" style="width:100%;height:420px;object-fit:cover;object-position:center;display:block;border-radius:16px;">
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
    <title>{title} | Koda Deep Dive</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet">
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect rx='20' width='100' height='100' fill='%236366F1'/><text x='50' y='68' font-size='55' text-anchor='middle' fill='white' font-family='system-ui' font-weight='800'>K</text></svg>">
    <meta property="og:title" content="{title} | Koda Deep Dive">
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
        "author": {{"@type": "Organization", "name": "Koda Deep Dive"}},
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

    # Topbar (V2 with hamburger drawer)
    _nav_css, nav_html, _nav_js = build_nav_v2(
        current_page="editorial",
        url_prefix="../",
        page_subtitle="Deep Dive",
        page_icon="explore",
        share_url="https://www.koda.community/editorial/",
    )
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
""" + NAV_CSS_V2 + """/* -- End Koda Nav V2 -- */
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
""" + _nav_js + """
</body>
</html>"""

    return html


# ── Archive + Landing Page Updates ───────────────────────────────────────────

def _excerpt(article_text: str, max_chars: int = 150) -> str:
    """Extract a clean excerpt from the article hook (first paragraph)."""
    paragraphs = [p.strip() for p in article_text.split('\n\n') if p.strip()]
    raw = paragraphs[0] if paragraphs else ""
    # Strip any markdown bold/italic
    raw = re.sub(r'\*+', '', raw)
    return raw[:max_chars].rstrip(' .,') + ("..." if len(raw) > max_chars else "")


def _format_date_display(date_str: str) -> str:
    """Format YYYY-MM-DD as '29 March 2026'."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{dt.day} {dt.strftime('%B %Y')}"


def _update_editorial_archive(
    article_title: str,
    filename: str,
    tag: str,
    date_str: str,
    word_count: int,
    article_text: str,
) -> None:
    """Prepend today's article card to editorial/index.html."""
    archive_path = DIGEST_DIR / "editorial" / "index.html"
    if not archive_path.exists():
        print("  WARNING: editorial/index.html not found, skipping archive update")
        return

    content = archive_path.read_text(encoding="utf-8")
    date_display = _format_date_display(date_str)
    read_min = max(1, word_count // 250)
    excerpt = _excerpt(article_text)

    new_card = f'''    <a href="./{filename}" class="article-card">
        <div class="article-meta">
            <span class="tag">{tag}</span>
            <span class="date">{date_display}</span>
        </div>
        <h2>{article_title}</h2>
        <p>{excerpt}</p>
        <div class="read-time">{read_min} min read</div>
    </a>
'''

    # Insert after the opening <div class="grid"> tag
    marker = '<div class="grid">'
    if marker in content:
        updated = content.replace(marker, marker + "\n" + new_card, 1)
        archive_path.write_text(updated, encoding="utf-8")
        print(f"  Updated editorial/index.html with card for {date_str}")
    else:
        print("  WARNING: could not find grid marker in editorial/index.html")


def _update_landing_page(
    article_title: str,
    filename: str,
    tag: str,
    date_str: str,
    word_count: int,
    article_text: str,
) -> None:
    """Replace the featured editorial card in index.html."""
    landing_path = DIGEST_DIR / "index.html"
    if not landing_path.exists():
        print("  WARNING: index.html not found, skipping landing page update")
        return

    content = landing_path.read_text(encoding="utf-8")
    date_display = _format_date_display(date_str)
    read_min = max(1, word_count // 250)
    excerpt = _excerpt(article_text, max_chars=120)

    start_marker = "<!-- EDITORIAL-CARD-START -->"
    end_marker = "<!-- EDITORIAL-CARD-END -->"

    if start_marker not in content or end_marker not in content:
        print("  WARNING: EDITORIAL-CARD-START/END markers not found in index.html, skipping")
        return

    new_card = f"""<!-- EDITORIAL-CARD-START -->
        <a href="./editorial/{filename}" class="block no-underline group">
            <div class="bg-surface-container border border-outline-variant/20 rounded-2xl p-8 md:p-10 transition-all group-hover:border-[#6366F1]/30 group-hover:-translate-y-1" style="background:linear-gradient(135deg, rgba(99,102,241,0.06), rgba(139,92,246,0.04));">
                <div class="flex items-center gap-3 mb-4">
                    <span style="display:inline-block;padding:4px 12px;border-radius:20px;font-size:10px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;background:rgba(99,102,241,0.15);color:#a5b4fc;">{tag}</span>
                    <span class="text-xs font-mono text-on-surface-variant/50">{date_display}</span>
                    <span class="text-xs font-mono text-on-surface-variant/40">{read_min} min read</span>
                </div>
                <h3 class="text-xl md:text-2xl font-extrabold text-on-surface tracking-tight mb-3 group-hover:text-[#a5b4fc] transition-colors">{article_title}</h3>
                <p class="text-sm text-on-surface-variant/70 leading-relaxed max-w-2xl">{excerpt}</p>
            </div>
        </a>
<!-- EDITORIAL-CARD-END -->"""

    # Replace between markers
    pattern = re.compile(
        re.escape(start_marker) + r".*?" + re.escape(end_marker),
        re.DOTALL
    )
    updated = pattern.sub(new_card, content)

    if updated == content:
        print("  WARNING: landing page editorial card replacement had no effect")
    else:
        landing_path.write_text(updated, encoding="utf-8")
        print(f"  Updated index.html editorial card for {date_str}")


# ── Editorial Media ──────────────────────────────────────────────────────────

SUPABASE_MEDIA_PREFIX = "https://lfwymyfaeihoglmlvbaj.supabase.co/storage/v1/object/public/koda-media"


def _generate_editorial_video_direction(
    article_text: str, article_title: str, date_label: str,
) -> str | None:
    """Generate anime-style video direction via Sonnet LLM call."""
    prompt = (
        f"You are a visual director for a brief anime-style video overview of an "
        f"editorial article. The video will be 1-2 minutes long with 3-4 key scenes.\n\n"
        f"Article title: {article_title}\nDate: {date_label}\n\n"
        f"Article text:\n{article_text[:6000]}\n\n"
        f"Create an ANIME VISUAL DIRECTION DOCUMENT with:\n"
        f"## ANIME VIDEO DIRECTION -- {article_title}\n\n"
        f"### Visual Identity\n"
        f"Cel-shaded art, vibrant colors, dynamic camera angles, dark backgrounds "
        f"with neon accent lighting (electric blue, vivid purple).\n\n"
        f"### Scene Breakdown (3-4 scenes)\n"
        f"For each: scene title, visual description, key argument, camera movement, color palette.\n\n"
        f"### Closing Frame\nA single powerful image encapsulating the thesis with Koda branding.\n\n"
        f"RULES: NO political figures or real people. Use abstract silhouettes/symbols. "
        f"Keep under 500 words. Use anime visual language."
    )
    return _llm_call(prompt, model=SONNET_MODEL, max_tokens=700, temperature=0.6)


def _generate_editorial_audio_direction(
    article_text: str, article_title: str, date_label: str,
) -> str:
    """Generate brief audio overview direction (deterministic template)."""
    snippet = article_text[:200].replace("\n", " ").strip()
    if len(article_text) > 200:
        snippet += "..."
    return (
        f"## EDITORIAL AUDIO DIRECTION -- {date_label}\n\n"
        f"### Format: Brief Overview (~5-8 minutes)\n"
        f"Single-topic deep analysis, NOT a news roundup.\n\n"
        f"### Article: {article_title}\nPreview: {snippet}\n\n"
        f"### Tone & Style\n"
        f"Conversational expert tone. Like explaining to a smart friend over coffee.\n"
        f"5-minute 'what you need to know' briefing on ONE topic.\n\n"
        f"### Structure: HOOK (30s) -> CONTEXT (1-2 min) -> DEEP DIVE (2-3 min) -> SO WHAT (1-2 min)\n\n"
        f"### Host Chemistry\n"
        f"Host A drives argument forward. Host B plays devil's advocate.\n"
        f"Energy shifts: excited for opportunities, concerned for risks, skeptical for hype.\n\n"
        f"### Avoid\n"
        f"No linear summaries. No robot transitions. No condescending explanations."
    )


def _generate_editorial_media(
    article: str, topic: dict, date: str, *, dry_run: bool = False,
) -> dict | None:
    """Generate brief anime video + audio for the editorial via notebooklm_media.py.

    Returns editorial-media-status dict on success, None on failure.
    """
    print("\n  Step 05F: Generating editorial media (video + audio)...")

    if dry_run:
        print("  DRY RUN: skipping editorial media generation")
        return None

    title = topic.get("topic", "Today's Analysis")[:80]
    date_label = datetime.strptime(date, "%Y-%m-%d").strftime("%d %B %Y")

    # Generate direction documents
    print("  Generating video direction...")
    video_dir = _generate_editorial_video_direction(article, title, date_label)
    if video_dir:
        print(f"  Video direction: {len(video_dir)} chars")
    else:
        print("  Video direction failed (will skip video)")

    audio_dir = _generate_editorial_audio_direction(article, title, date_label)
    print(f"  Audio direction: {len(audio_dir)} chars")

    # Write temp files
    data_dir = DIGEST_DIR / "pipeline" / "data"
    article_file = data_dir / "editorial-article.txt"
    article_file.write_text(article, encoding="utf-8")

    video_dir_file = None
    if video_dir:
        video_dir_file = data_dir / "editorial-video-direction.txt"
        video_dir_file.write_text(video_dir, encoding="utf-8")

    audio_dir_file = data_dir / "editorial-audio-direction.txt"
    audio_dir_file.write_text(audio_dir, encoding="utf-8")

    # Call notebooklm_media.py --editorial-file
    # MUST use --new-notebook so editorial artifacts don't collide with digest
    # artifacts in the permanent Koda notebook (download_video grabs latest)
    cmd = [
        sys.executable, str(DIGEST_DIR / "notebooklm_media.py"),
        "--editorial-file", str(article_file),
        "--editorial-audio-direction", str(audio_dir_file),
        "--date", date,
        "--output-dir", str(DIGEST_DIR),
        "--skip-digest",
        "--new-notebook",
        "--notebook-title", f"Koda Editorial {date}",
    ]
    if video_dir_file:
        cmd.extend(["--editorial-video-direction", str(video_dir_file)])

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"

    print("  Running notebooklm_media.py --editorial-file ...")
    try:
        result = subprocess.run(cmd, env=env, capture_output=False, timeout=1800)
    except subprocess.TimeoutExpired:
        print("  WARNING: Editorial media generation timed out (30 min)")
        return None
    except Exception as e:
        print(f"  WARNING: Editorial media generation failed: {e}")
        return None

    # Read back status
    status_path = DIGEST_DIR / "editorial-media-status.json"
    if status_path.exists():
        with open(status_path, "r", encoding="utf-8") as f:
            status = json.load(f)
        audio_ok = status.get("editorial_audio", {}).get("success", False)
        video_ok = status.get("editorial_video", {}).get("success", False)
        print(f"  Editorial media: audio={'OK' if audio_ok else 'FAIL'}, video={'OK' if video_ok else 'FAIL'}")
        return status
    else:
        print("  WARNING: No editorial-media-status.json generated")
        return None


def _inject_media_strip(html: str, media_status: dict) -> str:
    """Inject the media strip HTML after the hero section in the editorial."""
    audio = media_status.get("editorial_audio", {})
    video = media_status.get("editorial_video", {})

    audio_url = audio.get("url", "")
    if not audio_url and audio.get("path"):
        # Extract just the filename from a potentially full path
        audio_filename = Path(audio["path"]).name
        audio_url = f"{SUPABASE_MEDIA_PREFIX}/{audio_filename}"

    youtube_id = video.get("youtube_id", "")
    youtube_url = video.get("youtube_url", f"https://www.youtube.com/watch?v={youtube_id}" if youtube_id else "")

    if not audio_url and not youtube_id:
        return html  # Nothing to inject

    # Build media strip HTML
    cards = []
    if audio_url:
        cards.append(f"""    <div class="media-card media-card--audio">
      <span class="material-symbols-outlined media-card__icon media-card__icon--audio">headphones</span>
      <div class="media-card__title">Expert Analysis</div>
      <div class="media-card__subtitle">Two-minute conversation (~2 min)</div>
      <button class="media-btn media-btn--podcast" id="edPodBtn" onclick="toggleEditorialPodcast()" aria-expanded="false" aria-controls="editorialPodcastPlayer">&#9654; Listen Now</button>
      <div class="ed-podcast-wrap" id="editorialPodcastPlayer">
        <audio controls preload="none"><source src="{audio_url}" type="audio/mpeg"></audio>
      </div>
    </div>""")

    if youtube_id:
        cards.append(f"""    <div class="media-card media-card--video">
      <span class="material-symbols-outlined media-card__icon media-card__icon--video">smart_display</span>
      <div class="media-card__title">Visual Narrative</div>
      <div class="media-card__subtitle">Animated story breakdown (~2 min)</div>
      <button class="media-btn media-btn--video" onclick="toggleVideo()">&#9654; Play Video</button>
      <a href="{youtube_url}" target="_blank" rel="noopener" class="media-yt-link">or watch on YouTube &rarr;</a>
      <div class="video-overlay" id="videoOverlay" role="dialog" aria-modal="true" aria-label="Video player" onclick="if(event.target===this)toggleVideo()">
        <div class="video-overlay-inner">
          <button class="video-overlay-close" onclick="toggleVideo()" aria-label="Close video">&times;</button>
          <iframe id="videoFrame" width="100%" style="aspect-ratio:16/9;border:none;border-radius:12px" allowfullscreen title="Editorial video"></iframe>
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

    # Media strip JS (podcast toggle + video overlay)
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

    # Inject after <article class="article-body"> (between hero and body text)
    marker = '<article class="article-body">'
    idx = html.find(marker)
    if idx != -1:
        insert_at = idx + len(marker)
        html = html[:insert_at] + "\n" + strip_html + html[insert_at:]
        print(f"  Injected media strip (audio={bool(audio_url)}, video={bool(youtube_id)})")
    else:
        print("  WARNING: Could not find <article> to inject media strip")

    # Inject media JS before </body>
    body_end = html.rfind("</body>")
    if body_end != -1:
        html = html[:body_end] + media_js + html[body_end:]

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
    hero_url = generate_editorial_hero(topic, args.date, article_text=article)
    if hero_url:
        print(f"  Hero URL: {hero_url}")
    else:
        print("  No hero image (skipped or failed)")

    # Step 05F: Generate editorial media (brief anime video + brief audio)
    editorial_media = _generate_editorial_media(article, topic, args.date, dry_run=args.dry_run)

    # Step 06E: Render HTML
    print("\n  Step 06E: Rendering HTML...")
    slug = slugify(topic.get("topic", "editorial"))
    filename = f"{args.date}-{slug}.html"
    html = render_html(article, topic, args.date, hero_url=hero_url)

    if not html:
        print("  ERROR: HTML rendering failed")
        write_json("editorial-status.json", {"date": args.date, "success": False, "error": "render_failed"})
        sys.exit(1)

    # Inject media strip if editorial media was generated
    if editorial_media:
        html = _inject_media_strip(html, editorial_media)

    if args.dry_run:
        print(f"  DRY RUN: would save editorial/{filename} ({len(html)} chars)")
    else:
        output_path = DIGEST_DIR / "editorial" / filename
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  Saved: editorial/{filename} ({len(html)} chars, {word_count} words)")

    # Derive article title (same logic as render_html uses)
    article_title = _truncate_title(topic.get("topic", "Today's Analysis"), max_len=120)

    # Save status
    status = {
        "date": args.date,
        "success": True,
        "filename": filename,
        "filepath": f"editorial/{filename}",
        "title": article_title,
        "topic": topic.get("topic", ""),
        "tag": topic.get("tag", ""),
        "expert_overlay": topic.get("expert_overlay", ""),
        "word_count": word_count,
        "hero_url": hero_url or "",
        "fact_check": {"claims_checked": len(fact_log), "verified": verified},
    }
    write_json("editorial-status.json", status)

    # Update editorial/index.html — prepend today's article card at the top
    if not args.dry_run:
        _update_editorial_archive(
            article_title=article_title,
            filename=filename,
            tag=topic.get("tag", "Strategy"),
            date_str=args.date,
            word_count=word_count,
            article_text=article,
        )

    # Update landing page index.html — replace featured editorial card
    if not args.dry_run:
        _update_landing_page(
            article_title=article_title,
            filename=filename,
            tag=topic.get("tag", "Strategy"),
            date_str=args.date,
            word_count=word_count,
            article_text=article,
        )

    print(f"\n  Editorial generation complete!")


if __name__ == "__main__":
    main()
