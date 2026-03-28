"""
Step 04: Generate media (podcast, infographic, video) via NotebookLM.

Reads digest-content.json, compiles a text summary for NotebookLM,
then calls notebooklm_media.py to generate and download media.

Input:  pipeline/data/digest-content.json
Output: podcast-{date}.mp3, infographic-{date}.jpg, video-{date}.mp4
        pipeline/data/media-status.json
"""

import argparse
import json
import subprocess
import sys
import os
import httpx
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import (DIGEST_DIR, OPENROUTER_API_KEY, today_str,
                              write_json, read_json)


def compile_text_for_notebooklm(digest):
    """Compile digest content into a text block for NotebookLM source."""
    date_label = digest.get("date_label", digest["date"])
    sections = []

    sections.append(f"Koda Daily Intelligence Brief — {date_label}\n")

    # Summary hook
    summary = digest.get("summary", {})
    if summary.get("hook"):
        sections.append(f"TODAY'S THEME: {summary['hook']}\n")

    # AI News
    ai_news = digest.get("ai_news", [])
    if ai_news:
        sections.append("AI DEVELOPMENTS:")
        for story in ai_news[:8]:
            sections.append(f"- {story['title']}: {story['body']}")
        sections.append("")

    # World News
    world_news = digest.get("world_news", [])
    if world_news:
        sections.append("WORLD NEWS:")
        for story in world_news[:6]:
            sections.append(f"- {story['title']}: {story['body']}")
        sections.append("")

    # Markets
    markets = digest.get("markets", {})
    if markets:
        sections.append("MARKET DATA:")
        for key, data in markets.items():
            if isinstance(data, dict) and "price" in data:
                sections.append(f"- {key.upper()}: {data['price']} ({data.get('change', 'N/A')})")
        sections.append("")

    # Tools
    tools = digest.get("tools", [])
    if tools:
        sections.append("AI TOOLS:")
        for tool in tools[:4]:
            sections.append(f"- {tool['title']}: {tool['body']}")
        sections.append("")

    text = "\n".join(sections)

    # Ensure within NotebookLM's sweet spot (600-1500 words)
    if len(text) > 8000:
        text = text[:8000] + "\n\n[Content trimmed for audio generation]"

    return text


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
SONNET_MODEL = "anthropic/claude-sonnet-4.6"


def build_differentiation_text(recent_themes, today_hook):
    """Build editorial direction text telling NotebookLM what NOT to repeat."""
    if not recent_themes:
        return None

    lines = ["EDITORIAL DIRECTION FOR TODAY'S EPISODE\n"]
    lines.append("In the last few days, this show covered these themes and angles:")

    for date in sorted(recent_themes.keys(), reverse=True):
        data = recent_themes[date]
        lines.append(f"\n{date}:")
        lines.append(f"  Theme: {data.get('hook', 'N/A')}")
        themes = data.get("top_themes", [])
        if themes:
            lines.append(f"  Key angles: {', '.join(themes)}")
        stories = data.get("top_stories", [])
        if stories:
            lines.append(f"  Lead stories: {', '.join(stories[:3])}")

    lines.append(f"\nToday's theme: {today_hook}")
    lines.append(
        "\nIMPORTANT PRODUCTION RULES:"
        "\n- Take a FRESH angle today. Do NOT repeat previous framing or conclusions."
        "\n- If a story continues from a previous day, focus on what CHANGED overnight."
        "\n- Prioritize today's unique developments over ongoing narratives."
        "\n- Use different examples, metaphors, and structure than previous episodes."
        "\n- Open with something surprising or new, not a recap."
    )

    return "\n".join(lines)


def generate_dynamic_focus(digest, recent_themes):
    """Generate a day-specific AUDIO_FOCUS via a fast Sonnet call."""
    if not OPENROUTER_API_KEY:
        return None

    today_hook = digest.get("summary", {}).get("hook", "")
    ai_titles = [s.get("title", "") for s in digest.get("ai_news", [])[:5]]
    world_titles = [s.get("title", "") for s in digest.get("world_news", [])[:3]]

    recent_summary = ""
    if recent_themes:
        for date in sorted(recent_themes.keys(), reverse=True)[:3]:
            data = recent_themes[date]
            recent_summary += f"\n{date}: {data.get('hook', '')} -- angles: {', '.join(data.get('top_themes', []))}"

    prompt = f"""You are the executive producer of a daily AI news video show.

Today's hook: {today_hook}
Today's top AI stories: {json.dumps(ai_titles)}
Today's top world stories: {json.dumps(world_titles)}

Recent episodes covered:{recent_summary if recent_summary else " (first episode, no history)"}

Write 2-3 sentences of AUDIO FOCUS instructions for today's episode host.
Tell them exactly what angle to take that is DIFFERENT from recent episodes.
Be specific about what to emphasize and what to skip or downplay.
Do NOT use em dashes. Keep it punchy and direct.

Reply with ONLY the instructions, no preamble."""

    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://koda.community",
            "X-Title": "Koda Digest Pipeline",
        }
        payload = {
            "model": SONNET_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 300,
            "temperature": 0.5,
        }
        resp = httpx.post(OPENROUTER_URL, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        focus = resp.json()["choices"][0]["message"]["content"].strip()
        return focus
    except Exception as e:
        print(f"  Warning: Dynamic focus generation failed: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Step 04: Generate media")
    parser.add_argument("--date", default=today_str(), help="Date (YYYY-MM-DD)")
    parser.add_argument("--skip-video", action="store_true", help="Skip video generation")
    args = parser.parse_args()

    print(f"[04] Generating media for {args.date}")

    # Load digest content
    digest = read_json("digest-content.json")
    if not digest:
        print("  ERROR: digest-content.json not found. Run 03_synthesize_content.py first.")
        sys.exit(1)

    # Compile text for NotebookLM
    text = compile_text_for_notebooklm(digest)
    print(f"  Compiled {len(text)} chars for NotebookLM")

    # Write text to temp file
    text_file = DIGEST_DIR / "pipeline" / "data" / "notebooklm-text.txt"
    with open(text_file, "w", encoding="utf-8") as f:
        f.write(text)

    # ── Cross-day differentiation ─────────────────────────────────────
    # Read from repo root (committed to git for cross-day persistence)
    ledger_path = DIGEST_DIR / "recent-themes.json"
    recent_themes = {}
    if ledger_path.exists():
        with open(ledger_path, "r", encoding="utf-8") as f:
            recent_themes = json.load(f)
    # Exclude today from recent themes (avoid self-reference)
    prior_themes = {d: v for d, v in recent_themes.items() if d != args.date}

    diff_file = None
    focus_str = None

    if prior_themes:
        print(f"  Theme ledger: {len(prior_themes)} prior days loaded")

        # Build differentiation source for NotebookLM
        today_hook = digest.get("summary", {}).get("hook", "")
        diff_text = build_differentiation_text(prior_themes, today_hook)
        if diff_text:
            diff_file = DIGEST_DIR / "pipeline" / "data" / "notebooklm-diff.txt"
            with open(diff_file, "w", encoding="utf-8") as f:
                f.write(diff_text)
            print(f"  Differentiation context: {len(diff_text)} chars")

        # Generate dynamic audio/video focus
        print("  Generating dynamic focus...")
        focus_str = generate_dynamic_focus(digest, prior_themes)
        if focus_str:
            print(f"  Dynamic focus: {focus_str[:100]}...")
        else:
            print("  Using default focus (no prior themes or API error)")
    else:
        print("  No prior themes found, using default focus")

    # Call notebooklm_media.py
    cmd = [
        sys.executable, str(DIGEST_DIR / "notebooklm_media.py"),
        "--text-file", str(text_file),
        "--date", args.date,
        "--output-dir", str(DIGEST_DIR),
    ]
    if args.skip_video:
        cmd.append("--skip-video")
    if diff_file:
        cmd.extend(["--diff-file", str(diff_file)])
    if focus_str:
        cmd.extend(["--focus", focus_str])

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"

    print(f"  Running notebooklm_media.py...")
    result = subprocess.run(cmd, env=env, capture_output=False, timeout=1800)

    # Read the status file that notebooklm_media.py writes
    status_path = DIGEST_DIR / "media-status.json"
    if status_path.exists():
        with open(status_path, "r", encoding="utf-8") as f:
            status = json.load(f)
        # Copy to pipeline data dir
        write_json("media-status.json", status)
        print(f"\n  Media generation {'completed' if result.returncode == 0 else 'had failures'}")
        print(f"  Exit code: {result.returncode}")
    else:
        print(f"  WARNING: No media-status.json generated")
        write_json("media-status.json", {
            "date": args.date,
            "exit_code": result.returncode,
            "steps": [],
            "media": {},
        })

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
