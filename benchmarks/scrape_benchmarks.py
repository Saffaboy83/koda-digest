"""
AI Model Benchmark Tracker

Scrapes benchmark leaderboards (LMSYS Chatbot Arena, LiveBench, SWE-Bench)
using Firecrawl JSON extraction. Outputs normalized JSON with model rankings.

Usage:
    python benchmarks/scrape_benchmarks.py
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

# ── Benchmark sources ───────────────────────────────────────────────────────

BENCHMARKS: list[dict[str, Any]] = [
    {
        "name": "Chatbot Arena",
        "url": "https://arena.ai/leaderboard/text",
        "category": "General",
        "description": "Human preference rankings from blind A/B comparisons (5.7M+ votes)",
        "schema": {
            "type": "object",
            "properties": {
                "models": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "rank": {"type": "integer"},
                            "model_name": {"type": "string"},
                            "elo_score": {"type": "number", "description": "Arena score"},
                            "provider": {"type": "string"},
                            "context_window": {"type": "string"},
                        },
                        "required": ["model_name"],
                    },
                },
            },
        },
        "prompt": "Extract the top 20 models from the Text Arena leaderboard table. For each row extract: rank number, exact model name (e.g. 'claude-opus-4-6-thinking'), Arena score (the number like 1504), provider/organization (e.g. 'Anthropic', 'Google', 'xAI'), and context window if shown. Use the EXACT model names from the table, not generic placeholders.",
        "wait": 10000,
    },
    {
        "name": "LiveBench",
        "url": "https://livebench.ai/",
        "category": "Reasoning",
        "description": "Contamination-free benchmark with monthly-refreshed questions",
        "schema": {
            "type": "object",
            "properties": {
                "models": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "rank": {"type": "integer"},
                            "model_name": {"type": "string"},
                            "score": {"type": "number", "description": "Overall score or average"},
                            "provider": {"type": "string"},
                        },
                        "required": ["model_name"],
                    },
                },
            },
        },
        "prompt": "Extract the top 20 models from the LiveBench leaderboard. Include rank, model name, overall score, and provider. Sort by score (highest first).",
        "wait": 8000,
    },
    {
        "name": "SWE-Bench Verified",
        "url": "https://www.swebench.com/",
        "category": "Coding",
        "description": "Real-world software engineering task completion",
        "schema": {
            "type": "object",
            "properties": {
                "models": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "rank": {"type": "integer"},
                            "model_name": {"type": "string", "description": "Model or agent/system name"},
                            "score": {"type": "number", "description": "Resolve rate percentage"},
                            "provider": {"type": "string"},
                        },
                        "required": ["model_name"],
                    },
                },
            },
        },
        "prompt": "Extract the top 20 models/agents from the SWE-Bench Verified leaderboard. Include rank, model/agent name, resolve rate (percentage), and provider. Sort by resolve rate (highest first).",
        "wait": 8000,
    },
]


def scrape_benchmark(benchmark: dict[str, Any]) -> dict[str, Any] | None:
    """Scrape a benchmark leaderboard and return structured data."""
    name = benchmark["name"]
    url = benchmark["url"]

    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "url": url,
        "formats": ["json"],
        "jsonOptions": {
            "schema": benchmark["schema"],
            "prompt": benchmark["prompt"],
        },
        "waitFor": benchmark.get("wait", 5000),
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
                # Assign ranks if missing
                for i, m in enumerate(models):
                    if not m.get("rank"):
                        m["rank"] = i + 1
                return {
                    "benchmark": name,
                    "category": benchmark.get("category", ""),
                    "description": benchmark.get("description", ""),
                    "source_url": url,
                    "scraped_at": datetime.now(tz=timezone.utc).isoformat(),
                    "model_count": len(models),
                    "models": models,
                }
            else:
                print(f"    {name}: no models extracted (attempt {attempt + 1}/2)")
                if attempt == 0:
                    time.sleep(3)
        except Exception as e:
            print(f"    {name}: error (attempt {attempt + 1}/2): {e}")
            if attempt == 0:
                time.sleep(3)

    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Benchmark Tracker")
    parser.add_argument("--output", default=str(Path(__file__).parent / "data.json"))
    args = parser.parse_args()

    if not FIRECRAWL_API_KEY:
        print("ERROR: FIRECRAWL_API_KEY not set")
        sys.exit(1)

    print(f"AI Benchmark Tracker")
    print(f"Scraping {len(BENCHMARKS)} leaderboards...")

    all_benchmarks: list[dict[str, Any]] = []
    total_models = 0

    for bench in BENCHMARKS:
        name = bench["name"]
        print(f"  {name}...", end=" ", flush=True)
        result = scrape_benchmark(bench)
        if result:
            all_benchmarks.append(result)
            total_models += result["model_count"]
            print(f"{result['model_count']} models")
        else:
            print("FAILED")

    output = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "benchmark_count": len(all_benchmarks),
        "total_models": total_models,
        "benchmarks": all_benchmarks,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(all_benchmarks)} benchmarks, {total_models} models to {output_path}")


if __name__ == "__main__":
    main()
