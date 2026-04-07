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
from nav_component import build_nav_v2

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

    nav_css, nav_html, nav_js = build_nav_v2(
        current_page="changelog",
        url_prefix="../",
        page_subtitle="Pulse",
        page_icon="pulse_alert",
        share_url="https://www.koda.community/changelog/",
    )

    # Build HTML with Nav V2 via concatenation (avoid brace issues in f-strings)
    html_head = f'''<!DOCTYPE html>
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
'''
    page_css = '''*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',sans-serif;background:#0b1326;color:#dae2fd;min-height:100vh;overflow-x:hidden}
.material-symbols-outlined{font-variation-settings:'FILL' 0,'wght' 400,'GRAD' 0,'opsz' 24;display:inline-block;vertical-align:middle}
.scroll-progress{position:fixed;top:0;left:0;width:0%;height:3px;background:linear-gradient(90deg,#3B82F6,#8B5CF6);z-index:1001;transition:width 0.1s linear;pointer-events:none}
'''

    return html_head + nav_css + "\n" + page_css + f'''.hero{{padding:100px 24px 40px;text-align:center;background:radial-gradient(ellipse 80% 50% at 20% 60%,rgba(59,130,246,0.12) 0%,transparent 100%),radial-gradient(ellipse 60% 40% at 80% 30%,rgba(139,92,246,0.08) 0%,transparent 100%)}}
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
''' + nav_html + f'''
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
<!-- Subscribe CTA -->
<section style="width:100%;padding:64px 24px">
    <div style="max-width:36rem;margin:0 auto;text-align:center">
        <div style="background:rgba(11,19,38,0.6);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.06);border-radius:16px;padding:40px;position:relative;overflow:hidden">
            <div style="position:absolute;top:0;left:50%;transform:translateX(-50%);width:128px;height:4px;background:linear-gradient(90deg,#3B82F6,#8B5CF6,#EC4899);border-radius:0 0 4px 4px"></div>
            <h3 style="font-size:20px;font-weight:700;color:white;margin-bottom:8px">Like what you see?</h3>
            <p style="color:#c2c6d6;font-size:14px;margin-bottom:24px">Get tomorrow's brief delivered to your inbox.</p>
            <form style="display:flex;gap:8px;max-width:28rem;margin:0 auto;padding:6px;border-radius:9999px;background:#171f33;border:1px solid rgba(255,255,255,0.06)" onsubmit="return kodaSubscribe(this)">
                <input type="email" name="email" required style="background:transparent;border:none;outline:none;color:white;padding:12px 20px;width:100%;font-size:14px" placeholder="your@email.com">
                <button type="submit" style="background:linear-gradient(135deg,#3B82F6,#6366F1);color:white;padding:12px 24px;border-radius:9999px;font-weight:700;font-size:14px;white-space:nowrap;border:none;cursor:pointer">Subscribe</button>
            </form>
            <p style="font-size:10px;color:#8c909f;margin-top:12px">One email per day. Unsubscribe anytime.</p>
        </div>
    </div>
</section>
<footer style="border-top:1px solid rgba(255,255,255,0.05);padding:64px 24px;position:relative;overflow:hidden">
    <div style="position:absolute;bottom:0;left:50%;transform:translateX(-50%);width:500px;height:200px;background:linear-gradient(to top,rgba(139,92,246,0.04),transparent);border-radius:50%;filter:blur(48px);pointer-events:none"></div>
    <div style="max-width:40rem;margin:0 auto;text-align:center;position:relative;z-index:1">
        <div style="display:flex;align-items:center;justify-content:center;gap:12px;margin-bottom:24px">
            <a href="https://x.com/intent/tweet?url=https://www.koda.community/changelog/" target="_blank" rel="noopener" style="width:36px;height:36px;border-radius:8px;background:rgba(255,255,255,0.05);display:flex;align-items:center;justify-content:center;color:#8c909f;text-decoration:none" title="Share on X"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg></a>
            <a href="https://www.linkedin.com/sharing/share-offsite/?url=https://www.koda.community/changelog/" target="_blank" rel="noopener" style="width:36px;height:36px;border-radius:8px;background:rgba(255,255,255,0.05);display:flex;align-items:center;justify-content:center;color:#8c909f;text-decoration:none" title="Share on LinkedIn"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg></a>
            <button onclick="navigator.clipboard.writeText('https://www.koda.community/changelog/')" style="width:36px;height:36px;border-radius:8px;background:rgba(255,255,255,0.05);display:flex;align-items:center;justify-content:center;color:#8c909f;border:none;cursor:pointer" title="Copy link"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg></button>
            <a href="../index.html" style="width:36px;height:36px;border-radius:8px;background:rgba(255,255,255,0.05);display:flex;align-items:center;justify-content:center;color:#8c909f;text-decoration:none" title="Search"><span class="material-symbols-outlined" style="font-size:16px">search</span></a>
        </div>
        <div style="display:inline-flex;align-items:center;gap:12px;margin-bottom:24px">
            <div style="width:36px;height:36px;border-radius:12px;background:linear-gradient(135deg,#3B82F6,#8B5CF6);display:flex;align-items:center;justify-content:center;color:white;font-weight:800;font-size:14px;box-shadow:0 4px 12px rgba(139,92,246,0.2)">K</div>
            <span style="font-size:18px;font-weight:700;background:linear-gradient(90deg,#3B82F6,#8B5CF6,#EC4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">Koda Intelligence</span>
        </div>
        <p style="color:#c2c6d6;font-size:14px;margin-bottom:32px">Read. Listen. Watch. Every morning.</p>
        <div style="display:flex;align-items:center;justify-content:center;gap:24px;margin-bottom:40px">
            <a href="../morning-briefing-koda.html" style="font-size:12px;font-weight:600;color:#c2c6d6;text-decoration:none;text-transform:uppercase;letter-spacing:0.05em"><span class="material-symbols-outlined" style="font-size:12px;vertical-align:-2px;margin-right:2px">bolt</span>The Signal</a>
            <span style="color:rgba(140,144,159,0.3)">|</span>
            <a href="../archive/" style="font-size:12px;font-weight:600;color:#c2c6d6;text-decoration:none;text-transform:uppercase;letter-spacing:0.05em"><span class="material-symbols-outlined" style="font-size:12px;vertical-align:-2px;margin-right:2px">lock_open</span>The Vault</a>
            <span style="color:rgba(140,144,159,0.3)">|</span>
            <a href="https://www.youtube.com/channel/UC8qqiKRGFAd5SwTr_2ZzPJg" target="_blank" rel="noopener" style="font-size:12px;font-weight:600;color:#c2c6d6;text-decoration:none;text-transform:uppercase;letter-spacing:0.05em">YouTube</a>
        </div>
        <p style="font-size:11px;color:rgba(140,144,159,0.6)">&copy; 2026 Koda Community &middot; <span style="font-family:'JetBrains Mono',monospace">koda.community</span></p>
    </div>
</footer>
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

/* Beehiiv Subscribe */
function kodaSubscribe(form){{
    var btn=form.querySelector('button');
    var email=form.querySelector('input[name="email"]').value;
    btn.textContent='Subscribing...';btn.disabled=true;
    fetch('/api/subscribe',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{email:email}})}}).then(function(r){{
        if(r.ok){{btn.textContent='Subscribed!';btn.style.background='#10B981';form.querySelector('input[name="email"]').value='';}}
        else{{btn.textContent='Try again';btn.disabled=false;}}
    }}).catch(function(){{btn.textContent='Try again';btn.disabled=false;}});
    return false;
}}
</script>
''' + nav_js + '''
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
