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
import httpx
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import (PERPLEXITY_API_KEY, today_str, today_label,
                              write_json, read_json)

# ── Perplexity Sonar API ─────────────────────────────────────────────────────

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"
SONAR_MODEL = "sonar"


def perplexity_search(query, system_prompt="Be precise and concise."):
    """Search via Perplexity Sonar API. Returns text response."""
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

    try:
        resp = httpx.post(PERPLEXITY_URL, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        citations = data.get("citations", [])
        return {"content": content, "citations": citations}
    except Exception as e:
        print(f"  Perplexity error: {e}")
        return None


# ── Query Definitions ────────────────────────────────────────────────────────

def build_queries(date_label, month_year):
    """Return the 5 search queries for news gathering.

    Uses today's date (not month/year) for AI news, competitive, and tools
    to maximize freshness and reduce cross-day repetition.
    """
    return {
        "ai_news": {
            "query": f"AI model releases and major AI developments today {date_label}. Include specific model names, companies, benchmarks, and capabilities announced in the last 48 hours.",
            "system": "You are an AI industry analyst. Report the most significant AI developments with specific details: model names, company names, key capabilities, and benchmark results. Focus ONLY on developments from the last 48 hours. Do NOT report on models launched more than a week ago unless there is new benchmark data or pricing news.",
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
            "query": f"OpenAI Google DeepMind Anthropic Meta AI Mistral latest news announcements today {date_label}.",
            "system": "You are a competitive intelligence analyst covering the AI industry. For each major company, report ONLY their most recent announcement from the last 48 hours. If a company has no new news today, say so rather than repeating old news.",
        },
        "tools": {
            "query": f"New AI productivity tools coding assistants agentic workflow tools launched or updated this week {date_label}. Include tool names, what they do, and links.",
            "system": "You are an AI tools reviewer. Recommend 6 specific tools with their names, one-line descriptions, use cases, and official URLs. Focus on tools released or updated in the LAST 7 DAYS. Prefer tools that are NEW over tools that are merely popular.",
        },
    }


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
