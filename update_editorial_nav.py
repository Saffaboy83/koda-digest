"""Update all editorial article pages with V2 nav (hamburger drawer) + footer."""
import re
from pathlib import Path

from nav_component import NAV_CSS_V2, build_nav_v2

DIGEST_DIR = Path(__file__).parent
EDITORIAL_DIR = DIGEST_DIR / "editorial"

FOOTER_HTML = """<footer style="background:#060e20;border-top:1px solid rgba(255,255,255,0.06);margin-top:64px">
    <div style="max-width:40rem;margin:0 auto;text-align:center;padding:64px 24px;position:relative">
        <div style="position:absolute;bottom:0;left:50%;transform:translateX(-50%);width:500px;height:200px;background:linear-gradient(to top,rgba(139,92,246,0.04),transparent);border-radius:50%;filter:blur(48px);pointer-events:none"></div>
        <div style="position:relative;z-index:1">
            <div style="display:flex;align-items:center;justify-content:center;gap:12px;margin-bottom:32px">
                <a href="https://x.com/intent/tweet?url=https://www.koda.community/editorial/" target="_blank" rel="noopener" style="width:36px;height:36px;border-radius:8px;background:rgba(255,255,255,0.05);display:flex;align-items:center;justify-content:center;color:#8c909f;text-decoration:none;transition:all 0.2s" title="Share on X"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg></a>
                <a href="https://www.linkedin.com/sharing/share-offsite/?url=https://www.koda.community/editorial/" target="_blank" rel="noopener" style="width:36px;height:36px;border-radius:8px;background:rgba(255,255,255,0.05);display:flex;align-items:center;justify-content:center;color:#8c909f;text-decoration:none;transition:all 0.2s" title="Share on LinkedIn"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg></a>
                <button onclick="navigator.clipboard.writeText(window.location.href);this.style.color='#10B981';setTimeout(()=>this.style.color='#8c909f',1500)" style="width:36px;height:36px;border-radius:8px;background:rgba(255,255,255,0.05);display:flex;align-items:center;justify-content:center;color:#8c909f;border:none;cursor:pointer;transition:all 0.2s" title="Copy link"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg></button>
                <a href="../index.html#archive" style="width:36px;height:36px;border-radius:8px;background:rgba(255,255,255,0.05);display:flex;align-items:center;justify-content:center;color:#8c909f;text-decoration:none;transition:all 0.2s" title="Search"><span class="material-symbols-outlined" style="font-size:16px">search</span></a>
            </div>
            <div style="display:inline-flex;align-items:center;gap:12px;margin-bottom:24px">
                <div style="width:36px;height:36px;border-radius:12px;background:linear-gradient(135deg,#3B82F6,#8B5CF6);display:flex;align-items:center;justify-content:center;color:white;font-weight:800;font-size:14px;box-shadow:0 4px 12px rgba(139,92,246,0.2)">K</div>
                <span style="font-size:18px;font-weight:700;background:linear-gradient(90deg,#3B82F6,#8B5CF6,#EC4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">Koda Intelligence</span>
            </div>
            <p style="color:#c2c6d6;font-size:14px;margin-bottom:32px">Read. Listen. Watch. Every morning.</p>
            <div style="display:flex;align-items:center;justify-content:center;gap:24px;margin-bottom:40px;flex-wrap:wrap">
                <a href="../morning-briefing-koda.html" style="font-size:12px;font-weight:600;color:#c2c6d6;text-decoration:none;text-transform:uppercase;letter-spacing:0.05em">The Signal</a>
                <span style="color:rgba(140,144,159,0.3)">|</span>
                <a href="../archive/" style="font-size:12px;font-weight:600;color:#c2c6d6;text-decoration:none;text-transform:uppercase;letter-spacing:0.05em">The Vault</a>
                <span style="color:rgba(140,144,159,0.3)">|</span>
                <a href="https://www.youtube.com/channel/UC8qqiKRGFAd5SwTr_2ZzPJg" target="_blank" rel="noopener" style="font-size:12px;font-weight:600;color:#c2c6d6;text-decoration:none;text-transform:uppercase;letter-spacing:0.05em">YouTube</a>
            </div>
            <p style="font-size:11px;color:rgba(140,144,159,0.6)">&copy; 2026 Koda Community &middot; <span style="font-family:'JetBrains Mono',monospace">koda.community</span></p>
        </div>
    </div>
</footer>"""


def update_article(filepath: Path) -> None:
    html = filepath.read_text(encoding="utf-8")

    css, nav_html, nav_js = build_nav_v2(
        current_page="editorial",
        url_prefix="../",
        page_subtitle="Deep Dive",
        page_icon="explore",
        share_url="https://www.koda.community/editorial/",
    )

    # ── Replace nav: V2 markers first, then legacy ──
    replaced = False
    new_html = re.sub(
        r"<!-- koda-nav-v2-start -->.*?<!-- koda-nav-v2-end -->",
        nav_html, html, flags=re.DOTALL,
    )
    if new_html != html:
        html = new_html
        replaced = True

    if not replaced:
        # Legacy: match first <header> that is the topbar (not hero)
        for pattern in [
            r'<header[^>]*(?:class="(?:fixed|topbar)|id="kodaTopbar"|style="position:fixed)[^>]*>.*?</header>',
        ]:
            html, count = re.subn(pattern, nav_html, html, count=1, flags=re.DOTALL)
            if count:
                replaced = True
                break

    if not replaced:
        # Last resort: match any first <header> that is NOT the hero
        m = re.search(r'<header[^>]*>(?:(?!hero-section).)*?</header>', html, flags=re.DOTALL)
        if m:
            html = html[:m.start()] + nav_html + html[m.end():]

    # ── Remove old nav JS, inject new ──
    html = re.sub(
        r"<!-- koda-nav-v2-js-start -->.*?<!-- koda-nav-v2-js-end -->",
        "", html, flags=re.DOTALL,
    )
    html = html.replace("</body>", nav_js + "\n</body>")

    # ── Footer ──
    if "<footer" not in html:
        html = html.replace("</body>", FOOTER_HTML + "\n</body>")

    # ── Inject V2 CSS ──
    # Remove old canonical nav CSS
    html = re.sub(
        r"/\* -- Koda Nav V2 -- \*/.*?/\* -- End Koda Nav V2 -- \*/",
        "", html, flags=re.DOTALL,
    )
    html = re.sub(
        r"/\* -- Canonical Nav -- \*/.*?@media\(max-width:768px\)\{\.koda-nav-link[^}]*\}\s*\}?",
        "", html, flags=re.DOTALL,
    )
    # Clean stray orphaned braces before the V2 CSS injection point
    html = re.sub(r"\n\s*}\s*\n+\s*\n*(?=</style>)", "\n", html)
    if "Koda Nav V2" not in html:
        css_with_end = css.rstrip() + "\n/* -- End Koda Nav V2 -- */\n"
        html = html.replace("</style>", css_with_end + "</style>", 1)

    # ── Ensure Material Symbols loaded ──
    if "Material+Symbols+Outlined" not in html:
        html = html.replace(
            "</head>",
            '<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet">\n</head>',
            1,
        )

    filepath.write_text(html, encoding="utf-8")
    print(f"  Updated: {filepath.name}")


if __name__ == "__main__":
    articles = sorted(EDITORIAL_DIR.glob("2026-*.html"))
    print(f"Found {len(articles)} editorial articles")
    for article in articles:
        update_article(article)
    print("Done")
