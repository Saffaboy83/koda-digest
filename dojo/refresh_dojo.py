#!/usr/bin/env python3
"""
Weekly refresh pipeline for the Claude Code Dojo.

Discovers new Claude Code features, patterns, and tips via web search,
evaluates relevance against existing content, generates new prompts,
and updates data.json.

Usage:
    python dojo/refresh_dojo.py [--dry-run] [--review]

Options:
    --dry-run    Print what would change without writing
    --review     Output diff for manual approval before committing
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from difflib import SequenceMatcher, unified_diff
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAX_NEW_PROMPTS: int = 5
MIN_RELEVANCE_SCORE: float = 0.4
FUZZY_MATCH_THRESHOLD: float = 0.65

DOJO_DIR: Path = Path(__file__).resolve().parent
BUILD_INDEX_SCRIPT: Path = DOJO_DIR.parent / "build-index.py"

# ── Per-dojo configuration ──

DOJO_CONFIGS: dict[str, dict] = {
    "claude-code": {
        "label": "Claude Code Dojo",
        "data_path": DOJO_DIR / "claude-code" / "data.json",
        "search_queries": [
            "Claude Code new features CLI",
            "Claude Code tips workflow 2026",
            "Claude Code best practices this week",
        ],
        "keyword_map": {
            "m1":  ["cli", "setup", "install", "terminal", "interface", "keyboard", "shortcut"],
            "m2":  ["claude.md", "claudemd", "workspace", "project brain", "rules file"],
            "m3":  ["permission", "plan mode", "auto-accept", "dangerously", "yolo"],
            "m4":  ["context", "token", "compact", "compaction", "window"],
            "m5":  ["skill", "automation", "slash command", "custom command"],
            "m6":  ["mcp", "server", "plugin", "tool server", "model context protocol"],
            "m7":  ["harness", "agent harness", "tool loop", "action space"],
            "m8":  ["sub-agent", "subagent", "multi-agent", "agent team", "orchestration"],
            "m9":  ["research", "loop", "auto research", "search loop", "retrieval"],
            "m10": ["browser", "chrome", "automation", "screenshot", "web scrape"],
            "m11": ["security", "secret", "injection", "prompt injection", "sandbox"],
            "m12": ["deploy", "deployment", "ci/cd", "docker", "production"],
            "m13": ["mistake", "anti-pattern", "antipattern", "pitfall", "common error"],
            "m14": ["power", "workflow", "advanced", "productivity", "parallel"],
            "m15": ["hook", "prehook", "posthook", "pretooluse", "posttooluse"],
        },
        "default_module": "m14",
    },
    "cowork": {
        "label": "Claude Cowork Dojo",
        "data_path": DOJO_DIR / "cowork" / "data.json",
        "search_queries": [
            "Claude Cowork new features desktop agent",
            "Claude Cowork skills plugins tips 2026",
            "Claude Cowork automation workflow this week",
        ],
        "keyword_map": {
            "m1":  ["cowork", "chat vs cowork", "desktop agent", "what is cowork"],
            "m2":  ["setup", "config", "global instructions", "folder structure", "install"],
            "m3":  ["delegation", "delegate", "end-state", "three-question", "prompt framework"],
            "m4":  ["file", "document", "excel", "powerpoint", "pdf", "invoice", "spreadsheet"],
            "m5":  ["skill", "skill.md", "custom skill", "skill creator", "skill stack"],
            "m6":  ["connector", "gmail", "calendar", "slack", "notion", "zapier", "mcp"],
            "m7":  ["plugin", "plugin marketplace", "build plugin", "package plugin"],
            "m8":  ["schedule", "scheduled task", "recurring", "cron", "automate"],
            "m9":  ["project", "memory", "context file", "claude.md", "persistent"],
            "m10": ["sub-agent", "parallel", "multi-step", "fan-out", "concurrent"],
            "m11": ["computer use", "screen control", "desktop", "browser", "click"],
            "m12": ["dispatch", "remote", "mobile", "qr code", "cross-device"],
            "m13": ["skill engineering", "frontmatter", "testing", "distribution", "mcp enhancement"],
            "m14": ["business os", "content repurpose", "research synthesis", "power workflow"],
            "m15": ["safety", "credit", "usage", "limit", "troubleshoot", "security", "vm"],
        },
        "default_module": "m14",
    },
}

# Legacy alias for backward compatibility
MODULE_KEYWORD_MAP = DOJO_CONFIGS["claude-code"]["keyword_map"]


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class Discovery:
    """A single discovery from web search."""

    def __init__(
        self,
        title: str,
        description: str,
        source_url: str,
        relevance_score: float,
    ) -> None:
        self.title = title
        self.description = description
        self.source_url = source_url
        self.relevance_score = relevance_score

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "source_url": self.source_url,
            "relevance_score": self.relevance_score,
        }


# ---------------------------------------------------------------------------
# Step 1: Discovery (placeholder tracks)
# ---------------------------------------------------------------------------

def discover_official_updates() -> list[Discovery]:
    """Search Anthropic docs/changelog for new Claude Code features.

    Returns an empty list by default. Replace the body with real
    Firecrawl or Perplexity API calls when environment keys are set.
    """
    print("  [Track 1] Searching Anthropic docs for official updates...")
    # Example shape of a real result:
    # return [Discovery(
    #     title="Claude Code 1.3: New /doctor command",
    #     description="The /doctor slash command runs diagnostics...",
    #     source_url="https://docs.anthropic.com/changelog/...",
    #     relevance_score=0.9,
    # )]
    return []


def discover_community_patterns() -> list[Discovery]:
    """Search blogs and tutorials for Claude Code tips and workflows.

    Returns an empty list by default. Replace the body with real
    search API calls when environment keys are set.
    """
    print("  [Track 2] Searching community blogs for patterns and tips...")
    return []


def discover_trending() -> list[Discovery]:
    """Search for recent Claude Code features trending this week.

    Returns an empty list by default. Replace the body with real
    search API calls when environment keys are set.
    """
    print("  [Track 3] Searching for trending Claude Code content...")
    return []


def run_discovery() -> list[Discovery]:
    """Execute all three discovery tracks and merge results."""
    results: list[Discovery] = []
    results.extend(discover_official_updates())
    results.extend(discover_community_patterns())
    results.extend(discover_trending())
    print(f"  -> {len(results)} total discoveries")
    return results


# ---------------------------------------------------------------------------
# Step 2: Load existing content
# ---------------------------------------------------------------------------

def load_data(path: Path) -> dict[str, Any]:
    """Read and parse data.json, returning the full structure."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_existing_index(data: dict[str, Any]) -> set[str]:
    """Build a set of lowercase labels and concept titles for dedup."""
    existing: set[str] = set()
    for module in data.get("modules", []):
        for concept in module.get("concepts", []):
            existing.add(concept["title"].lower().strip())
        for prompt in module.get("prompts", []):
            existing.add(prompt["label"].lower().strip())
    return existing


# ---------------------------------------------------------------------------
# Step 3: Dedup and filter
# ---------------------------------------------------------------------------

def is_duplicate(title: str, existing: set[str]) -> bool:
    """Check if a discovery title fuzzy-matches any existing label or concept."""
    normalized = title.lower().strip()
    for item in existing:
        ratio = SequenceMatcher(None, normalized, item).ratio()
        if ratio >= FUZZY_MATCH_THRESHOLD:
            return True
    return False


def filter_discoveries(
    discoveries: list[Discovery],
    existing: set[str],
) -> list[Discovery]:
    """Remove duplicates, apply relevance floor, and cap at MAX_NEW_PROMPTS."""
    filtered: list[Discovery] = []
    for d in discoveries:
        if d.relevance_score < MIN_RELEVANCE_SCORE:
            print(f"    Skipped (low relevance {d.relevance_score:.2f}): {d.title}")
            continue
        if is_duplicate(d.title, existing):
            print(f"    Skipped (duplicate): {d.title}")
            continue
        filtered.append(d)

    # Sort by relevance descending, keep top N
    filtered.sort(key=lambda d: d.relevance_score, reverse=True)
    kept = filtered[:MAX_NEW_PROMPTS]

    if len(filtered) > MAX_NEW_PROMPTS:
        print(f"    Capped from {len(filtered)} to {MAX_NEW_PROMPTS} items")

    return kept


# ---------------------------------------------------------------------------
# Step 4: Module mapping
# ---------------------------------------------------------------------------

def map_to_module(
    discovery: Discovery,
    keyword_map: dict[str, list[str]],
    default_module: str = "m14",
) -> str:
    """Map a discovery to the best-matching module ID based on keyword overlap."""
    text = f"{discovery.title} {discovery.description}".lower()
    best_module = default_module
    best_score = 0

    for module_id, keywords in keyword_map.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best_module = module_id
    return best_module


# ---------------------------------------------------------------------------
# Step 5: Generate prompt entry
# ---------------------------------------------------------------------------

def next_prompt_id(module: dict[str, Any]) -> str:
    """Compute the next sequential prompt ID for a module.

    Existing IDs follow the pattern 'N.M' where N is the module number.
    Some modules use legacy prefixes (e.g. 'B.4', '11.hooks.3') so we
    fall back to module_number.next_seq when parsing fails.
    """
    module_num = module["number"]
    max_seq = 0
    for p in module.get("prompts", []):
        parts = str(p["id"]).split(".")
        try:
            # Standard format: "N.M"
            if len(parts) == 2:
                seq = int(parts[1])
            # Extended format: "N.sub.M"
            elif len(parts) == 3:
                seq = int(parts[2])
            else:
                seq = 0
        except ValueError:
            seq = 0
        max_seq = max(max_seq, seq)
    return f"{module_num}.{max_seq + 1}"


def generate_prompt_entry(
    discovery: Discovery,
    module: dict[str, Any],
) -> dict[str, Any]:
    """Create a prompt entry dict matching the existing data.json format."""
    prompt_id = next_prompt_id(module)

    # Infer difficulty from module belt
    belt = module.get("belt", "white")
    difficulty_map = {
        "white": "Beginner",
        "yellow": "Intermediate",
        "green": "Intermediate",
        "blue": "Advanced",
        "brown": "Advanced",
        "black": "Advanced",
    }
    difficulty = difficulty_map.get(belt, "Intermediate")

    return {
        "id": prompt_id,
        "label": discovery.title,
        "difficulty": difficulty,
        "prompt": discovery.description,
        "expectedOutcome": f"Hands-on practice with {discovery.title.lower()}.",
        "source": discovery.source_url,
    }


# ---------------------------------------------------------------------------
# Step 6: Update data.json
# ---------------------------------------------------------------------------

def bump_patch_version(version: str) -> str:
    """Increment the patch segment of a semver string (e.g. 1.0.0 -> 1.0.1)."""
    parts = version.split(".")
    if len(parts) != 3:
        return version
    try:
        parts[2] = str(int(parts[2]) + 1)
    except ValueError:
        pass
    return ".".join(parts)


def apply_updates(
    data: dict[str, Any],
    new_entries: list[tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    """Return a new data dict with new prompts merged into their modules.

    Does NOT mutate the original dict.
    """
    updated = json.loads(json.dumps(data))  # deep copy

    module_lookup: dict[str, dict[str, Any]] = {
        m["id"]: m for m in updated["modules"]
    }

    added_count = 0
    for module_id, entry in new_entries:
        target = module_lookup.get(module_id)
        if target is None:
            print(f"    WARNING: module {module_id} not found, skipping")
            continue
        target["prompts"].append(entry)
        added_count += 1

    # Update metadata
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    updated["metadata"]["lastUpdated"] = today
    updated["metadata"]["version"] = bump_patch_version(
        updated["metadata"]["version"]
    )
    updated["metadata"]["totalPrompts"] = sum(
        len(m.get("prompts", [])) for m in updated["modules"]
    )
    return updated


def write_data(path: Path, data: dict[str, Any]) -> None:
    """Write data.json with consistent formatting."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


# ---------------------------------------------------------------------------
# Step 7: Rebuild search index
# ---------------------------------------------------------------------------

def rebuild_search_index() -> None:
    """Run the site-level build-index.py to refresh the search index."""
    if not BUILD_INDEX_SCRIPT.exists():
        print(f"  WARNING: {BUILD_INDEX_SCRIPT} not found, skipping index rebuild")
        return

    print(f"  Running {BUILD_INDEX_SCRIPT.name}...")
    result = subprocess.run(
        [sys.executable, str(BUILD_INDEX_SCRIPT)],
        cwd=str(BUILD_INDEX_SCRIPT.parent),
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("  Search index rebuilt successfully")
    else:
        print(f"  WARNING: build-index.py exited with code {result.returncode}")
        if result.stderr:
            print(f"  stderr: {result.stderr[:300]}")


# ---------------------------------------------------------------------------
# Diff / review helpers
# ---------------------------------------------------------------------------

def compute_diff(original: dict[str, Any], updated: dict[str, Any]) -> str:
    """Produce a unified diff between original and updated JSON."""
    original_lines = json.dumps(original, indent=2).splitlines(keepends=True)
    updated_lines = json.dumps(updated, indent=2).splitlines(keepends=True)
    diff = unified_diff(
        original_lines,
        updated_lines,
        fromfile="data.json (before)",
        tofile="data.json (after)",
        lineterm="",
    )
    return "\n".join(diff)


def print_summary(new_entries: list[tuple[str, dict[str, Any]]]) -> None:
    """Print a human-readable summary of proposed changes."""
    if not new_entries:
        print("\n  No new prompts to add.")
        return

    print(f"\n  Proposed additions ({len(new_entries)} prompts):")
    for module_id, entry in new_entries:
        print(f"    [{module_id}] {entry['id']} - {entry['label']}")
        print(f"           Difficulty: {entry['difficulty']}")
        if entry.get("source"):
            print(f"           Source: {entry['source']}")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def refresh_single_dojo(
    dojo_key: str,
    config: dict,
    dry_run: bool = False,
    review: bool = False,
) -> bool:
    """Run the refresh pipeline for a single dojo. Returns True if changes were made."""
    data_path: Path = config["data_path"]
    keyword_map: dict[str, list[str]] = config["keyword_map"]
    default_module: str = config.get("default_module", "m14")

    print(f"\n{'-' * 50}")
    print(f"  {config['label']}")
    print(f"{'-' * 50}")

    # Step 1: Discovery
    print("\n  Step 1: Discovery")
    discoveries = run_discovery()

    if not discoveries:
        print("  No discoveries found. Skipping this dojo.")
        return False

    # Step 2: Load existing content
    print("\n  Step 2: Loading existing content")
    if not data_path.exists():
        print(f"  ERROR: {data_path} not found, skipping")
        return False

    data = load_data(data_path)
    existing = build_existing_index(data)
    print(f"  Loaded {len(existing)} existing labels/concepts")

    # Step 3: Dedup and filter
    print("\n  Step 3: Dedup and filter")
    filtered = filter_discoveries(discoveries, existing)
    print(f"  -> {len(filtered)} new items after filtering")

    if not filtered:
        print("  All discoveries already covered. Nothing to add.")
        return False

    # Step 4: Module mapping
    print("\n  Step 4: Module mapping")
    module_lookup: dict[str, dict[str, Any]] = {
        m["id"]: m for m in data["modules"]
    }
    mapped: list[tuple[str, Discovery]] = []
    for d in filtered:
        target = map_to_module(d, keyword_map, default_module)
        print(f"    {d.title} -> {target} ({module_lookup[target]['title']})")
        mapped.append((target, d))

    # Step 5: Generate prompt entries
    print("\n  Step 5: Generate prompt entries")
    new_entries: list[tuple[str, dict[str, Any]]] = []
    for module_id, discovery in mapped:
        entry = generate_prompt_entry(discovery, module_lookup[module_id])
        new_entries.append((module_id, entry))
        print(f"    Created {entry['id']}: {entry['label']}")

    print_summary(new_entries)

    # Step 6: Update data.json
    print("\n  Step 6: Update data.json")
    updated = apply_updates(data, new_entries)

    if review or dry_run:
        diff_text = compute_diff(data, updated)
        if diff_text:
            print("\n  --- Diff ---")
            print(diff_text)
            print("  --- End Diff ---")

    if dry_run:
        print("\n  [DRY RUN] No files written.")
        return False

    if review:
        answer = input(f"\n  Apply changes to {dojo_key}? [y/N] ").strip().lower()
        if answer != "y":
            print("  Skipped by user.")
            return False

    write_data(data_path, updated)
    print(f"  Written to {data_path}")
    print(f"  Version: {updated['metadata']['version']}")
    print(f"  Total prompts: {updated['metadata']['totalPrompts']}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Weekly content refresh for all Koda Dojos"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would change without writing",
    )
    parser.add_argument(
        "--review",
        action="store_true",
        help="Output diff for manual approval before committing",
    )
    parser.add_argument(
        "--dojo",
        choices=list(DOJO_CONFIGS.keys()),
        help="Refresh only a specific dojo (default: all)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  Koda Dojo -- Weekly Refresh Pipeline")
    print("=" * 60)

    # Select which dojos to refresh
    if args.dojo:
        targets = {args.dojo: DOJO_CONFIGS[args.dojo]}
    else:
        targets = DOJO_CONFIGS

    any_changes = False
    for dojo_key, config in targets.items():
        changed = refresh_single_dojo(
            dojo_key, config, dry_run=args.dry_run, review=args.review
        )
        any_changes = any_changes or changed

    # Rebuild search index once after all dojos are updated
    if any_changes:
        print("\nStep 7: Rebuild search index")
        rebuild_search_index()

    print("\n" + "=" * 60)
    dojos_str = ", ".join(targets.keys())
    print(f"  Refresh complete. Dojos processed: {dojos_str}")
    print("=" * 60)


if __name__ == "__main__":
    main()
