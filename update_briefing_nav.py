"""Update all dated morning briefing pages with Nav V2 (hamburger drawer) + canonical footer."""
import re
from pathlib import Path

from nav_component import NAV_CSS_V2, build_nav_v2

DIGEST_DIR = Path(__file__).parent


def build_briefing_footer(share_url: str) -> str:
    """Canonical footer for briefing pages (no social badges -- they're in the topbar)."""
    return f'''<footer style="background:#060e20;border-top:1px solid rgba(255,255,255,0.06);margin-top:auto">
    <div style="max-width:40rem;margin:0 auto;text-align:center;padding:64px 24px;position:relative">
        <div style="position:absolute;bottom:0;left:50%;transform:translateX(-50%);width:500px;height:200px;background:linear-gradient(to top,rgba(139,92,246,0.04),transparent);border-radius:50%;filter:blur(48px);pointer-events:none"></div>
        <div style="position:relative;z-index:1">
            <div style="display:inline-flex;align-items:center;gap:12px;margin-bottom:24px">
                <div style="width:36px;height:36px;border-radius:12px;background:linear-gradient(135deg,#3B82F6,#8B5CF6);display:flex;align-items:center;justify-content:center;color:white;font-weight:800;font-size:14px;box-shadow:0 4px 12px rgba(139,92,246,0.2)">K</div>
                <span style="font-size:18px;font-weight:700;background:linear-gradient(90deg,#3B82F6,#8B5CF6,#EC4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">Koda Intelligence</span>
            </div>
            <p style="color:#c2c6d6;font-size:14px;margin-bottom:32px">Read. Listen. Watch. Every morning.</p>
            <div style="display:flex;align-items:center;justify-content:center;gap:24px;margin-bottom:40px;flex-wrap:wrap">
                <a href="./morning-briefing-koda.html" style="font-size:12px;font-weight:600;color:#c2c6d6;text-decoration:none;text-transform:uppercase;letter-spacing:0.05em;transition:color 0.2s" onmouseover="this.style.color='#3B82F6'" onmouseout="this.style.color='#c2c6d6'"><span class="material-symbols-outlined" style="font-size:12px;vertical-align:-2px;margin-right:2px">bolt</span>The Signal</a>
                <span style="color:rgba(140,144,159,0.3)">|</span>
                <a href="./archive/" style="font-size:12px;font-weight:600;color:#c2c6d6;text-decoration:none;text-transform:uppercase;letter-spacing:0.05em;transition:color 0.2s" onmouseover="this.style.color='#8B5CF6'" onmouseout="this.style.color='#c2c6d6'"><span class="material-symbols-outlined" style="font-size:12px;vertical-align:-2px;margin-right:2px">lock_open</span>The Vault</a>
                <span style="color:rgba(140,144,159,0.3)">|</span>
                <a href="https://www.youtube.com/channel/UC8qqiKRGFAd5SwTr_2ZzPJg" target="_blank" rel="noopener" style="font-size:12px;font-weight:600;color:#c2c6d6;text-decoration:none;text-transform:uppercase;letter-spacing:0.05em;transition:color 0.2s" onmouseover="this.style.color='#EC4899'" onmouseout="this.style.color='#c2c6d6'">YouTube</a>
            </div>
            <p style="font-size:11px;color:rgba(140,144,159,0.6)">&copy; 2026 Koda Community &middot; <span style="font-family:'JetBrains Mono',monospace">koda.community</span></p>
        </div>
    </div>
</footer>'''


def update_briefing(filepath: Path) -> None:
    html = filepath.read_text(encoding="utf-8")
    filename = filepath.name
    share_url = f"https://www.koda.community/{filename}"

    css, nav_html, nav_js = build_nav_v2(
        current_page="signal",
        url_prefix="./",
        page_subtitle="The Signal",
        page_icon="bolt",
        share_url=share_url,
    )

    # ── Replace header ──
    replaced = False

    # Try V2 markers first (in case already partially updated)
    new_html = re.sub(
        r"<!-- koda-nav-v2-start -->.*?<!-- koda-nav-v2-end -->",
        nav_html, html, flags=re.DOTALL,
    )
    if new_html != html:
        html = new_html
        replaced = True

    if not replaced:
        # Legacy Tailwind-based header (dated briefings)
        html, count = re.subn(
            r'<header\s+class="fixed\s+top-0[^"]*"[^>]*>.*?</header>',
            nav_html, html, count=1, flags=re.DOTALL,
        )
        if count:
            replaced = True

    if not replaced:
        # Legacy inline-style header
        for pattern in [
            r'<header[^>]*(?:class="(?:fixed|topbar)|style="position:fixed)[^>]*>.*?</header>',
        ]:
            html, count = re.subn(pattern, nav_html, html, count=1, flags=re.DOTALL)
            if count:
                replaced = True
                break

    if not replaced:
        # Very early digests: <div class="topbar">...</div> (with nested divs)
        # Match from opening <div class="topbar"> to its content up to the next section
        m = re.search(
            r'<div\s+class="topbar">.*?</div>\s*</div>\s*(?:</div>\s*)?(?=\n(?:<section|<div class="hero|<!-- ))',
            html, flags=re.DOTALL,
        )
        if m:
            html = html[:m.start()] + nav_html + html[m.end():]
            replaced = True

    if not replaced:
        # Alternative early format: <nav class="topbar">...</nav>
        html, count = re.subn(
            r'<nav\s+class="topbar"[^>]*>.*?</nav>',
            nav_html, html, count=1, flags=re.DOTALL,
        )
        if count:
            replaced = True

    if not replaced:
        if "koda-nav-v2-start" in html:
            print(f"  Skipped (already up-to-date): {filename}")
            return
        print(f"  WARN: Could not find header in {filename}")
        return

    # ── Replace footer ──
    new_footer = build_briefing_footer(share_url)
    html = re.sub(r"<footer[^>]*>.*?</footer>", new_footer, html, count=1, flags=re.DOTALL)

    # ── Remove old nav-specific JS ──
    # Remove shareDigest function
    html = re.sub(
        r"(?:// Share buttons\n)?function shareDigest\(platform\)\s*\{.*?\n\}",
        "", html, count=1, flags=re.DOTALL,
    )
    # Remove date picker IIFE
    html = re.sub(
        r"// Date picker navigation\n\(function\(\)\s*\{.*?\}\)\(\);",
        "", html, count=1, flags=re.DOTALL,
    )

    # ── Remove old nav V2 JS if present, then inject new ──
    html = re.sub(
        r"<!-- koda-nav-v2-js-start -->.*?<!-- koda-nav-v2-js-end -->",
        "", html, flags=re.DOTALL,
    )
    html = html.replace("</body>", nav_js + "\n</body>")

    # ── Inject V2 CSS ──
    # Remove old V2 CSS if present
    html = re.sub(
        r"/\* -- Koda Nav V2 -- \*/.*?/\* -- End Koda Nav V2 -- \*/",
        "", html, flags=re.DOTALL,
    )
    # Remove old day-nav-btn CSS
    html = re.sub(
        r"\.day-nav-btn\s*\{[^}]*\}\s*",
        "", html,
    )
    # Remove old topbar/day-nav CSS rules (early digests)
    for old_cls in [
        r"\.topbar\{[^}]*\}",
        r"\.topbar-inner\{[^}]*\}",
        r"\.topbar-right\{[^}]*\}",
        r"\.day-nav\{[^}]*\}",
        r"\.day-nav-btn:hover:not\(\.disabled\)\{[^}]*\}",
        r"\.day-nav-current\{[^}]*\}",
        r"\.dark-toggle\{[^}]*\}",
    ]:
        html = re.sub(old_cls + r"\s*", "", html)
    # Clean orphaned braces (a } on its own line preceded by a blank line)
    html = re.sub(r"\n\n+\s*}\s*\n+\s*\n*(?=</style>)", "\n", html)
    if "Koda Nav V2" not in html:
        css_with_end = css.rstrip() + "\n/* -- End Koda Nav V2 -- */\n"
        html = html.replace("</style>", css_with_end + "</style>", 1)

    # ── Ensure Material Symbols font loaded ──
    if "Material+Symbols+Outlined" not in html:
        html = html.replace(
            "</head>",
            '<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet">\n</head>',
            1,
        )

    filepath.write_text(html, encoding="utf-8")
    print(f"  Updated: {filename}")


def force_update_nav(filepath: Path) -> None:
    """Force-update a file that already has V2 markers with the latest nav component."""
    html = filepath.read_text(encoding="utf-8")
    filename = filepath.name
    share_url = f"https://www.koda.community/{filename}"

    css, nav_html, nav_js = build_nav_v2(
        current_page="signal",
        url_prefix="./",
        page_subtitle="The Signal",
        page_icon="bolt",
        share_url=share_url,
    )

    # Replace V2 nav HTML
    html = re.sub(
        r"<!-- koda-nav-v2-start -->.*?<!-- koda-nav-v2-end -->",
        nav_html, html, flags=re.DOTALL,
    )

    # Inject date picker for briefing pages (before kn-desktop-social)
    date_match = re.search(r'data-digest-date="(\d{4}-\d{2}-\d{2})"', html)
    if date_match:
        digest_date = date_match.group(1)
        date_picker_html = (
            f'<div class="hidden md:flex items-center" id="dayNav">'
            f'<div class="relative">'
            f'<button id="datePickerBtn" class="flex items-center gap-1 font-mono text-[10px] font-bold text-[#3B82F6] px-2 py-1 bg-[#3B82F6]/10 rounded-md hover:bg-[#3B82F6]/20 transition-all cursor-pointer border-none" title="Jump to date">'
            f'<span class="material-symbols-outlined" style="font-size:14px">calendar_month</span>'
            f'<span id="dateLabel">{digest_date}</span>'
            f'</button>'
            f'<input type="date" id="datePicker" class="absolute top-full left-0 mt-1 opacity-0 pointer-events-none w-0 h-0" value="{digest_date}" min="2026-03-24">'
            f'</div></div>\n        '
        )
        html = html.replace(
            '<div class="kn-desktop-social">',
            date_picker_html + '<div class="kn-desktop-social">',
            1,
        )

    # Replace V2 nav JS
    html = re.sub(
        r"<!-- koda-nav-v2-js-start -->.*?<!-- koda-nav-v2-js-end -->",
        nav_js, html, flags=re.DOTALL,
    )
    # Replace V2 CSS
    html = re.sub(
        r"/\* -- Koda Nav V2 -- \*/.*?/\* -- End Koda Nav V2 -- \*/",
        css.rstrip() + "\n/* -- End Koda Nav V2 -- */",
        html, flags=re.DOTALL,
    )
    # Replace footer with canonical version (removes social badges from footer)
    new_footer = build_briefing_footer(share_url)
    html = re.sub(r"<footer[^>]*>.*?</footer>", new_footer, html, count=1, flags=re.DOTALL)

    filepath.write_text(html, encoding="utf-8")
    print(f"  Force-updated: {filename}")


if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv

    briefings = sorted(DIGEST_DIR.glob("morning-briefing-koda-2026-*.html"))
    print(f"Found {len(briefings)} dated briefings" + (" (force mode)" if force else ""))
    for briefing in briefings:
        if force and "koda-nav-v2-start" in briefing.read_text(encoding="utf-8"):
            force_update_nav(briefing)
        else:
            update_briefing(briefing)

    # Also update the main (undated) briefing if it already has V2 nav
    main_briefing = DIGEST_DIR / "morning-briefing-koda.html"
    if main_briefing.exists() and "koda-nav-v2-start" in main_briefing.read_text(encoding="utf-8"):
        force_update_nav(main_briefing)

    print("Done")
