"""
Koda Digest Pipeline Orchestrator.

Runs all pipeline steps with state tracking.
Steps 04, 04E, and 04R run in parallel (separate notebooks, no data deps).
Can resume from any failed step.

Usage:
    python -m pipeline.run_all                    # Run all steps
    python -m pipeline.run_all --from 03          # Resume from step 03
    python -m pipeline.run_all --only 01 03 05    # Run specific steps
    python -m pipeline.run_all --skip-video       # Skip video generation
    python -m pipeline.run_all --skip-media       # Skip media (steps 04)
    python -m pipeline.run_all --skip-deploy      # Skip deploy (step 06)
    python -m pipeline.run_all --skip-email       # Skip email (step 07)
"""

import argparse
import json
import subprocess
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import DIGEST_DIR, today_str, ensure_data_dir, write_json, read_json

# ── Step Definitions ─────────────────────────────────────────────────────────

STEPS = [
    ("01",  "Gather News",          "01_gather_news.py"),
    ("01B", "Discover Tools & Blogs", "01b_discover_tools.py"),
    ("01C", "Competitive Monitor",  "01c_competitive_monitor.py"),
    ("01D", "Changelog Tracker",    "01d_changelog_tracker.py"),
    ("02",  "Gather Newsletters",   "02_gather_newsletters.py"),
    ("03",  "Synthesize Content",   "03_synthesize_content.py"),
    ("03B", "Verify Stats",         "03b_verify_stats.py"),
    ("04",  "Generate Media",       "04_generate_media.py"),
    ("04E", "Generate Editorial",   "08_generate_editorial.py"),
    ("04R", "Generate Reviews",     "05b_generate_reviews.py"),
    ("05",  "Generate HTML",        "05_generate_html.py"),
    ("06",  "Deploy",               "06_deploy.py"),
    ("07",  "Send Email",           "07_send_email.py"),
]

# Step ordering index for --from comparisons (string comparison breaks for "03B" vs "04")
STEP_ORDER = {step_id: i for i, (step_id, _, _) in enumerate(STEPS)}

# Steps that run in parallel (separate notebooks/APIs, no shared data dependencies)
PARALLEL_STEPS = {"04", "04E", "04R"}

# Non-critical steps: pipeline continues if these fail
NON_CRITICAL = {"01B", "01C", "01D", "03B", "04", "04E", "04R", "07"}

# Per-step timeouts (seconds)
STEP_TIMEOUTS = {
    "04":  3600,  # Veo 3 cinematic video: 30-45 min
    "04E": 2400,  # Editorial: research + draft + fact-check + hero + media: up to 40 min
    "04R":  600,  # Reviews: 3 tools x scrape + LLM: ~10 min
    "01D":  900,  # Changelog: scrape 25 companies: up to 15 min
}
DEFAULT_TIMEOUT = 900


def _get_timeout(step_id: str) -> int:
    return STEP_TIMEOUTS.get(step_id, DEFAULT_TIMEOUT)


def run_step(step_id: str, name: str, script: str, date: str,
             extra_args: list[str] | None = None) -> tuple[bool, float]:
    """Run a pipeline step and return (success, duration_seconds)."""
    script_path = DIGEST_DIR / "pipeline" / script
    cmd = [sys.executable, str(script_path), "--date", date]
    if extra_args:
        cmd.extend(extra_args)

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"

    print(f"\n{'='*60}")
    print(f"  Step {step_id}: {name}")
    print(f"{'='*60}")

    start = datetime.now()
    try:
        step_timeout = _get_timeout(step_id)
        result = subprocess.run(
            cmd, env=env, timeout=step_timeout,
            cwd=str(DIGEST_DIR),
        )
        duration = (datetime.now() - start).total_seconds()
        success = result.returncode == 0
        print(f"\n  {'OK' if success else 'FAILED'} ({duration:.1f}s)")
        return success, duration
    except subprocess.TimeoutExpired:
        duration = (datetime.now() - start).total_seconds()
        print(f"\n  TIMEOUT after {duration:.1f}s")
        return False, duration
    except Exception as e:
        duration = (datetime.now() - start).total_seconds()
        print(f"\n  ERROR: {e}")
        return False, duration


def _run_parallel_block(
    parallel_group: list[tuple[str, str, str, list[str]]],
    date: str,
) -> dict[str, dict]:
    """Run a group of steps in parallel using threads.

    Each step is a subprocess, so threads give true parallelism here.
    Returns dict of step_id -> {name, success, duration}.
    """
    print(f"\n{'='*60}")
    print(f"  PARALLEL BLOCK: {', '.join(s[0] for s in parallel_group)}")
    print(f"  (These steps run concurrently -- logs may interleave)")
    print(f"{'='*60}")

    block_results: dict[str, dict] = {}

    def _worker(step_id: str, name: str, script: str,
                extra: list[str]) -> tuple[str, str, bool, float]:
        success, duration = run_step(step_id, name, script, date, extra)
        return step_id, name, success, duration

    with ThreadPoolExecutor(max_workers=len(parallel_group)) as pool:
        futures = {
            pool.submit(_worker, sid, nm, sc, ex): sid
            for sid, nm, sc, ex in parallel_group
        }
        for future in as_completed(futures):
            step_id, name, success, duration = future.result()
            block_results[step_id] = {
                "name": name, "success": success, "duration": duration,
            }

    return block_results


def main():
    parser = argparse.ArgumentParser(description="Koda Digest Pipeline Orchestrator")
    parser.add_argument("--date", default=today_str(), help="Date (YYYY-MM-DD)")
    parser.add_argument("--from", dest="from_step", help="Resume from this step (e.g., 03)")
    parser.add_argument("--only", nargs="+", help="Run only these steps (e.g., 01 03 05)")
    parser.add_argument("--skip-video", action="store_true", help="Skip video in step 04")
    parser.add_argument("--skip-media", action="store_true", help="Skip step 04 entirely")
    parser.add_argument("--skip-deploy", action="store_true", help="Skip step 06")
    parser.add_argument("--skip-email", action="store_true", help="Skip step 07")
    parser.add_argument("--dry-run", action="store_true", help="Don't deploy or send email")
    args = parser.parse_args()

    ensure_data_dir()

    print(f"Koda Digest Pipeline")
    print(f"Date: {args.date}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Warn about missing critical env vars
    _critical_vars = {
        "PERPLEXITY_API_KEY": "step 01 (news gathering)",
        "OPENROUTER_API_KEY": "steps 03/04E (LLM synthesis & editorial)",
    }
    for var, usage in _critical_vars.items():
        if not os.environ.get(var):
            print(f"  WARNING: {var} not set -- {usage} will fail")

    # Determine which steps to run
    skip_steps: set[str] = set()
    if args.skip_media:
        skip_steps.add("04")
    if args.skip_deploy or args.dry_run:
        skip_steps.add("06")
    if args.skip_email or args.dry_run:
        skip_steps.add("07")

    steps_to_run: list[tuple[str, str, str]] = []
    for step_id, name, script in STEPS:
        if args.only and step_id not in args.only:
            continue
        if args.from_step and STEP_ORDER.get(step_id, 99) < STEP_ORDER.get(args.from_step, 0):
            continue
        if step_id in skip_steps:
            continue
        steps_to_run.append((step_id, name, script))

    print(f"Steps: {', '.join(s[0] for s in steps_to_run)}")

    # Run steps
    results: dict[str, dict] = {}
    all_passed = True
    pipeline_start = datetime.now()

    # Collect steps into sequential runs and one parallel block
    i = 0
    while i < len(steps_to_run):
        step_id, name, script = steps_to_run[i]

        # Check if this step starts a parallel block
        if step_id in PARALLEL_STEPS:
            # Gather all consecutive parallel steps
            parallel_group: list[tuple[str, str, str, list[str]]] = []
            while i < len(steps_to_run) and steps_to_run[i][0] in PARALLEL_STEPS:
                sid, nm, sc = steps_to_run[i]
                extra: list[str] = []
                if sid == "04" and args.skip_video:
                    extra.append("--skip-video")
                parallel_group.append((sid, nm, sc, extra))
                i += 1

            # Run them all in parallel
            block_results = _run_parallel_block(parallel_group, args.date)
            for sid, info in block_results.items():
                results[sid] = info
                if not info["success"]:
                    all_passed = False
                    if sid in NON_CRITICAL:
                        print(f"  Non-critical step {sid} failed -- continuing...")
                    else:
                        print(f"\n  Critical step {sid} failed. Pipeline stopped.")
                        break
        else:
            # Sequential step
            extra_args: list[str] = []
            if step_id == "06" and args.dry_run:
                extra_args.append("--dry-run")
            if step_id == "07" and args.dry_run:
                extra_args.append("--dry-run")

            success, duration = run_step(step_id, name, script, args.date, extra_args)
            results[step_id] = {"name": name, "success": success, "duration": duration}

            if not success:
                all_passed = False
                if step_id in NON_CRITICAL:
                    print(f"  Non-critical step {step_id} failed -- continuing...")
                else:
                    print(f"\n  Critical step {step_id} failed. Pipeline stopped.")
                    print(f"  To resume: python -m pipeline.run_all --from {step_id} --date {args.date}")
                    break
            i += 1

    # Summary
    total_duration = (datetime.now() - pipeline_start).total_seconds()
    print(f"\n{'='*60}")
    print(f"  Pipeline {'COMPLETED' if all_passed else 'INCOMPLETE'}")
    print(f"  Total time: {total_duration:.1f}s")
    print(f"{'='*60}")

    for step_id, info in results.items():
        icon = "OK" if info["success"] else "FAIL"
        print(f"  [{icon}] {step_id} {info['name']} ({info['duration']:.1f}s)")

    # Save pipeline state
    state = {
        "date": args.date,
        "completed_at": datetime.now().isoformat(),
        "all_passed": all_passed,
        "total_duration": total_duration,
        "steps": results,
    }
    write_json("pipeline-state.json", state)

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
