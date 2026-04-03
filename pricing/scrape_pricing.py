"""
AI API Pricing Tracker

Scrapes pricing pages from major AI API providers using Firecrawl JSON extraction.
Outputs a normalized JSON file with per-model pricing data.

Usage:
    python pricing/scrape_pricing.py
    python pricing/scrape_pricing.py --output pricing/data.json

Designed to run weekly (or on-demand) to keep pricing data fresh.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import FIRECRAWL_API_KEY

FIRECRAWL_API_URL = "https://api.firecrawl.dev/v1"

# ── Provider definitions ────────────────────────────────────────────────────

PROVIDERS: list[dict[str, str]] = [
    {"name": "OpenAI", "url": "https://openai.com/api/pricing/", "wait": "5000"},
    {"name": "Anthropic", "url": "https://docs.anthropic.com/en/docs/about-claude/models", "wait": "3000"},
    {"name": "Google Gemini", "url": "https://ai.google.dev/gemini-api/docs/pricing", "wait": "5000"},
    {"name": "Mistral", "url": "https://mistral.ai/products#pricing", "wait": "3000"},
    {"name": "Groq", "url": "https://groq.com/pricing/", "wait": "3000"},
    {"name": "Together AI", "url": "https://www.together.ai/pricing", "wait": "3000"},
    {"name": "xAI", "url": "https://x.ai/api", "wait": "3000"},
    {"name": "Perplexity", "url": "https://docs.perplexity.ai/guides/pricing", "wait": "3000"},
    {"name": "Cohere", "url": "https://cohere.com/pricing", "wait": "5000"},
    {"name": "AWS Bedrock", "url": "https://aws.amazon.com/bedrock/pricing/", "wait": "5000"},
]

PRICING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "models": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "model_name": {"type": "string", "description": "Official model name or ID"},
                    "input_price_per_1m_tokens": {
                        "type": "number",
                        "description": "USD cost per 1 million input tokens",
                    },
                    "output_price_per_1m_tokens": {
                        "type": "number",
                        "description": "USD cost per 1 million output tokens",
                    },
                    "context_window": {
                        "type": "string",
                        "description": "Max context window (e.g. '128K', '1M', '200K')",
                    },
                    "model_type": {
                        "type": "string",
                        "description": "Type: chat, embedding, image, audio, reasoning",
                    },
                },
                "required": ["model_name"],
            },
        },
    },
}


def scrape_provider_pricing(provider: dict[str, str]) -> dict[str, Any] | None:
    """Scrape a single provider's pricing page and return normalized data."""
    name = provider["name"]
    url = provider["url"]
    wait_ms = int(provider.get("wait", "3000"))

    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "url": url,
        "formats": ["json"],
        "jsonOptions": {
            "schema": PRICING_SCHEMA,
            "prompt": (
                f"Extract ALL available AI model pricing from this {name} pricing page. "
                "For each model, extract the model name, input price per 1 million tokens (USD), "
                "output price per 1 million tokens (USD), context window size, and model type. "
                "If prices are per 1K tokens, multiply by 1000 to normalize to per 1M. "
                "Only include models with visible pricing. Skip deprecated models."
            ),
        },
        "waitFor": wait_ms,
        "timeout": 30000,
    }

    for attempt in range(2):
        try:
            resp = httpx.post(
                f"{FIRECRAWL_API_URL}/scrape",
                json=payload,
                headers=headers,
                timeout=45,
            )
            resp.raise_for_status()
            data = resp.json()
            extracted = data.get("data", {}).get("json", {})
            models = extracted.get("models", [])

            if models:
                return {
                    "provider": name,
                    "source_url": url,
                    "scraped_at": datetime.utcnow().isoformat() + "Z",
                    "model_count": len(models),
                    "models": models,
                }
            else:
                print(f"    {name}: no models extracted (attempt {attempt + 1}/2)")
                if attempt == 0:
                    time.sleep(2)
        except Exception as e:
            print(f"    {name}: scrape error (attempt {attempt + 1}/2): {e}")
            if attempt == 0:
                time.sleep(2)

    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="AI API Pricing Tracker")
    parser.add_argument(
        "--output",
        default=str(Path(__file__).parent / "data.json"),
        help="Output JSON path",
    )
    args = parser.parse_args()

    if not FIRECRAWL_API_KEY:
        print("ERROR: FIRECRAWL_API_KEY not set")
        sys.exit(1)

    print(f"AI API Pricing Tracker")
    print(f"Scraping {len(PROVIDERS)} providers...")

    all_providers: list[dict[str, Any]] = []
    total_models = 0

    for provider in PROVIDERS:
        name = provider["name"]
        print(f"  {name}...", end=" ", flush=True)
        result = scrape_provider_pricing(provider)
        if result:
            all_providers.append(result)
            total_models += result["model_count"]
            print(f"{result['model_count']} models")
        else:
            print("FAILED")

    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "provider_count": len(all_providers),
        "total_models": total_models,
        "providers": all_providers,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(all_providers)} providers, {total_models} models to {output_path}")

    # Load previous data for change detection
    prev_path = output_path.with_name("data-previous.json")
    if prev_path.exists():
        with open(prev_path, encoding="utf-8") as f:
            prev = json.load(f)
        detect_changes(prev, output)

    # Rotate: current becomes previous for next run
    if output_path.exists():
        import shutil
        shutil.copy2(output_path, prev_path)


def detect_changes(prev: dict, current: dict) -> None:
    """Compare previous and current pricing data, print changes."""
    prev_prices: dict[str, dict] = {}
    for p in prev.get("providers", []):
        for m in p.get("models", []):
            key = f"{p['provider']}/{m['model_name']}"
            prev_prices[key] = m

    changes = []
    for p in current.get("providers", []):
        for m in p.get("models", []):
            key = f"{p['provider']}/{m['model_name']}"
            if key in prev_prices:
                old = prev_prices[key]
                old_in = old.get("input_price_per_1m_tokens")
                new_in = m.get("input_price_per_1m_tokens")
                if old_in and new_in and old_in != new_in:
                    direction = "DOWN" if new_in < old_in else "UP"
                    pct = ((new_in - old_in) / old_in) * 100
                    changes.append(f"  {direction}: {key} input ${old_in} -> ${new_in} ({pct:+.1f}%)")
            else:
                changes.append(f"  NEW: {key}")

    if changes:
        print(f"\nPrice changes detected ({len(changes)}):")
        for c in changes:
            print(c)
    else:
        print("\nNo price changes detected since last run.")


if __name__ == "__main__":
    main()
