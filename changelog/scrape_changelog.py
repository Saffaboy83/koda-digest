"""
"Who Shipped What" AI Changelog Tracker

Uses Firecrawl map() to discover all URLs on company blogs/changelogs,
compares against previous snapshot to find new posts, then scrapes
each new post for a summary. Accumulates entries over a rolling 30-day window.

Usage:
    python changelog/scrape_changelog.py
    python changelog/scrape_changelog.py --date 2026-04-03
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import FIRECRAWL_API_KEY

FIRECRAWL_API_URL = "https://api.firecrawl.dev/v1"

# ── Company Sources (multi-URL per company) ──────────────────────────────────

COMPANY_SOURCES: list[dict[str, Any]] = [
    {
        "company": "OpenAI",
        "color": "#10B981",
        "sources": [
            {"url": "https://openai.com/news/", "type": "blog"},
            {"url": "https://platform.openai.com/docs/changelog", "type": "changelog"},
        ],
    },
    {
        "company": "Anthropic",
        "color": "#D97706",
        "sources": [
            {"url": "https://www.anthropic.com/news", "type": "blog"},
            {"url": "https://docs.anthropic.com/en/docs/about-claude/models", "type": "changelog"},
        ],
    },
    {
        "company": "Google",
        "color": "#3B82F6",
        "sources": [
            {"url": "https://blog.google/technology/ai/", "type": "blog"},
            {"url": "https://developers.googleblog.com/en/", "type": "blog"},
            {"url": "https://cloud.google.com/blog/products/ai-machine-learning", "type": "blog"},
        ],
    },
    {
        "company": "Microsoft",
        "color": "#00A4EF",
        "sources": [
            {"url": "https://blogs.microsoft.com/ai/", "type": "blog"},
            {"url": "https://devblogs.microsoft.com/ai/", "type": "blog"},
        ],
    },
    {
        "company": "Amazon AWS",
        "color": "#FF9900",
        "sources": [
            {"url": "https://aws.amazon.com/blogs/machine-learning/", "type": "blog"},
            {"url": "https://aws.amazon.com/about-aws/whats-new/", "type": "changelog"},
        ],
    },
    {
        "company": "Meta AI",
        "color": "#6366F1",
        "sources": [
            {"url": "https://ai.meta.com/blog/", "type": "blog"},
        ],
    },
    {
        "company": "Apple",
        "color": "#A3AAAE",
        "sources": [
            {"url": "https://machinelearning.apple.com", "type": "blog"},
        ],
    },
    {
        "company": "NVIDIA",
        "color": "#76B900",
        "sources": [
            {"url": "https://developer.nvidia.com/blog/", "type": "blog"},
            {"url": "https://blogs.nvidia.com/blog/category/deep-learning/", "type": "blog"},
        ],
    },
    {
        "company": "Mistral",
        "color": "#F97316",
        "sources": [
            {"url": "https://mistral.ai/news/", "type": "blog"},
        ],
    },
    {
        "company": "xAI",
        "color": "#8B5CF6",
        "sources": [
            {"url": "https://x.ai/blog", "type": "blog"},
            {"url": "https://x.ai/news", "type": "blog"},
        ],
    },
    {
        "company": "Cohere",
        "color": "#EF4444",
        "sources": [
            {"url": "https://cohere.com/blog", "type": "blog"},
        ],
    },
    {
        "company": "Hugging Face",
        "color": "#FFD21E",
        "sources": [
            {"url": "https://huggingface.co/blog", "type": "blog"},
        ],
    },
    {
        "company": "Stability AI",
        "color": "#C084FC",
        "sources": [
            {"url": "https://stability.ai/news", "type": "blog"},
        ],
    },
    {
        "company": "DeepSeek",
        "color": "#4F46E5",
        "sources": [
            {"url": "https://api-docs.deepseek.com/news", "type": "changelog"},
        ],
    },
    {
        "company": "Qwen",
        "color": "#7C3AED",
        "sources": [
            {"url": "https://qwenlm.github.io/blog/", "type": "blog"},
        ],
    },
    {
        "company": "Together AI",
        "color": "#EC4899",
        "sources": [
            {"url": "https://www.together.ai/blog", "type": "blog"},
        ],
    },
    {
        "company": "Groq",
        "color": "#06B6D4",
        "sources": [
            {"url": "https://groq.com/news/", "type": "blog"},
        ],
    },
    {
        "company": "Perplexity",
        "color": "#F59E0B",
        "sources": [
            {"url": "https://www.perplexity.ai/hub", "type": "blog"},
        ],
    },
    {
        "company": "Databricks",
        "color": "#FF3621",
        "sources": [
            {"url": "https://www.databricks.com/blog/category/generative-ai", "type": "blog"},
        ],
    },
    {
        "company": "Runway",
        "color": "#00E5FF",
        "sources": [
            {"url": "https://runwayml.com/blog/", "type": "blog"},
        ],
    },
    {
        "company": "ElevenLabs",
        "color": "#F472B6",
        "sources": [
            {"url": "https://elevenlabs.io/blog", "type": "blog"},
        ],
    },
    {
        "company": "Adobe",
        "color": "#FF0000",
        "sources": [
            {"url": "https://blog.adobe.com/en/topics/adobe-firefly", "type": "blog"},
        ],
    },
    {
        "company": "Cursor",
        "color": "#7DD3FC",
        "sources": [
            {"url": "https://www.cursor.com/blog", "type": "blog"},
        ],
    },
    {
        "company": "Midjourney",
        "color": "#FBBF24",
        "sources": [
            {"url": "https://docs.midjourney.com/changelog", "type": "changelog"},
        ],
    },
    {
        "company": "Samsung",
        "color": "#1428A0",
        "sources": [
            {"url": "https://news.samsung.com/global/tag/galaxy-ai", "type": "blog"},
        ],
    },
]

CATEGORIES = [
    "Model Release", "Feature", "API Update", "SDK Release",
    "Developer Tools", "Pricing", "Policy", "Partnership",
    "Research", "Infrastructure", "Open Source", "Acquisition", "Safety",
]

NEW_POST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string", "description": "2-3 sentence summary of the post"},
        "date": {"type": "string", "description": "Publication date if shown (YYYY-MM-DD format preferred)"},
        "category": {
            "type": "string",
            "description": f"One of: {', '.join(CATEGORIES)}",
        },
    },
    "required": ["title"],
}

# URL path segments that indicate non-article pages
SKIP_PATH_PATTERNS = [
    "/tag/", "/category/", "/page/", "/author/", "/archive/",
    "/rss", ".xml", ".json", "/feed", "/sitemap",
    "/careers", "/legal/", "/terms", "/privacy",
    "/login", "/signup", "/helpcenter", "/getting-started",
    "/search", "/contact", "/about/",
]


# ── Helpers ──────────────────────────────────────────────────────────────────


# Module-level flag to stop all API calls once credits are exhausted
_credits_exhausted = False


def firecrawl_request(
    endpoint: str,
    payload: dict[str, Any],
    timeout: int = 25,
    max_retries: int = 2,
) -> dict[str, Any] | None:
    """Make a Firecrawl API request with retry + exponential backoff.

    Stops retrying immediately on 402 (Payment Required) and sets a global
    flag so all subsequent calls are skipped without burning more credits.
    """
    global _credits_exhausted
    if _credits_exhausted:
        return None

    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json",
    }
    url = f"{FIRECRAWL_API_URL}/{endpoint}"

    for attempt in range(max_retries + 1):
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 402:
                _credits_exhausted = True
                print(f"CREDITS EXHAUSTED", end=" ", flush=True)
                return None
            if attempt < max_retries:
                wait = 2 ** attempt
                print(f"retry({attempt + 1}/{max_retries})...", end=" ", flush=True)
                time.sleep(wait)
            else:
                print(f"failed({e})", end=" ", flush=True)
                return None
        except (httpx.TimeoutException, Exception) as e:
            if attempt < max_retries:
                wait = 2 ** attempt
                print(f"retry({attempt + 1}/{max_retries})...", end=" ", flush=True)
                time.sleep(wait)
            else:
                print(f"failed({e})", end=" ", flush=True)
                return None
    return None


def normalize_date(date_str: str) -> str:
    """Parse any date format and return YYYY-MM-DD, or empty string."""
    if not date_str or not date_str.strip():
        return ""
    from dateutil import parser as dateparser

    try:
        dt = dateparser.parse(date_str)
        if dt is None:
            return ""
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return ""


def is_recent(date_iso: str, max_days: int = 30) -> bool:
    """Check if a YYYY-MM-DD date is within the last N days."""
    if not date_iso:
        return False
    try:
        dt = datetime.strptime(date_iso, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        age = (datetime.now(tz=timezone.utc) - dt).days
        return age <= max_days
    except Exception:
        return False


def deduplicate_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate entries by URL and fuzzy title matching (0.85 threshold)."""
    seen_urls: set[str] = set()
    seen_titles: list[str] = []
    result: list[dict[str, Any]] = []

    for entry in entries:
        url = entry.get("url", "")
        title = entry.get("title", "")

        # Exact URL dedup
        if url in seen_urls:
            continue

        # Fuzzy title dedup within same company
        is_dup = False
        for prev_title in seen_titles:
            if SequenceMatcher(None, title.lower(), prev_title.lower()).ratio() > 0.85:
                is_dup = True
                break

        if is_dup:
            continue

        seen_urls.add(url)
        seen_titles.append(title)
        result.append(entry)

    return result


def load_accumulated(data_path: Path, max_days: int = 30) -> list[dict[str, Any]]:
    """Load existing entries from data.json, normalize dates, and prune old ones."""
    if not data_path.exists():
        return []
    try:
        with open(data_path, encoding="utf-8") as f:
            data = json.load(f)
        entries = data.get("entries", [])
        result = []
        for e in entries:
            raw_date = e.get("date", "")
            # Normalize legacy date formats (e.g., "Mar 25, 2026") to YYYY-MM-DD
            iso_date = raw_date if len(raw_date) == 10 and raw_date[4] == "-" else normalize_date(raw_date)
            if iso_date:
                e["date"] = iso_date
            if is_recent(e.get("date", ""), max_days):
                result.append(e)
        return result
    except Exception:
        return []


# ── Core Scraping ────────────────────────────────────────────────────────────


def map_blog_urls(blog_url: str, company: str) -> list[str]:
    """Discover blog post URLs using map() + search() fallback."""
    base_parts = urlparse(blog_url).netloc.replace("www.", "").split(".")
    root_domain = ".".join(base_parts[-2:])

    post_urls: list[str] = []
    seen: set[str] = set()

    # Method 1: Firecrawl map
    data = firecrawl_request("map", {"url": blog_url, "limit": 50, "includeSubdomains": True}, timeout=20)
    if data:
        links = data.get("links", [])
        for url in links:
            parsed = urlparse(url)
            domain = parsed.netloc.replace("www.", "")
            if root_domain not in domain:
                continue
            path = parsed.path.strip("/")
            if not path or len(path) < 10:
                continue
            if any(skip in path.lower() for skip in SKIP_PATH_PATTERNS):
                continue
            if url not in seen:
                post_urls.append(url)
                seen.add(url)

    # Method 2: Search fallback if map found too few URLs
    if len(post_urls) < 5:
        current_year = datetime.now().year
        query = f"site:{root_domain} ({company} OR AI) (release OR launch OR update OR announcement OR changelog) {current_year}"
        data = firecrawl_request("search", {"query": query, "limit": 15}, timeout=20)
        if data:
            results = data.get("data", [])
            for r in results:
                url = r.get("url", "")
                if url and url not in seen and root_domain in url:
                    post_urls.append(url)
                    seen.add(url)

    return post_urls


def scrape_new_post(url: str) -> dict[str, Any] | None:
    """Scrape a single new blog post for title, summary, date, category."""
    data = firecrawl_request(
        "scrape",
        {
            "url": url,
            "formats": ["json"],
            "jsonOptions": {
                "schema": NEW_POST_SCHEMA,
                "prompt": (
                    "Extract the blog post title, a 2-3 sentence summary, publication date "
                    f"(in YYYY-MM-DD format), and category (one of: {', '.join(CATEGORIES)})."
                ),
            },
            "onlyMainContent": True,
            "timeout": 15000,
        },
        timeout=25,
    )
    if not data:
        return None
    return data.get("data", {}).get("json", {})


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Changelog Tracker")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--output", default=str(Path(__file__).parent / "data.json"))
    args = parser.parse_args()

    if not FIRECRAWL_API_KEY:
        print("ERROR: FIRECRAWL_API_KEY not set")
        sys.exit(1)

    data_path = Path(args.output)
    snapshot_path = Path(__file__).parent / "url-snapshot.json"

    print("AI Changelog Tracker (Daily)")
    print(f"Date: {args.date}")
    print(f"Scanning {len(COMPANY_SOURCES)} companies...")

    # Load accumulated entries (rolling 30-day window)
    accumulated = load_accumulated(data_path, max_days=30)
    existing_urls = {e.get("url", "") for e in accumulated}
    print(f"  Accumulated: {len(accumulated)} entries from previous runs")

    # Load previous URL snapshot
    prev_snapshot: dict[str, list[str]] = {}
    if snapshot_path.exists():
        with open(snapshot_path, encoding="utf-8") as f:
            prev_snapshot = json.load(f).get("urls", {})

    new_snapshot: dict[str, list[str]] = {}
    new_entries: list[dict[str, Any]] = []

    for company_cfg in COMPANY_SOURCES:
        company = company_cfg["company"]
        color = company_cfg["color"]
        sources = company_cfg["sources"]
        print(f"\n  {company}...", flush=True)

        # Collect URLs from all sources for this company
        all_urls: list[str] = []
        seen_urls: set[str] = set()

        for src in sources:
            src_url = src["url"]
            print(f"    [{src['type']}] {src_url}...", end=" ", flush=True)
            urls = map_blog_urls(src_url, company)
            for u in urls:
                if u not in seen_urls:
                    all_urls.append(u)
                    seen_urls.add(u)
            print(f"{len(urls)} URLs", flush=True)

        new_snapshot[company] = all_urls

        if not all_urls:
            print(f"    skip (no URLs found)")
            continue

        # Find genuinely new URLs (not in snapshot AND not in accumulated data)
        prev_urls = set(prev_snapshot.get(company, []))
        new_urls = [u for u in all_urls if u not in prev_urls and u not in existing_urls]

        if not new_urls:
            print(f"    {len(all_urls)} total, 0 new")
            continue

        # Cap scrapes per company: 5 on cold start (many new), 15 on daily runs (few new)
        scrape_cap = 5 if len(new_urls) > 20 else 15
        print(f"    {len(all_urls)} total, {len(new_urls)} new -> scraping up to {scrape_cap}")

        # Scrape new posts
        scraped = 0
        for post_url in new_urls[:scrape_cap]:
            data = scrape_new_post(post_url)
            if not data or not data.get("title"):
                continue

            raw_date = data.get("date", "")
            iso_date = normalize_date(raw_date)
            if not is_recent(iso_date, max_days=30):
                continue

            # Validate category
            cat = data.get("category", "")
            if cat not in CATEGORIES:
                cat = "Feature"  # default fallback

            entry = {
                "company": company,
                "color": color,
                "url": post_url,
                "title": data.get("title", ""),
                "summary": data.get("summary", ""),
                "date": iso_date,
                "category": cat,
            }
            new_entries.append(entry)
            scraped += 1
            print(f"      [{cat}] {iso_date} - {entry['title'][:60]}")

            # Rate courtesy
            time.sleep(0.5)

    # Merge new entries with accumulated, then dedup
    merged = new_entries + accumulated
    merged = deduplicate_entries(merged)

    # Sort by date (newest first)
    merged.sort(key=lambda x: x.get("date", "1970-01-01"), reverse=True)

    # Count unique companies in final dataset
    companies_in_data = {e["company"] for e in merged}

    # Save changelog data
    output = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "company_count": len(COMPANY_SOURCES),
        "companies_with_posts": len(companies_in_data),
        "total_entries": len(merged),
        "new_today": len(new_entries),
        "entries": merged,
    }

    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Save URL snapshot for next run
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(
            {"updated_at": datetime.now(tz=timezone.utc).isoformat(), "urls": new_snapshot},
            f,
            indent=2,
        )

    print(f"\nDone: {len(new_entries)} new + {len(accumulated)} accumulated = {len(merged)} total entries")
    print(f"Saved to {data_path}")


if __name__ == "__main__":
    main()
