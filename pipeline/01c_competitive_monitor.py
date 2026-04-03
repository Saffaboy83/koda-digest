"""
Step 01C: Competitive Change Monitoring

Monitors AI company announcement/pricing/blog pages for changes since
the last run using Firecrawl's change tracking. Surfaces only what's new.

Input:  pipeline/data/competitive-baseline.json (previous snapshots)
Output: pipeline/data/competitive-changes.json (today's changes)
        pipeline/data/competitive-baseline.json (updated baseline)
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
from pipeline.config import FIRECRAWL_API_KEY, today_str, write_json, read_json

FIRECRAWL_API_URL = "https://api.firecrawl.dev/v1"

# ── Watchlist ───────────────────────────────────────────────────────────────

WATCHLIST: list[dict[str, str]] = [
    {"company": "OpenAI", "page": "Blog", "url": "https://openai.com/blog"},
    {"company": "OpenAI", "page": "Pricing", "url": "https://openai.com/api/pricing/"},
    {"company": "Anthropic", "page": "News", "url": "https://www.anthropic.com/news"},
    {"company": "Anthropic", "page": "Pricing", "url": "https://docs.anthropic.com/en/docs/about-claude/models"},
    {"company": "Google DeepMind", "page": "Blog", "url": "https://blog.google/technology/ai/"},
    {"company": "Mistral", "page": "News", "url": "https://mistral.ai/news/"},
    {"company": "Meta AI", "page": "Blog", "url": "https://ai.meta.com/blog/"},
    {"company": "xAI", "page": "API", "url": "https://x.ai/api"},
    {"company": "Cohere", "page": "Blog", "url": "https://cohere.com/blog"},
    {"company": "Perplexity", "page": "Blog", "url": "https://www.perplexity.ai/hub"},
    {"company": "Groq", "page": "News", "url": "https://groq.com/news/"},
    {"company": "Together AI", "page": "Blog", "url": "https://www.together.ai/blog"},
]

CHANGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "page_title": {"type": "string"},
        "new_items": {
            "type": "array",
            "description": "New announcements, blog posts, or items not in the baseline",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "summary": {"type": "string", "description": "1-2 sentence summary"},
                    "date": {"type": "string", "description": "Date if shown"},
                    "url": {"type": "string"},
                },
                "required": ["title"],
            },
        },
    },
}


def scrape_page_snapshot(url: str, wait_ms: int = 5000) -> str | None:
    """Scrape a page and return markdown content for baseline comparison."""
    if not FIRECRAWL_API_KEY:
        return None

    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "url": url,
        "formats": ["markdown"],
        "onlyMainContent": True,
        "waitFor": wait_ms,
        "timeout": 20000,
    }

    try:
        resp = httpx.post(
            f"{FIRECRAWL_API_URL}/scrape",
            json=payload,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("data", {}).get("markdown", "")
    except Exception as e:
        print(f"      Scrape failed: {e}")
        return None


def detect_changes(
    url: str, current_md: str, baseline_md: str | None
) -> list[dict[str, str]]:
    """Use Firecrawl JSON extraction to identify new items vs baseline."""
    if not baseline_md:
        return []  # First run, no baseline to compare against

    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json",
    }

    # Use the scrape endpoint with JSON extraction, passing both current and baseline
    # as context so the LLM can identify what's new
    diff_prompt = (
        "Compare the CURRENT page content against the BASELINE content below. "
        "Identify NEW items (blog posts, announcements, pricing changes, model releases) "
        "that appear in the CURRENT content but NOT in the BASELINE. "
        "Only return genuinely new items. Ignore layout or formatting changes.\n\n"
        f"BASELINE (previous snapshot, first 2000 chars):\n{baseline_md[:2000]}\n\n"
        f"CURRENT (today's snapshot, first 3000 chars):\n{current_md[:3000]}"
    )

    payload = {
        "url": url,
        "formats": ["json"],
        "jsonOptions": {
            "schema": CHANGE_SCHEMA,
            "prompt": diff_prompt,
        },
        "waitFor": 3000,
        "timeout": 20000,
    }

    try:
        resp = httpx.post(
            f"{FIRECRAWL_API_URL}/scrape",
            json=payload,
            headers=headers,
            timeout=35,
        )
        resp.raise_for_status()
        extracted = resp.json().get("data", {}).get("json", {})
        return extracted.get("new_items", [])
    except Exception as e:
        print(f"      Change detection failed: {e}")
        return []


def main() -> None:
    parser = argparse.ArgumentParser(description="Step 01C: Competitive Change Monitor")
    parser.add_argument("--date", default=today_str(), help="Date (YYYY-MM-DD)")
    args = parser.parse_args()

    print(f"[01C] Monitoring {len(WATCHLIST)} competitive pages")

    if not FIRECRAWL_API_KEY:
        print("  No FIRECRAWL_API_KEY -- skipping competitive monitoring")
        sys.exit(0)

    # Load baseline from previous run
    baseline = read_json("competitive-baseline.json") or {}
    baseline_snapshots = baseline.get("snapshots", {})

    all_changes: list[dict[str, Any]] = []
    new_snapshots: dict[str, str] = {}

    for entry in WATCHLIST:
        company = entry["company"]
        page = entry["page"]
        url = entry["url"]
        key = f"{company}|{page}"

        print(f"  {company} ({page})...", end=" ", flush=True)

        current_md = scrape_page_snapshot(url)
        if not current_md or len(current_md) < 100:
            print("skip (empty)")
            # Keep old baseline if scrape failed
            if key in baseline_snapshots:
                new_snapshots[key] = baseline_snapshots[key]
            continue

        new_snapshots[key] = current_md[:5000]  # Store truncated for baseline

        old_md = baseline_snapshots.get(key)
        if not old_md:
            print("new baseline")
            continue

        # Quick check: if content is identical, skip expensive LLM diff
        if current_md[:3000] == old_md[:3000]:
            print("no change")
            continue

        changes = detect_changes(url, current_md, old_md)
        if changes:
            for c in changes:
                c["company"] = company
                c["page_type"] = page
                c["source_url"] = url
            all_changes.extend(changes)
            print(f"{len(changes)} changes")
        else:
            print("no new items")

    # Save changes for synthesis
    changes_data = {
        "date": args.date,
        "monitored_at": datetime.now(tz=timezone.utc).isoformat(),
        "pages_monitored": len(WATCHLIST),
        "changes_found": len(all_changes),
        "changes": all_changes,
    }
    write_json("competitive-changes.json", changes_data)

    # Update baseline for next run
    baseline_data = {
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
        "snapshots": new_snapshots,
    }
    write_json("competitive-baseline.json", baseline_data)

    print(f"  Found {len(all_changes)} changes across {len(WATCHLIST)} pages")
    if all_changes:
        for c in all_changes[:5]:
            print(f"    [{c.get('company', '')}] {c.get('title', '')}")


if __name__ == "__main__":
    main()
