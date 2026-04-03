"""
"Who Shipped What" AI Changelog Tracker

Uses Firecrawl map() to discover all URLs on company blogs/changelogs,
compares against previous week's snapshot to find new posts, then scrapes
each new post for a summary.

Usage:
    python changelog/scrape_changelog.py
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import FIRECRAWL_API_KEY

FIRECRAWL_API_URL = "https://api.firecrawl.dev/v1"

# ── Company blog/changelog URLs ────────────────────────────────────────────

COMPANY_BLOGS: list[dict[str, str]] = [
    {"company": "OpenAI", "url": "https://openai.com/blog", "color": "#10B981"},
    {"company": "Anthropic", "url": "https://www.anthropic.com/news", "color": "#D97706"},
    {"company": "Google DeepMind", "url": "https://blog.google/technology/ai/", "color": "#3B82F6"},
    {"company": "Mistral", "url": "https://mistral.ai/news/", "color": "#F97316"},
    {"company": "Meta AI", "url": "https://ai.meta.com/blog/", "color": "#6366F1"},
    {"company": "xAI", "url": "https://x.ai/blog", "color": "#8B5CF6"},
    {"company": "Cohere", "url": "https://cohere.com/blog", "color": "#EF4444"},
    {"company": "Together AI", "url": "https://www.together.ai/blog", "color": "#EC4899"},
    {"company": "Groq", "url": "https://groq.com/news/", "color": "#06B6D4"},
    {"company": "Perplexity", "url": "https://www.perplexity.ai/hub", "color": "#F59E0B"},
]

NEW_POST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string", "description": "2-3 sentence summary of the post"},
        "date": {"type": "string", "description": "Publication date if shown"},
        "category": {
            "type": "string",
            "description": "One of: Model Release, Feature, Pricing, Policy, Partnership, Research, Infrastructure",
        },
    },
    "required": ["title"],
}


def map_blog_urls(blog_url: str) -> list[str]:
    """Use Firecrawl map to discover all URLs on a blog."""
    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        resp = httpx.post(
            f"{FIRECRAWL_API_URL}/map",
            json={"url": blog_url, "limit": 50},
            headers=headers,
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        links = data.get("links", [])
        # Filter to likely blog post URLs (have path segments beyond root)
        from urllib.parse import urlparse
        base_domain = urlparse(blog_url).netloc
        post_urls = []
        for url in links:
            parsed = urlparse(url)
            if parsed.netloc != base_domain:
                continue
            path = parsed.path.strip("/")
            # Skip homepages, category pages, tag pages
            if not path or len(path) < 10:
                continue
            if any(skip in path for skip in ["/tag/", "/category/", "/page/", "/author/"]):
                continue
            post_urls.append(url)
        return post_urls
    except Exception as e:
        print(f"      Map failed: {e}")
        return []


def is_recent(date_str: str, max_days: int = 30) -> bool:
    """Check if a date string is within the last N days. Returns True if undated."""
    if not date_str or not date_str.strip():
        return False  # Skip undated posts
    from dateutil import parser as dateparser
    try:
        dt = dateparser.parse(date_str)
        if dt is None:
            return False
        age = (datetime.now(tz=timezone.utc) - dt.replace(tzinfo=timezone.utc)).days
        return age <= max_days
    except Exception:
        return False


def scrape_new_post(url: str) -> dict[str, Any] | None:
    """Scrape a single new blog post for title, summary, date, category."""
    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        resp = httpx.post(
            f"{FIRECRAWL_API_URL}/scrape",
            json={
                "url": url,
                "formats": ["json"],
                "jsonOptions": {
                    "schema": NEW_POST_SCHEMA,
                    "prompt": "Extract the blog post title, a 2-3 sentence summary, publication date, and category (Model Release, Feature, Pricing, Policy, Partnership, Research, or Infrastructure).",
                },
                "onlyMainContent": True,
                "timeout": 15000,
            },
            headers=headers,
            timeout=25,
        )
        resp.raise_for_status()
        return resp.json().get("data", {}).get("json", {})
    except Exception as e:
        print(f"        Scrape failed: {e}")
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Changelog Tracker")
    parser.add_argument("--output", default=str(Path(__file__).parent / "data.json"))
    args = parser.parse_args()

    if not FIRECRAWL_API_KEY:
        print("ERROR: FIRECRAWL_API_KEY not set")
        sys.exit(1)

    print("AI Changelog Tracker")
    print(f"Scanning {len(COMPANY_BLOGS)} company blogs...")

    # Load previous URL snapshot
    snapshot_path = Path(__file__).parent / "url-snapshot.json"
    prev_snapshot: dict[str, list[str]] = {}
    if snapshot_path.exists():
        with open(snapshot_path, encoding="utf-8") as f:
            prev_snapshot = json.load(f).get("urls", {})

    new_snapshot: dict[str, list[str]] = {}
    all_entries: list[dict[str, Any]] = []

    for blog in COMPANY_BLOGS:
        company = blog["company"]
        url = blog["url"]
        color = blog["color"]
        print(f"  {company}...", end=" ", flush=True)

        current_urls = map_blog_urls(url)
        new_snapshot[company] = current_urls

        if not current_urls:
            print("skip (no URLs found)")
            continue

        prev_urls = set(prev_snapshot.get(company, []))
        new_urls = [u for u in current_urls if u not in prev_urls]

        if not new_urls:
            print(f"{len(current_urls)} URLs, 0 new")
            continue

        print(f"{len(current_urls)} URLs, {len(new_urls)} new")

        # Scrape up to 8 new posts per company, keep only recent ones
        scraped = 0
        for post_url in new_urls[:8]:
            data = scrape_new_post(post_url)
            if not data or not data.get("title"):
                continue
            post_date = data.get("date", "")
            if not is_recent(post_date, max_days=30):
                continue
            entry = {
                "company": company,
                "color": color,
                "url": post_url,
                "title": data.get("title", ""),
                "summary": data.get("summary", ""),
                "date": post_date,
                "category": data.get("category", ""),
            }
            all_entries.append(entry)
            scraped += 1
            print(f"      [{entry['category'] or '?'}] {post_date} - {entry['title'][:50]}")

    # Save changelog data
    output = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "company_count": len(COMPANY_BLOGS),
        "new_posts": len(all_entries),
        "entries": all_entries,
    }

    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Save URL snapshot for next run
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump({"updated_at": datetime.now(tz=timezone.utc).isoformat(), "urls": new_snapshot}, f, indent=2)

    print(f"\nSaved {len(all_entries)} new posts to {output_path}")


if __name__ == "__main__":
    main()
