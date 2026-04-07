"""
Step 01F: Update Leaderboard

Scrapes AI benchmark leaderboards (Chatbot Arena, LiveBench, SWE-Bench)
via Firecrawl and rebuilds the Leaderboard HTML page at /benchmarks/.

Runs on Mondays only (use --force to override).

Input:  benchmarks/data.json (previous run)
Output: benchmarks/data.json (updated rankings)
        benchmarks/index.html (rebuilt leaderboard page)

Usage:
    python pipeline/01f_update_benchmarks.py --date 2026-04-07
    python pipeline/01f_update_benchmarks.py --force
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import DIGEST_DIR, today_str

# Only run on Monday (0=Mon)
SCHEDULED_DAYS = {0}


def main() -> None:
    parser = argparse.ArgumentParser(description="Step 01F: Update Leaderboard")
    parser.add_argument("--date", default=today_str(), help="Date (YYYY-MM-DD)")
    parser.add_argument("--force", action="store_true", help="Run even on non-scheduled days")
    args = parser.parse_args()

    run_date = datetime.strptime(args.date, "%Y-%m-%d")
    if run_date.weekday() not in SCHEDULED_DAYS and not args.force:
        day_name = run_date.strftime("%A")
        print(f"[01F] Skipping leaderboard update -- {day_name} is not a scheduled day (Monday only)")
        print("  Use --force to override")
        sys.exit(0)

    print(f"[01F] Leaderboard update for {args.date}")

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"

    # Step 1: Scrape benchmark leaderboards
    print("  Scraping AI benchmarks...")
    scrape_script = DIGEST_DIR / "benchmarks" / "scrape_benchmarks.py"
    result = subprocess.run(
        [sys.executable, str(scrape_script)],
        env=env,
        timeout=600,
    )
    if result.returncode != 0:
        print("[01F] ERROR: Benchmark scrape failed")
        sys.exit(1)

    # Step 2: Rebuild HTML page
    print("  Building Leaderboard page...")
    build_script = DIGEST_DIR / "benchmarks" / "build_page.py"
    result = subprocess.run(
        [sys.executable, str(build_script)],
        env=env,
        timeout=120,
    )
    if result.returncode != 0:
        print("[01F] ERROR: Page build failed")
        sys.exit(1)

    print("[01F] Leaderboard updated successfully")


if __name__ == "__main__":
    main()
