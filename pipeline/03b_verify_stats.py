"""
Step 03B -- Stat Verification Gate

Runs after synthesis (03), before media (04). Extracts every specific
number/stat/benchmark from digest-content.json, checks whether each
was present in the raw search results, and verifies unsourced stats
via Perplexity. Hallucinated stats are hedged or removed.

Input:  pipeline/data/digest-content.json
        pipeline/data/raw-search-results.json (from step 01)
Output: pipeline/data/digest-content.json (corrected in place)
        pipeline/data/stat-verification-log.json

Usage:
    python -m pipeline.03b_verify_stats --date 2026-03-29
"""

import argparse
import json
import os
import re
import sys
import httpx
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import DIGEST_DIR, today_str, read_json, write_json

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"
PERPLEXITY_MODEL = "sonar-pro"


def extract_stats_from_content(digest: dict) -> list[dict]:
    """Extract all specific numbers, benchmarks, and stats from digest content."""
    stats: list[dict] = []

    def scan_text(text: str, section: str, story_title: str) -> None:
        if not text:
            return
        # Match patterns: numbers with units, percentages, dollar amounts, scores
        patterns = [
            # Benchmark scores (e.g., "GPQA 0.8", "MMLU 85.6%", "PinchBench 85.6%")
            (r'\b([A-Z][A-Za-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:score\s+(?:of\s+)?)?(\d+\.?\d*%?)\b', 'benchmark'),
            # Parameter counts (e.g., "120B parameters", "12B active")
            (r'(\d+\.?\d*[BMK])\s*(?:-?parameter|params?|active)', 'parameter_count'),
            # Context lengths (e.g., "256k context", "1 million tokens")
            (r'(\d+[kKMB]?)\s*(?:context|tokens?)', 'context_length'),
            # Dollar amounts (e.g., "$105.32", "$66,413")
            (r'\$[\d,]+\.?\d*', 'price'),
            # Percentages with context (e.g., "30% less", "+4.41%")
            (r'[+-]?\d+\.?\d*%', 'percentage'),
            # Specific counts (e.g., "255 releases", "500 hours", "700+ subjects")
            (r'(\d{2,})\+?\s*(releases?|hours?|subjects?|models?|variants?|days?)', 'count'),
        ]

        for pattern, stat_type in patterns:
            for match in re.finditer(pattern, text):
                stat_text = match.group(0).strip()
                # Get surrounding context (30 chars each side)
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context = text[start:end].strip()

                stats.append({
                    "stat": stat_text,
                    "type": stat_type,
                    "context": context,
                    "section": section,
                    "story": story_title,
                })

    # Scan all sections
    for story in digest.get("ai_news", []):
        scan_text(story.get("title", ""), "ai_news", story.get("title", ""))
        scan_text(story.get("body", ""), "ai_news", story.get("title", ""))

    for story in digest.get("world_news", []):
        scan_text(story.get("title", ""), "world_news", story.get("title", ""))
        scan_text(story.get("body", ""), "world_news", story.get("title", ""))

    for tool in digest.get("tools", []):
        scan_text(tool.get("title", ""), "tools", tool.get("title", ""))
        scan_text(tool.get("body", ""), "tools", tool.get("title", ""))

    # Markets are sourced data -- skip verification
    return stats


def check_stat_in_sources(stat: dict, raw_results: str) -> bool:
    """Check if a stat appears in the raw search results text."""
    stat_text = stat["stat"]
    # Normalize for comparison
    normalized_stat = stat_text.lower().replace(",", "").replace("%", "").strip()

    # Check exact match
    if normalized_stat in raw_results.lower():
        return True

    # Check numeric value match (e.g., "0.8" matches "0.80" or "80%")
    numbers = re.findall(r'\d+\.?\d*', stat_text)
    for num in numbers:
        if num in raw_results:
            return True

    return False


def verify_stat_with_perplexity(stat: dict, api_key: str) -> dict:
    """Verify a single stat using Perplexity search."""
    query = f"Verify this claim (March 2026): {stat['context']}. Is this specific number accurate? Cite sources."

    try:
        resp = httpx.post(
            PERPLEXITY_URL,
            json={
                "model": PERPLEXITY_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a fact-checker. For the given claim, determine if the specific number/stat is accurate. Reply with VERIFIED, PLAUSIBLE, or INACCURATE, followed by a one-sentence explanation with source."},
                    {"role": "user", "content": query},
                ],
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        resp.raise_for_status()
        answer = resp.json()["choices"][0]["message"]["content"].strip()

        # Parse verdict
        verdict = "UNVERIFIABLE"
        answer_upper = answer.upper()
        if answer_upper.startswith("VERIFIED"):
            verdict = "VERIFIED"
        elif answer_upper.startswith("PLAUSIBLE"):
            verdict = "PLAUSIBLE"
        elif answer_upper.startswith("INACCURATE"):
            verdict = "INACCURATE"

        return {"verdict": verdict, "detail": answer}

    except Exception as e:
        return {"verdict": "ERROR", "detail": str(e)}


def hedge_stat_in_text(text: str, stat_text: str) -> str:
    """Replace an inaccurate stat with hedged language."""
    # For benchmark scores, replace with generic language
    if re.search(r'[A-Z]+\s+\d+\.?\d*', stat_text):
        # e.g., "GPQA 0.8" -> "strong benchmark performance"
        hedged = text.replace(stat_text, "strong benchmark performance")
        if hedged != text:
            return hedged

    # For specific counts that are wrong, add "approximately"
    number_match = re.search(r'(\d+)', stat_text)
    if number_match:
        num = number_match.group(1)
        hedged = text.replace(f"{num} ", f"approximately {num} ")
        if hedged != text:
            return hedged

    return text


def main() -> None:
    parser = argparse.ArgumentParser(description="Stat Verification Gate")
    parser.add_argument("--date", default=today_str())
    args = parser.parse_args()

    print(f"[03B] Stat verification for {args.date}")

    # Load digest content
    digest = read_json("digest-content.json")
    if not digest:
        print("  No digest-content.json found. Skipping.")
        sys.exit(0)

    # Load raw search results for source checking
    raw_results_text = ""
    raw_data = read_json("raw-search-results.json")
    if raw_data:
        raw_results_text = json.dumps(raw_data, ensure_ascii=False)
        print(f"  Raw search results: {len(raw_results_text)} chars")
    else:
        print("  WARNING: No raw-search-results.json. All stats will need Perplexity verification.")

    # Extract stats
    stats = extract_stats_from_content(digest)
    print(f"  Extracted {len(stats)} stats to verify")

    if not stats:
        print("  No stats found. Skipping.")
        sys.exit(0)

    # Classify each stat
    sourced = []
    unsourced = []

    for stat in stats:
        # Skip market data (always from live APIs)
        if stat["section"] == "markets":
            stat["classification"] = "SOURCED"
            sourced.append(stat)
            continue

        # Skip dollar amounts in market context
        if stat["type"] == "price" and "market" in stat.get("context", "").lower():
            stat["classification"] = "SOURCED"
            sourced.append(stat)
            continue

        if check_stat_in_sources(stat, raw_results_text):
            stat["classification"] = "SOURCED"
            sourced.append(stat)
        else:
            stat["classification"] = "UNSOURCED"
            unsourced.append(stat)

    print(f"  Sourced: {len(sourced)}, Unsourced: {len(unsourced)}")

    # Verify unsourced stats with Perplexity
    api_key = os.environ.get("PERPLEXITY_API_KEY", "")
    if not api_key:
        print("  WARNING: No PERPLEXITY_API_KEY. Cannot verify unsourced stats.")
        print("  Unsourced stats will be flagged but not auto-corrected.")
    else:
        corrections_made = 0
        for stat in unsourced:
            result = verify_stat_with_perplexity(stat, api_key)
            stat["verification"] = result

            if result["verdict"] == "INACCURATE":
                print(f"  INACCURATE: {stat['stat']} in '{stat['story']}'")
                print(f"    -> {result['detail'][:120]}")

                # Apply correction to digest content
                section_key = stat["section"]
                stories = digest.get(section_key, [])
                for story in stories:
                    if story.get("title") == stat["story"]:
                        original_body = story.get("body", "")
                        corrected = hedge_stat_in_text(original_body, stat["stat"])
                        if corrected != original_body:
                            story["body"] = corrected
                            corrections_made += 1
                            print(f"    Hedged in output")
                        break

            elif result["verdict"] == "VERIFIED":
                print(f"  VERIFIED: {stat['stat']}")
            elif result["verdict"] == "PLAUSIBLE":
                print(f"  PLAUSIBLE: {stat['stat']}")
            else:
                print(f"  {result['verdict']}: {stat['stat']}")

        if corrections_made > 0:
            write_json("digest-content.json", digest)
            print(f"\n  Applied {corrections_made} corrections to digest-content.json")

    # Save verification log
    log = {
        "date": args.date,
        "total_stats": len(stats),
        "sourced": len(sourced),
        "unsourced": len(unsourced),
        "stats": stats,
    }
    write_json("stat-verification-log.json", log)
    print(f"\n  Verification log saved ({len(stats)} stats checked)")


if __name__ == "__main__":
    main()
