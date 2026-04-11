"""
Generate branded YouTube thumbnails (1280x720) for Koda videos.

Two-stage approach:
  1. Gemini Imagen 4 generates a bold, topic-specific base image
  2. PIL composites title text, section badge, gradient bar, and branding

Fallback chain: Gemini base -> hero image -> solid dark canvas.

Usage (standalone):
    python -m pipeline.generate_thumbnail \
        --topic "AI arms race heats up" \
        --section signal \
        --date 2026-04-11 \
        --hero hero-2026-04-11.jpg \
        --video-id UYDIX_C7WO4

Usage (from pipeline):
    from pipeline.generate_thumbnail import create_thumbnail, set_thumbnail_on_youtube
    path = create_thumbnail(topic=hook, section="signal", date=date, hero_path=hero)
    if path:
        set_thumbnail_on_youtube(video_id, path)
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ── Paths ───────────────────────────────────────────────────────────────────

DIGEST_DIR = Path(__file__).resolve().parent.parent

# ── Constants ───────────────────────────────────────────────────────────────

THUMB_W, THUMB_H = 1280, 720
BG_COLOR = (11, 19, 38)  # #0b1326 (Koda dark navy)
GRADIENT_BLUE = (59, 130, 246)   # #3B82F6
GRADIENT_PURPLE = (139, 92, 246)  # #8B5CF6

SECTION_STYLES = {
    "signal": {
        "badge_bg": GRADIENT_BLUE,
        "badge_label": "THE SIGNAL",
        "gradient_left": GRADIENT_BLUE,
        "gradient_right": GRADIENT_PURPLE,
    },
    "editorial": {
        "badge_bg": GRADIENT_PURPLE,
        "badge_label": "DEEP DIVE",
        "gradient_left": GRADIENT_PURPLE,
        "gradient_right": GRADIENT_BLUE,
    },
}

# Font fallback chain (Windows -> Linux/Railway -> ultimate fallback)
FONT_BOLD = "segoeuib.ttf"
FONT_SEMI = "seguisb.ttf"
FONT_FALLBACK = "arialbd.ttf"


# ── Font helpers ────────────────────────────────────────────────────────────

def _load_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    """Load a font with fallback chain."""
    for candidate in [name, FONT_FALLBACK, "DejaVuSans-Bold.ttf"]:
        try:
            return ImageFont.truetype(candidate, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Word-wrap text to fit within max_width pixels."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = font.getbbox(test)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


# ── Title shortening ────────────────────────────────────────────────────────

def shorten_title(topic: str, max_chars: int = 45) -> str:
    """Shorten a long topic/hook into a punchy thumbnail title.

    YouTube thumbnails need short text (6-10 words) for readability at
    small sizes. This truncates at the nearest colon, period, or word
    boundary to keep the title punchy.
    """
    if len(topic) <= max_chars:
        return topic

    # Try splitting at a colon first (common in hooks)
    if ":" in topic[:max_chars]:
        return topic[:topic.index(":") + 1].strip()

    # Try splitting at a sentence-ending period (followed by space) or dash
    for sep in [". ", " -- ", " - "]:
        idx = topic.find(sep)
        if 0 < idx <= max_chars:
            return topic[:idx].strip()

    # Word-boundary truncation
    truncated = topic[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > max_chars // 2:
        return truncated[:last_space].strip()

    return truncated.strip()


# ── Gemini prompt generation ────────────────────────────────────────────────

def generate_thumbnail_prompt(topic: str, section: str) -> str:
    """Craft a Gemini Imagen prompt for a bold, click-worthy thumbnail base image.

    The image should be visually striking at small sizes (YouTube sidebar)
    with bold, simple compositions and dramatic lighting.
    """
    # Truncate topic to keep prompt focused
    topic_short = topic[:200] if len(topic) > 200 else topic

    if section == "editorial":
        return (
            f"A bold anime-style conceptual illustration for a tech analysis video thumbnail. "
            f"The theme is: {topic_short}. "
            f"Use vivid saturated colors, dramatic cel-shaded lighting, strong geometric composition. "
            f"Dark background with glowing elements. Abstract and conceptual, not literal. "
            f"Cinematic widescreen composition (16:9 aspect ratio). "
            f"NO text, NO words, NO letters, NO watermarks, NO logos. "
            f"High contrast, visually striking even at small sizes."
        )

    # Signal (default): cinematic photorealistic news imagery
    return (
        f"A dramatic, cinematic photorealistic image for a daily AI news video thumbnail. "
        f"The theme is: {topic_short}. "
        f"Dark moody lighting with blue and purple accent tones. "
        f"Bold composition with a single powerful focal point. "
        f"Futuristic technology aesthetic, editorial news photography style. "
        f"Cinematic widescreen composition (16:9 aspect ratio). "
        f"NO text, NO words, NO letters, NO watermarks, NO logos, NO faces of real people. "
        f"High contrast, dramatic shadows, visually striking at small sizes."
    )


# ── Image generation ────────────────────────────────────────────────────────

def _generate_base_image(prompt: str, output_path: str) -> bool:
    """Generate a base thumbnail image via Gemini Imagen 4."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("  Thumbnail: GEMINI_API_KEY not set, skipping Gemini base image")
        return False

    gemini_script = DIGEST_DIR / "gemini_image.py"
    if not gemini_script.exists():
        print(f"  Thumbnail: gemini_image.py not found at {gemini_script}")
        return False

    cmd = [
        sys.executable, str(gemini_script),
        "--prompt", prompt,
        "--output", output_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0 and Path(output_path).exists():
            size_kb = Path(output_path).stat().st_size // 1024
            print(f"  Thumbnail: Gemini base image generated ({size_kb}KB)")
            return True
        print(f"  Thumbnail: Gemini generation failed (exit {result.returncode})")
        if result.stderr:
            print(f"    {result.stderr[-200:]}")
    except subprocess.TimeoutExpired:
        print("  Thumbnail: Gemini generation timed out (120s)")
    except Exception as e:
        print(f"  Thumbnail: Gemini error: {e}")

    return False


# ── PIL compositing ─────────────────────────────────────────────────────────

def _draw_gradient_bar(
    draw: ImageDraw.Draw,
    y: int,
    height: int,
    left_color: tuple[int, int, int],
    right_color: tuple[int, int, int],
    width: int = THUMB_W,
) -> None:
    """Draw a horizontal gradient bar."""
    for x in range(width):
        t = x / width
        r = int(left_color[0] + (right_color[0] - left_color[0]) * t)
        g = int(left_color[1] + (right_color[1] - left_color[1]) * t)
        b = int(left_color[2] + (right_color[2] - left_color[2]) * t)
        draw.line([(x, y), (x, y + height - 1)], fill=(r, g, b))


def _composite_thumbnail(
    base_image_path: str,
    title: str,
    section: str,
    output_path: str,
) -> bool:
    """Composite branding, title, and badges onto a base image.

    Creates a 1280x720 YouTube thumbnail with:
    - Base image (blurred + dark overlay)
    - Large bold title (max 2 lines, heavy drop shadow)
    - Section badge (top-left)
    - Gradient bar (bottom)
    - Brand mark (bottom-left)
    """
    try:
        style = SECTION_STYLES.get(section, SECTION_STYLES["signal"])

        # Load fonts
        font_title = _load_font(FONT_BOLD, 58)
        font_badge = _load_font(FONT_SEMI, 20)
        font_domain = _load_font(FONT_SEMI, 18)
        font_k = _load_font(FONT_BOLD, 20)

        # Create canvas
        canvas = Image.new("RGB", (THUMB_W, THUMB_H), BG_COLOR)

        # Load base image and scale to cover
        if Path(base_image_path).exists():
            base = Image.open(base_image_path).convert("RGB")
            scale = max(THUMB_W / base.width, THUMB_H / base.height)
            new_w = int(base.width * scale)
            new_h = int(base.height * scale)
            base = base.resize((new_w, new_h), Image.LANCZOS)

            # Center crop to thumbnail dimensions
            left = (new_w - THUMB_W) // 2
            top = (new_h - THUMB_H) // 2
            base = base.crop((left, top, left + THUMB_W, top + THUMB_H))

            # Light blur for readability (less than OG cards since this IS the visual)
            base = base.filter(ImageFilter.GaussianBlur(radius=2))
            canvas.paste(base, (0, 0))

        # Dark overlay (45% opacity -- lighter than OG cards for more visual pop)
        overlay = Image.new("RGBA", (THUMB_W, THUMB_H), (11, 19, 38, 115))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")

        draw = ImageDraw.Draw(canvas)

        # ── Bottom gradient bar (6px) ───────────────────────────────────
        _draw_gradient_bar(
            draw, THUMB_H - 6, 6,
            style["gradient_left"], style["gradient_right"],
        )

        # ── Top accent bar (3px) ────────────────────────────────────────
        _draw_gradient_bar(
            draw, 0, 3,
            style["gradient_left"], style["gradient_right"],
        )

        # ── Section badge (top-left) ────────────────────────────────────
        badge_text = style["badge_label"]
        badge_bbox = font_badge.getbbox(badge_text)
        badge_w = badge_bbox[2] - badge_bbox[0] + 28
        badge_h = badge_bbox[3] - badge_bbox[1] + 16
        badge_x, badge_y = 48, 36
        draw.rounded_rectangle(
            [badge_x, badge_y, badge_x + badge_w, badge_y + badge_h],
            radius=8, fill=style["badge_bg"],
        )
        draw.text(
            (badge_x + 14, badge_y + 6), badge_text,
            fill=(255, 255, 255), font=font_badge,
        )

        # ── Title text (large, bold, max 2 lines) ──────────────────────
        text_x = 48
        max_text_w = THUMB_W - 96  # 48px padding each side
        lines = _wrap_text(title, font_title, max_text_w)

        # Limit to 2 lines for thumbnail readability
        if len(lines) > 2:
            lines = lines[:2]
            if len(lines[1]) > 45:
                lines[1] = lines[1][:42] + "..."

        line_height = 72
        total_text_h = len(lines) * line_height
        # Center title vertically (shifted slightly below center)
        text_start_y = (THUMB_H - total_text_h) // 2 + 30

        for i, line in enumerate(lines):
            y = text_start_y + i * line_height
            # Heavy drop shadow for small-size readability
            for offset in [(3, 3), (2, 2), (1, 1)]:
                draw.text(
                    (text_x + offset[0], y + offset[1]), line,
                    fill=(0, 0, 0), font=font_title,
                )
            # Main white text
            draw.text((text_x, y), line, fill=(255, 255, 255), font=font_title)

        # ── Brand mark (bottom-left) ────────────────────────────────────
        k_size = 30
        k_x, k_y = 48, THUMB_H - 52
        draw.rounded_rectangle(
            [k_x, k_y, k_x + k_size, k_y + k_size],
            radius=7, fill=(99, 102, 241),  # #6366F1
        )
        draw.text((k_x + 8, k_y + 3), "K", fill=(255, 255, 255), font=font_k)
        draw.text(
            (k_x + k_size + 10, k_y + 5), "koda.community",
            fill=(194, 198, 214), font=font_domain,
        )

        # ── Save with quality stepping (<2MB for YouTube) ──────────────
        canvas = canvas.convert("RGB")
        for quality in (92, 85, 78, 70, 60):
            canvas.save(output_path, "JPEG", quality=quality, optimize=True)
            if Path(output_path).stat().st_size < 2_000_000:
                size_kb = Path(output_path).stat().st_size // 1024
                print(f"  Thumbnail: composited ({size_kb}KB, q={quality})")
                return True

        # Last resort: save at minimum quality
        canvas.save(output_path, "JPEG", quality=50, optimize=True)
        return True

    except Exception as e:
        print(f"  Thumbnail: compositing failed: {e}")
        import traceback
        traceback.print_exc()
        return False


# ── Orchestrator ────────────────────────────────────────────────────────────

def create_thumbnail(
    topic: str,
    section: str,
    date: str,
    hero_path: str | None = None,
    output_dir: str | None = None,
    skip_gemini: bool = False,
) -> str | None:
    """Generate a branded YouTube thumbnail.

    Fallback chain:
      1. Gemini Imagen 4 base image + PIL composite
      2. Hero image + PIL composite
      3. Solid dark canvas + PIL composite

    Returns the output path on success, None on failure.
    """
    out_dir = Path(output_dir) if output_dir else DIGEST_DIR
    output_path = str(out_dir / f"thumbnail-{section}-{date}.jpg")
    gemini_base = str(out_dir / f"_thumb-base-{section}-{date}.jpg")

    print(f"\n  Generating {section} thumbnail for {date}...")

    # Stage 1: Generate base image
    base_image_path = None

    if not skip_gemini:
        prompt = generate_thumbnail_prompt(topic, section)
        if _generate_base_image(prompt, gemini_base):
            base_image_path = gemini_base

    if not base_image_path and hero_path and Path(hero_path).exists():
        print(f"  Thumbnail: using hero image as base ({hero_path})")
        base_image_path = hero_path

    if not base_image_path:
        print("  Thumbnail: no base image available, using solid canvas")
        # _composite_thumbnail handles missing base gracefully
        base_image_path = "__nonexistent__"

    # Stage 2: Composite text and branding (short title for readability)
    display_title = shorten_title(topic)
    if _composite_thumbnail(base_image_path, display_title, section, output_path):
        # Clean up temp Gemini base if used
        if Path(gemini_base).exists() and gemini_base != output_path:
            try:
                Path(gemini_base).unlink()
            except OSError:
                pass
        return output_path

    return None


def set_thumbnail_on_youtube(video_id: str, thumbnail_path: str) -> bool:
    """Set a thumbnail on an existing YouTube video via youtube_upload.py."""
    if not Path(thumbnail_path).exists():
        print(f"  Thumbnail: file not found: {thumbnail_path}")
        return False

    upload_script = DIGEST_DIR / "youtube_upload.py"
    cmd = [
        sys.executable, str(upload_script),
        "--file", "dummy",  # required arg but not used in thumbnail-only mode
        "--title", "dummy",  # required arg but not used
        "--description", "dummy",  # required arg but not used
        "--set-thumbnail-for", video_id,
        "--thumbnail", thumbnail_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            print(f"  Thumbnail: set on YouTube video {video_id}")
            return True
        print(f"  Thumbnail: YouTube set failed (exit {result.returncode})")
        if result.stderr:
            print(f"    {result.stderr[-200:]}")
    except subprocess.TimeoutExpired:
        print("  Thumbnail: YouTube set timed out (60s)")
    except Exception as e:
        print(f"  Thumbnail: YouTube set error: {e}")

    return False


# ── CLI ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate YouTube thumbnail")
    parser.add_argument("--topic", required=True, help="Video topic/hook text")
    parser.add_argument(
        "--section", required=True, choices=["signal", "editorial"],
        help="Video section type",
    )
    parser.add_argument("--date", required=True, help="Date (YYYY-MM-DD)")
    parser.add_argument("--hero", default=None, help="Path to hero image fallback")
    parser.add_argument("--video-id", default=None, help="YouTube video ID to set thumbnail on")
    parser.add_argument("--output-dir", default=None, help="Output directory (default: project root)")
    parser.add_argument("--skip-gemini", action="store_true", help="Skip Gemini, use hero-only")

    args = parser.parse_args()

    thumb_path = create_thumbnail(
        topic=args.topic,
        section=args.section,
        date=args.date,
        hero_path=args.hero,
        output_dir=args.output_dir,
        skip_gemini=args.skip_gemini,
    )

    if not thumb_path:
        print("FAILED: Could not generate thumbnail")
        sys.exit(1)

    print(f"Thumbnail: {thumb_path} ({Path(thumb_path).stat().st_size // 1024}KB)")

    if args.video_id:
        ok = set_thumbnail_on_youtube(args.video_id, thumb_path)
        if not ok:
            print("WARNING: Thumbnail generated but could not set on YouTube")
            sys.exit(1)

    print("Done.")


if __name__ == "__main__":
    main()
