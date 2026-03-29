"""
Step 06: Deploy to Vercel via git push.

1. Upload media (podcast, infographic) to Supabase Storage
2. Run build-index.py to update manifest + search index
3. Stage, commit, and push to origin/main
4. Vercel auto-deploys on push

Input:  HTML files, media files, manifest.json, search-index.json
Output: Live site at www.koda.community, media on Supabase Storage
"""

import argparse
import subprocess
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import DIGEST_DIR, today_str


def run(cmd, cwd=None):
    """Run a shell command and return (success, output)."""
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True,
        cwd=cwd or str(DIGEST_DIR), timeout=120
    )
    return result.returncode == 0, result.stdout + result.stderr


def main():
    parser = argparse.ArgumentParser(description="Step 06: Deploy to Vercel")
    parser.add_argument("--date", default=today_str(), help="Date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be committed")
    args = parser.parse_args()

    print(f"[06] Deploying digest for {args.date}")

    # Note: Media uploads (Supabase, YouTube) happen in step 04 after generation,
    # BEFORE step 05 renders the HTML (which needs youtube-result.json and Supabase URLs).

    # Step 1: Rebuild search index
    print("  Rebuilding search index...")
    ok, output = run(f"{sys.executable} build-index.py")
    if ok:
        print("    manifest.json + search-index.json updated")
    else:
        print(f"    WARNING: build-index.py failed: {output[-200:]}")

    # Step 2: Stage files
    # Note: podcast-*.mp3 and infographic-*.jpg are gitignored
    # (served from Supabase Storage, not Vercel). Hero images are committed.
    files_to_stage = [
        "morning-briefing-koda.html",
        f"morning-briefing-koda-{args.date}.html",
        f"hero-{args.date}.jpg",
        "manifest.json",
        "search-index.json",
        "recent-themes.json",
        "latest-markets.json",
        "index.html",
        "vercel.json",
        ".gitignore",
    ]

    # Add any editorial HTML files generated for today
    editorial_dir = DIGEST_DIR / "editorial"
    for editorial_file in sorted(editorial_dir.glob(f"{args.date}-*.html")):
        files_to_stage.append(f"editorial/{editorial_file.name}")

    existing = []
    for f in files_to_stage:
        path = DIGEST_DIR / f
        if path.exists():
            existing.append(f)
        else:
            print(f"    Skipping {f} (not found)")

    if not existing:
        print("  ERROR: No files to stage")
        sys.exit(1)

    print(f"  Staging {len(existing)} files...")

    if args.dry_run:
        for f in existing:
            print(f"    Would stage: {f}")
        print("  DRY RUN — nothing committed")
        return

    # Stage
    stage_cmd = "git add " + " ".join(f'"{f}"' for f in existing)
    ok, output = run(stage_cmd)
    if not ok:
        print(f"  ERROR staging files: {output}")
        sys.exit(1)

    # Step 3: Commit
    commit_msg = f"Digest {args.date}"
    ok, output = run(f'git commit -m "{commit_msg}"')
    if not ok:
        if "nothing to commit" in output:
            print("  Nothing new to commit")
            return
        print(f"  ERROR committing: {output}")
        sys.exit(1)
    print(f"  Committed: {commit_msg}")

    # Step 4: Push
    print("  Pushing to origin/main...")
    ok, output = run("git push origin main")
    if ok:
        print("  Pushed successfully — Vercel will auto-deploy in ~30s")
    else:
        print(f"  WARNING: Push failed: {output[-300:]}")
        print("  Manual fallback: cd ~/Digest && git push origin main")
        sys.exit(1)


if __name__ == "__main__":
    main()
