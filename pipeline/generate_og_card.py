"""
Generate branded Open Graph cards (1200x630) for social sharing.

Creates professional social preview cards with:
- Hero image as dimmed background
- Section badge (The Signal, Deep Dive, The Lab)
- Title text overlay
- koda.community domain badge
- Gradient accent bar

Usage:
    from pipeline.generate_og_card import create_og_card
    create_og_card(
        hero_path="path/to/hero.jpg",
        title="The Signal | 11 April 2026",
        section="signal",  # signal | editorial | review
        output_path="path/to/og-card.jpg",
    )
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ── Constants ────────────────────────────────────────────────────────────────

OG_W, OG_H = 1200, 630
BG_COLOR = (11, 19, 38)  # #0b1326
GRADIENT_LEFT = (59, 130, 246)   # #3B82F6
GRADIENT_RIGHT = (139, 92, 246)  # #8B5CF6

SECTION_COLORS = {
    "signal":    {"badge_bg": (59, 130, 246), "label": "THE SIGNAL"},
    "editorial": {"badge_bg": (139, 92, 246), "label": "DEEP DIVE"},
    "review":    {"badge_bg": (139, 92, 246), "label": "THE LAB"},
}

# Fonts (Segoe UI available on Windows; Railway uses fallback)
FONT_BOLD = "segoeuib.ttf"
FONT_SEMI = "seguisb.ttf"
FONT_REG = "segoeui.ttf"
FONT_FALLBACK = "arialbd.ttf"


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


def _draw_gradient_bar(draw: ImageDraw.Draw, y: int, height: int, width: int = OG_W) -> None:
    """Draw a horizontal gradient bar from blue to purple."""
    for x in range(width):
        t = x / width
        r = int(GRADIENT_LEFT[0] + (GRADIENT_RIGHT[0] - GRADIENT_LEFT[0]) * t)
        g = int(GRADIENT_LEFT[1] + (GRADIENT_RIGHT[1] - GRADIENT_LEFT[1]) * t)
        b = int(GRADIENT_LEFT[2] + (GRADIENT_RIGHT[2] - GRADIENT_LEFT[2]) * t)
        draw.line([(x, y), (x, y + height - 1)], fill=(r, g, b))


def _draw_rounded_rect(draw: ImageDraw.Draw, xy: tuple, fill: tuple, radius: int = 8) -> None:
    """Draw a rounded rectangle."""
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill)


def create_og_card(
    hero_path: str,
    title: str,
    section: str = "signal",
    output_path: str = "og-card.jpg",
    subtitle: str = "",
) -> bool:
    """Generate a branded 1200x630 OG card.

    Args:
        hero_path: Path to the hero/source image
        title: Main title text for the card
        section: One of "signal", "editorial", "review"
        output_path: Where to save the result
        subtitle: Optional subtitle/description text

    Returns:
        True on success, False on failure
    """
    try:
        section_info = SECTION_COLORS.get(section, SECTION_COLORS["signal"])

        # Load fonts
        font_title = _load_font(FONT_BOLD, 42)
        font_badge = _load_font(FONT_SEMI, 16)
        font_domain = _load_font(FONT_SEMI, 18)
        font_subtitle = _load_font(FONT_REG, 22)

        # Create canvas
        canvas = Image.new("RGB", (OG_W, OG_H), BG_COLOR)

        # Load and process hero image as background
        hero = Image.open(hero_path).convert("RGB")

        # Scale hero to cover the canvas
        scale = max(OG_W / hero.width, OG_H / hero.height)
        new_w = int(hero.width * scale)
        new_h = int(hero.height * scale)
        hero = hero.resize((new_w, new_h), Image.LANCZOS)

        # Center crop
        left = (new_w - OG_W) // 2
        top = (new_h - OG_H) // 2
        hero = hero.crop((left, top, left + OG_W, top + OG_H))

        # Apply slight blur for readability
        hero = hero.filter(ImageFilter.GaussianBlur(radius=3))

        # Paste hero as background
        canvas.paste(hero, (0, 0))

        # Dark overlay (60% opacity)
        overlay = Image.new("RGBA", (OG_W, OG_H), (11, 19, 38, 160))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")

        draw = ImageDraw.Draw(canvas)

        # Bottom gradient accent bar
        _draw_gradient_bar(draw, OG_H - 5, 5)

        # Top gradient accent bar (thin)
        _draw_gradient_bar(draw, 0, 3)

        # Section badge (top-left)
        badge_text = section_info["label"]
        badge_bbox = font_badge.getbbox(badge_text)
        badge_w = badge_bbox[2] - badge_bbox[0] + 24
        badge_h = badge_bbox[3] - badge_bbox[1] + 14
        badge_x, badge_y = 48, 40
        _draw_rounded_rect(draw, (badge_x, badge_y, badge_x + badge_w, badge_y + badge_h),
                           fill=section_info["badge_bg"], radius=6)
        draw.text((badge_x + 12, badge_y + 5), badge_text, fill=(255, 255, 255), font=font_badge)

        # Title text (centered vertically, left-aligned with padding)
        text_x = 48
        max_text_w = OG_W - 96  # 48px padding each side
        lines = _wrap_text(title, font_title, max_text_w)

        # Limit to 3 lines max
        if len(lines) > 3:
            lines = lines[:3]
            lines[2] = lines[2][:50] + "..." if len(lines[2]) > 50 else lines[2]

        line_height = 56
        total_text_h = len(lines) * line_height
        # Position title in center-lower area (above domain badge)
        text_start_y = (OG_H - total_text_h) // 2 + 20

        for i, line in enumerate(lines):
            y = text_start_y + i * line_height
            # Text shadow for readability
            draw.text((text_x + 2, y + 2), line, fill=(0, 0, 0, 128), font=font_title)
            draw.text((text_x, y), line, fill=(255, 255, 255), font=font_title)

        # Subtitle (if provided, below title)
        if subtitle:
            sub_lines = _wrap_text(subtitle, font_subtitle, max_text_w)[:2]
            sub_y = text_start_y + total_text_h + 12
            for i, line in enumerate(sub_lines):
                draw.text((text_x, sub_y + i * 30), line, fill=(194, 198, 214), font=font_subtitle)

        # Domain badge (bottom-left)
        domain_text = "koda.community"
        domain_y = OG_H - 52
        # Small K icon circle
        k_size = 28
        k_x = 48
        _draw_rounded_rect(draw, (k_x, domain_y - 2, k_x + k_size, domain_y + k_size - 2),
                           fill=(99, 102, 241), radius=6)  # #6366F1
        k_font = _load_font(FONT_BOLD, 16)
        draw.text((k_x + 8, domain_y + 2), "K", fill=(255, 255, 255), font=k_font)
        draw.text((k_x + k_size + 10, domain_y + 3), domain_text,
                  fill=(194, 198, 214), font=font_domain)

        # Save with quality optimization
        canvas = canvas.convert("RGB")
        for quality in (88, 80, 72, 60):
            canvas.save(output_path, "JPEG", quality=quality, optimize=True)
            if Path(output_path).stat().st_size < 600_000:
                return True
        canvas.save(output_path, "JPEG", quality=50, optimize=True)
        return True

    except Exception as e:
        print(f"  OG card generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate branded OG card")
    parser.add_argument("--hero", required=True, help="Path to hero image")
    parser.add_argument("--title", required=True, help="Card title")
    parser.add_argument("--section", default="signal", choices=["signal", "editorial", "review"])
    parser.add_argument("--subtitle", default="", help="Optional subtitle")
    parser.add_argument("--output", default="og-card.jpg", help="Output path")
    args = parser.parse_args()

    ok = create_og_card(args.hero, args.title, args.section, args.output, args.subtitle)
    if ok:
        size = Path(args.output).stat().st_size // 1024
        print(f"Created: {args.output} ({size}KB)")
    else:
        print("FAILED")
