"""
Step 01: Gather news data from multiple sources.

Uses Perplexity Sonar API when available, falls back to printing
instructions for Claude Code WebSearch MCP.

Input:  None (or --date flag)
Output: pipeline/data/raw-data.json
"""

import argparse
import json
import sys
import os
import time
import httpx
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import (PERPLEXITY_API_KEY, FIRECRAWL_API_KEY, today_str,
                              today_label, write_json, read_json)

# ── Perplexity Sonar API ─────────────────────────────────────────────────────

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"
SONAR_MODEL = "sonar"


def perplexity_search(query: str, system_prompt: str = "Be precise and concise.", max_retries: int = 2) -> dict | None:
    """Search via Perplexity Sonar API. Returns text response. Retries on transient failures."""
    if not PERPLEXITY_API_KEY:
        return None

    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": SONAR_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ],
        "max_tokens": 4000,
        "temperature": 0.15,
        "return_citations": True,
    }

    for attempt in range(max_retries + 1):
        try:
            resp = httpx.post(PERPLEXITY_URL, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            citations = data.get("citations", [])
            if not content.strip():
                print(f"    Empty response (attempt {attempt + 1}/{max_retries + 1})")
                if attempt < max_retries:
                    time.sleep(2 ** attempt)
                    continue
                return None
            return {"content": content, "citations": citations}
        except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
            print(f"    Perplexity error (attempt {attempt + 1}/{max_retries + 1}): {e}")
            if attempt < max_retries:
                time.sleep(2 ** attempt)
            else:
                return None
        except Exception as e:
            print(f"    Perplexity unexpected error: {e}")
            return None
    return None


# ── Firecrawl Source Verification ────────────────────────────────────────────

FIRECRAWL_API_URL = "https://api.firecrawl.dev/v1"
MAX_SOURCE_TEXT = 3000  # chars per source to keep token usage reasonable


def firecrawl_scrape_markdown(url: str, timeout: int = 20) -> str | None:
    """Scrape a URL with Firecrawl and return clean markdown content."""
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
        "timeout": 15000,
    }

    try:
        resp = httpx.post(
            f"{FIRECRAWL_API_URL}/scrape",
            json=payload,
            headers=headers,
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        markdown = data.get("data", {}).get("markdown", "")
        return markdown[:MAX_SOURCE_TEXT] if markdown else None
    except Exception as e:
        print(f"      Firecrawl scrape failed for {url}: {e}")
        return None


def verify_sources(results: dict[str, dict], max_per_query: int = 3) -> dict[str, list[dict]]:
    """Scrape top citation URLs from Perplexity results for source verification.

    Returns dict mapping query key -> list of {url, text} verified sources.
    Only scrapes URLs that look like article pages (not homepages, search results, etc.).
    """
    if not FIRECRAWL_API_KEY:
        print("  Source verification skipped (no FIRECRAWL_API_KEY)")
        return {}

    print("  Verifying sources via Firecrawl...")

    skip_domains = {
        "google.com", "youtube.com", "twitter.com", "x.com", "reddit.com",
        "facebook.com", "instagram.com", "linkedin.com", "wikipedia.org",
    }

    verified: dict[str, list[dict]] = {}
    seen_urls: set[str] = set()
    total_scraped = 0

    for key, result in results.items():
        citations = result.get("citations", [])
        if not citations:
            continue

        verified[key] = []
        scraped_for_key = 0

        for url in citations:
            if scraped_for_key >= max_per_query:
                break
            if url in seen_urls:
                continue

            # Skip non-article domains
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.lower().replace("www.", "")
            if domain in skip_domains:
                continue
            # Skip homepages (path is just "/" or empty)
            path = urlparse(url).path.strip("/")
            if not path or path.count("/") == 0 and len(path) < 5:
                continue

            seen_urls.add(url)
            text = firecrawl_scrape_markdown(url)
            if text and len(text) > 200:
                verified[key].append({"url": url, "text": text})
                scraped_for_key += 1
                total_scraped += 1
                print(f"    [{key}] {domain}: {len(text)} chars")

    print(f"  Verified {total_scraped} sources across {len(verified)} queries")
    return verified


# ── Query Definitions ────────────────────────────────────────────────────────

def build_queries(date_label, month_year):
    """Return the 5 search queries for news gathering.

    Uses today's date (not month/year) for AI news, competitive, and tools
    to maximize freshness and reduce cross-day repetition.
    """
    return {
        "ai_news": {
            "query": f"AI model releases and major AI developments this week {date_label}. Include specific model names, companies, benchmarks, and capabilities announced in the last 5 days.",
            "system": "You are an AI industry analyst. Report the most significant AI developments with specific details: model names, company names, key capabilities, and benchmark results. Cover the last 5 days, prioritizing the most recent developments first. If nothing was announced in the last 48 hours (e.g., over a weekend), include the most notable stories from the past 5 days. Do NOT report on models launched more than 10 days ago unless there is new benchmark data or pricing news.",
        },
        "world_news": {
            "query": f"Top world news stories today {date_label}. Cover geopolitics, economy, conflicts, diplomacy, and major global events.",
            "system": "You are a world news editor. Report the top 6-8 global stories with key facts, locations, and context. Focus on what happened TODAY, not ongoing background. For continuing events, lead with the new development.",
        },
        "markets": {
            "query": f"S&P 500, NASDAQ, Bitcoin, Ethereum, Oil Brent price and percentage change today {date_label}. Include market sentiment indicators.",
            "system": "You are a financial markets analyst. Provide exact closing prices, daily percentage changes, and brief sentiment analysis. Use numbers, not words.",
        },
        "competitive": {
            "query": f"OpenAI Google DeepMind Anthropic Meta AI Mistral latest news announcements this week {date_label}.",
            "system": "You are a competitive intelligence analyst covering the AI industry. For each major company, report their most significant recent announcement from the last 5 days. Prioritize the newest developments. If a company has genuinely no news this week, briefly note their last known activity.",
        },
        "tools": {
            "query": f"New AI productivity tools coding assistants agentic workflow tools launched or updated this week {date_label}. Include tool names, what they do, and links.",
            "system": "You are an AI tools reviewer. Recommend 6 specific tools with their names, one-line descriptions, use cases, and official URLs. Focus on tools released or updated in the LAST 7 DAYS. Prefer tools that are NEW over tools that are merely popular.",
        },
    }


# ── Firecrawl Direct News Search ────────────────────────────────────────────

NOISE_DOMAINS = {
    "google.com", "youtube.com", "twitter.com", "x.com", "reddit.com",
    "facebook.com", "instagram.com", "linkedin.com", "wikipedia.org",
    "tiktok.com", "pinterest.com", "medium.com", "github.com",
}


def firecrawl_search(query: str, limit: int = 8, max_retries: int = 2) -> list[dict]:
    """Search via Firecrawl and return list of {url, title, description}."""
    if not FIRECRAWL_API_KEY:
        return []

    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"query": query, "limit": limit}

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
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "description": r.get("description", ""),
                }
                for r in data.get("data", [])
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


def firecrawl_direct_search(date_label: str, existing_citations: set[str]) -> dict[str, list[dict]]:
    """Run direct web searches via Firecrawl to supplement Perplexity.

    Searches for AI news, world news, and tool launches independently.
    Deduplicates against Perplexity citations and scrapes unique URLs.

    Returns dict: {"ai": [...], "world": [...], "tools": [...]}
    Each item: {"url", "title", "snippet", "text"}
    """
    if not FIRECRAWL_API_KEY:
        print("  Direct search skipped (no FIRECRAWL_API_KEY)")
        return {}

    print("  Running Firecrawl direct news search...")

    queries = {
        "ai": f"AI model release announcement {date_label}",
        "world": f"major world news today {date_label}",
        "tools": f"new AI tool launch startup {date_label}",
    }

    from urllib.parse import urlparse

    result: dict[str, list[dict]] = {}
    total_scraped = 0

    for key, query in queries.items():
        print(f"    Searching: {key}...")
        raw_results = firecrawl_search(query, limit=8)
        if not raw_results:
            print(f"      No results")
            continue

        # Filter out duplicates and noise
        unique = []
        for r in raw_results:
            url = r.get("url", "")
            if not url or url in existing_citations:
                continue
            domain = urlparse(url).netloc.lower().replace("www.", "")
            if domain in NOISE_DOMAINS:
                continue
            path = urlparse(url).path.strip("/")
            if not path or (path.count("/") == 0 and len(path) < 5):
                continue
            unique.append(r)

        print(f"      {len(raw_results)} results, {len(unique)} unique after dedup")

        # Scrape top 4 unique URLs for full text
        items = []
        for r in unique[:4]:
            url = r["url"]
            text = firecrawl_scrape_markdown(url)
            items.append({
                "url": url,
                "title": r.get("title", ""),
                "snippet": r.get("description", ""),
                "text": text[:MAX_SOURCE_TEXT] if text and len(text) > 200 else "",
            })
            if text and len(text) > 200:
                total_scraped += 1
                domain = urlparse(url).netloc.lower().replace("www.", "")
                print(f"      [{key}] {domain}: {len(text)} chars")

        result[key] = items

    print(f"  Direct search: {total_scraped} articles scraped across {len(result)} tracks")
    return result


# ── Live Market Data ─────────────────────────────────────────────────────────

def fetch_live_markets():
    """Fetch real-time market data via yfinance. Returns structured dict."""
    try:
        import yfinance as yf
    except ImportError:
        print("  WARNING: yfinance not installed — falling back to search")
        return None

    tickers = {
        "sp500": "^GSPC",
        "nasdaq": "^IXIC",
        "btc": "BTC-USD",
        "eth": "ETH-USD",
        "oil": "BZ=F",
    }

    markets = {}
    for key, symbol in tickers.items():
        try:
            t = yf.Ticker(symbol)
            info = t.fast_info
            price = info.last_price
            prev = info.previous_close
            if price and prev and prev != 0:
                change_pct = ((price - prev) / prev) * 100
                direction = "up" if change_pct > 0 else "down" if change_pct < 0 else "neutral"
                sign = "+" if change_pct > 0 else ""

                if key in ("btc", "eth"):
                    price_fmt = f"${price:,.2f}"
                elif key == "oil":
                    price_fmt = f"${price:,.2f}"
                else:
                    price_fmt = f"{price:,.2f}"

                # Fetch 7-day history for sparkline
                sparkline = []
                try:
                    hist = t.history(period="7d")
                    if not hist.empty:
                        sparkline = [round(float(c), 2) for c in hist["Close"].tolist()]
                except Exception:
                    pass

                markets[key] = {
                    "price": price_fmt,
                    "change": f"{sign}{change_pct:.2f}%",
                    "direction": direction,
                    "sparkline": sparkline,
                }
            else:
                markets[key] = {"price": "N/A", "change": "N/A", "direction": "neutral", "sparkline": []}
        except Exception as e:
            print(f"  WARNING: Could not fetch {symbol}: {e}")
            markets[key] = {"price": "N/A", "change": "N/A", "direction": "neutral", "sparkline": []}

    # Fear & Greed sentiment (try CNN first, then alternative.me crypto index)
    sentiment_fetched = False
    try:
        resp = httpx.get("https://production.dataviz.cnn.io/index/fearandgreed/graphdata", timeout=10)
        resp.raise_for_status()
        fg = resp.json()
        score = int(fg["fear_and_greed"]["score"])
        rating = fg["fear_and_greed"]["rating"]
        direction = "up" if score >= 50 else "down"
        markets["sentiment"] = {"value": str(score), "label": rating, "direction": direction}
        sentiment_fetched = True
    except Exception:
        pass

    if not sentiment_fetched:
        try:
            resp = httpx.get("https://api.alternative.me/fng/?limit=1", timeout=10)
            resp.raise_for_status()
            fg = resp.json()["data"][0]
            score = int(fg["value"])
            rating = fg["value_classification"]
            direction = "up" if score >= 50 else "down"
            markets["sentiment"] = {"value": str(score), "label": rating, "direction": direction}
        except Exception:
            markets["sentiment"] = {"value": "N/A", "label": "N/A", "direction": "neutral"}

    return markets


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Step 01: Gather news data")
    parser.add_argument("--date", default=today_str(), help="Date (YYYY-MM-DD)")
    args = parser.parse_args()

    date_obj = datetime.strptime(args.date, "%Y-%m-%d")
    date_label = date_obj.strftime("%d %B %Y")
    month_year = date_obj.strftime("%B %Y")

    print(f"[01] Gathering news for {date_label}")

    if not PERPLEXITY_API_KEY:
        print("  WARNING: No PERPLEXITY_API_KEY in .env")
        print("  This script requires the Perplexity Sonar API.")
        print("  Add your key to Digest/.env and retry.")
        sys.exit(1)

    queries = build_queries(date_label, month_year)
    results = {}

    for key, q in queries.items():
        print(f"  Searching: {key}...")
        result = perplexity_search(q["query"], q["system"])
        if result:
            results[key] = result
            print(f"    Got {len(result['content'])} chars, {len(result['citations'])} citations")
        else:
            results[key] = {"content": "", "citations": []}
            print(f"    FAILED — empty result")

    # Check if we have enough data for a useful digest
    successful = sum(1 for r in results.values() if r.get("content"))
    if successful == 0:
        print("  FATAL: All 5 queries returned empty -- no data to work with")
        sys.exit(1)
    elif successful < 3:
        print(f"  WARNING: Only {successful}/5 queries returned data -- digest quality may be reduced")
    else:
        print(f"  {successful}/5 queries returned data")

    # Verify sources by scraping actual citation URLs
    verified_sources = verify_sources(results)

    # Direct news search via Firecrawl (supplements Perplexity)
    all_citations = set()
    for r in results.values():
        all_citations.update(r.get("citations", []))
    for vs_list in verified_sources.values():
        all_citations.update(s.get("url", "") for s in vs_list)

    firecrawl_search_results = {}
    try:
        firecrawl_search_results = firecrawl_direct_search(date_label, all_citations)
    except Exception as e:
        print(f"  WARNING: Direct search failed (non-critical): {e}")

    # Fetch live market data (replaces unreliable search-based market quotes)
    print(f"  Fetching live market data...")
    live_markets = fetch_live_markets()
    if live_markets:
        non_na = sum(1 for v in live_markets.values() if isinstance(v, dict) and v.get("price") != "N/A")
        print(f"    Got {non_na}/{len(live_markets)} tickers with live prices")
    else:
        print(f"    Live markets unavailable — using search fallback")

    output = {
        "date": args.date,
        "date_label": date_label,
        "gathered_at": datetime.now().isoformat(),
        "source": "perplexity_sonar",
        "queries": {k: q["query"] for k, q in queries.items()},
        "results": results,
        "verified_sources": verified_sources,
        "firecrawl_search": firecrawl_search_results,
        "live_markets": live_markets,
    }

    path = write_json("raw-data.json", output)
    print(f"\n  Saved to {path}")

    # Save raw search results separately for stat verification (Step 03B)
    write_json("raw-search-results.json", results)
    print(f"  Saved raw-search-results.json for stat verification")

    # Quick summary
    total_chars = sum(len(r["content"]) for r in results.values())
    total_citations = sum(len(r["citations"]) for r in results.values())
    print(f"  Total: {total_chars} chars, {total_citations} citations across {len(results)} searches")


if __name__ == "__main__":
    main()
