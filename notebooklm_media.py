"""
NotebookLM Media Generator for Koda Digest.

Generates podcast (audio), infographic, and video using the notebooklm-py API.
Falls back to Chrome-based manual generation if auth expires.

Usage:
    python notebooklm_media.py --text-file news.txt [--date 2026-03-24] [--skip-video]
    python notebooklm_media.py --text "Your compiled news text here..."

Output files (in --output-dir, default: current directory):
    podcast-YYYY-MM-DD.mp3       Compressed podcast audio
    infographic-YYYY-MM-DD.jpg   Daily infographic (converted from PNG)
    video-YYYY-MM-DD.mp4         Video for YouTube upload (if not skipped)
    media-status.json            Status of each generation step

Exit codes:
    0  All requested media generated successfully
    1  Some media failed (check media-status.json for details)
    2  Auth failure — cookies expired, re-run notebooklm_login.py
    3  Fatal error
"""

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Windows event loop fix
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ── Constants ────────────────────────────────────────────────────────────────

NOTEBOOK_ID = "f928d89b-2520-4180-a71a-d93a75a5487c"

FFMPEG_PATH = os.path.expanduser(
    "~/AppData/Local/Microsoft/WinGet/Packages/"
    "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/"
    "ffmpeg-8.1-full_build/bin/ffmpeg.exe"
)

AUDIO_FOCUS = (
    "Focus on the biggest AI breakthroughs, key world events and their "
    "market impact, and practical AI tools people can use today."
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def make_status(step, success, detail="", path=""):
    return {"step": step, "success": success, "detail": detail, "path": path}


def compress_audio(input_path, output_path):
    """Compress audio to MP3 (64kbps mono, 22050Hz) via ffmpeg."""
    ffmpeg = FFMPEG_PATH if os.path.exists(FFMPEG_PATH) else shutil.which("ffmpeg")
    if not ffmpeg:
        return False, "ffmpeg not found"

    cmd = [
        ffmpeg, "-y", "-i", str(input_path),
        "-codec:a", "libmp3lame", "-b:a", "64k",
        "-ac", "1", "-ar", "22050",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        return False, result.stderr[-500:]
    return True, f"Compressed to {output_path}"


def convert_png_to_jpg(png_path, jpg_path):
    """Convert PNG infographic to JPG for smaller file size."""
    ffmpeg = FFMPEG_PATH if os.path.exists(FFMPEG_PATH) else shutil.which("ffmpeg")
    if not ffmpeg:
        # Fall back: just rename/copy
        shutil.copy2(png_path, jpg_path)
        return True, "Copied as-is (no ffmpeg for conversion)"

    cmd = [ffmpeg, "-y", "-i", str(png_path), "-q:v", "2", str(jpg_path)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        # Fall back: keep as PNG with .jpg extension (browsers handle it)
        shutil.copy2(png_path, jpg_path)
        return True, "Copied PNG as JPG (conversion failed)"
    return True, f"Converted to {jpg_path}"


# ── Main Pipeline ────────────────────────────────────────────────────────────


async def run_pipeline(text_content, date_str, output_dir, skip_video=False):
    """Run the full NotebookLM media generation pipeline."""

    results = []
    media_paths = {}

    # ── Import and connect ───────────────────────────────────────────────
    try:
        from notebooklm import (NotebookLMClient, AudioFormat, AudioLength,
                                InfographicOrientation, InfographicDetail,
                                VideoFormat, VideoStyle)
    except ImportError:
        print("ERROR: notebooklm-py not installed. Run: pip install notebooklm-py")
        return results, media_paths, 3

    try:
        client_cm = await NotebookLMClient.from_storage()
        client = await client_cm.__aenter__()
    except Exception as e:
        error_msg = str(e)
        if "storage" in error_msg.lower() or "cookie" in error_msg.lower() or "auth" in error_msg.lower():
            print("\n" + "=" * 60)
            print("AUTH EXPIRED — Cookies need refreshing.")
            print("Run:  python notebooklm_login.py")
            print("Then re-run this script.")
            print("=" * 60)
            results.append(make_status("auth", False, f"Auth failed: {error_msg}"))
            return results, media_paths, 2
        raise

    try:
        # ── Step 1: Clean old sources ────────────────────────────────────
        print("[1/6] Cleaning old text sources...")
        try:
            sources = await client.sources.list(NOTEBOOK_ID)
            deleted = 0
            for src in sources:
                try:
                    await client.sources.delete(NOTEBOOK_ID, src.id)
                    deleted += 1
                    await asyncio.sleep(1)  # Rate limit buffer
                except Exception as e:
                    print(f"  Warning: Could not delete source {src.id}: {e}")
            results.append(make_status("clean_sources", True, f"Deleted {deleted} old sources"))
            print(f"  Deleted {deleted} old sources.")
        except Exception as e:
            results.append(make_status("clean_sources", False, str(e)))
            print(f"  Warning: Could not clean sources: {e}")

        # ── Step 2: Add today's news text ────────────────────────────────
        print("[2/6] Adding today's news text...")
        try:
            await client.sources.add_text(
                NOTEBOOK_ID,
                f"Koda Daily Digest — {date_str}",
                text_content,
                wait=True,
            )
            results.append(make_status("add_text", True, f"Added {len(text_content)} chars"))
            print(f"  Added {len(text_content)} characters.")
            await asyncio.sleep(3)  # Let NotebookLM process the source
        except Exception as e:
            results.append(make_status("add_text", False, str(e)))
            print(f"  ERROR adding text: {e}")
            # Can't generate media without source text
            return results, media_paths, 1

        # ── Step 3: PARALLEL generation (audio + infographic + video) ────
        print("[3/5] Triggering all media generation in PARALLEL...")

        audio_path = Path(output_dir) / f"podcast-{date_str}.mp3"
        infographic_jpg = Path(output_dir) / f"infographic-{date_str}.jpg"
        video_path = Path(output_dir) / f"video-{date_str}.mp4"

        # Fire all generation requests concurrently
        async def start_audio():
            s = await client.artifacts.generate_audio(
                NOTEBOOK_ID,
                instructions=AUDIO_FOCUS,
                audio_format=AudioFormat.DEEP_DIVE,
                audio_length=AudioLength.DEFAULT,
            )
            print(f"  Audio generation started (task: {s.task_id})")
            return s

        async def start_infographic():
            s = await client.artifacts.generate_infographic(
                NOTEBOOK_ID,
                orientation=InfographicOrientation.LANDSCAPE,
                detail_level=InfographicDetail.DETAILED,
            )
            print(f"  Infographic generation started (task: {s.task_id})")
            return s

        async def start_video():
            s = await client.artifacts.generate_video(
                NOTEBOOK_ID,
                instructions=AUDIO_FOCUS,
                video_format=VideoFormat.EXPLAINER,
                video_style=VideoStyle.AUTO_SELECT,
            )
            print(f"  Video generation started (task: {s.task_id})")
            return s

        # Launch all generation tasks in parallel
        gen_tasks = [start_audio(), start_infographic()]
        if not skip_video:
            gen_tasks.append(start_video())

        try:
            gen_results = await asyncio.gather(*gen_tasks, return_exceptions=True)
        except Exception as e:
            print(f"  Error launching parallel generation: {e}")
            gen_results = [e] * len(gen_tasks)

        audio_status = gen_results[0] if not isinstance(gen_results[0], Exception) else None
        infographic_status = gen_results[1] if not isinstance(gen_results[1], Exception) else None
        video_status = gen_results[2] if len(gen_results) > 2 and not isinstance(gen_results[2], Exception) else None

        if isinstance(gen_results[0], Exception):
            print(f"  Audio launch failed: {gen_results[0]}")
        if isinstance(gen_results[1], Exception):
            print(f"  Infographic launch failed: {gen_results[1]}")
        if len(gen_results) > 2 and isinstance(gen_results[2], Exception):
            print(f"  Video launch failed: {gen_results[2]}")

        # Wait for all to complete in parallel
        print("[4/5] Waiting for all media to complete...")

        async def complete_audio():
            if not audio_status:
                return
            await client.artifacts.wait_for_completion(
                NOTEBOOK_ID, audio_status.task_id, timeout=1800.0
            )
            raw_audio = Path(output_dir) / f"podcast-raw-{date_str}.wav"
            await client.artifacts.download_audio(NOTEBOOK_ID, str(raw_audio))
            print(f"  Audio downloaded")
            ok, detail = compress_audio(raw_audio, audio_path)
            if ok:
                results.append(make_status("audio", True, detail, str(audio_path)))
                media_paths["podcast"] = str(audio_path)
                print(f"  Audio compressed: {audio_path}")
                try:
                    raw_audio.unlink()
                except OSError:
                    pass
            else:
                results.append(make_status("audio", False, f"Compression failed: {detail}"))
                print(f"  Audio compression failed: {detail}")

        async def complete_infographic():
            if not infographic_status:
                return
            await client.artifacts.wait_for_completion(
                NOTEBOOK_ID, infographic_status.task_id, timeout=1800.0
            )
            infographic_png = Path(output_dir) / f"infographic-{date_str}.png"
            await client.artifacts.download_infographic(NOTEBOOK_ID, str(infographic_png))
            print(f"  Infographic downloaded")
            ok, detail = convert_png_to_jpg(infographic_png, infographic_jpg)
            results.append(make_status("infographic", True, detail, str(infographic_jpg)))
            media_paths["infographic"] = str(infographic_jpg)
            print(f"  Infographic saved: {infographic_jpg}")
            if infographic_png.exists() and infographic_jpg.exists():
                try:
                    infographic_png.unlink()
                except OSError:
                    pass

        async def complete_video():
            if not video_status:
                return
            await client.artifacts.wait_for_completion(
                NOTEBOOK_ID, video_status.task_id, timeout=1800.0
            )
            await client.artifacts.download_video(NOTEBOOK_ID, str(video_path))
            results.append(make_status("video", True, "Downloaded", str(video_path)))
            media_paths["video"] = str(video_path)
            print(f"  Video downloaded: {video_path}")

        # Run all completions in parallel
        completion_tasks = [complete_audio(), complete_infographic()]
        if not skip_video and video_status:
            completion_tasks.append(complete_video())
        elif skip_video:
            results.append(make_status("video", True, "Skipped by user request"))
            print("  Video: skipped")

        completion_results = await asyncio.gather(*completion_tasks, return_exceptions=True)
        for i, r in enumerate(completion_results):
            if isinstance(r, Exception):
                step_name = ["audio", "infographic", "video"][i] if i < 3 else f"step_{i}"
                results.append(make_status(step_name, False, str(r)))
                print(f"  {step_name} failed: {r}")

        # ── Step 6: Summary ──────────────────────────────────────────────
        print("\n[6/6] Summary:")
        exit_code = 0
        for r in results:
            icon = "OK" if r["success"] else "FAIL"
            print(f"  [{icon}] {r['step']}: {r['detail']}")
            if not r["success"] and r["step"] not in ("clean_sources",):
                exit_code = 1

        return results, media_paths, exit_code

    except Exception as e:
        error_msg = str(e)
        if "token" in error_msg.lower() or "401" in error_msg or "403" in error_msg:
            print("\n" + "=" * 60)
            print("AUTH EXPIRED during generation.")
            print("Run:  python notebooklm_login.py")
            print("Then re-run this script.")
            print("=" * 60)
            results.append(make_status("auth_mid", False, error_msg))
            return results, media_paths, 2
        raise
    finally:
        try:
            await client_cm.__aexit__(None, None, None)
        except Exception:
            pass


# ── Chrome Fallback Instructions ─────────────────────────────────────────────


def print_chrome_fallback(failed_steps):
    """Print instructions for Chrome-based manual generation."""
    print("\n" + "=" * 60)
    print("CHROME FALLBACK — Manual steps needed:")
    print("=" * 60)
    print(f"\nThe following steps failed via API: {', '.join(failed_steps)}")
    print(f"\nNotebook: https://notebooklm.google.com/notebook/{NOTEBOOK_ID}")
    print("\nIn Claude Code, run the skill's Chrome MCP steps for:")

    if "audio" in failed_steps:
        print("  - Audio: Open NotebookLM > 3-dot menu on audio > Download")
        print("    Then compress: ffmpeg -i podcast-raw.m4a -codec:a libmp3lame -b:a 64k -ac 1 -ar 22050 podcast.mp3")

    if "infographic" in failed_steps:
        print("  - Infographic: Open NotebookLM > 3-dot menu on infographic > Download")

    if "video" in failed_steps:
        print("  - Video: Open NotebookLM > 3-dot menu on video > Download")
        print("    Then upload: python youtube_upload.py --file video.mp4 --title '...' --privacy public")

    print("\nOr re-authenticate and retry:")
    print("  python notebooklm_login.py")
    print("  python notebooklm_media.py --text-file news.txt")
    print("=" * 60)


# ── Entry Point ──────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Generate Koda Digest media via NotebookLM API")
    text_group = parser.add_mutually_exclusive_group(required=True)
    text_group.add_argument("--text-file", help="Path to file containing compiled news text")
    text_group.add_argument("--text", help="Compiled news text (inline)")

    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"),
                        help="Date for filenames (default: today)")
    parser.add_argument("--output-dir", default=".",
                        help="Output directory (default: current directory)")
    parser.add_argument("--skip-video", action="store_true",
                        help="Skip video generation")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON to stdout")

    args = parser.parse_args()

    # Read text content
    if args.text_file:
        with open(args.text_file, "r", encoding="utf-8") as f:
            text_content = f.read().strip()
    else:
        text_content = args.text.strip()

    if len(text_content) < 100:
        print("ERROR: Text content too short (< 100 chars). Provide a proper news summary.")
        sys.exit(3)

    os.makedirs(args.output_dir, exist_ok=True)

    print(f"Koda Digest Media Generator")
    print(f"Date: {args.date}")
    print(f"Output: {os.path.abspath(args.output_dir)}")
    print(f"Text: {len(text_content)} characters")
    print(f"Video: {'skip' if args.skip_video else 'generate'}")
    print()

    # Run the async pipeline
    results, media_paths, exit_code = asyncio.run(
        run_pipeline(text_content, args.date, args.output_dir, args.skip_video)
    )

    # Write status file
    status = {
        "date": args.date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "exit_code": exit_code,
        "steps": results,
        "media": media_paths,
    }
    status_path = os.path.join(args.output_dir, "media-status.json")
    with open(status_path, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)

    if args.json:
        print(json.dumps(status, indent=2))

    # Show Chrome fallback for any failures
    failed = [r["step"] for r in results
              if not r["success"] and r["step"] in ("audio", "infographic", "video")]
    if failed:
        print_chrome_fallback(failed)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
