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
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import DIGEST_DIR, today_str, write_json, read_json


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

    # Call notebooklm_media.py
    cmd = [
        sys.executable, str(DIGEST_DIR / "notebooklm_media.py"),
        "--text-file", str(text_file),
        "--date", args.date,
        "--output-dir", str(DIGEST_DIR),
    ]
    if args.skip_video:
        cmd.append("--skip-video")

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
