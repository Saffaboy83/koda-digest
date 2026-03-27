"""
Step 02: Gather newsletter content from Gmail.

When run standalone: uses Gmail API directly (requires credentials).
When run from Claude Code: outputs instructions for the MCP approach.

For now, this script is designed to be called by Claude Code which
fills in the newsletter data using the Gmail MCP tools.

Input:  None (or --date flag)
Output: pipeline/data/newsletters.json
"""

import argparse
import json
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import today_str, write_json, read_json

# ── Newsletter Search Config ────────────────────────────────────────────────

GMAIL_SEARCH_QUERY = "from:newsletter OR subject:digest OR subject:weekly newer_than:3d"

# Known newsletter senders to prioritize
PRIORITY_SENDERS = [
    "buildfastwithai",
    "deloitte",
    "riskinfo",
    "ben's bites",
    "the rundown",
    "tldr",
    "superhuman",
    "morning brew",
]


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Step 02: Gather newsletters")
    parser.add_argument("--date", default=today_str(), help="Date (YYYY-MM-DD)")
    parser.add_argument("--input", help="Path to pre-gathered newsletter JSON (from Claude Code MCP)")
    args = parser.parse_args()

    print(f"[02] Gathering newsletters for {args.date}")

    if args.input:
        # Load pre-gathered data (Claude Code already fetched via Gmail MCP)
        with open(args.input, "r", encoding="utf-8") as f:
            newsletters = json.load(f)
        print(f"  Loaded {len(newsletters.get('newsletters', []))} newsletters from {args.input}")
    else:
        # Check if data already exists from a previous run or Claude Code
        existing = read_json("newsletters.json")
        if existing and existing.get("date") == args.date:
            print(f"  Using existing newsletter data from earlier run")
            print(f"  Contains {len(existing.get('newsletters', []))} newsletters")
            return

        # No pre-gathered data — print instructions for Claude Code
        print(f"\n  No newsletter data available.")
        print(f"  When running from Claude Code, use these MCP calls:")
        print(f"    1. gmail_search_messages: query='{GMAIL_SEARCH_QUERY}'")
        print(f"    2. gmail_read_message on each result")
        print(f"    3. Save results using: python 02_gather_newsletters.py --input newsletters-raw.json")
        print(f"\n  Creating empty placeholder...")

        newsletters = {
            "date": args.date,
            "gathered_at": datetime.now().isoformat(),
            "source": "placeholder",
            "newsletters": [],
        }

    # Ensure required structure
    if "date" not in newsletters:
        newsletters["date"] = args.date
    if "gathered_at" not in newsletters:
        newsletters["gathered_at"] = datetime.now().isoformat()

    path = write_json("newsletters.json", newsletters)
    print(f"  Saved to {path}")


def create_newsletter_entry(sender, subject, date, content, source_link=""):
    """Helper to create a properly structured newsletter entry.

    Call this from Claude Code when processing Gmail MCP results:

        from pipeline.step_02_newsletters import create_newsletter_entry
        entry = create_newsletter_entry("BuildFast with AI", "Weekly #42",
                                         "2026-03-24", "<email content>")
    """
    return {
        "sender": sender,
        "subject": subject,
        "date": date,
        "content": content,
        "source_link": source_link,
    }


if __name__ == "__main__":
    main()
