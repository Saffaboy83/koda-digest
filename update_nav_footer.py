"""Update all sub-page navbars and footers to canonical design (V2 with hamburger drawer)."""
import re
from pathlib import Path

from nav_component import NAV_CSS_V2, build_nav_v2

DIGEST_DIR = Path(__file__).parent


def build_footer(share_url: str) -> str:
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
                <a href="../morning-briefing-koda.html" style="font-size:12px;font-weight:600;color:#c2c6d6;text-decoration:none;text-transform:uppercase;letter-spacing:0.05em;transition:color 0.2s" onmouseover="this.style.color='#3B82F6'" onmouseout="this.style.color='#c2c6d6'"><span class="material-symbols-outlined" style="font-size:12px;vertical-align:-2px;margin-right:2px">bolt</span>The Signal</a>
                <span style="color:rgba(140,144,159,0.3)">|</span>
                <a href="../archive/" style="font-size:12px;font-weight:600;color:#c2c6d6;text-decoration:none;text-transform:uppercase;letter-spacing:0.05em;transition:color 0.2s" onmouseover="this.style.color='#8B5CF6'" onmouseout="this.style.color='#c2c6d6'"><span class="material-symbols-outlined" style="font-size:12px;vertical-align:-2px;margin-right:2px">lock_open</span>The Vault</a>
                <span style="color:rgba(140,144,159,0.3)">|</span>
                <a href="https://www.youtube.com/channel/UC8qqiKRGFAd5SwTr_2ZzPJg" target="_blank" rel="noopener" style="font-size:12px;font-weight:600;color:#c2c6d6;text-decoration:none;text-transform:uppercase;letter-spacing:0.05em;transition:color 0.2s" onmouseover="this.style.color='#EC4899'" onmouseout="this.style.color='#c2c6d6'">YouTube</a>
            </div>
            <p style="font-size:11px;color:rgba(140,144,159,0.6)">&copy; 2026 Koda Community &middot; <span style="font-family:'JetBrains Mono',monospace">koda.community</span></p>
        </div>
    </div>
</footer>'''


# ── Pages config: (filepath, page_id, label, icon, share_url) ──

PAGES = [
    ("editorial/index.html", "editorial", "Deep Dive", "explore", "https://www.koda.community/editorial/"),
    ("changelog/index.html", "changelog", "Pulse", "pulse_alert", "https://www.koda.community/changelog/"),
    ("pricing/index.html", "pricing", "Token Tracker", "monitoring", "https://www.koda.community/pricing/"),
    ("benchmarks/index.html", "benchmarks", "Leaderboard", "trophy", "https://www.koda.community/benchmarks/"),
    ("archive/index.html", "archive", "The Vault", "lock_open", "https://www.koda.community/archive/"),
    ("reviews/index.html", "reviews", "The Lab", "science", "https://www.koda.community/reviews/"),
]


def update_page(filepath: str, current: str, label: str, icon: str, share_url: str) -> None:
    full_path = DIGEST_DIR / filepath
    html = full_path.read_text(encoding="utf-8")

    css, nav_html, nav_js = build_nav_v2(
        current_page=current,
        url_prefix="../",
        page_subtitle=label,
        page_icon=icon,
        share_url=share_url,
    )
    new_footer = build_footer(share_url)

    # ── Remove old nav (V2 markers first, then legacy patterns) ──
    html = re.sub(
        r"<!-- koda-nav-v2-start -->.*?<!-- koda-nav-v2-end -->",
        nav_html, html, flags=re.DOTALL,
    )
    if "koda-nav-v2-start" not in html:
        # Legacy: replace old <header class="topbar"> or <nav class="topbar">
        for pattern in [
            r"<header[^>]*class=\"topbar\"[^>]*>.*?</header>",
            r"<header\s+style=\"position:fixed.*?</header>",
            r"<nav\s+class=\"topbar\"[^>]*>.*?</nav>",
        ]:
            html, count = re.subn(pattern, nav_html, html, count=1, flags=re.DOTALL)
            if count:
                break

    # ── Remove old nav JS, inject new ──
    html = re.sub(
        r"<!-- koda-nav-v2-js-start -->.*?<!-- koda-nav-v2-js-end -->",
        "", html, flags=re.DOTALL,
    )
    html = html.replace("</body>", nav_js + "\n</body>")

    # ── Replace footer ──
    html = re.sub(r"<footer[^>]*>.*?</footer>", new_footer, html, flags=re.DOTALL)

    # ── Inject V2 CSS (replace old canonical nav CSS or append) ──
    html = re.sub(
        r"/\* -- Koda Nav V2 -- \*/.*?/\* -- End Koda Nav V2 -- \*/",
        "", html, flags=re.DOTALL,
    )
    # Remove old canonical nav CSS blocks (including trailing closing brace)
    html = re.sub(
        r"/\* -- Canonical Nav -- \*/.*?@media\(max-width:768px\)\{\.(?:nav-link|koda-nav-link)[^}]*\}\s*\}?",
        "", html, flags=re.DOTALL,
    )
    # Clean stray orphaned braces (a } on its own line preceded by a blank line)
    html = re.sub(r"\n\n+\s*}\s*\n+\s*\n*(?=</style>)", "\n", html)
    # Inject V2 CSS
    if "Koda Nav V2" not in html:
        css_with_end = css.rstrip() + "\n/* -- End Koda Nav V2 -- */\n"
        html = html.replace("</style>", css_with_end + "</style>", 1)

    # ── Ensure Material Symbols is loaded ──
    if "Material+Symbols+Outlined" not in html:
        html = html.replace(
            "</head>",
            '<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet">\n</head>',
            1,
        )

    full_path.write_text(html, encoding="utf-8")
    print(f"  Updated: {filepath}")


if __name__ == "__main__":
    for page in PAGES:
        update_page(*page)
    print("\nAll 5 sub-pages updated with V2 nav + footer")
