"""
Koda Digest Pipeline Orchestrator.

Runs all pipeline steps in sequence with state tracking.
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
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import DIGEST_DIR, today_str, ensure_data_dir, write_json, read_json

# ── Step Definitions ─────────────────────────────────────────────────────────

STEPS = [
    ("01", "Gather News", "01_gather_news.py"),
    ("02", "Gather Newsletters", "02_gather_newsletters.py"),
    ("03", "Synthesize Content", "03_synthesize_content.py"),
    ("04", "Generate Media", "04_generate_media.py"),
    ("05", "Generate HTML", "05_generate_html.py"),
    ("06", "Deploy", "06_deploy.py"),
    ("07", "Send Email", "07_send_email.py"),
]


def run_step(step_id, name, script, date, extra_args=None):
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
        # Media generation (step 04) needs longer timeout for video
        step_timeout = 1800 if step_id == "04" else 900
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

    # Determine which steps to run
    skip_steps = set()
    if args.skip_media:
        skip_steps.add("04")
    if args.skip_deploy or args.dry_run:
        skip_steps.add("06")
    if args.skip_email or args.dry_run:
        skip_steps.add("07")

    steps_to_run = []
    for step_id, name, script in STEPS:
        if args.only and step_id not in args.only:
            continue
        if args.from_step and step_id < args.from_step:
            continue
        if step_id in skip_steps:
            continue
        steps_to_run.append((step_id, name, script))

    print(f"Steps: {', '.join(s[0] for s in steps_to_run)}")

    # Run steps
    results = {}
    all_passed = True
    pipeline_start = datetime.now()

    for step_id, name, script in steps_to_run:
        extra_args = []
        if step_id == "04" and args.skip_video:
            extra_args.append("--skip-video")
        if step_id == "06" and args.dry_run:
            extra_args.append("--dry-run")
        if step_id == "07" and args.dry_run:
            extra_args.append("--dry-run")

        success, duration = run_step(step_id, name, script, args.date, extra_args)
        results[step_id] = {"name": name, "success": success, "duration": duration}

        if not success:
            all_passed = False
            # Steps 04 (media) and 07 (email) are non-critical
            if step_id in ("04", "07"):
                print(f"  Non-critical step {step_id} failed — continuing...")
            else:
                print(f"\n  Critical step {step_id} failed. Pipeline stopped.")
                print(f"  To resume: python -m pipeline.run_all --from {step_id} --date {args.date}")
                break

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
