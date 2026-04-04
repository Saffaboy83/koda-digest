"""Shared navigation component for all Koda Intelligence pages.

Single source of truth for the topbar + hamburger drawer navigation.
Used by: update_nav_footer.py, update_editorial_nav.py, pipeline scripts.
"""
from __future__ import annotations

# ── Nav items (icon, label, relative_path, page_id) ──

NAV_ITEMS: list[tuple[str, str, str, str]] = [
    ("bolt", "The Signal", "morning-briefing-koda.html", "signal"),
    ("explore", "Deep Dive", "editorial/", "editorial"),
    ("monitoring", "Token Tracker", "pricing/", "pricing"),
    ("trophy", "Leaderboard", "benchmarks/", "benchmarks"),
    ("science", "The Lab", "reviews/", "reviews"),
    ("pulse_alert", "Pulse", "changelog/", "changelog"),
    ("lock_open", "The Vault", "archive/", "archive"),
]

# ── CSS (kn- prefix to avoid collisions) ──

NAV_CSS_V2 = """
/* -- Koda Nav V2 -- */
.kn-topbar{position:fixed;top:0;width:100%;z-index:1000;background:rgba(11,19,38,0.85);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border-bottom:1px solid rgba(255,255,255,0.06)}
.kn-topbar-inner{max-width:1280px;margin:0 auto;padding:0 20px;height:56px;display:flex;align-items:center;justify-content:space-between;gap:8px}
.kn-brand{display:flex;align-items:center;gap:10px;text-decoration:none;color:inherit;flex-shrink:0}
.kn-brand-icon{width:32px;height:32px;border-radius:8px;background:linear-gradient(135deg,#3B82F6,#8B5CF6);display:flex;align-items:center;justify-content:center;color:white;font-weight:900;font-size:14px;flex-shrink:0}
.kn-brand-text{font-size:14px;font-weight:700;color:#3B82F6}
.kn-brand-sub{font-size:10px;color:#8c909f;display:none}
@media(min-width:640px){.kn-brand-sub{display:block}}

/* Desktop nav links */
.kn-links{display:none;align-items:center;gap:2px;overflow-x:auto;-webkit-overflow-scrolling:touch;flex:1;justify-content:center}
@media(min-width:769px){.kn-links{display:flex}}
.kn-link{font-size:10px;font-family:'JetBrains Mono',monospace;font-weight:700;padding:5px 8px;border-radius:6px;text-decoration:none;transition:all 0.2s;white-space:nowrap;color:#8c909f;background:rgba(255,255,255,0.04)}
.kn-link:hover{color:#dae2fd;background:rgba(255,255,255,0.08)}
.kn-link-active{color:#3B82F6!important;background:rgba(59,130,246,0.12)!important;border-bottom:2px solid #3B82F6}
.kn-link .material-symbols-outlined{font-size:13px;vertical-align:-2px;margin-right:2px}

/* Actions (search, hamburger) */
.kn-actions{display:flex;align-items:center;gap:4px;flex-shrink:0}
.kn-action-btn{width:36px;height:36px;border-radius:8px;background:rgba(255,255,255,0.05);display:flex;align-items:center;justify-content:center;color:#8c909f;border:none;cursor:pointer;transition:all 0.2s;text-decoration:none}
.kn-action-btn:hover{background:rgba(59,130,246,0.15);color:#3B82F6}
.kn-action-btn .material-symbols-outlined{font-size:20px}

/* Hamburger - visible on mobile only */
.kn-hamburger{display:flex}
@media(min-width:769px){.kn-hamburger{display:none}}

/* Desktop social - hidden on mobile (drawer has them) */
.kn-desktop-social{display:none;align-items:center;gap:4px}
@media(min-width:769px){.kn-desktop-social{display:flex}}

/* Home button - desktop only, in links row */
.kn-home{background:linear-gradient(135deg,#3B82F6,#6366F1);color:white!important;font-size:10px;font-family:'JetBrains Mono',monospace;font-weight:700;padding:5px 10px;border-radius:6px;text-decoration:none;white-space:nowrap;transition:all 0.2s}
.kn-home:hover{box-shadow:0 4px 16px rgba(59,130,246,0.3)}

/* ── Drawer ── */
.kn-overlay{position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:1001;opacity:0;visibility:hidden;transition:opacity 0.3s,visibility 0.3s}
.kn-overlay.kn-open{opacity:1;visibility:visible}
.kn-drawer{position:fixed;top:0;right:0;bottom:0;width:min(280px,85vw);background:rgba(11,19,38,0.98);backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);border-left:1px solid rgba(173,198,255,0.1);z-index:1002;transform:translateX(100%);transition:transform 0.3s cubic-bezier(0.16,1,0.3,1);overflow-y:auto;-webkit-overflow-scrolling:touch}
.kn-drawer.kn-open{transform:translateX(0)}
@media(prefers-reduced-motion:reduce){.kn-overlay,.kn-drawer{transition-duration:0.01ms!important}}

/* Drawer header */
.kn-drawer-header{display:flex;align-items:center;justify-content:space-between;padding:16px 20px;border-bottom:1px solid rgba(255,255,255,0.06)}
.kn-drawer-brand{display:flex;align-items:center;gap:10px}
.kn-drawer-close{width:36px;height:36px;border-radius:8px;background:rgba(255,255,255,0.05);display:flex;align-items:center;justify-content:center;color:#8c909f;border:none;cursor:pointer;transition:all 0.2s}
.kn-drawer-close:hover{background:rgba(239,68,68,0.15);color:#EF4444}

/* Drawer sections */
.kn-drawer-section{padding:12px 20px 4px;font-size:9px;font-family:'JetBrains Mono',monospace;font-weight:700;text-transform:uppercase;letter-spacing:0.15em;color:#6b7280}
.kn-drawer-divider{height:1px;background:rgba(255,255,255,0.06);margin:8px 20px}

/* Drawer nav links */
.kn-drawer-link{display:flex;align-items:center;gap:12px;padding:12px 20px;text-decoration:none;color:#c2c6d6;font-size:14px;font-weight:500;transition:all 0.2s;border-left:3px solid transparent}
.kn-drawer-link:hover{background:rgba(255,255,255,0.04);color:#dae2fd}
.kn-drawer-link-active{color:#3B82F6!important;border-left-color:#3B82F6;background:rgba(59,130,246,0.08)}
.kn-drawer-link .material-symbols-outlined{font-size:20px;color:#6b7280;flex-shrink:0}
.kn-drawer-link-active .material-symbols-outlined{color:#3B82F6}

/* Drawer home link */
.kn-drawer-home{display:flex;align-items:center;gap:12px;padding:12px 20px;text-decoration:none;color:white;font-size:14px;font-weight:600;border-left:3px solid transparent;transition:all 0.2s}
.kn-drawer-home:hover{background:rgba(59,130,246,0.1)}
.kn-drawer-home .material-symbols-outlined{font-size:20px;color:#3B82F6}

/* Drawer social row */
.kn-drawer-social{display:flex;gap:8px;padding:12px 20px}
.kn-drawer-social a,.kn-drawer-social button{width:36px;height:36px;border-radius:8px;background:rgba(255,255,255,0.05);display:flex;align-items:center;justify-content:center;color:#8c909f;border:none;cursor:pointer;text-decoration:none;transition:all 0.2s}
.kn-drawer-social a:hover,.kn-drawer-social button:hover{background:rgba(59,130,246,0.15);color:#3B82F6}

/* Body scroll lock */
body.kn-locked{overflow:hidden}
"""


def _icon_span(icon: str, size: int = 13) -> str:
    return (
        f'<span class="material-symbols-outlined" '
        f'style="font-size:{size}px;vertical-align:-2px;margin-right:2px">{icon}</span>'
    )


def build_nav_v2(
    current_page: str,
    url_prefix: str = "../",
    page_subtitle: str = "",
    page_icon: str = "",
    share_url: str = "https://www.koda.community",
) -> tuple[str, str, str]:
    """Build the canonical nav component.

    Args:
        current_page: page_id of the current page (e.g. "signal", "editorial").
                      Use "" for the home page (no active link).
        url_prefix: Path prefix for nav hrefs ("../" for sub-dirs, "./" for root).
        page_subtitle: Optional subtitle shown next to brand on desktop.
        page_icon: Material icon name for the subtitle.
        share_url: URL used for social share buttons.

    Returns:
        (css_block, html_block, js_block) ready for injection.
    """
    home_url = f"{url_prefix}index.html"

    # ── Desktop links ──
    desktop_links: list[str] = []
    for icon, label, path, page_id in NAV_ITEMS:
        href = f"{url_prefix}{path}"
        cls = "kn-link kn-link-active" if page_id == current_page else "kn-link"
        desktop_links.append(
            f'<a href="{href}" class="{cls}">{_icon_span(icon)}{label}</a>'
        )
    # Home link at end (desktop only)
    desktop_links.append(f'<a href="{home_url}" class="kn-home">&larr; Home</a>')

    # ── Drawer links ──
    drawer_links: list[str] = []
    # Home first in drawer
    drawer_links.append(
        f'<a href="{home_url}" class="kn-drawer-home">'
        f'<span class="material-symbols-outlined">home</span>Home</a>'
    )
    for icon, label, path, page_id in NAV_ITEMS:
        href = f"{url_prefix}{path}"
        cls = "kn-drawer-link kn-drawer-link-active" if page_id == current_page else "kn-drawer-link"
        drawer_links.append(
            f'<a href="{href}" class="{cls}">'
            f'<span class="material-symbols-outlined">{icon}</span>{label}</a>'
        )

    # ── Brand subtitle ──
    sub_html = ""
    if page_subtitle and page_icon:
        sub_html = (
            f'<div class="kn-brand-sub">'
            f'<span class="material-symbols-outlined" style="font-size:11px;vertical-align:-1px;margin-right:2px">{page_icon}</span>'
            f'{page_subtitle}</div>'
        )

    # ── Assemble HTML ──
    html = f"""<!-- koda-nav-v2-start -->
<header class="kn-topbar" id="knTopbar">
<div class="kn-topbar-inner">
    <a href="{home_url}" class="kn-brand">
        <div class="kn-brand-icon">K</div>
        <div>
            <div class="kn-brand-text">Koda Intelligence</div>
            {sub_html}
        </div>
    </a>
    <div class="kn-links">
        {chr(10).join(f"        {l}" for l in desktop_links)}
    </div>
    <div class="kn-actions">
        <div class="kn-desktop-social">
            <a href="https://x.com/intent/tweet?url={share_url}" target="_blank" rel="noopener" class="kn-action-btn" title="Share on X">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
            </a>
            <a href="https://www.linkedin.com/sharing/share-offsite/?url={share_url}" target="_blank" rel="noopener" class="kn-action-btn" title="Share on LinkedIn">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>
            </a>
            <button class="kn-action-btn" onclick="navigator.clipboard.writeText(window.location.href);this.style.color='#10B981';setTimeout(()=>this.style.color='',1500)" title="Copy link">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg>
            </button>
        </div>
        <button class="kn-action-btn" id="knSearchBtn" title="Search (Ctrl+K)" aria-label="Search">
            <span class="material-symbols-outlined">search</span>
        </button>
        <button class="kn-action-btn kn-hamburger" id="knMenuBtn" title="Menu" aria-label="Open menu" aria-expanded="false">
            <span class="material-symbols-outlined">menu</span>
        </button>
    </div>
</div>
</header>

<!-- Drawer overlay -->
<div class="kn-overlay" id="knOverlay"></div>

<!-- Slide-out drawer -->
<nav class="kn-drawer" id="knDrawer" role="dialog" aria-modal="true" aria-label="Navigation menu">
    <div class="kn-drawer-header">
        <div class="kn-drawer-brand">
            <div class="kn-brand-icon">K</div>
            <span class="kn-brand-text">Koda</span>
        </div>
        <button class="kn-drawer-close" id="knDrawerClose" aria-label="Close menu">
            <span class="material-symbols-outlined">close</span>
        </button>
    </div>
    <div class="kn-drawer-section">Navigate</div>
    {chr(10).join(f"    {l}" for l in drawer_links)}
    <div class="kn-drawer-divider"></div>
    <div class="kn-drawer-section">Share</div>
    <div class="kn-drawer-social">
        <a href="https://x.com/intent/tweet?url={share_url}" target="_blank" rel="noopener" title="Share on X">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
        </a>
        <a href="https://www.linkedin.com/sharing/share-offsite/?url={share_url}" target="_blank" rel="noopener" title="Share on LinkedIn">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>
        </a>
        <button onclick="navigator.clipboard.writeText(window.location.href);this.style.color='#10B981';setTimeout(()=>this.style.color='',1500)" title="Copy link">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg>
        </button>
    </div>
</nav>
<!-- koda-nav-v2-end -->"""

    # ── JavaScript ──
    js = """<!-- koda-nav-v2-js-start -->
<script>
(function(){
    var btn=document.getElementById('knMenuBtn'),
        drawer=document.getElementById('knDrawer'),
        overlay=document.getElementById('knOverlay'),
        closeBtn=document.getElementById('knDrawerClose'),
        searchBtn=document.getElementById('knSearchBtn');
    function open(){
        drawer.classList.add('kn-open');
        overlay.classList.add('kn-open');
        document.body.classList.add('kn-locked');
        btn.setAttribute('aria-expanded','true');
        closeBtn.focus();
    }
    function close(){
        drawer.classList.remove('kn-open');
        overlay.classList.remove('kn-open');
        document.body.classList.remove('kn-locked');
        btn.setAttribute('aria-expanded','false');
        btn.focus();
    }
    if(btn) btn.addEventListener('click',open);
    if(closeBtn) closeBtn.addEventListener('click',close);
    if(overlay) overlay.addEventListener('click',close);
    document.addEventListener('keydown',function(e){
        if(e.key==='Escape' && drawer.classList.contains('kn-open')) close();
    });
    /* Search: hook into existing overlay if present, otherwise go to archive */
    if(searchBtn) searchBtn.addEventListener('click',function(){
        var so=document.getElementById('searchOverlay');
        if(so){so.classList.remove('hidden');so.style.display='';var si=document.getElementById('globalSearchInput');if(si)si.focus();}
        else{window.location.href=searchBtn.closest('.kn-topbar').querySelector('.kn-brand').href.replace('index.html','')+'archive/';}
    });
})();
</script>
<!-- koda-nav-v2-js-end -->"""

    return NAV_CSS_V2, html, js
