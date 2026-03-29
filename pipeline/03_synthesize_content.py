"""
Step 03: Synthesize raw data into structured digest content.

Uses OpenRouter (Claude Sonnet) to transform raw search results and
newsletter content into editorial-quality, structured JSON.

Input:  pipeline/data/raw-data.json + pipeline/data/newsletters.json
Output: pipeline/data/digest-content.json
"""

import argparse
import json
import sys
import os
import httpx
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import DIGEST_DIR, OPENROUTER_API_KEY, today_str, write_json, read_json

# ── OpenRouter API ───────────────────────────────────────────────────────────

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
LLM_MODEL = "anthropic/claude-opus-4-6"


def llm_call(prompt, system="", model=LLM_MODEL, max_tokens=4000):
    """Call OpenRouter API and return the text response."""
    if not OPENROUTER_API_KEY:
        return None

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://koda.community",
        "X-Title": "Koda Digest Pipeline",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }

    resp = httpx.post(OPENROUTER_URL, json=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def llm_json(prompt, system="", model=LLM_MODEL, max_tokens=4000):
    """Call LLM and parse the response as JSON."""
    system_with_json = system + "\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown, no code fences, no explanation."
    raw = llm_call(prompt, system_with_json, model, max_tokens)
    if not raw:
        return None

    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    return json.loads(text)


# ── Synthesis Prompts ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are the editor of Koda Intelligence Briefing, a daily AI-focused news digest.
Your job is to synthesize raw search results into structured, editorial-quality content.
Write in a direct, analytical voice. Be specific: use names, numbers, and dates.
Never use em dashes. Use commas, colons, semicolons, or separate sentences instead.
This is a public-facing briefing, not a personal newsletter. No personal data."""


def synthesize_ai_news(raw_content, citations):
    """Transform raw AI news into structured story cards."""
    prompt = f"""Analyze this raw AI news data and extract 8-12 distinct stories.

RAW DATA:
{raw_content}

CITATIONS:
{json.dumps(citations, indent=2)}

Return a JSON array of story objects. Each story:
{{
  "title": "Short headline (8 words max)",
  "body": "2-3 sentence summary with specific details",
  "category": "one of: Model Release, Benchmark, Agents, Hardware, Enterprise, Policy, Biotech, Design, Trend, China, Consolidation, Open Source",
  "source_name": "Source publication name",
  "source_url": "URL from citations if available, otherwise empty string"
}}

Return 8-12 stories, ordered by significance."""
    return llm_json(prompt, SYSTEM_PROMPT) or []


def synthesize_world_news(raw_content, citations):
    """Transform raw world news into structured story cards."""
    prompt = f"""Analyze this raw world news data and extract 6-8 distinct stories.

RAW DATA:
{raw_content}

CITATIONS:
{json.dumps(citations, indent=2)}

Return a JSON array of story objects:
{{
  "title": "Short headline (8 words max)",
  "body": "2-3 sentence summary with key facts",
  "category": "one of: Conflict, Diplomacy, Economy, Policy, Humanitarian, Infrastructure, Climate, Technology",
  "source_name": "Source name",
  "source_url": "URL from citations if available, otherwise empty string"
}}

Return 6-8 stories, ordered by global impact."""
    return llm_json(prompt, SYSTEM_PROMPT) or []


def synthesize_markets(raw_content):
    """Extract market data into structured format."""
    prompt = f"""Extract exact market data from this text.

RAW DATA:
{raw_content}

Return a JSON object:
{{
  "sp500": {{"price": "6,581", "change": "+1.15%", "direction": "up"}},
  "nasdaq": {{"price": "21,947", "change": "+1.38%", "direction": "up"}},
  "btc": {{"price": "$71,000", "change": "+3.79%", "direction": "up"}},
  "eth": {{"price": "$2,134", "change": "+5.16%", "direction": "up"}},
  "oil": {{"price": "$110", "change": "Elevated", "direction": "neutral"}},
  "sentiment": {{"value": "11", "label": "Extreme Fear", "direction": "down"}}
}}

Use exact numbers from the data. If a value is unavailable, use "N/A"."""
    return llm_json(prompt, SYSTEM_PROMPT, model=LLM_MODEL) or {}


def synthesize_competitive(raw_content, citations):
    """Transform competitive landscape data into company cards."""
    prompt = f"""Analyze this competitive intelligence data for major AI companies.

RAW DATA:
{raw_content}

CITATIONS:
{json.dumps(citations, indent=2)}

Return a JSON array of company objects. ONLY include companies that have verifiable recent news with a source URL. If there is no concrete news for a company today, OMIT it entirely. Do NOT generate filler text like "no significant announcements" or "coverage will be updated."

Each object:
{{
  "name": "Company name",
  "status": "One-line status summary",
  "body": "2-3 sentence analysis of latest moves",
  "source_url": "Source URL (REQUIRED - omit the company if you have no URL)"
}}

Candidate companies: OpenAI, Google DeepMind, Anthropic, Meta AI, Mistral, China Challengers (group).
Only include those with real, sourced news today."""
    return llm_json(prompt, SYSTEM_PROMPT) or []


def synthesize_tools(raw_content, citations):
    """Transform AI tools data into tip cards."""
    prompt = f"""Analyze this AI tools data and create 6 actionable tip cards.

RAW DATA:
{raw_content}

CITATIONS:
{json.dumps(citations, indent=2)}

Return a JSON array of 6 tip objects:
{{
  "category": "one of: Mindset, Build, Hardware, Creativity, Productivity, Coding",
  "title": "Tool or technique name",
  "body": "2-3 sentence actionable description of what it does and how to use it",
  "url": "Official URL if available, otherwise empty string"
}}"""
    return llm_json(prompt, SYSTEM_PROMPT) or []


def synthesize_newsletters(newsletters_data):
    """Transform raw newsletter content into structured summaries."""
    if not newsletters_data:
        return []

    entries = []
    for nl in newsletters_data:
        content = nl.get("content", "")
        if len(content) < 50:
            continue

        # Use Sonnet for newsletter summarization (higher accuracy, fewer hallucinations)
        prompt = f"""Summarize this newsletter into structured sections.

NEWSLETTER FROM: {nl.get('sender', 'Unknown')}
SUBJECT: {nl.get('subject', '')}
CONTENT:
{content[:3000]}

Return a JSON object:
{{
  "name": "{nl.get('sender', 'Unknown')}",
  "date_badge": "{nl.get('date', '')}",
  "headlines": ["headline 1", "headline 2", "headline 3"],
  "deep_dives": "2-3 sentence summary of the main analysis or deep-dive content",
  "quick_hits": ["quick hit 1", "quick hit 2", "quick hit 3"],
  "tools": ["tool mention 1", "tool mention 2"],
  "quote": "Most notable quote from the newsletter (if any, otherwise empty string)",
  "source_link": "{nl.get('source_link', '')}"
}}"""
        result = llm_json(prompt, SYSTEM_PROMPT, model=LLM_MODEL, max_tokens=1500)
        if result:
            entries.append(result)

    return entries


def synthesize_summary(ai_news, world_news, markets):
    """Generate the executive summary hook and focus topics."""
    ai_titles = [s["title"] for s in (ai_news or [])[:5]]
    world_titles = [s["title"] for s in (world_news or [])[:5]]
    market_mood = markets.get("sentiment", {}).get("label", "Mixed") if markets else "Mixed"

    # Load recent hooks from theme ledger to prevent repetition
    recent_hooks_block = ""
    ledger_path = DIGEST_DIR / "recent-themes.json"
    if ledger_path.exists():
        try:
            with open(ledger_path, "r", encoding="utf-8") as f:
                ledger = json.load(f)
            recent_hooks = [
                f"  - {d}: \"{entry.get('hook', '')}\""
                for d, entry in sorted(ledger.items(), reverse=True)
            ]
            if recent_hooks:
                recent_hooks_block = (
                    "\n\nRECENT HOOKS (DO NOT repeat these patterns or phrasing):\n"
                    + "\n".join(recent_hooks)
                    + "\n\nYou MUST use a completely different sentence structure and opening phrase. "
                    "Vary your approach: try a question, a statistic lead-in, a contrast ('While X, Y'), "
                    "a declarative surprise, or a named-entity opening. NEVER start with 'AI labs race' "
                    "or any variation seen above."
                )
        except Exception:
            pass

    prompt = f"""Create the executive summary for today's Koda Intelligence Briefing.

TOP AI STORIES: {json.dumps(ai_titles)}
TOP WORLD STORIES: {json.dumps(world_titles)}
MARKET MOOD: {market_mood}{recent_hooks_block}

Return a JSON object:
{{
  "hook": "One punchy sentence that captures today's biggest theme (max 20 words). MUST use a fresh sentence structure unlike any recent hook.",
  "briefs": [
    {{"icon": "ai", "label": "AI", "text": "One sentence on the biggest AI story"}},
    {{"icon": "world", "label": "World", "text": "One sentence on the biggest world story"}},
    {{"icon": "markets", "label": "Markets", "text": "One sentence on market direction"}},
    {{"icon": "wildcard", "label": "Wild Card", "text": "One unexpected or cross-cutting insight"}}
  ],
  "focus_topics": [
    {{"number": 1, "title": "Focus Topic 1 (3-5 words)", "description": "2-3 sentence analysis"}},
    {{"number": 2, "title": "Focus Topic 2 (3-5 words)", "description": "2-3 sentence analysis"}},
    {{"number": 3, "title": "Focus Topic 3 (3-5 words)", "description": "2-3 sentence analysis"}}
  ],
  "kpis": {{
    "ai_stories": {len(ai_news or [])},
    "world_events": {len(world_news or [])},
    "market_mood": "{market_mood}",
    "tools_featured": 6
  }}
}}"""
    return llm_json(prompt, SYSTEM_PROMPT) or {}


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Step 03: Synthesize content")
    parser.add_argument("--date", default=today_str(), help="Date (YYYY-MM-DD)")
    args = parser.parse_args()

    print(f"[03] Synthesizing content for {args.date}")

    if not OPENROUTER_API_KEY:
        print("  ERROR: No OPENROUTER_API_KEY in .env")
        print("  This script requires the OpenRouter API for content synthesis.")
        sys.exit(1)

    # Load inputs
    raw_data = read_json("raw-data.json")
    newsletters_data = read_json("newsletters.json")

    if not raw_data:
        print("  ERROR: raw-data.json not found. Run 01_gather_news.py first.")
        sys.exit(1)

    results = raw_data.get("results", {})

    # Synthesize each section
    print("  Synthesizing AI news...")
    ai_news = synthesize_ai_news(
        results.get("ai_news", {}).get("content", ""),
        results.get("ai_news", {}).get("citations", []),
    )
    print(f"    {len(ai_news)} stories")

    print("  Synthesizing world news...")
    world_news = synthesize_world_news(
        results.get("world_news", {}).get("content", ""),
        results.get("world_news", {}).get("citations", []),
    )
    print(f"    {len(world_news)} stories")

    print("  Synthesizing market data...")
    live_markets = raw_data.get("live_markets")
    if live_markets:
        markets = live_markets
        print(f"    Using live market data — {len(markets)} tickers")
    else:
        markets = synthesize_markets(
            results.get("markets", {}).get("content", ""),
        )
        print(f"    {len(markets)} tickers (from search fallback)")

    print("  Synthesizing competitive landscape...")
    competitive = synthesize_competitive(
        results.get("competitive", {}).get("content", ""),
        results.get("competitive", {}).get("citations", []),
    )
    print(f"    {len(competitive)} companies")

    print("  Synthesizing AI tools...")
    tools = synthesize_tools(
        results.get("tools", {}).get("content", ""),
        results.get("tools", {}).get("citations", []),
    )
    print(f"    {len(tools)} tools")

    print("  Synthesizing newsletters...")
    newsletter_summaries = synthesize_newsletters(
        newsletters_data.get("newsletters", []) if newsletters_data else []
    )
    print(f"    {len(newsletter_summaries)} newsletters")

    print("  Generating executive summary...")
    summary = synthesize_summary(ai_news, world_news, markets)

    # Assemble final digest content
    digest = {
        "date": args.date,
        "date_label": raw_data.get("date_label", args.date),
        "synthesized_at": datetime.now().isoformat(),
        "summary": summary,
        "ai_news": ai_news,
        "world_news": world_news,
        "markets": markets,
        "competitive": competitive,
        "tools": tools,
        "newsletters": newsletter_summaries,
    }

    path = write_json("digest-content.json", digest)
    print(f"\n  Saved to {path}")

    # Summary stats
    sections = [("AI News", ai_news), ("World News", world_news),
                ("Competitive", competitive), ("Tools", tools),
                ("Newsletters", newsletter_summaries)]
    total_items = sum(len(s) for _, s in sections)
    print(f"  Total: {total_items} content items across {len(sections)} sections + markets")

    # ── Save rolling theme ledger for cross-day differentiation ────────
    print("  Updating theme ledger...")
    update_theme_ledger(args.date, summary, ai_news, world_news)


def update_theme_ledger(date, summary, ai_news, world_news):
    """Extract today's themes and append to the rolling ledger (last 5 days).

    Saves to DIGEST_DIR/recent-themes.json (repo root, committed to git)
    so the ledger persists across Railway container runs.
    """
    # Extract today's themes
    hook = summary.get("hook", "") if summary else ""
    ai_titles = [s.get("title", "") for s in (ai_news or [])[:5]]
    world_titles = [s.get("title", "") for s in (world_news or [])[:3]]
    focus_topics = [
        t.get("title", "")
        for t in summary.get("focus_topics", [])
    ] if summary else []

    today_entry = {
        "hook": hook,
        "top_themes": focus_topics[:3],
        "top_stories": ai_titles[:3] + world_titles[:2],
        "story_angles": [
            b.get("text", "")[:80]
            for b in summary.get("briefs", [])
        ] if summary else [],
    }

    # Load existing ledger from repo root, add today, trim to 5 days
    ledger_path = DIGEST_DIR / "recent-themes.json"
    ledger = {}
    if ledger_path.exists():
        with open(ledger_path, "r", encoding="utf-8") as f:
            ledger = json.load(f)

    ledger[date] = today_entry

    sorted_dates = sorted(ledger.keys(), reverse=True)
    trimmed = {d: ledger[d] for d in sorted_dates[:5]}

    with open(ledger_path, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, indent=2, ensure_ascii=False)
    print(f"    Ledger: {len(trimmed)} days stored (saved to repo root)")


if __name__ == "__main__":
    main()
