"""
Build the "Who Shipped What" changelog HTML page.
Uses the Koda Digest design system.

Usage:
    python changelog/build_page.py
"""

import argparse
import json
import sys
import os
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CATEGORY_COLORS: dict[str, str] = {
    "Model Release": "#8B5CF6",
    "Feature": "#3B82F6",
    "API Update": "#14B8A6",
    "SDK Release": "#22D3EE",
    "Developer Tools": "#A78BFA",
    "Pricing": "#10B981",
    "Policy": "#F59E0B",
    "Partnership": "#06B6D4",
    "Research": "#EC4899",
    "Infrastructure": "#6366F1",
    "Open Source": "#84CC16",
    "Acquisition": "#F97316",
    "Safety": "#EF4444",
}

CATEGORY_ICONS: dict[str, str] = {
    "Model Release": "rocket_launch",
    "Feature": "new_releases",
    "API Update": "api",
    "SDK Release": "code",
    "Developer Tools": "build",
    "Pricing": "payments",
    "Policy": "gavel",
    "Partnership": "handshake",
    "Research": "science",
    "Infrastructure": "dns",
    "Open Source": "lock_open",
    "Acquisition": "merge_type",
    "Safety": "shield",
}


def format_display_date(iso_date: str) -> str:
    """Convert YYYY-MM-DD to human-readable format."""
    try:
        dt = datetime.strptime(iso_date, "%Y-%m-%d")
        return dt.strftime("%b %d, %Y")
    except Exception:
        return iso_date


def build_html(data: dict) -> str:
    generated_at = data.get("generated_at", "")
    try:
        dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        date_label = dt.strftime("%B %d, %Y")
    except Exception:
        date_label = generated_at[:10] if generated_at else "Unknown"

    entries = data.get("entries", [])
    total_entries = data.get("total_entries", len(entries))
    new_today = data.get("new_today", 0)
    companies_with_posts = data.get("companies_with_posts", 0)

    # Entries are already sorted newest-first from the scraper
    # Group entries by company
    by_company: dict[str, list[dict]] = {}
    for e in entries:
        company = e.get("company", "Unknown")
        by_company.setdefault(company, []).append(e)

    # Build company filter buttons
    company_colors = {e.get("company", ""): e.get("color", "#3B82F6") for e in entries}

    filter_buttons = '<button class="filter-btn active" onclick="filterCompany(this,\'all\')">All</button>\n'
    for company in sorted(by_company.keys()):
        color = company_colors.get(company, "#3B82F6")
        filter_buttons += f'<button class="filter-btn" style="--btn-color:{color}" onclick="filterCompany(this,\'{company}\')">{company}</button>\n'

    # Build timeline entries
    timeline_html = ""
    if not entries:
        timeline_html = '<div class="empty-state animate-in"><span class="material-symbols-outlined" style="font-size:48px;color:#64748B">inbox</span><p style="color:#8c909f;margin-top:12px">No releases detected. Check back after the next scan.</p></div>'
    else:
        for company, posts in sorted(by_company.items()):
            color = posts[0].get("color", "#3B82F6")
            cards = ""
            for p in posts:
                cat = p.get("category", "")
                cat_color = CATEGORY_COLORS.get(cat, "#64748B")
                cat_icon = CATEGORY_ICONS.get(cat, "article")
                title = p.get("title", "")
                summary = p.get("summary", "")
                url = p.get("url", "")
                raw_date = p.get("date", "")
                display_date = format_display_date(raw_date)

                link_html = f'<a href="{url}" target="_blank" rel="noopener" style="color:#adc6ff;font-size:11px;text-decoration:none;font-weight:600">Read &nearr;</a>' if url else ""
                date_html = f'<span style="color:#64748B;font-size:11px">{display_date}</span>' if display_date else ""

                cards += f'''
                <div class="changelog-card">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
                        <span class="material-symbols-outlined" style="font-size:16px;color:{cat_color}">{cat_icon}</span>
                        <span class="text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded-full" style="color:{cat_color};background:{cat_color}15">{cat or "Update"}</span>
                        {date_html}
                    </div>
                    <div style="font-size:14px;font-weight:700;color:#dae2fd;margin-bottom:4px">{title}</div>
                    <div style="font-size:12px;color:#c2c6d6;line-height:1.5">{summary}</div>
                    <div style="margin-top:8px">{link_html}</div>
                </div>'''

            timeline_html += f'''
        <div class="company-section animate-in" data-company="{company}">
            <div class="company-header">
                <div class="company-dot" style="background:{color}"></div>
                <h3 style="font-size:18px;font-weight:800">{company}</h3>
                <span style="color:#64748B;font-size:12px">{len(posts)} release{"s" if len(posts) != 1 else ""}</span>
                <div style="height:1px;flex-grow:1;background:rgba(255,255,255,0.06)"></div>
            </div>
            <div class="changelog-cards">{cards}</div>
        </div>'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Who Shipped What | Koda Intelligence</title>
<meta name="description" content="Daily AI company release tracker. {total_entries} releases across {companies_with_posts} companies in the last 30 days.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Inter',sans-serif;background:#0b1326;color:#dae2fd;min-height:100vh;overflow-x:hidden}}
.material-symbols-outlined{{font-variation-settings:'FILL' 0,'wght' 400,'GRAD' 0,'opsz' 24;display:inline-block;vertical-align:middle}}
.scroll-progress{{position:fixed;top:0;left:0;width:0%;height:3px;background:linear-gradient(90deg,#3B82F6,#8B5CF6);z-index:1001;transition:width 0.1s linear;pointer-events:none}}
.topbar{{position:fixed;top:0;width:100%;z-index:50;background:rgba(11,19,38,0.8);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border-bottom:1px solid rgba(255,255,255,0.06)}}
.topbar-inner{{max-width:1280px;margin:0 auto;padding:0 24px;height:56px;display:flex;align-items:center;justify-content:space-between}}
.brand{{display:flex;align-items:center;gap:12px;text-decoration:none;color:inherit}}
.brand-icon{{width:32px;height:32px;border-radius:8px;background:linear-gradient(135deg,#3B82F6,#8B5CF6);display:flex;align-items:center;justify-content:center;color:white;font-weight:900;font-size:14px}}
.brand-text{{font-size:14px;font-weight:700;color:#3B82F6}}
.brand-sub{{font-size:10px;color:#8c909f;display:none}}
@media(min-width:640px){{.brand-sub{{display:block}}}}
.nav-links{{display:flex;align-items:center;gap:8px}}
.nav-link{{font-size:11px;font-family:'JetBrains Mono',monospace;font-weight:700;padding:6px 12px;border-radius:8px;text-decoration:none;transition:all 0.2s}}
.nav-link-home{{background:linear-gradient(135deg,#3B82F6,#6366F1);color:white}}
.nav-link-secondary{{color:#8c909f;background:rgba(255,255,255,0.04)}}
.nav-link-secondary:hover{{color:#dae2fd;background:rgba(255,255,255,0.08)}}
.hero{{padding:100px 24px 40px;text-align:center;background:radial-gradient(ellipse 80% 50% at 20% 60%,rgba(59,130,246,0.12) 0%,transparent 100%),radial-gradient(ellipse 60% 40% at 80% 30%,rgba(139,92,246,0.08) 0%,transparent 100%)}}
.hero h1{{font-size:clamp(28px,5vw,48px);font-weight:900;background:linear-gradient(135deg,#3B82F6 0%,#8B5CF6 50%,#EC4899 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:8px;letter-spacing:-0.02em}}
.hero p{{color:#c2c6d6;font-size:15px;max-width:600px;margin:0 auto}}
.hero .badge{{display:inline-block;padding:4px 14px;border-radius:9999px;border:1px solid rgba(173,198,255,0.2);background:rgba(173,198,255,0.05);color:#adc6ff;font-size:10px;text-transform:uppercase;letter-spacing:0.2em;font-weight:700;margin-bottom:16px}}
.stats{{display:flex;gap:16px;justify-content:center;flex-wrap:wrap;padding:0 24px;margin-bottom:32px}}
.stat{{background:rgba(23,31,51,0.4);backdrop-filter:blur(20px);border:1px solid rgba(173,198,255,0.1);border-radius:12px;padding:16px 24px;text-align:center;min-width:120px}}
.stat-value{{font-size:24px;font-weight:800;color:#dae2fd}}
.stat-label{{font-size:11px;color:#8c909f;margin-top:2px;text-transform:uppercase;letter-spacing:0.05em}}
.container{{max-width:900px;margin:0 auto;padding:0 24px 64px}}
.company-section{{margin-bottom:40px}}
.company-header{{display:flex;align-items:center;gap:12px;margin-bottom:16px}}
.company-dot{{width:10px;height:10px;border-radius:50%;flex-shrink:0}}
.changelog-cards{{display:flex;flex-direction:column;gap:10px;padding-left:22px;border-left:2px solid rgba(255,255,255,0.06);margin-left:4px}}
.changelog-card{{background:rgba(23,31,51,0.4);border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:14px 16px;transition:background 0.2s}}
.changelog-card:hover{{background:rgba(23,31,51,0.7)}}
.filter-bar{{margin-bottom:28px}}
.filter-pills{{display:flex;flex-wrap:wrap;gap:6px}}
.filter-btn{{font-size:11px;font-weight:600;padding:5px 12px;border-radius:9999px;border:1px solid rgba(255,255,255,0.08);background:rgba(255,255,255,0.03);color:#c2c6d6;cursor:pointer;transition:all 0.2s;font-family:'Inter',sans-serif}}
.filter-btn:hover{{background:rgba(255,255,255,0.08);color:#dae2fd}}
.filter-btn.active{{background:var(--btn-color,#3B82F6);color:white;border-color:var(--btn-color,#3B82F6)}}
.empty-state{{text-align:center;padding:60px 24px}}
footer{{background:#060e20;border-top:1px solid rgba(255,255,255,0.06);margin-top:auto}}
footer .inner{{max-width:1280px;margin:0 auto;display:flex;flex-direction:column;align-items:center;padding:32px 24px;gap:12px;text-align:center}}
@media(min-width:768px){{footer .inner{{flex-direction:row;justify-content:space-between;text-align:left}}}}
.animate-in{{opacity:0;transform:translateY(24px);transition:opacity 0.7s cubic-bezier(0.16,1,0.3,1),transform 0.7s cubic-bezier(0.16,1,0.3,1)}}
.animate-in.visible{{opacity:1;transform:translateY(0)}}
.back-to-top{{position:fixed;bottom:24px;right:24px;width:44px;height:44px;border-radius:50%;background:rgba(23,31,51,0.9);backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,0.08);color:#dae2fd;cursor:pointer;z-index:999;opacity:0;transform:translateY(12px);transition:opacity 0.3s,transform 0.3s,background 0.2s;pointer-events:none;display:flex;align-items:center;justify-content:center}}
.back-to-top.visible{{opacity:1;transform:translateY(0);pointer-events:auto}}
.back-to-top:hover{{background:#6366F1;color:white}}
</style>
</head>
<body>
<div class="scroll-progress" id="scrollProgress"></div>
<header class="topbar">
<div class="topbar-inner">
    <a href="../index.html" class="brand"><div class="brand-icon">K</div><div><div class="brand-text">Koda Intelligence</div><div class="brand-sub"><span class="material-symbols-outlined" style="font-size:11px;vertical-align:-1px;margin-right:2px">pulse_alert</span>Pulse</div></div></a>
    <div class="nav-links">
        <a href="../morning-briefing-koda.html" class="nav-link nav-link-secondary"><span class="material-symbols-outlined" style="font-size:13px;vertical-align:-2px;margin-right:2px">bolt</span>The Signal</a>
        <a href="../pricing/" class="nav-link nav-link-secondary"><span class="material-symbols-outlined" style="font-size:13px;vertical-align:-2px;margin-right:2px">monitoring</span>Token Tracker</a>
        <a href="../benchmarks/" class="nav-link nav-link-secondary"><span class="material-symbols-outlined" style="font-size:13px;vertical-align:-2px;margin-right:2px">trophy</span>Leaderboard</a>
        <a href="../index.html" class="nav-link nav-link-home">&larr; Home</a>
    </div>
</div>
</header>
<section class="hero animate-in">
    <div class="badge">Daily Release Tracker</div>
    <h1>Who Shipped What</h1>
    <p>Every AI company release tracked daily. Model launches, API updates, pricing changes, partnerships, and more across 25 companies.</p>
</section>
<div class="stats animate-in">
    <div class="stat"><div class="stat-value">{total_entries}</div><div class="stat-label">Releases (30 days)</div></div>
    <div class="stat"><div class="stat-value">{companies_with_posts}</div><div class="stat-label">Companies</div></div>
    <div class="stat"><div class="stat-value">{new_today}</div><div class="stat-label">New Today</div></div>
    <div class="stat"><div class="stat-value">{date_label}</div><div class="stat-label">Last Scanned</div></div>
</div>
<div class="container">
    <div class="filter-bar animate-in">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
            <span class="material-symbols-outlined" style="color:#3B82F6;font-size:18px">filter_alt</span>
            <span style="font-size:11px;color:#8c909f;text-transform:uppercase;letter-spacing:0.1em;font-weight:600">Filter by Company</span>
        </div>
        <div class="filter-pills">{filter_buttons}</div>
    </div>
    {timeline_html}
</div>
<footer><div class="inner">
    <div><span style="font-size:14px;font-weight:700;color:#3B82F6">Koda Intelligence</span>
    <p style="font-size:11px;color:#c2c6d6;margin-top:4px">Blog URLs mapped and diffed daily via Firecrawl. New posts scraped for summaries.</p></div>
    <div style="display:flex;gap:24px;font-size:11px;text-transform:uppercase;letter-spacing:0.08em">
        <a href="../index.html" style="color:#c2c6d6;text-decoration:none">Home</a>
        <a href="../pricing/" style="color:#c2c6d6;text-decoration:none">Token Tracker</a>
        <span style="color:#64748B">&copy; 2026 Koda Intelligence</span>
    </div>
</div></footer>
<button class="back-to-top" id="backToTop" onclick="window.scrollTo({{top:0,behavior:'smooth'}})"><span class="material-symbols-outlined">arrow_upward</span></button>
<script>
window.addEventListener('scroll',function(){{
  var h=document.documentElement;
  document.getElementById('scrollProgress').style.width=(h.scrollTop/(h.scrollHeight-h.clientHeight))*100+'%';
  var btn=document.getElementById('backToTop');
  if(h.scrollTop>400)btn.classList.add('visible');else btn.classList.remove('visible');
}});
var obs=new IntersectionObserver(function(e){{e.forEach(function(x){{if(x.isIntersecting)x.target.classList.add('visible')}});}},{{threshold:0.1}});
document.querySelectorAll('.animate-in').forEach(function(el){{obs.observe(el);}});

function filterCompany(btn, company) {{
  document.querySelectorAll('.filter-btn').forEach(function(b){{b.classList.remove('active')}});
  btn.classList.add('active');
  document.querySelectorAll('.company-section').forEach(function(s){{
    s.style.display = (company === 'all' || s.dataset.company === company) ? '' : 'none';
  }});
}}
</script>
</body>
</html>'''


def main() -> None:
    parser = argparse.ArgumentParser(description="Build changelog page")
    parser.add_argument("--input", default=str(Path(__file__).parent / "data.json"))
    parser.add_argument("--output", default=str(Path(__file__).parent / "index.html"))
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: {input_path} not found. Run scrape_changelog.py first.")
        sys.exit(1)

    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    html = build_html(data)
    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Built changelog page: {output_path} ({len(html)} chars)")


if __name__ == "__main__":
    main()
