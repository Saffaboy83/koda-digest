"""
Step 01D: AI Changelog Tracker

Scrapes company blogs/changelogs for new posts, accumulates over 30 days,
and builds the "Who Shipped What" HTML page.

Input:  changelog/data.json (accumulated from previous runs)
        changelog/url-snapshot.json (URL diff tracking)
Output: changelog/data.json (updated with new entries)
        changelog/index.html (rebuilt HTML page)

Usage:
    python pipeline/01d_changelog_tracker.py --date 2026-04-03
"""

import argparse
import subprocess
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import DIGEST_DIR, today_str


def main():
    parser = argparse.ArgumentParser(description="Step 01D: AI Changelog Tracker")
    parser.add_argument("--date", default=today_str(), help="Date (YYYY-MM-DD)")
    args = parser.parse_args()

    print(f"[01D] AI Changelog Tracker for {args.date}")

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"

    # Step 1: Scrape new posts
    print("  Scraping company blogs...")
    scrape_script = DIGEST_DIR / "changelog" / "scrape_changelog.py"
    result = subprocess.run(
        [sys.executable, str(scrape_script), "--date", args.date],
        env=env, cwd=str(DIGEST_DIR), timeout=480,
    )
    if result.returncode != 0:
        print("  ERROR: scrape_changelog.py failed")
        sys.exit(1)

    # Step 2: Build HTML page
    print("  Building changelog page...")
    build_script = DIGEST_DIR / "changelog" / "build_page.py"
    result = subprocess.run(
        [sys.executable, str(build_script)],
        env=env, cwd=str(DIGEST_DIR), timeout=30,
    )
    if result.returncode != 0:
        print("  ERROR: build_page.py failed")
        sys.exit(1)

    print("  Changelog updated successfully")


if __name__ == "__main__":
    main()
