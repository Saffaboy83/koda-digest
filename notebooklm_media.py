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

NOTEBOOK_ID = os.environ.get(
    "NOTEBOOK_ID", "f928d89b-2520-4180-a71a-d93a75a5487c"
)

FFMPEG_PATH = os.environ.get("FFMPEG_PATH", "") or shutil.which("ffmpeg") or os.path.expanduser(
    "~/AppData/Local/Microsoft/WinGet/Packages/"
    "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/"
    "ffmpeg-8.1-full_build/bin/ffmpeg.exe"
)

DEFAULT_AUDIO_FOCUS = (
    "Deliver this as an intelligence briefing that works for both AI practitioners and "
    "business professionals who do not live in tech. "
    "When introducing technical concepts like parameter counts, context windows, "
    "mixture-of-experts, or open-weight models, briefly explain WHY it matters in plain "
    "language before diving into details. For example: 'DeepSeek released a model with "
    "1 trillion parameters. To put that in perspective, that is roughly 5x larger than the "
    "models most companies were running just a year ago, and they made it freely available.' "
    "Structure: Open with the single most important story and why the listener should care. "
    "AI developments: lead with impact, then technical detail. "
    "World events: focus on what changed and what happens next. "
    "Markets: one-line numbers, then what is driving them. "
    "Tools: who should use it and what problem it solves. "
    "Tone: Two smart colleagues catching each other up over coffee. Confident but not "
    "jargon-heavy. When one host uses a technical term, the other should naturally clarify it. "
    "Pacing: Spend more time on the 2-3 stories that matter most, less time listing everything. "
    "Avoid: Assuming the listener knows what MoE, context windows, or open-weight means "
    "without a quick explainer."
)

DEFAULT_INFOGRAPHIC_FOCUS = (
    'Create a professional, magazine-quality infographic for "Koda Daily AI Digest". '
    "Layout: Use a structured 2x2 grid with 4 featured story quadrants. Each quadrant "
    "should have a bold headline, a rich AI-generated illustration, and 2-3 key data points "
    "or statistics. "
    "Visual style: Dark premium theme with deep navy/indigo background. Use neon accent "
    "colors (electric blue, vivid purple, bright emerald). Modern tech aesthetic with subtle "
    "glow effects and clean sans-serif typography with clear hierarchy. "
    "Include: data visualizations (mini charts, progress bars, trend arrows), tech-themed "
    "icons and illustrations for each story, and brand elements. "
    'Brand: "Koda" with a paw-print icon bottom-left, "koda.community" bottom-right, '
    "date prominently in the header. "
    "Quality: Think Bloomberg Terminal meets Wired magazine. Dense with information but "
    "visually clean and scannable. "
    "STRICT RULE: Do NOT depict any recognizable political figures, heads of state, or "
    "government officials. Use abstract representations instead: flags, building exteriors, "
    "policy icons, military hardware silhouettes."
)

DEFAULT_VIDEO_FOCUS = (
    "Create a cinematic intelligence briefing in the style of a high-production documentary "
    "or HBO news special. This is a Veo 3 cinematic video -- push the visual quality to its "
    "maximum. Every frame should feel like it belongs in a Netflix documentary or a Bloomberg "
    "Originals film. "
    "\n\n"
    "STRUCTURE & NARRATIVE: "
    "Cold open (0:00-0:15): Start mid-action. No titles, no introductions. Drop the viewer "
    "into the most dramatic visual of the day -- the moment of crisis or breakthrough. "
    "Narration begins over the imagery. "
    "Act 1 -- The Crisis (0:15-1:30): The headline story that affects everyone. Build tension "
    "with escalating visuals. Use a mix of wide establishing shots and tight close-ups. "
    "Show scale and consequence. "
    "Act 2 -- The Technology (1:30-3:00): The AI developments. Shift the visual palette from "
    "warm/urgent to cool/precise. Show the contrast between physical world chaos and digital "
    "world precision. Use data visualizations that feel alive -- not static charts but flowing, "
    "animated representations. "
    "Act 3 -- The Collision (3:00-4:00): Where these forces meet. Use visual juxtaposition -- "
    "intercut between the physical and digital worlds. Build to a thesis statement. "
    "Close (4:00-4:30): End on a single powerful image that encapsulates the day's theme. "
    "Hold the frame. Let it breathe. "
    "\n\n"
    "VISUAL DIRECTION PER SCENE: "
    "Crisis scenes: Aerial drone shots of strategic chokepoints, naval vessels in formation, "
    "smoke plumes on horizons, trading floors with cascading red tickers, close-ups of "
    "commodity price screens. Warm amber-red color grading. Handheld camera feel for urgency. "
    "Technology scenes: Vast data center interiors stretching to vanishing point, racks of "
    "GPUs with blinking status lights, holographic neural network visualizations floating in "
    "dark space, code scrolling on screens reflected in glass. Cool blue-cyan color grading. "
    "Smooth dolly and crane movements for precision. "
    "Collision scenes: Split-screen or morphing transitions -- a cargo ship hull dissolves into "
    "a server rack, a missile trajectory transforms into a neural network edge, oil flowing "
    "through a pipeline cross-fades to data flowing through fiber optics. "
    "Closing shot: Pull back to a global satellite view showing both conflicts and data centers "
    "lit up simultaneously. "
    "\n\n"
    "CINEMATOGRAPHY: "
    "Lighting: Golden hour for geopolitical scenes, cool fluorescent for tech interiors, "
    "dramatic chiaroscuro for the collision act. "
    "Camera movement: Slow dolly pushes for tension, smooth crane shots for scale reveals, "
    "subtle handheld for breaking-news urgency. "
    "Depth of field: Shallow focus for emotional close-ups, deep focus for establishing shots. "
    "Transitions: Dissolves and morphs between acts (never hard cuts between worlds). "
    "Color palette: Each act has its own grade -- warm amber (crisis), cool blue (tech), "
    "mixed warm-cool (collision), muted desaturated (closing). "
    "\n\n"
    "TONE: Authoritative but human. Like a seasoned correspondent who has seen both wars and "
    "Silicon Valley boardrooms. Never sensationalist. Every word earns its place. "
    "PACING: Urgent in Act 1, contemplative in Act 2, accelerating in Act 3, still in the close. "
    "\n\n"
    "STRICT RULE -- NO POLITICAL FIGURES: Do NOT show any recognizable political figures, "
    "heads of state, politicians, or government officials in the video. No faces of presidents, "
    "prime ministers, generals, or named political leaders. Instead show abstract representations "
    "of power and decision-making: empty podiums, government buildings exteriors, flags, "
    "diplomatic tables, military hardware without identifiable personnel, policy documents, "
    "press briefing rooms without people. This applies to ALL acts and scenes."
    "\n\n"
    "TECHNICAL STABILIZERS (apply to ALL scenes): "
    "Maintain subject center-frame stability in all shots. "
    "Consistent shadow direction within each act. "
    "Prevent horizon warping on drone and crane movements. "
    "Preserve architectural geometry in all environment shots. "
    "Lock screen text legibility on any data visualizations. "
    "Smooth interpolation on all transitions -- dissolves over hard cuts."
    "\n\n"
    "SOUND DESIGN & ATMOSPHERE: "
    "Crisis scenes: distant machinery rumble, dust particles in light beams, heat shimmer "
    "on tarmac, muffled radio chatter. "
    "Technology scenes: deep server fan hum, electrical crackle of cooling systems, cool "
    "air condensation, high-frequency data transfer tone. "
    "Collision scenes: both soundscapes bleeding together, rising ambient tension, "
    "mechanical rhythms merging with digital pulses. "
    "Close: silence except a single sustained tone fading to black."
    "\n\n"
    "SENSORY TEXTURE (layer into every scene): "
    "Rain on glass, steam from vents, dust motes caught in shafts of light. "
    "Screen reflections on faces and polished surfaces. "
    "Depth particles: fog layers, atmospheric haze, bokeh light points in backgrounds. "
    "Material textures: brushed metal, polished glass, rough concrete, wet asphalt reflections."
)

VIDEO_POLL_INTERVAL = 15.0  # seconds between download attempts
VIDEO_POLL_TIMEOUT = 3600.0  # max wait for cinematic video (60 min -- Veo 3 can take 45+)

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


async def run_pipeline(text_content, date_str, output_dir, skip_video=False,
                       diff_text=None, audio_focus=None, infographic_focus=None,
                       video_focus=None, visual_script=None,
                       infographic_source=None, new_notebook=False,
                       notebook_title=None, existing_notebook_id=None):
    """Run the full NotebookLM media generation pipeline."""

    results = []
    media_paths = {}
    focus = audio_focus or DEFAULT_AUDIO_FOCUS
    ig_focus = infographic_focus or DEFAULT_INFOGRAPHIC_FOCUS
    vid_focus = video_focus or DEFAULT_VIDEO_FOCUS

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
        # ── Step 1: Notebook setup ────────────────────────────────────
        if existing_notebook_id:
            notebook_id = existing_notebook_id
            print(f"[1/6] Using existing notebook: {notebook_id}")
            results.append(make_status("use_notebook", True, f"Using: {notebook_id}"))
        elif new_notebook:
            title = notebook_title or f"Koda Media — {date_str}"
            print(f"[1/6] Creating new notebook: {title}")
            try:
                nb = await client.notebooks.create(title)
                notebook_id = nb.id
                results.append(make_status("create_notebook", True, f"Created: {notebook_id}"))
                print(f"  Created notebook: {notebook_id}")
                await asyncio.sleep(2)
            except Exception as e:
                results.append(make_status("create_notebook", False, str(e)))
                print(f"  ERROR creating notebook: {e}")
                return results, media_paths, 1
        else:
            notebook_id = NOTEBOOK_ID
            print("[1/6] Cleaning old text sources...")
            try:
                sources = await client.sources.list(notebook_id)
                deleted = 0
                for src in sources:
                    try:
                        await client.sources.delete(notebook_id, src.id)
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
                notebook_id,
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

        # ── Step 2b: Add differentiation context (if provided) ────────
        if diff_text:
            print("[2b/6] Adding differentiation context...")
            try:
                await client.sources.add_text(
                    notebook_id,
                    f"Editorial Direction -- {date_str}",
                    diff_text,
                    wait=True,
                )
                results.append(make_status("add_diff", True,
                                           f"Added {len(diff_text)} chars differentiation"))
                print(f"  Added {len(diff_text)} chars differentiation context.")
                await asyncio.sleep(2)
            except Exception as e:
                results.append(make_status("add_diff", False, str(e)))
                print(f"  Warning: Could not add differentiation source: {e}")

        # ── Step 2c: Add visual script (if provided) ────────────────
        if visual_script:
            print("[2c/6] Adding visual script source...")
            try:
                await client.sources.add_text(
                    notebook_id,
                    f"Visual Production Script -- {date_str}",
                    visual_script,
                    wait=True,
                )
                results.append(make_status("add_visual_script", True,
                                           f"Added {len(visual_script)} chars visual script"))
                print(f"  Added {len(visual_script)} chars visual script.")
                await asyncio.sleep(2)
            except Exception as e:
                results.append(make_status("add_visual_script", False, str(e)))
                print(f"  Warning: Could not add visual script source: {e}")

        # ── Step 2d: Add infographic visual direction source (if provided) ──
        if infographic_source:
            print("[2d/6] Adding infographic visual direction source...")
            try:
                await client.sources.add_text(
                    notebook_id,
                    f"Infographic Visual Direction -- {date_str}",
                    infographic_source,
                    wait=True,
                )
                results.append(make_status("add_infographic_source", True,
                                           f"Added {len(infographic_source)} chars infographic direction"))
                print(f"  Added {len(infographic_source)} chars infographic direction.")
                await asyncio.sleep(2)
            except Exception as e:
                results.append(make_status("add_infographic_source", False, str(e)))
                print(f"  Warning: Could not add infographic source: {e}")

        # ── Step 3: PARALLEL generation (audio + infographic + video) ────
        print("[3/5] Triggering all media generation in PARALLEL...")

        audio_path = Path(output_dir) / f"podcast-{date_str}.mp3"
        infographic_jpg = Path(output_dir) / f"infographic-{date_str}.jpg"
        video_path = Path(output_dir) / f"video-{date_str}.mp4"

        # Fire all generation requests concurrently
        async def start_audio():
            s = await client.artifacts.generate_audio(
                notebook_id,
                instructions=focus,
                audio_format=AudioFormat.DEEP_DIVE,
                audio_length=AudioLength.DEFAULT,
            )
            print(f"  Audio generation started (task: {s.task_id})")
            return s

        async def start_infographic():
            s = await client.artifacts.generate_infographic(
                notebook_id,
                instructions=ig_focus,
                orientation=InfographicOrientation.LANDSCAPE,
                detail_level=InfographicDetail.DETAILED,
            )
            print(f"  Infographic generation started (task: {s.task_id})")
            return s

        async def start_video():
            s = await client.artifacts.generate_cinematic_video(
                notebook_id,
                instructions=vid_focus,
            )
            print(f"  Cinematic video generation started (task: {s.task_id})")
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
                notebook_id, audio_status.task_id, timeout=1800.0
            )
            raw_audio = Path(output_dir) / f"podcast-raw-{date_str}.wav"
            await client.artifacts.download_audio(notebook_id, str(raw_audio))
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
                notebook_id, infographic_status.task_id, timeout=1800.0
            )
            infographic_png = Path(output_dir) / f"infographic-{date_str}.png"
            await client.artifacts.download_infographic(notebook_id, str(infographic_png))
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
            # Bypass: library's wait_for_completion has a URL validation bug
            # that downgrades COMPLETED to PROCESSING for video artifacts.
            # Instead, try short wait then fall back to direct download retries.
            try:
                await client.artifacts.wait_for_completion(
                    notebook_id, video_status.task_id, timeout=120.0
                )
                await client.artifacts.download_video(notebook_id, str(video_path))
                results.append(make_status("video", True, "Downloaded", str(video_path)))
                media_paths["video"] = str(video_path)
                print(f"  Video downloaded: {video_path}")
                return
            except TimeoutError:
                print("    Video wait_for_completion timed out (URL validation bug)")
                print("    Falling back to direct download polling...")
            except Exception as e:
                print(f"    Video wait error: {e}, trying direct downloads...")

            # Retry download directly -- video may be ready even though
            # the library's URL check disagrees
            start = time.monotonic()
            interval = VIDEO_POLL_INTERVAL
            attempt = 0
            while time.monotonic() - start < VIDEO_POLL_TIMEOUT:
                attempt += 1
                elapsed = time.monotonic() - start
                try:
                    await client.artifacts.download_video(
                        notebook_id, str(video_path)
                    )
                    results.append(make_status(
                        "video", True,
                        f"Downloaded (direct attempt #{attempt}, {elapsed:.0f}s)",
                        str(video_path),
                    ))
                    media_paths["video"] = str(video_path)
                    print(f"  Video downloaded: {video_path}"
                          f" (attempt #{attempt}, {elapsed:.0f}s)")
                    return
                except Exception as e:
                    print(f"    Video download attempt #{attempt}"
                          f" ({elapsed:.0f}s): {e}")
                await asyncio.sleep(interval)
                interval = min(interval * 1.3, 60.0)

            results.append(make_status(
                "video", False,
                f"All download attempts failed after {VIDEO_POLL_TIMEOUT}s",
            ))
            print(f"  Video: all download attempts failed")

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

        media_paths["notebook_id"] = notebook_id
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


def print_chrome_fallback(failed_steps, notebook_id=None):
    """Print instructions for Chrome-based manual generation."""
    nb_id = notebook_id or NOTEBOOK_ID
    print("\n" + "=" * 60)
    print("CHROME FALLBACK — Manual steps needed:")
    print("=" * 60)
    print(f"\nThe following steps failed via API: {', '.join(failed_steps)}")
    print(f"\nNotebook: https://notebooklm.google.com/notebook/{nb_id}")
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
    parser.add_argument("--diff-file",
                        help="Path to differentiation context text file")
    parser.add_argument("--focus",
                        help="Dynamic audio/video focus instructions (overrides default)")
    parser.add_argument("--infographic-focus",
                        help="Custom infographic visual direction prompt (overrides default)")
    parser.add_argument("--video-focus",
                        help="Custom cinematic video direction prompt (overrides default)")
    parser.add_argument("--visual-script-file",
                        help="Path to visual production script for cinematic video (added as notebook source)")
    parser.add_argument("--infographic-source-file",
                        help="Path to infographic visual direction source (added as notebook source)")
    parser.add_argument("--new-notebook", action="store_true",
                        help="Create a new notebook instead of reusing the permanent Koda one")
    parser.add_argument("--notebook-title",
                        help="Title for the new notebook (requires --new-notebook)")
    parser.add_argument("--notebook-id",
                        help="Use an existing notebook by ID (skips creation and source cleanup)")
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

    # Read optional differentiation text
    diff_text = None
    if args.diff_file:
        with open(args.diff_file, "r", encoding="utf-8") as f:
            diff_text = f.read().strip()

    # Read optional visual script
    visual_script = None
    if args.visual_script_file:
        with open(args.visual_script_file, "r", encoding="utf-8") as f:
            visual_script = f.read().strip()

    # Read optional infographic source
    infographic_source = None
    if args.infographic_source_file:
        with open(args.infographic_source_file, "r", encoding="utf-8") as f:
            infographic_source = f.read().strip()

    os.makedirs(args.output_dir, exist_ok=True)

    print(f"Koda Digest Media Generator")
    print(f"Date: {args.date}")
    print(f"Output: {os.path.abspath(args.output_dir)}")
    print(f"Text: {len(text_content)} characters")
    print(f"Differentiation: {'yes' if diff_text else 'no'}")
    print(f"Visual script: {'yes' if visual_script else 'no'}")
    print(f"Infographic source: {'yes' if infographic_source else 'no'}")
    print(f"Focus: {'custom' if args.focus else 'default'}")
    print(f"Infographic: {'custom prompt' if args.infographic_focus else 'default prompt'}")
    print(f"Video: {'skip' if args.skip_video else 'cinematic'}")
    print(f"Video prompt: {'custom' if args.video_focus else 'default'}")
    if args.notebook_id:
        print(f"Notebook: existing ({args.notebook_id})")
    elif args.new_notebook:
        print(f"Notebook: NEW")
    else:
        print(f"Notebook: permanent (Koda)")
    if args.notebook_title:
        print(f"Notebook title: {args.notebook_title}")
    print()

    # Run the async pipeline
    results, media_paths, exit_code = asyncio.run(
        run_pipeline(text_content, args.date, args.output_dir, args.skip_video,
                     diff_text=diff_text, audio_focus=args.focus,
                     infographic_focus=args.infographic_focus,
                     video_focus=args.video_focus,
                     visual_script=visual_script,
                     infographic_source=infographic_source,
                     new_notebook=args.new_notebook,
                     notebook_title=args.notebook_title,
                     existing_notebook_id=args.notebook_id)
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
    actual_notebook_id = media_paths.get("notebook_id")
    failed = [r["step"] for r in results
              if not r["success"] and r["step"] in ("audio", "infographic", "video")]
    if failed:
        print_chrome_fallback(failed, notebook_id=actual_notebook_id)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
