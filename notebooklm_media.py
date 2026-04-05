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
    "This is a conversation between two people who genuinely find this stuff fascinating. "
    "You are telling a friend the most interesting things that happened today -- not reading "
    "a briefing document. Open with the single most surprising thing and why it matters to "
    "someone's actual life or career. Make them lean in within the first 10 seconds. "
    "\n\n"
    "HOST CHEMISTRY: One host drives the story forward. The other asks the question the "
    "audience is thinking -- 'Wait, what does that actually mean?' or 'Why should I care "
    "about that?' This creates natural explanation moments without feeling like a lecture. "
    "When a technical term comes up, the second host should genuinely ask about it, and the "
    "first host explains it with a real-world comparison. For example: 'That is like having "
    "a brain 5x larger than anything we had last year, and they gave it away for free.' "
    "\n\n"
    "WHAT TO BAN: Never say 'moving on to', 'let us shift to', 'in other news', or 'on "
    "the AI front'. These are robot transitions. Instead, connect stories naturally -- 'and "
    "here is the thing, while that was happening...' or 'which makes this next part wild...' "
    "\n\n"
    "PACING: Spend real time on the 2-3 stories that matter most. Go deep on those. When a "
    "big number drops, pause and let it land. If something is genuinely absurd or surprising, "
    "react like a real person would. Rush through the minor stories. It is okay to say 'quick "
    "hits' and rattle through three things in 30 seconds. "
    "\n\n"
    "EMOTIONAL RANGE: Be excited when something is exciting. Be concerned when something is "
    "concerning. Be skeptical when a claim sounds too good. Do not maintain one flat "
    "authoritative tone the entire time. Real conversations have energy shifts. "
    "\n\n"
    "END EACH TOPIC with a forward-looking question, not a conclusion. 'So the real question "
    "is...' or 'What I want to know is...' This pulls the listener forward. "
    "\n\n"
    "JARGON RULE: When you hit a term like parameter counts, context windows, mixture-of-experts, "
    "or open-weight -- the second host should jump in with genuine curiosity, not obligation. "
    "'Okay wait, explain that for me' feels natural. 'For our listeners who may not know' "
    "feels condescending. Always the first one."
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
    "Create a cinematic story about real people building, discovering, and adapting in a "
    "world of rapid progress. This is not a warning -- it is a window into what is becoming "
    "possible. Every frame should make a viewer feel something -- curiosity, momentum, wonder, "
    "or possibility. Push Veo 3 visual quality to its maximum. "
    "\n\n"
    "THE PERSON RULE: Every scene needs a personal anchor. A hand reaching for a phone. A face "
    "lit by a laptop screen, focused and intent. Someone walking through a bustling office. A "
    "team gathered around a screen. Someone smiling at a result. Technology is always the "
    "backdrop, never the subject. The subject is what this means for a real person watching "
    "this video over breakfast. "
    "\n\n"
    "STRUCTURE & NARRATIVE: "
    "Cold open (0:00-0:15): Start with a moment, not a headline. Drop the viewer into a scene "
    "that makes them ask 'what is happening?' Narration opens with a question or a surprising "
    "fact that a non-technical person would find fascinating. "
    "Act 1 -- The Signal (0:15-1:30): The story that matters today. Show why a real person "
    "should care, and what it opens up. Wide establishing shots, then find the person in the "
    "frame. Build engagement through faces and reactions. Let the audience see why this matters. "
    "Act 2 -- The Build (1:30-3:00): The technology story. But tell it through what it unlocks "
    "for people, not what the specs are. Show someone using it, building with it, benefiting "
    "from it. Transition palette from warm to cool. Data visualizations should feel alive -- "
    "flowing, organic, not clinical. "
    "Act 3 -- The Unlock (3:00-4:00): Where today's signal meets today's tools in someone's "
    "actual life. Not conflict -- convergence. How does the development from Act 1 connect "
    "with what was built in Act 2? Show a person connecting the dots. Build to a possibility, "
    "not just a question. "
    "Close (4:00-4:30): End on a person in motion. Someone heading out with energy. A city in "
    "full swing. A hand starting something new. Hold the frame -- the day is just beginning. "
    "\n\n"
    "VISUAL DIRECTION PER SCENE: "
    "Signal scenes: Find the person first, then reveal the scale around them. A person checking "
    "news on a phone, then pull back to show the trading floor behind them. Warm amber-gold "
    "color grading. Handheld camera for intimacy and connection. "
    "Build scenes: People interacting with technology -- fingers on keyboards, screens "
    "reflecting in glasses, a developer leaning back from a monitor with satisfaction. Data "
    "center interiors with a person walking through, dwarfed by the scale. Cool blue-cyan "
    "grading. Smooth dolly movements for wonder. "
    "Unlock scenes: Split-screen or morphing transitions with personal continuity -- a hand "
    "swiping a phone dissolves into a hand on a control panel. Same person, expanded world. "
    "Closing shot: Personal momentum. Purposeful. Forward. "
    "\n\n"
    "CINEMATOGRAPHY: "
    "Lighting: Golden hour warmth for personal moments, cool fluorescent for tech interiors, "
    "bright mixed palette for the unlock act. "
    "Camera movement: Slow dolly pushes for emotional beats, smooth crane shots for scale, "
    "subtle handheld for genuine moments. "
    "Depth of field: Shallow focus on faces and hands, deep focus for establishing shots. "
    "Transitions: Dissolves and morphs, never hard cuts. "
    "Color palette: warm amber (signal), cool blue (build), bright mixed (unlock), warm "
    "energized (closing). "
    "\n\n"
    "NARRATION TONE: Like a friend who just got back from covering a story and cannot wait to "
    "tell you about it. Genuine, not performative. Curious, not authoritative. When describing "
    "something incredible, let the wonder show. When describing something challenging, frame it "
    "honestly but show what people are doing about it. This is not a newscast -- it is a story "
    "that leaves people feeling informed and energized, not anxious. "
    "\n\n"
    "STRICT RULE -- NO POLITICAL FIGURES: Do NOT show any recognizable political figures, "
    "heads of state, politicians, or government officials. No faces of presidents, prime "
    "ministers, generals, or named political leaders. Use abstract representations: empty "
    "podiums, building exteriors, flags, diplomatic tables, military hardware without "
    "identifiable personnel, policy documents, press briefing rooms without people. "
    "\n\n"
    "TECHNICAL STABILIZERS (apply to ALL scenes): "
    "Maintain subject center-frame stability in all shots. "
    "Consistent shadow direction within each act. "
    "Prevent horizon warping on drone and crane movements. "
    "Preserve architectural geometry in all environment shots. "
    "Lock screen text legibility on any data visualizations. "
    "Smooth interpolation on all transitions -- dissolves over hard cuts. "
    "\n\n"
    "SENSORY TEXTURE (layer into every scene): "
    "Morning light through windows, steam from coffee cups, dust motes caught in shafts of "
    "light. Screen reflections on faces and polished surfaces. Phone notifications, the warm "
    "glow of a laptop in a focused workspace. "
    "Depth particles: atmospheric haze, bokeh light points, golden hour flare. "
    "Material textures: brushed metal, polished glass, warm wood, clean concrete."
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

            # Clean old studio artifacts (audio, video, infographic, etc.)
            print("  Cleaning old studio artifacts...")
            try:
                artifacts = await client.artifacts.list(notebook_id)
                art_deleted = 0
                for art in artifacts:
                    try:
                        await client.artifacts.delete(notebook_id, art.id)
                        art_deleted += 1
                        print(f"    Deleted {art.kind}: {art.title or art.id[:16]}")
                        await asyncio.sleep(1)
                    except Exception as e:
                        print(f"    Warning: Could not delete artifact {art.id}: {e}")
                results.append(make_status("clean_artifacts", True,
                               f"Deleted {art_deleted} old artifacts"))
                print(f"  Deleted {art_deleted} old artifacts.")
            except Exception as e:
                results.append(make_status("clean_artifacts", False, str(e)))
                print(f"  Warning: Could not clean artifacts: {e}")

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
            if not r["success"] and r["step"] not in ("clean_sources", "clean_artifacts"):
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


# ── Editorial Media Pipeline ────────────────────────────────────────────────


async def run_editorial_pipeline(
    article_text: str,
    date_str: str,
    output_dir: str,
    video_direction: str | None = None,
    audio_direction: str | None = None,
    existing_notebook_id: str | None = None,
    create_new_notebook: bool = False,
) -> tuple[list[dict], dict, int]:
    """Run the editorial media pipeline: brief anime video + brief audio overview.

    When create_new_notebook=True, creates a dedicated notebook for editorial
    media to avoid artifact collision with the permanent digest notebook.
    Otherwise uses existing_notebook_id or the permanent Koda notebook.

    Returns: (results_list, media_paths_dict, exit_code)
    """
    from notebooklm import (NotebookLMClient, AudioFormat, AudioLength,
                            InfographicOrientation, InfographicDetail,
                            VideoFormat, VideoStyle)

    results: list[dict] = []
    media_paths: dict[str, str] = {}
    notebook_id = existing_notebook_id or NOTEBOOK_ID

    client_cm = await NotebookLMClient.from_storage()
    try:
        client = await client_cm.__aenter__()
        print(f"\n[Editorial] Authenticated with NotebookLM")
    except Exception as e:
        error_msg = str(e)
        if "token" in error_msg.lower() or "cookie" in error_msg.lower():
            print("\nAUTH EXPIRED. Run:  python notebooklm_login.py")
            return [make_status("auth", False, error_msg)], {}, 2
        raise

    created_notebook = False
    try:
        # Create a new notebook if requested (avoids artifact collision)
        if create_new_notebook:
            print(f"[E0/5] Creating dedicated editorial notebook...")
            nb = await client.notebooks.create(f"Koda Editorial {date_str}")
            notebook_id = nb.id
            created_notebook = True
            print(f"  Created notebook: {notebook_id}")

        # ── Step E1: Clean old sources ──────────────────────────────────
        print("[E1/5] Cleaning old notebook sources for editorial...")
        try:
            old_sources = await client.sources.list(notebook_id)
            if old_sources:
                for src in old_sources:
                    await client.sources.delete(notebook_id, src.source_id)
                results.append(make_status("clean_sources", True,
                                           f"Removed {len(old_sources)} old sources"))
                print(f"  Removed {len(old_sources)} old sources")
            else:
                results.append(make_status("clean_sources", True, "No sources to clean"))
                print("  No sources to clean")
        except Exception as e:
            results.append(make_status("clean_sources", False, str(e)))
            print(f"  Warning: Could not clean sources: {e}")

        await asyncio.sleep(2)

        # ── Step E2: Upload editorial sources ───────────────────────────
        print("[E2/5] Uploading editorial sources...")

        # E2a: Article text
        try:
            await client.sources.add_text(
                notebook_id,
                f"Editorial Deep Dive -- {date_str}",
                article_text,
                wait=True,
            )
            results.append(make_status("add_editorial_text", True,
                                       f"Added {len(article_text)} chars article"))
            print(f"  Added editorial article ({len(article_text)} chars)")
            await asyncio.sleep(2)
        except Exception as e:
            results.append(make_status("add_editorial_text", False, str(e)))
            print(f"  ERROR: Could not add editorial text: {e}")
            # Fatal -- can't generate without the article
            return results, media_paths, 1

        # E2b: Video direction (if provided)
        if video_direction:
            try:
                await client.sources.add_text(
                    notebook_id,
                    f"Editorial Video Direction -- {date_str}",
                    video_direction,
                    wait=True,
                )
                results.append(make_status("add_editorial_video_dir", True,
                                           f"Added {len(video_direction)} chars video direction"))
                print(f"  Added video direction ({len(video_direction)} chars)")
                await asyncio.sleep(2)
            except Exception as e:
                results.append(make_status("add_editorial_video_dir", False, str(e)))
                print(f"  Warning: Could not add video direction: {e}")

        # E2c: Audio direction (if provided)
        if audio_direction:
            try:
                await client.sources.add_text(
                    notebook_id,
                    f"Editorial Audio Direction -- {date_str}",
                    audio_direction,
                    wait=True,
                )
                results.append(make_status("add_editorial_audio_dir", True,
                                           f"Added {len(audio_direction)} chars audio direction"))
                print(f"  Added audio direction ({len(audio_direction)} chars)")
                await asyncio.sleep(2)
            except Exception as e:
                results.append(make_status("add_editorial_audio_dir", False, str(e)))
                print(f"  Warning: Could not add audio direction: {e}")

        # ── Step E3: PARALLEL generation (brief video + brief audio) ────
        print("[E3/5] Triggering editorial media generation in PARALLEL...")

        editorial_audio_path = Path(output_dir) / f"editorial-podcast-{date_str}.mp3"
        editorial_video_path = Path(output_dir) / f"editorial-video-{date_str}.mp4"

        # Build focus prompts from direction docs
        audio_focus = audio_direction or (
            f"Brief overview of the editorial article for {date_str}. "
            f"Single-topic deep analysis. Conversational expert tone."
        )
        video_focus = video_direction or (
            f"Brief anime-style overview of the editorial article for {date_str}."
        )

        async def start_editorial_audio():
            s = await client.artifacts.generate_audio(
                notebook_id,
                instructions=audio_focus,
                audio_format=AudioFormat.BRIEF,
                audio_length=AudioLength.SHORT,
            )
            print(f"  Editorial audio generation started (task: {s.task_id})")
            return s

        async def start_editorial_video():
            s = await client.artifacts.generate_video(
                notebook_id,
                instructions=video_focus,
                video_format=VideoFormat.BRIEF,
                video_style=VideoStyle.ANIME,
            )
            print(f"  Editorial video generation started (task: {s.task_id})")
            return s

        try:
            gen_results = await asyncio.gather(
                start_editorial_audio(),
                start_editorial_video(),
                return_exceptions=True,
            )
        except Exception as e:
            print(f"  Error launching editorial generation: {e}")
            gen_results = [e, e]

        audio_status = gen_results[0] if not isinstance(gen_results[0], Exception) else None
        video_status = gen_results[1] if not isinstance(gen_results[1], Exception) else None

        if isinstance(gen_results[0], Exception):
            print(f"  Editorial audio launch failed: {gen_results[0]}")
        if isinstance(gen_results[1], Exception):
            print(f"  Editorial video launch failed: {gen_results[1]}")

        # ── Step E4: Wait for completion + download ─────────────────────
        print("[E4/5] Waiting for editorial media to complete...")

        async def complete_editorial_audio():
            if not audio_status:
                return
            await client.artifacts.wait_for_completion(
                notebook_id, audio_status.task_id, timeout=1800.0
            )
            raw_audio = Path(output_dir) / f"editorial-podcast-raw-{date_str}.wav"
            await client.artifacts.download_audio(notebook_id, str(raw_audio))
            print(f"  Editorial audio downloaded")
            ok, detail = compress_audio(raw_audio, editorial_audio_path)
            if ok:
                results.append(make_status("editorial_audio", True, detail,
                                           str(editorial_audio_path)))
                media_paths["editorial_podcast"] = str(editorial_audio_path)
                print(f"  Editorial audio compressed: {editorial_audio_path}")
                try:
                    raw_audio.unlink()
                except OSError:
                    pass
            else:
                results.append(make_status("editorial_audio", False,
                                           f"Compression failed: {detail}"))
                print(f"  Editorial audio compression failed: {detail}")

        async def complete_editorial_video():
            if not video_status:
                return
            # Remove stale files so download_video rename doesn't fail on Windows
            for stale in (editorial_video_path, Path(str(editorial_video_path) + ".tmp")):
                try:
                    stale.unlink()
                except OSError:
                    pass
            # Brief videos are typically fast (~5 min); use shorter timeout
            try:
                await client.artifacts.wait_for_completion(
                    notebook_id, video_status.task_id, timeout=600.0
                )
                await client.artifacts.download_video(
                    notebook_id, str(editorial_video_path)
                )
                results.append(make_status("editorial_video", True,
                                           "Downloaded",
                                           str(editorial_video_path)))
                media_paths["editorial_video"] = str(editorial_video_path)
                print(f"  Editorial video downloaded: {editorial_video_path}")
                return
            except TimeoutError:
                print("    Editorial video wait timed out, trying direct downloads...")
            except Exception as e:
                print(f"    Editorial video wait error: {e}, trying direct downloads...")

            # Retry with polling (same pattern as main pipeline)
            start = time.monotonic()
            interval = 10.0
            attempt = 0
            while time.monotonic() - start < 900.0:  # 15 min max for brief
                attempt += 1
                elapsed = time.monotonic() - start
                # Clean stale files before each retry (Windows rename compat)
                for stale in (editorial_video_path, Path(str(editorial_video_path) + ".tmp")):
                    try:
                        stale.unlink()
                    except OSError:
                        pass
                try:
                    await client.artifacts.download_video(
                        notebook_id, str(editorial_video_path)
                    )
                    results.append(make_status(
                        "editorial_video", True,
                        f"Downloaded (attempt #{attempt}, {elapsed:.0f}s)",
                        str(editorial_video_path),
                    ))
                    media_paths["editorial_video"] = str(editorial_video_path)
                    print(f"  Editorial video downloaded (attempt #{attempt}, {elapsed:.0f}s)")
                    return
                except Exception as e:
                    print(f"    Editorial video attempt #{attempt} ({elapsed:.0f}s): {e}")
                await asyncio.sleep(interval)
                interval = min(interval * 1.3, 30.0)

            results.append(make_status(
                "editorial_video", False,
                "All download attempts failed after 900s",
            ))
            print("  Editorial video: all download attempts failed")

        completion_results = await asyncio.gather(
            complete_editorial_audio(),
            complete_editorial_video(),
            return_exceptions=True,
        )
        for i, r in enumerate(completion_results):
            if isinstance(r, Exception):
                step_name = ["editorial_audio", "editorial_video"][i]
                results.append(make_status(step_name, False, str(r)))
                print(f"  {step_name} failed: {r}")

        # ── Step E5: Summary ────────────────────────────────────────────
        print("\n[E5/5] Editorial media summary:")
        exit_code = 0
        for r in results:
            icon = "OK" if r["success"] else "FAIL"
            print(f"  [{icon}] {r['step']}: {r['detail']}")
            if not r["success"] and r["step"] in ("editorial_audio", "editorial_video"):
                exit_code = 1

        media_paths["notebook_id"] = notebook_id

        # Clean up temp notebook (don't leave orphan notebooks)
        if created_notebook:
            try:
                await client.notebooks.delete(notebook_id)
                print(f"  Cleaned up temp editorial notebook: {notebook_id}")
            except Exception as e2:
                print(f"  Warning: could not delete temp notebook: {e2}")

        return results, media_paths, exit_code

    except Exception as e:
        error_msg = str(e)
        if "token" in error_msg.lower() or "401" in error_msg or "403" in error_msg:
            print("\nAUTH EXPIRED during editorial generation.")
            print("Run:  python notebooklm_login.py")
            results.append(make_status("auth_mid", False, error_msg))
            return results, media_paths, 2
        raise
    finally:
        try:
            await client_cm.__aexit__(None, None, None)
        except Exception:
            pass


# ── Entry Point ──────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Generate Koda Digest media via NotebookLM API")
    text_group = parser.add_mutually_exclusive_group(required=False)
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

    # Editorial media arguments
    parser.add_argument("--skip-digest", action="store_true",
                        help="Skip digest media generation (only run editorial pipeline)")
    parser.add_argument("--editorial-file",
                        help="Path to editorial article text file (triggers editorial media pipeline)")
    parser.add_argument("--editorial-video-direction",
                        help="Path to editorial video direction text file")
    parser.add_argument("--editorial-audio-direction",
                        help="Path to editorial audio direction text file")

    args = parser.parse_args()

    # Read text content (not required when --skip-digest)
    text_content = ""
    if args.text_file:
        with open(args.text_file, "r", encoding="utf-8") as f:
            text_content = f.read().strip()
    elif args.text:
        text_content = args.text.strip()

    if not args.skip_digest and len(text_content) < 100:
        print("ERROR: Text content too short (< 100 chars). Provide --text-file or --text.")
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
    if args.editorial_file:
        print(f"Editorial: {args.editorial_file}")
    print()

    # Run the digest media pipeline (unless --skip-digest)
    actual_notebook_id = None
    if args.skip_digest:
        print("Skipping digest media pipeline (--skip-digest)")
        results, media_paths, exit_code = [], {}, 0
    else:
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

    # ── Editorial media pipeline (if --editorial-file provided) ─────────
    if args.editorial_file:
        print("\n" + "=" * 60)
        print("EDITORIAL MEDIA PIPELINE")
        print("=" * 60)

        with open(args.editorial_file, "r", encoding="utf-8") as f:
            editorial_text = f.read().strip()

        if len(editorial_text) < 100:
            print("WARNING: Editorial text too short (< 100 chars). Skipping editorial media.")
        else:
            # Read optional direction files
            editorial_video_dir = None
            if args.editorial_video_direction:
                with open(args.editorial_video_direction, "r", encoding="utf-8") as f:
                    editorial_video_dir = f.read().strip()

            editorial_audio_dir = None
            if args.editorial_audio_direction:
                with open(args.editorial_audio_direction, "r", encoding="utf-8") as f:
                    editorial_audio_dir = f.read().strip()

            print(f"Editorial text: {len(editorial_text)} chars")
            print(f"Video direction: {'yes' if editorial_video_dir else 'no'}")
            print(f"Audio direction: {'yes' if editorial_audio_dir else 'no'}")
            print()

            # Use new notebook for editorial when --new-notebook is set,
            # to avoid artifact collision with digest in permanent notebook.
            ed_notebook_id = actual_notebook_id
            if args.new_notebook or actual_notebook_id is None:
                ed_notebook_id = None  # signals run_editorial_pipeline to create new

            ed_results, ed_media, ed_exit = asyncio.run(
                run_editorial_pipeline(
                    editorial_text,
                    args.date,
                    args.output_dir,
                    video_direction=editorial_video_dir,
                    audio_direction=editorial_audio_dir,
                    existing_notebook_id=ed_notebook_id,
                    create_new_notebook=args.new_notebook,
                )
            )

            # Write editorial media status
            ed_status = {
                "date": args.date,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "exit_code": ed_exit,
                "editorial_audio": {
                    "success": bool(ed_media.get("editorial_podcast")),
                    "path": ed_media.get("editorial_podcast", ""),
                },
                "editorial_video": {
                    "success": bool(ed_media.get("editorial_video")),
                    "path": ed_media.get("editorial_video", ""),
                },
            }
            ed_status_path = os.path.join(args.output_dir, "editorial-media-status.json")
            with open(ed_status_path, "w", encoding="utf-8") as f:
                json.dump(ed_status, f, indent=2)
            print(f"\nEditorial media status written to: {ed_status_path}")

            if args.json:
                print(json.dumps(ed_status, indent=2))

            # Merge exit code -- worst of both
            if ed_exit > exit_code:
                exit_code = ed_exit

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
