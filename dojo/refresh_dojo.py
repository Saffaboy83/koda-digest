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
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher, unified_diff
from pathlib import Path
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAX_NEW_PROMPTS: int = 5
MIN_RELEVANCE_SCORE: float = 0.4
FUZZY_MATCH_THRESHOLD: float = 0.65
STALE_PROMPT_DAYS: int = 60  # re-synthesise pipeline prompts older than this

DOJO_DIR: Path = Path(__file__).resolve().parent
BUILD_INDEX_SCRIPT: Path = DOJO_DIR.parent / "build-index.py"

# ── API config ──

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"
PERPLEXITY_MODEL = "sonar"
FIRECRAWL_API_URL = "https://api.firecrawl.dev/v1"
MAX_SOURCE_TEXT = 2000  # chars to keep per scraped page


def _load_env() -> None:
    """Load .env from the Digest root directory."""
    env_path = DOJO_DIR.parent / ".env"
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())


_load_env()

PERPLEXITY_API_KEY: str = os.environ.get("PERPLEXITY_API_KEY", "")
FIRECRAWL_API_KEY: str = os.environ.get("FIRECRAWL_API_KEY", "")
OPENROUTER_API_KEY: str = os.environ.get("OPENROUTER_API_KEY", "")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
SYNTHESIS_MODEL = "anthropic/claude-sonnet-4-6"
MAX_SCRAPE_CHARS = 3000  # body chars fed to synthesis LLM

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
# Step 1: Discovery
# ---------------------------------------------------------------------------

def _firecrawl_search(query: str, limit: int = 5) -> list[dict]:
    """Search via Firecrawl. Returns list of {url, title, description}."""
    if not FIRECRAWL_API_KEY:
        return []
    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"query": query, "limit": limit}
    for attempt in range(3):
        try:
            resp = httpx.post(
                f"{FIRECRAWL_API_URL}/search",
                json=payload,
                headers=headers,
                timeout=25,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [])
        except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
            print(f"    Firecrawl error (attempt {attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)
    return []


def _perplexity_search(query: str) -> dict | None:
    """Search via Perplexity Sonar. Returns {content, citations}."""
    if not PERPLEXITY_API_KEY:
        return None
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": PERPLEXITY_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a research assistant. Return a JSON array of discoveries. "
                    "Each item must have: title (string), description (1-2 sentence summary), "
                    "source_url (string), relevance_score (0.0-1.0). "
                    "Only include items published in the last 30 days. "
                    "Return ONLY the JSON array, no markdown fences."
                ),
            },
            {"role": "user", "content": query},
        ],
        "max_tokens": 2000,
        "temperature": 0.1,
        "return_citations": True,
    }
    for attempt in range(3):
        try:
            resp = httpx.post(PERPLEXITY_URL, json=payload, headers=headers, timeout=35)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            citations = data.get("citations", [])
            if content.strip():
                return {"content": content, "citations": citations}
        except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
            print(f"    Perplexity error (attempt {attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)
        except Exception as e:
            print(f"    Perplexity unexpected error: {e}")
            return None
    return None


def _parse_perplexity_json(result: dict | None) -> list[dict]:
    """Extract a list of discovery dicts from a Perplexity response."""
    if not result:
        return []
    content = result.get("content", "")
    # Strip markdown fences if present
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1]
        content = content.rsplit("```", 1)[0]
    try:
        items = json.loads(content)
        if isinstance(items, list):
            return items
    except json.JSONDecodeError:
        pass
    return []


def _score_firecrawl_result(item: dict, dojo_key: str) -> float:
    """Assign a relevance score to a Firecrawl result based on title/description keywords."""
    text = f"{item.get('title', '')} {item.get('description', '')}".lower()
    keywords = {
        "claude-code": ["claude code", "claude.md", "mcp", "slash command", "hook", "sub-agent",
                        "plan mode", "claude cli", "agentic"],
        "cowork": ["cowork", "claude cowork", "skill.md", "desktop agent", "scheduled task",
                   "computer use", "plugin", "connector"],
    }
    hits = sum(1 for kw in keywords.get(dojo_key, []) if kw in text)
    if hits == 0:
        return 0.0
    return min(0.5 + hits * 0.15, 1.0)


# Discovery context is set per-dojo run via this module-level var
_current_dojo_key: str = "claude-code"


def discover_official_updates(queries: list[str]) -> list[Discovery]:
    """Scrape Anthropic docs and changelog via Firecrawl for official updates."""
    print("  [Track 1] Searching Anthropic docs for official updates...")
    results: list[Discovery] = []
    official_query = f"{queries[0]} site:docs.anthropic.com OR site:anthropic.com"
    items = _firecrawl_search(official_query, limit=5)
    for item in items:
        score = _score_firecrawl_result(item, _current_dojo_key)
        if score < MIN_RELEVANCE_SCORE:
            continue
        results.append(Discovery(
            title=item.get("title", "Untitled").strip(),
            description=item.get("description", "")[:300].strip(),
            source_url=item.get("url", ""),
            relevance_score=score,
        ))
    return results


def discover_community_patterns(queries: list[str]) -> list[Discovery]:
    """Search community blogs and tutorials via Firecrawl."""
    print("  [Track 2] Searching community blogs for patterns and tips...")
    results: list[Discovery] = []
    items = _firecrawl_search(queries[1], limit=6)
    for item in items:
        score = _score_firecrawl_result(item, _current_dojo_key)
        if score < MIN_RELEVANCE_SCORE:
            continue
        results.append(Discovery(
            title=item.get("title", "Untitled").strip(),
            description=item.get("description", "")[:300].strip(),
            source_url=item.get("url", ""),
            relevance_score=score,
        ))
    return results


def discover_trending(queries: list[str]) -> list[Discovery]:
    """Search for recently trending content via Perplexity Sonar."""
    print("  [Track 3] Searching for trending Claude Code content...")
    prompt = (
        f"Find the most useful or notable '{queries[2]}' tips, features, or tutorials "
        f"published in the last 30 days. Focus on practical, hands-on content."
    )
    result = _perplexity_search(prompt)
    items = _parse_perplexity_json(result)
    results: list[Discovery] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        score = float(item.get("relevance_score", 0.5))
        if score < MIN_RELEVANCE_SCORE:
            continue
        results.append(Discovery(
            title=str(item.get("title", "Untitled")).strip(),
            description=str(item.get("description", ""))[:300].strip(),
            source_url=str(item.get("source_url", "")),
            relevance_score=score,
        ))
    return results


def run_discovery(queries: list[str]) -> list[Discovery]:
    """Execute all three discovery tracks and merge results."""
    results: list[Discovery] = []
    results.extend(discover_official_updates(queries))
    results.extend(discover_community_patterns(queries))
    results.extend(discover_trending(queries))
    print(f"  -> {len(results)} total discoveries")
    return results


# ---------------------------------------------------------------------------
# Step 1.5: Scrape + synthesise into real exercises
# ---------------------------------------------------------------------------

def _firecrawl_scrape(url: str) -> str:
    """Scrape a URL with Firecrawl and return clean markdown. Returns '' on failure."""
    if not FIRECRAWL_API_KEY or not url:
        return ""
    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"url": url, "formats": ["markdown"], "onlyMainContent": True, "timeout": 15000}
    try:
        resp = httpx.post(
            f"{FIRECRAWL_API_URL}/scrape",
            json=payload,
            headers=headers,
            timeout=25,
        )
        resp.raise_for_status()
        markdown = resp.json().get("data", {}).get("markdown", "")
        return markdown[:MAX_SCRAPE_CHARS]
    except Exception as e:
        print(f"      Scrape failed ({url[:60]}...): {e}")
        return ""


_SYNTHESIS_SYSTEM = """\
You are a curriculum designer for the Koda Dojo, an interactive Claude Code learning platform.
Your job is to turn a web article or video summary into a single, self-contained hands-on exercise.

Rules:
- The exercise must be something the learner runs INSIDE Claude Code (not just reads about).
- Write in second-person imperative ("Ask Claude to...", "Create a...", "Configure...").
- The prompt field should have 3-6 numbered steps or bullet points.
- expectedOutcome: one sentence describing what the learner will have produced.
- label: a short (6-word max) action-oriented title, NOT the article title.
- Respond with ONLY a JSON object — no markdown fences, no explanation.
  {"label": "...", "prompt": "...", "expectedOutcome": "..."}
"""


def _synthesise_exercise(discovery: Discovery, module: dict[str, Any]) -> dict[str, Any] | None:
    """Scrape source + call Sonnet to generate a real hands-on exercise.

    Returns a partial entry dict with label/prompt/expectedOutcome, or None if
    synthesis fails or produces low-quality output.
    """
    if not OPENROUTER_API_KEY:
        return None

    body = _firecrawl_scrape(discovery.source_url)

    user_msg = (
        f"Module: {module['title']} (belt: {module.get('belt', 'white')})\n"
        f"Article title: {discovery.title}\n"
        f"Article summary: {discovery.description}\n"
    )
    if body:
        user_msg += f"\nArticle body (first {MAX_SCRAPE_CHARS} chars):\n{body}"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://koda.community",
        "X-Title": "Koda Dojo Refresh",
    }
    payload = {
        "model": SYNTHESIS_MODEL,
        "messages": [
            {"role": "system", "content": _SYNTHESIS_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        "max_tokens": 600,
        "temperature": 0.4,
    }

    for attempt in range(3):
        try:
            resp = httpx.post(OPENROUTER_URL, json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            # Strip fences if the model added them anyway
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            result = json.loads(raw)
            label = str(result.get("label", "")).strip()
            prompt = str(result.get("prompt", "")).strip()
            outcome = str(result.get("expectedOutcome", "")).strip()
            # Reject if any key field is suspiciously short
            if len(label) < 5 or len(prompt) < 40 or len(outcome) < 10:
                print(f"      Synthesis output too short, skipping: {label!r}")
                return None
            return {"label": label, "prompt": prompt, "expectedOutcome": outcome}
        except json.JSONDecodeError as e:
            print(f"      Synthesis JSON parse error (attempt {attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)
        except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
            print(f"      Synthesis API error (attempt {attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)
    return None


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

def _max_seq_in_module(module: dict[str, Any]) -> int:
    """Return the highest sequence number seen in a module's prompt IDs."""
    max_seq = 0
    for p in module.get("prompts", []):
        parts = str(p["id"]).split(".")
        try:
            if len(parts) == 2:
                seq = int(parts[1])
            elif len(parts) == 3:
                seq = int(parts[2])
            else:
                seq = 0
        except ValueError:
            seq = 0
        max_seq = max(max_seq, seq)
    return max_seq


def next_prompt_id(module: dict[str, Any], staged: dict[str, int]) -> str:
    """Compute the next sequential prompt ID, accounting for already-staged entries.

    `staged` maps module_id -> highest seq assigned this run, so multiple
    entries targeting the same module get distinct IDs within a single run.
    """
    module_id = module["id"]
    module_num = module["number"]
    persisted_max = _max_seq_in_module(module)
    run_max = staged.get(module_id, 0)
    next_seq = max(persisted_max, run_max) + 1
    staged[module_id] = next_seq
    return f"{module_num}.{next_seq}"


def generate_prompt_entry(
    discovery: Discovery,
    module: dict[str, Any],
    staged: dict[str, int],
) -> dict[str, Any] | None:
    """Scrape + synthesise a real hands-on exercise, then wrap it as a prompt entry.

    Returns None if synthesis fails (entry is skipped).
    """
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

    print(f"      Synthesising exercise for: {discovery.title[:60]}")
    synthesised = _synthesise_exercise(discovery, module)

    if synthesised is None:
        print(f"      Synthesis failed — skipping.")
        return None

    prompt_id = next_prompt_id(module, staged)
    return {
        "id": prompt_id,
        "label": synthesised["label"],
        "difficulty": difficulty,
        "prompt": synthesised["prompt"],
        "expectedOutcome": synthesised["expectedOutcome"],
        "source": discovery.source_url,
        "addedDate": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }


# ---------------------------------------------------------------------------
# Step 5.5: Stale prompt detection and replacement
# ---------------------------------------------------------------------------

def find_stale_prompts(
    data: dict[str, Any],
    stale_days: int,
) -> list[tuple[str, dict[str, Any]]]:
    """Return (module_id, prompt_entry) for pipeline prompts older than stale_days.

    Only prompts with both a `source` and an `addedDate` field are candidates.
    Hand-crafted prompts (no `source`) are never touched.
    """
    cutoff = datetime.now(timezone.utc).date()
    stale: list[tuple[str, dict[str, Any]]] = []
    for module in data.get("modules", []):
        for prompt in module.get("prompts", []):
            if not prompt.get("source") or not prompt.get("addedDate"):
                continue
            try:
                added = datetime.strptime(prompt["addedDate"], "%Y-%m-%d").date()
            except ValueError:
                continue
            if (cutoff - added).days >= stale_days:
                stale.append((module["id"], prompt))
    return stale


def replace_stale_prompts(
    data: dict[str, Any],
    stale: list[tuple[str, dict[str, Any]]],
    module_lookup: dict[str, dict[str, Any]],
    dry_run: bool = False,
) -> tuple[dict[str, Any], int]:
    """Re-synthesise stale prompts and patch them in-place. Returns (updated_data, count)."""
    updated = json.loads(json.dumps(data))  # deep copy
    # Rebuild lookup on the copy so mutations below are reflected
    updated_module_lookup: dict[str, dict[str, Any]] = {
        m["id"]: m for m in updated["modules"]
    }

    replaced = 0
    for module_id, original_entry in stale:
        module = updated_module_lookup.get(module_id)
        if module is None:
            continue

        print(f"    Stale [{original_entry['id']}] {original_entry['label'][:60]} (added {original_entry['addedDate']})")

        if dry_run:
            print(f"      [DRY RUN] Would re-synthesise from: {original_entry['source'][:60]}")
            continue

        discovery = Discovery(
            title=original_entry["label"],
            description=original_entry.get("prompt", "")[:200],
            source_url=original_entry["source"],
            relevance_score=0.8,
        )
        print(f"      Re-synthesising from: {discovery.source_url[:60]}")
        synthesised = _synthesise_exercise(discovery, module)

        if synthesised is None:
            print(f"      Synthesis failed — keeping original.")
            continue

        # Patch the entry in-place inside the copy
        for prompt in module["prompts"]:
            if prompt["id"] == original_entry["id"]:
                prompt["label"] = synthesised["label"]
                prompt["prompt"] = synthesised["prompt"]
                prompt["expectedOutcome"] = synthesised["expectedOutcome"]
                prompt["addedDate"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                break

        replaced += 1
        print(f"      Replaced with: {synthesised['label']}")

    return updated, replaced


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
# Step 7: Rebuild HTML landing page
# ---------------------------------------------------------------------------

def rebuild_html() -> None:
    """Patch dojo/index.html with live prompt counts and module totals from data.json.

    Updates:
    - Total prompts stat
    - Per-dojo "N hands-on prompts" in the dojo card descriptions
    """
    import re

    html_path = DOJO_DIR / "index.html"
    if not html_path.exists():
        print(f"  WARNING: {html_path} not found, skipping HTML update")
        return

    # Gather live counts from every dojo's data.json
    total_prompts = 0
    total_modules = 0
    dojo_counts: dict[str, int] = {}  # label -> prompt count

    for dojo_key, config in DOJO_CONFIGS.items():
        data_path: Path = config["data_path"]
        if not data_path.exists():
            continue
        with open(data_path, encoding="utf-8") as f:
            data = json.load(f)
        count = data["metadata"].get("totalPrompts", 0)
        mods = data["metadata"].get("totalModules", 0)
        label = data["metadata"].get("name", dojo_key)
        dojo_counts[label] = count
        total_prompts += count
        total_modules += mods

    html = html_path.read_text(encoding="utf-8")

    # 1. Update total prompts KPI stat
    html = re.sub(
        r'(<div class="stat-value">)\d+(</div><div class="stat-label">Prompts</div>)',
        lambda m: f"{m.group(1)}{total_prompts}{m.group(2)}",
        html,
    )

    # 2. Update total modules KPI stat
    html = re.sub(
        r'(<div class="stat-value">)\d+(</div><div class="stat-label">Modules</div>)',
        lambda m: f"{m.group(1)}{total_modules}{m.group(2)}",
        html,
    )

    # 3. Update per-dojo "N hands-on prompts" in card descriptions
    # Dojos appear in DOJO_CONFIGS order in the HTML; replace sequentially.
    ordered_counts = [
        config["data_path"]
        for config in DOJO_CONFIGS.values()
        if config["data_path"].exists()
    ]
    counts_in_order: list[int] = []
    for data_path in ordered_counts:
        with open(data_path, encoding="utf-8") as f:
            d = json.load(f)
        counts_in_order.append(d["metadata"].get("totalPrompts", 0))

    occurrences = re.findall(r'\d+ hands-on prompts', html)
    for i, count in enumerate(counts_in_order):
        if i >= len(occurrences):
            break
        html = html.replace(occurrences[i], f"{count} hands-on prompts", 1)

    html_path.write_text(html, encoding="utf-8")
    print(f"  dojo/index.html updated — {total_prompts} total prompts across {total_modules} modules")


# ---------------------------------------------------------------------------
# Step 8: Rebuild search index
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
    global _current_dojo_key
    _current_dojo_key = dojo_key

    data_path: Path = config["data_path"]
    keyword_map: dict[str, list[str]] = config["keyword_map"]
    default_module: str = config.get("default_module", "m14")
    queries: list[str] = config.get("search_queries", [dojo_key])

    print(f"\n{'-' * 50}")
    print(f"  {config['label']}")
    print(f"{'-' * 50}")

    # Step 1: Discovery
    print("\n  Step 1: Discovery")
    discoveries = run_discovery(queries)

    if not discoveries:
        print("  No discoveries found. Skipping this dojo.")
        return False

    # Step 2: Load existing content
    print("\n  Step 2: Loading existing content")
    if not data_path.exists():
        print(f"  ERROR: {data_path} not found, skipping")
        return False

    data = load_data(data_path)
    module_lookup: dict[str, dict[str, Any]] = {
        m["id"]: m for m in data["modules"]
    }

    # Step 2.5: Replace stale prompts
    stale = find_stale_prompts(data, STALE_PROMPT_DAYS)
    stale_replaced = 0
    if stale:
        print(f"\n  Step 2.5: Replacing {len(stale)} stale prompt(s)")
        data, stale_replaced = replace_stale_prompts(
            data, stale, module_lookup, dry_run=dry_run
        )
        # Rebuild module_lookup on updated data
        module_lookup = {m["id"]: m for m in data["modules"]}
        if stale_replaced:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            data["metadata"]["lastUpdated"] = today
            data["metadata"]["version"] = bump_patch_version(data["metadata"]["version"])
    else:
        print("\n  Step 2.5: No stale prompts found")

    existing = build_existing_index(data)
    print(f"  Loaded {len(existing)} existing labels/concepts")

    # Step 3: Dedup and filter
    print("\n  Step 3: Dedup and filter")
    filtered = filter_discoveries(discoveries, existing)
    print(f"  -> {len(filtered)} new items after filtering")

    if not filtered:
        print("  All discoveries already covered. Nothing to add.")
        if stale_replaced:
            # Stale replacements already written to `data`; persist and exit
            if not dry_run:
                write_data(data_path, data)
                print(f"  Written to {data_path} ({stale_replaced} stale prompts replaced)")
            return stale_replaced > 0
        return False

    # Step 4: Module mapping
    print("\n  Step 4: Module mapping")
    mapped: list[tuple[str, Discovery]] = []
    for d in filtered:
        target = map_to_module(d, keyword_map, default_module)
        print(f"    {d.title} -> {target} ({module_lookup[target]['title']})")
        mapped.append((target, d))

    # Step 5: Synthesise prompt entries via Sonnet
    print("\n  Step 5: Synthesise prompt entries")
    new_entries: list[tuple[str, dict[str, Any]]] = []
    staged: dict[str, int] = {}  # tracks assigned seq numbers per module this run
    for module_id, discovery in mapped:
        entry = generate_prompt_entry(discovery, module_lookup[module_id], staged)
        if entry is None:
            continue
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
    if stale_replaced:
        print(f"  Stale prompts replaced: {stale_replaced}")
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

    # Rebuild HTML + search index once after all dojos are updated
    if any_changes:
        print("\nStep 7: Rebuild HTML landing page")
        rebuild_html()
        print("\nStep 8: Rebuild search index")
        rebuild_search_index()

    print("\n" + "=" * 60)
    dojos_str = ", ".join(targets.keys())
    print(f"  Refresh complete. Dojos processed: {dojos_str}")
    print("=" * 60)


if __name__ == "__main__":
    main()
