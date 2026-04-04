"""
Step 01B: Discover fresh AI tools and blog announcements via Firecrawl.

Supplements Perplexity (Step 01) with targeted scraping of curated
tool directories and primary-source company blogs.

Three discovery tracks:
  1. Tool Discovery  - Product Hunt, TAAFT, FutureTools
  2. AI News Blogs   - OpenAI, Google AI, Anthropic, Meta, HuggingFace, Mistral
  3. Competitive Intel - Same blogs, competitive-focused extraction

Input:  pipeline/data/raw-data.json (reads existing, injects firecrawl key)
Output: pipeline/data/raw-data.json (updated with firecrawl discoveries)
"""

import argparse
import json
import sys
import os
import time
import httpx
from datetime import datetime, timedelta
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import (FIRECRAWL_API_KEY, DIGEST_DIR, today_str,
                              write_json, read_json, ensure_data_dir)

# ── Firecrawl API ───────────────────────────────────────────────────────────

FIRECRAWL_API_URL = "https://api.firecrawl.dev/v1"

WELL_KNOWN_TOOLS = {
    "chatgpt", "claude", "gemini", "copilot", "github copilot", "cursor",
    "zapier", "notion", "manus", "perplexity", "midjourney", "dall-e",
    "stable diffusion", "hugging face", "replicate", "vercel", "supabase",
}

BLOG_SOURCES: list[dict[str, str]] = [
    {"company": "OpenAI", "url": "https://openai.com/blog", "method": "scrape"},
    {"company": "Google DeepMind", "url": "https://blog.google/technology/ai/", "method": "scrape"},
    {"company": "Anthropic", "url": "https://www.anthropic.com/news", "method": "scrape"},
    {"company": "Meta AI", "url": "https://ai.meta.com/blog/", "method": "search"},
    {"company": "Hugging Face", "url": "https://huggingface.co/blog", "method": "search"},
    {"company": "Mistral", "url": "https://mistral.ai/news/", "method": "scrape"},
]

TOOL_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "tools": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "tagline": {"type": "string"},
                    "url": {"type": "string"},
                    "category": {"type": "string"},
                },
                "required": ["name", "tagline"],
            },
        },
    },
}

TOOL_ENRICHMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Tool or product name"},
        "description": {"type": "string", "description": "One-paragraph description of what the tool does"},
        "pricing": {"type": "string", "description": "Pricing summary, e.g. 'Free', 'Freemium', '$19/mo', 'Enterprise only'"},
        "key_features": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Top 3-5 features or capabilities",
        },
        "use_cases": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Top 2-3 use cases or target audiences",
        },
        "company": {"type": "string", "description": "Company or team behind the tool"},
    },
}

BLOG_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "posts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "date": {"type": "string"},
                    "summary": {"type": "string"},
                    "url": {"type": "string"},
                },
                "required": ["title", "summary"],
            },
        },
    },
}


# ── Firecrawl Helpers ───────────────────────────────────────────────────────

def firecrawl_search(query: str, limit: int = 8, max_retries: int = 2) -> list[dict]:
    """Search via Firecrawl and return list of {url, title, description}."""
    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "query": query,
        "limit": limit,
    }

    for attempt in range(max_retries + 1):
        try:
            resp = httpx.post(
                f"{FIRECRAWL_API_URL}/search",
                json=payload,
                headers=headers,
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("data", [])
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "description": r.get("description", ""),
                }
                for r in results
                if r.get("title")
            ]
        except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
            print(f"    Firecrawl search error (attempt {attempt + 1}/{max_retries + 1}): {e}")
            if attempt < max_retries:
                time.sleep(2 ** attempt)
        except Exception as e:
            print(f"    Firecrawl search unexpected error: {e}")
            return []
    return []


def firecrawl_scrape_json(url: str, schema: dict, prompt: str = "",
                          max_retries: int = 2) -> dict | None:
    """Scrape a URL with Firecrawl and extract structured JSON."""
    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json",
    }
    json_options: dict[str, Any] = {"schema": schema}
    if prompt:
        json_options["prompt"] = prompt

    payload = {
        "url": url,
        "formats": ["json"],
        "jsonOptions": json_options,
        "timeout": 15000,
    }

    for attempt in range(max_retries + 1):
        try:
            resp = httpx.post(
                f"{FIRECRAWL_API_URL}/scrape",
                json=payload,
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", {}).get("json", {})
        except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
            print(f"    Firecrawl scrape error for {url} (attempt {attempt + 1}/{max_retries + 1}): {e}")
            if attempt < max_retries:
                time.sleep(2 ** attempt)
        except Exception as e:
            print(f"    Firecrawl scrape unexpected error for {url}: {e}")
            return None
    return None


# ── Tool Landing Page Enrichment ───────────────────────────────────────────

def enrich_tools_from_landing_pages(tools: list[dict], max_tools: int = 8) -> list[dict]:
    """Scrape tool landing pages to extract pricing, features, and use cases.

    Enriches each tool dict in-place with a 'landing_page' key containing
    structured data from the tool's website. Skips tools without URLs.
    """
    enriched_count = 0
    for tool in tools[:max_tools]:
        url = tool.get("url", "")
        if not url or not url.startswith("http"):
            continue

        data = firecrawl_scrape_json(
            url,
            schema=TOOL_ENRICHMENT_SCHEMA,
            prompt="Extract the product name, description, pricing, top features, use cases, and company from this landing page.",
        )
        if data:
            tool["landing_page"] = data
            enriched_count += 1
            pricing = data.get("pricing", "Unknown")
            features_n = len(data.get("key_features", []))
            print(f"      {tool.get('name', 'Unknown')}: pricing={pricing}, {features_n} features")

    return tools


# ── Track 1: Tool Discovery ────────────────────────────────────────────────

def discover_tools_producthunt(date_label: str) -> list[dict]:
    """Find new AI tools launched on Product Hunt."""
    print("    Product Hunt...")
    results = firecrawl_search(
        f"new AI tool launched today site:producthunt.com {date_label}",
        limit=8,
    )
    return [
        {
            "name": r["title"].split(" - ")[0].split(" | ")[0].strip(),
            "tagline": r["description"][:200] if r["description"] else "",
            "url": r["url"],
            "category": "Product Hunt Launch",
            "source": "producthunt",
        }
        for r in results
    ]


def discover_tools_taaft(date_label: str) -> list[dict]:
    """Find newest tools from There's An AI For That via search."""
    print("    There's An AI For That...")
    results = firecrawl_search(
        f"new AI tool site:theresanaiforthat.com {date_label}",
        limit=8,
    )
    return [
        {
            "name": r["title"].split(" - ")[0].split(" | ")[0].strip(),
            "tagline": r["description"][:200] if r["description"] else "",
            "url": r["url"],
            "category": "AI Tool",
            "source": "theresanaiforthat",
        }
        for r in results
        if r.get("title")
    ]


def discover_tools_futuretools(date_label: str) -> list[dict]:
    """Find new AI tools from FutureTools directory."""
    print("    FutureTools...")
    results = firecrawl_search(
        f"new AI tool site:futuretools.io {date_label}",
        limit=5,
    )
    return [
        {
            "name": r["title"].split(" - ")[0].split(" | ")[0].strip(),
            "tagline": r["description"][:200] if r["description"] else "",
            "url": r["url"],
            "category": "Directory Pick",
            "source": "futuretools",
        }
        for r in results
    ]


# ── Track 2: AI News from Primary Blogs ────────────────────────────────────

def scrape_ai_blogs(date_str: str) -> list[dict]:
    """Fetch recent posts from major AI company blogs via scrape or search."""
    cutoff = datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=2)
    date_label = cutoff.strftime("%d %B %Y")
    all_posts: list[dict] = []

    for blog in BLOG_SOURCES:
        company = blog["company"]
        url = blog["url"]
        method = blog.get("method", "scrape")
        print(f"    {company} blog ({method})...")

        if method == "search":
            results = firecrawl_search(
                f"{company} latest announcement site:{url.split('//')[1].split('/')[0]}",
                limit=5,
            )
            for r in results:
                all_posts.append({
                    "title": r.get("title", ""),
                    "date": "",
                    "summary": r.get("description", "")[:300],
                    "url": r.get("url", ""),
                    "company": company,
                    "source_blog": url,
                })
            continue

        data = firecrawl_scrape_json(
            url,
            BLOG_EXTRACTION_SCHEMA,
            prompt=f"Extract the most recent blog posts from {company}. For each post get: title, date (ISO format if possible), summary (2-3 sentences), and url (full link to the post).",
        )
        if not data or "posts" not in data:
            continue

        for post in data["posts"]:
            post["company"] = company
            post["source_blog"] = url

            post_date = post.get("date", "")
            if post_date:
                try:
                    parsed = datetime.fromisoformat(post_date.replace("Z", "+00:00"))
                    if parsed.replace(tzinfo=None) < cutoff:
                        continue
                except (ValueError, TypeError):
                    pass

            all_posts.append(post)

    return all_posts


# ── Track 3: Competitive Intel (derived from blog data) ────────────────────

def extract_competitive_intel(blog_posts: list[dict]) -> list[dict]:
    """Transform blog posts into competitive intelligence entries."""
    intel: list[dict] = []
    for post in blog_posts:
        company = post.get("company", "Unknown")
        title = post.get("title", "")
        summary = post.get("summary", "")

        announcement_type = "Update"
        title_lower = title.lower()
        if any(w in title_lower for w in ("launch", "introducing", "announcing", "release", "new")):
            announcement_type = "Launch"
        elif any(w in title_lower for w in ("research", "paper", "study")):
            announcement_type = "Research"
        elif any(w in title_lower for w in ("partner", "collaborat", "integrat")):
            announcement_type = "Partnership"
        elif any(w in title_lower for w in ("safety", "policy", "responsible")):
            announcement_type = "Policy"

        intel.append({
            "company": company,
            "announcement_type": announcement_type,
            "title": title,
            "key_detail": summary[:300] if summary else "",
            "url": post.get("url", ""),
        })

    return intel


# ── Deduplication ───────────────────────────────────────────────────────────

def deduplicate_tools(tools: list[dict]) -> list[dict]:
    """Remove well-known tools, duplicates, and recently featured tools."""
    ledger_path = DIGEST_DIR / "recent-themes.json"
    recent_names: set[str] = set()
    if ledger_path.exists():
        try:
            with open(ledger_path, "r", encoding="utf-8") as f:
                ledger = json.load(f)
            for date in sorted(ledger.keys(), reverse=True)[:14]:
                for tool_name in ledger[date].get("featured_tools", []):
                    recent_names.add(tool_name.lower())
        except Exception:
            pass

    seen_urls: set[str] = set()
    seen_names: set[str] = set()
    filtered: list[dict] = []

    for tool in tools:
        name = tool.get("name", "").strip()
        name_lower = name.lower()
        url = tool.get("url", "")

        if not name:
            continue
        if name_lower in WELL_KNOWN_TOOLS:
            continue
        if any(known in name_lower for known in WELL_KNOWN_TOOLS):
            continue
        if name_lower in recent_names:
            continue
        if url and url in seen_urls:
            continue
        if name_lower in seen_names:
            continue

        seen_urls.add(url)
        seen_names.add(name_lower)
        filtered.append(tool)

    return filtered


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Step 01B: Discover tools & blogs via Firecrawl")
    parser.add_argument("--date", default=today_str(), help="Date (YYYY-MM-DD)")
    args = parser.parse_args()

    date_obj = datetime.strptime(args.date, "%Y-%m-%d")
    date_label = date_obj.strftime("%d %B %Y")

    print(f"[01B] Discovering tools & blogs for {date_label}")

    if not FIRECRAWL_API_KEY:
        print("  No FIRECRAWL_API_KEY set -- skipping Firecrawl discovery")
        print("  Pipeline will use Perplexity-only data (no degradation)")
        sys.exit(0)

    ensure_data_dir()

    # ── Track 1: Tool Discovery ──────────────────────────────────────────
    print("  Track 1: Tool Discovery")
    all_tools: list[dict] = []

    ph_tools = discover_tools_producthunt(date_label)
    all_tools.extend(ph_tools)
    print(f"      Product Hunt: {len(ph_tools)} tools")

    taaft_tools = discover_tools_taaft(date_label)
    all_tools.extend(taaft_tools)
    print(f"      TAAFT: {len(taaft_tools)} tools")

    ft_tools = discover_tools_futuretools(date_label)
    all_tools.extend(ft_tools)
    print(f"      FutureTools: {len(ft_tools)} tools")

    deduped_tools = deduplicate_tools(all_tools)
    print(f"      After dedup: {len(deduped_tools)} tools (from {len(all_tools)} raw)")

    # Enrich top tools with landing page data (pricing, features, use cases)
    print("    Enriching tool landing pages...")
    deduped_tools = enrich_tools_from_landing_pages(deduped_tools)
    enriched_n = sum(1 for t in deduped_tools if t.get("landing_page"))
    print(f"      Enriched: {enriched_n}/{len(deduped_tools)} tools")

    # ── Track 2: AI News from Primary Blogs ──────────────────────────────
    print("  Track 2: AI News Blogs")
    blog_posts = scrape_ai_blogs(args.date)
    print(f"      {len(blog_posts)} recent posts from {len(BLOG_SOURCES)} blogs")

    # ── Track 3: Competitive Intel (derived from blog data) ──────────────
    print("  Track 3: Competitive Intel")
    competitive_intel = extract_competitive_intel(blog_posts)
    print(f"      {len(competitive_intel)} company announcements")

    # ── Inject into raw-data.json ────────────────────────────────────────
    firecrawl_data = {
        "discovered_at": datetime.now().isoformat(),
        "tools": deduped_tools,
        "ai_news": blog_posts,
        "competitive": competitive_intel,
    }

    raw_data = read_json("raw-data.json")
    if raw_data:
        raw_data["firecrawl"] = firecrawl_data
        write_json("raw-data.json", raw_data)
        print(f"\n  Injected firecrawl data into raw-data.json")
    else:
        write_json("firecrawl-discoveries.json", firecrawl_data)
        print(f"\n  raw-data.json not found -- saved standalone firecrawl-discoveries.json")

    # Summary
    print(f"  Summary: {len(deduped_tools)} tools, {len(blog_posts)} blog posts, {len(competitive_intel)} competitive items")


if __name__ == "__main__":
    main()
