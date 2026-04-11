"""
Generate premium branded Open Graph cards (1200x630) for social sharing.

Cinematic poster-style cards with:
- Full-bleed hero as background with cinematic gradient overlay
- Bold title with multi-layer text shadow for depth
- Section pill badge with glow effect
- Subtle domain watermark
- Bottom gradient accent strip

Usage:
    from pipeline.generate_og_card import create_og_card
    create_og_card(
        hero_path="path/to/hero.jpg",
        title="The Signal | 11 April 2026",
        section="signal",
        output_path="path/to/og-card.jpg",
    )
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ── Canvas ───────────────────────────────────────────────────────────────────

OG_W, OG_H = 1200, 630

# ── Brand palette ────────────────────────────────────────────────────────────

BG = (11, 19, 38)           # #0b1326
BLUE = (59, 130, 246)       # #3B82F6
PURPLE = (139, 92, 246)     # #8B5CF6
INDIGO = (99, 102, 241)     # #6366F1
WHITE = (255, 255, 255)
LIGHT = (218, 226, 253)     # #dae2fd
MUTED = (140, 144, 159)     # #8c909f

SECTIONS = {
    "signal":      {"color": BLUE,   "label": "THE SIGNAL"},
    "editorial":   {"color": PURPLE, "label": "DEEP DIVE"},
    "review":      {"color": PURPLE, "label": "THE LAB"},
    "landing":     {"color": INDIGO, "label": "KODA INTELLIGENCE"},
    "lab":         {"color": PURPLE, "label": "THE LAB"},
    "dojo":        {"color": BLUE,   "label": "THE DOJO"},
    "pulse":       {"color": BLUE,   "label": "THE PULSE"},
    "leaderboard": {"color": INDIGO, "label": "TOKEN TRACKER"},
    "vault":       {"color": INDIGO, "label": "THE VAULT"},
}

# ── Fonts ────────────────────────────────────────────────────────────────────

_FONT_CHAIN_BOLD = ["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"]
_FONT_CHAIN_REG = ["seguisb.ttf", "segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"]


def _font(chain: list[str], size: int) -> ImageFont.FreeTypeFont:
    for name in chain:
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _bold(size: int) -> ImageFont.FreeTypeFont:
    return _font(_FONT_CHAIN_BOLD, size)


def _reg(size: int) -> ImageFont.FreeTypeFont:
    return _font(_FONT_CHAIN_REG, size)


# ── Text helpers ─────────────────────────────────────────────────────────────

def _wrap(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        test = f"{cur} {w}".strip()
        if font.getbbox(test)[2] <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def _text_with_shadow(
    draw: ImageDraw.Draw,
    pos: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple = WHITE,
    shadow_layers: int = 3,
) -> None:
    """Draw text with multi-layer shadow for cinematic depth."""
    x, y = pos
    for i in range(shadow_layers, 0, -1):
        alpha = 40 + i * 20
        draw.text((x + i, y + i), text, fill=(0, 0, 0, min(alpha, 180)), font=font)
    draw.text((x, y), text, fill=fill, font=font)


# ── Gradient helpers ─────────────────────────────────────────────────────────

def _cinematic_overlay(size: tuple[int, int]) -> Image.Image:
    """Create a cinematic bottom-heavy gradient overlay.

    Top 30%: light fade (30% opacity) to let the hero show
    Bottom 70%: deep fade (85% opacity) for text readability
    """
    w, h = size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for y in range(h):
        t = y / h
        if t < 0.25:
            # Top quarter: light overlay to let hero breathe
            alpha = int(40 + t * 200)
        elif t < 0.45:
            # Middle: transition zone
            alpha = int(90 + (t - 0.25) * 500)
        else:
            # Bottom 55%: deep overlay for text
            alpha = int(190 + (t - 0.45) * 80)
        alpha = min(alpha, 225)
        draw.line([(0, y), (w, y)], fill=(BG[0], BG[1], BG[2], alpha))

    return overlay


def _gradient_strip(
    draw: ImageDraw.Draw, y: int, h: int, w: int = OG_W,
    left: tuple = BLUE, right: tuple = PURPLE,
) -> None:
    for x in range(w):
        t = x / w
        r = int(left[0] + (right[0] - left[0]) * t)
        g = int(left[1] + (right[1] - left[1]) * t)
        b = int(left[2] + (right[2] - left[2]) * t)
        draw.line([(x, y), (x, y + h - 1)], fill=(r, g, b))


def _pill(
    draw: ImageDraw.Draw, x: int, y: int, text: str,
    font: ImageFont.FreeTypeFont, color: tuple, glow: bool = True,
) -> None:
    """Draw a pill badge with optional glow."""
    bbox = font.getbbox(text)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    pad_x, pad_y = 16, 8
    pw, ph = tw + pad_x * 2, th + pad_y * 2

    if glow:
        # Subtle glow behind the pill
        glow_img = Image.new("RGBA", (pw + 16, ph + 16), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow_img)
        gd.rounded_rectangle([0, 0, pw + 15, ph + 15], radius=ph // 2,
                             fill=(color[0], color[1], color[2], 50))
        glow_img = glow_img.filter(ImageFilter.GaussianBlur(6))
        # We can't paste RGBA on RGB draw surface easily, skip glow for now
        # (it adds complexity for marginal visual gain in JPEG)

    draw.rounded_rectangle(
        [x, y, x + pw, y + ph],
        radius=ph // 2,
        fill=color,
    )
    draw.text((x + pad_x, y + pad_y - 1), text, fill=WHITE, font=font)


# ── Main generator ───────────────────────────────────────────────────────────

def create_og_card(
    hero_path: str,
    title: str,
    section: str = "signal",
    output_path: str = "og-card.jpg",
    subtitle: str = "",
) -> bool:
    """Generate a premium branded 1200x630 OG card.

    Args:
        hero_path: Path to the hero/source image
        title: Main title text for the card
        section: One of the SECTIONS keys
        output_path: Where to save the JPEG result
        subtitle: Optional subtitle/hook text

    Returns:
        True on success, False on failure.
    """
    try:
        sec = SECTIONS.get(section, SECTIONS["signal"])

        # ── 1. Hero background ───────────────────────────────────────────
        hero = Image.open(hero_path).convert("RGB")

        # Cover-crop to 1200x630
        scale = max(OG_W / hero.width, OG_H / hero.height)
        hero = hero.resize(
            (int(hero.width * scale), int(hero.height * scale)), Image.LANCZOS
        )
        lx = (hero.width - OG_W) // 2
        ly = (hero.height - OG_H) // 2
        hero = hero.crop((lx, ly, lx + OG_W, ly + OG_H))

        # Slight blur for depth-of-field effect
        hero = hero.filter(ImageFilter.GaussianBlur(radius=2))

        canvas = hero.convert("RGBA")

        # ── 2. Cinematic gradient overlay ─────────────────────────────────
        overlay = _cinematic_overlay((OG_W, OG_H))
        canvas = Image.alpha_composite(canvas, overlay)

        # ── 3. Bottom accent strip (gradient bar) ─────────────────────────
        canvas_rgb = canvas.convert("RGB")
        draw = ImageDraw.Draw(canvas_rgb)
        _gradient_strip(draw, OG_H - 4, 4)

        # ── 4. Section pill badge (top-left) ──────────────────────────────
        pill_font = _bold(14)
        _pill(draw, 48, 36, sec["label"], pill_font, sec["color"])

        # ── 5. Title ─────────────────────────────────────────────────────
        title_font = _bold(48)
        max_tw = OG_W - 120  # 60px padding each side
        lines = _wrap(title, title_font, max_tw)

        # Cap at 3 lines
        if len(lines) > 3:
            lines = lines[:3]
            if len(lines[2]) > 45:
                lines[2] = lines[2][:45].rstrip() + "..."

        line_h = 62
        total_h = len(lines) * line_h

        # Position: bottom-heavy (text sits in the lower 60% of the card)
        text_top = OG_H - total_h - (130 if subtitle else 90)

        for i, line in enumerate(lines):
            _text_with_shadow(
                draw, (60, text_top + i * line_h), line,
                title_font, WHITE, shadow_layers=4,
            )

        # ── 6. Subtitle ──────────────────────────────────────────────────
        if subtitle:
            sub_font = _reg(22)
            sub_lines = _wrap(subtitle, sub_font, max_tw)[:2]
            sub_top = text_top + total_h + 10
            for i, line in enumerate(sub_lines):
                _text_with_shadow(
                    draw, (60, sub_top + i * 28), line,
                    sub_font, LIGHT, shadow_layers=2,
                )

        # ── 7. Domain watermark (bottom-left) ────────────────────────────
        wm_font = _reg(16)
        draw.text((60, OG_H - 32), "koda.community", fill=MUTED, font=wm_font)

        # ── 8. Decorative K badge (bottom-right) ─────────────────────────
        k_size = 36
        k_x = OG_W - 60 - k_size
        k_y = OG_H - 32 - k_size + 8
        draw.rounded_rectangle(
            [k_x, k_y, k_x + k_size, k_y + k_size],
            radius=10, fill=INDIGO,
        )
        k_font = _bold(20)
        # Center K in the badge
        kb = k_font.getbbox("K")
        kw, kh = kb[2] - kb[0], kb[3] - kb[1]
        draw.text(
            (k_x + (k_size - kw) // 2, k_y + (k_size - kh) // 2 - 2),
            "K", fill=WHITE, font=k_font,
        )

        # ── 9. Save ──────────────────────────────────────────────────────
        for q in (90, 82, 74, 65):
            canvas_rgb.save(output_path, "JPEG", quality=q, optimize=True)
            if Path(output_path).stat().st_size < 600_000:
                return True
        canvas_rgb.save(output_path, "JPEG", quality=55, optimize=True)
        return True

    except Exception as e:
        print(f"  OG card generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate premium branded OG card")
    parser.add_argument("--hero", required=True, help="Path to hero image")
    parser.add_argument("--title", required=True, help="Card title")
    parser.add_argument("--section", default="signal",
                        choices=list(SECTIONS.keys()))
    parser.add_argument("--subtitle", default="", help="Optional subtitle")
    parser.add_argument("--output", default="og-card.jpg", help="Output path")
    args = parser.parse_args()

    ok = create_og_card(args.hero, args.title, args.section, args.output, args.subtitle)
    if ok:
        size = Path(args.output).stat().st_size // 1024
        print(f"Created: {args.output} ({size}KB)")
    else:
        print("FAILED")
