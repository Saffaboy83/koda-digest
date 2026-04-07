"""
Build the AI benchmark dashboard HTML page from scraped data.
Uses the Koda Digest design system.

Usage:
    python benchmarks/build_page.py
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
    "General": "#3B82F6",
    "Reasoning": "#8B5CF6",
    "Coding": "#10B981",
    "Math": "#F59E0B",
    "Safety": "#EF4444",
}

CATEGORY_ICONS: dict[str, str] = {
    "General": "forum",
    "Reasoning": "psychology",
    "Coding": "code",
    "Math": "calculate",
    "Safety": "shield",
}


def build_html(data: dict) -> str:
    generated_at = data.get("generated_at", "")
    try:
        dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        date_label = dt.strftime("%B %d, %Y")
    except Exception:
        date_label = generated_at[:10] if generated_at else "Unknown"

    benchmark_count = data.get("benchmark_count", 0)
    total_models = data.get("total_models", 0)

    # Build leaderboard columns (side by side on desktop)
    bench_cards = []
    for bench in data.get("benchmarks", []):
        name = bench.get("benchmark", "")
        category = bench.get("category", "General")
        description = bench.get("description", "")
        color = CATEGORY_COLORS.get(category, "#3B82F6")
        icon = CATEGORY_ICONS.get(category, "leaderboard")
        models = bench.get("models", [])
        source_url = bench.get("source_url", "")
        score_label = "Elo" if "arena" in name.lower() else "Score"

        rows = ""
        for m in models[:15]:
            rank = m.get("rank", "")
            model_name = m.get("model_name", "")
            score = m.get("score") or m.get("elo_score") or ""
            provider = m.get("provider", "")

            medal = ""
            if rank == 1:
                medal = '&#129351; '
            elif rank == 2:
                medal = '&#129352; '
            elif rank == 3:
                medal = '&#129353; '

            rank_style = f'color:{color};font-weight:700' if rank <= 3 else 'color:#8c909f'
            score_display = f"{score}" if score else "N/A"

            rows += f'''<tr>
<td style="text-align:center;{rank_style};width:44px">{medal}{rank}</td>
<td><span class="font-mono text-[12px]">{model_name}</span><br><span style="font-size:10px;color:#64748B">{provider}</span></td>
<td style="text-align:right;font-weight:600;font-size:13px">{score_display}</td>
</tr>'''

        bench_cards.append(f'''
        <div class="bench-card animate-in">
            <div class="bench-card-header" style="border-bottom-color:{color}30">
                <div style="display:flex;align-items:center;gap:8px">
                    <span class="material-symbols-outlined" style="color:{color}">{icon}</span>
                    <h3 style="font-size:16px;font-weight:800">{name}</h3>
                </div>
                <a href="{source_url}" target="_blank" rel="noopener" class="source-link">{score_label} &nearr;</a>
            </div>
            <p style="color:#8c909f;font-size:11px;padding:8px 16px 0;line-height:1.4">{description}</p>
            <div class="bench-card-table">
                <table>
                    <thead><tr>
                        <th style="text-align:center;width:44px">#</th>
                        <th>Model</th>
                        <th style="text-align:right">{score_label}</th>
                    </tr></thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>
        </div>''')

    sections_html = '<div class="bench-grid">' + ''.join(bench_cards) + '</div>'

    # Top 3 across all benchmarks for hero cards
    hero_cards = ""
    for bench in data.get("benchmarks", []):
        category = bench.get("category", "General")
        color = CATEGORY_COLORS.get(category, "#3B82F6")
        icon = CATEGORY_ICONS.get(category, "leaderboard")
        models = bench.get("models", [])
        if models:
            top = models[0]
            name = bench.get("benchmark", "").split("(")[0].strip()
            score = top.get("score") or top.get("elo_score") or "N/A"
            hero_cards += f'''
            <div class="p-4 bg-[#131b2e] border border-white/[0.06] rounded-xl hover:bg-[#171f33] transition-colors duration-300">
                <div class="flex items-center gap-2 mb-2">
                    <span class="material-symbols-outlined text-lg" style="color:{color}">{icon}</span>
                    <span class="text-[10px] uppercase tracking-wider font-bold" style="color:{color}">{name}</span>
                </div>
                <div class="text-sm font-bold text-[#dae2fd]">&#129351; {top.get("model_name", "")}</div>
                <div class="text-xs text-[#8c909f] mt-0.5">{top.get("provider", "")}</div>
                <div class="text-lg font-black mt-2" style="color:{color}">{score}</div>
            </div>'''

    nav_css, nav_html, nav_js = build_nav_v2(
        current_page="benchmarks",
        url_prefix="../",
        page_subtitle="Leaderboard",
        page_icon="trophy",
        share_url="https://www.koda.community/benchmarks/",
    )

    html_head = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Leaderboard | Koda Intelligence</title>
<meta name="description" content="Live AI model benchmark rankings across {benchmark_count} leaderboards. Updated daily by Koda Intelligence.">
<meta property="og:title" content="Leaderboard | Koda Intelligence">
<meta property="og:url" content="https://www.koda.community/benchmarks/">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Inter',sans-serif;background:#0b1326;color:#dae2fd;min-height:100vh;overflow-x:hidden}}
.material-symbols-outlined{{font-variation-settings:'FILL' 0,'wght' 400,'GRAD' 0,'opsz' 24;display:inline-block;vertical-align:middle}}
.scroll-progress{{position:fixed;top:0;left:0;width:0%;height:3px;background:linear-gradient(90deg,#3B82F6,#8B5CF6);z-index:1001;transition:width 0.1s linear;pointer-events:none}}
.hero{{padding:100px 24px 40px;text-align:center;background:radial-gradient(ellipse 80% 50% at 20% 60%,rgba(59,130,246,0.12) 0%,transparent 100%),radial-gradient(ellipse 60% 40% at 80% 30%,rgba(139,92,246,0.08) 0%,transparent 100%)}}
.hero h1{{font-size:clamp(28px,5vw,48px);font-weight:900;background:linear-gradient(135deg,#3B82F6 0%,#8B5CF6 50%,#EC4899 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:8px;letter-spacing:-0.02em}}
.hero p{{color:#c2c6d6;font-size:15px;max-width:600px;margin:0 auto}}
.hero .badge{{display:inline-block;padding:4px 14px;border-radius:9999px;border:1px solid rgba(173,198,255,0.2);background:rgba(173,198,255,0.05);color:#adc6ff;font-size:10px;text-transform:uppercase;letter-spacing:0.2em;font-weight:700;margin-bottom:16px}}
.stats{{display:flex;gap:16px;justify-content:center;flex-wrap:wrap;padding:0 24px;margin-bottom:32px}}
.stat{{background:rgba(23,31,51,0.4);backdrop-filter:blur(20px);border:1px solid rgba(173,198,255,0.1);border-radius:12px;padding:16px 24px;text-align:center;min-width:120px}}
.stat-value{{font-size:24px;font-weight:800;color:#dae2fd}}
.stat-label{{font-size:11px;color:#8c909f;margin-top:2px;text-transform:uppercase;letter-spacing:0.05em}}
.container{{max-width:1280px;margin:0 auto;padding:0 24px 64px}}
.section-header{{display:flex;align-items:center;gap:12px;margin-bottom:16px;margin-top:40px;flex-wrap:wrap}}
.section-header h2{{font-size:20px;font-weight:900;text-transform:uppercase;letter-spacing:-0.01em;white-space:nowrap}}
.section-header .line{{height:1px;flex-grow:1;background:rgba(255,255,255,0.06)}}
.source-link{{font-size:11px;color:#adc6ff;text-decoration:none;font-weight:600;white-space:nowrap}}
.source-link:hover{{color:white}}
.leaders{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin-bottom:32px}}
.table-wrap{{border-radius:16px;border:1px solid rgba(255,255,255,0.06);overflow:hidden;background:rgba(23,31,51,0.3);backdrop-filter:blur(12px)}}
table{{width:100%;border-collapse:collapse;font-size:14px}}
thead th{{text-align:left;padding:14px 16px;color:#8c909f;font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:0.08em;background:rgba(11,19,38,0.6);border-bottom:1px solid rgba(255,255,255,0.06)}}
tbody tr{{border-bottom:1px solid rgba(255,255,255,0.03);transition:background 0.15s}}
tbody tr:hover{{background:rgba(59,130,246,0.05)}}
tbody td{{padding:12px 16px}}
.font-mono{{font-family:'JetBrains Mono',monospace}}
.bench-grid{{display:grid;grid-template-columns:1fr;gap:20px;margin-top:32px}}
@media(min-width:1024px){{.bench-grid{{grid-template-columns:repeat(3,1fr)}}}}
@media(min-width:768px) and (max-width:1023px){{.bench-grid{{grid-template-columns:1fr 1fr}}}}
.bench-card{{border-radius:16px;border:1px solid rgba(255,255,255,0.06);background:rgba(23,31,51,0.3);backdrop-filter:blur(12px);overflow:hidden;display:flex;flex-direction:column}}
.bench-card-header{{display:flex;justify-content:space-between;align-items:center;padding:16px;border-bottom:2px solid rgba(255,255,255,0.06)}}
.bench-card-table{{flex:1;overflow-y:auto;max-height:600px}}
.bench-card-table table{{font-size:13px}}
.bench-card-table thead th{{position:sticky;top:0;background:rgba(11,19,38,0.9);padding:10px 12px;font-size:10px}}
.bench-card-table tbody td{{padding:8px 12px;border-bottom:1px solid rgba(255,255,255,0.03)}}
.bench-card-table tbody tr:hover{{background:rgba(59,130,246,0.05)}}
footer{{background:#060e20;border-top:1px solid rgba(255,255,255,0.06);margin-top:auto}}
footer .inner{{max-width:1280px;margin:0 auto;display:flex;flex-direction:column;align-items:center;padding:32px 24px;gap:12px;text-align:center}}
@media(min-width:768px){{footer .inner{{flex-direction:row;justify-content:space-between;text-align:left}}}}
.animate-in{{opacity:0;transform:translateY(24px);transition:opacity 0.7s cubic-bezier(0.16,1,0.3,1),transform 0.7s cubic-bezier(0.16,1,0.3,1)}}
.animate-in.visible{{opacity:1;transform:translateY(0)}}
.back-to-top{{position:fixed;bottom:24px;right:24px;width:44px;height:44px;border-radius:50%;background:rgba(23,31,51,0.9);backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,0.08);color:#dae2fd;font-size:18px;cursor:pointer;z-index:999;opacity:0;transform:translateY(12px);transition:opacity 0.3s,transform 0.3s,background 0.2s;pointer-events:none;display:flex;align-items:center;justify-content:center}}
.back-to-top.visible{{opacity:1;transform:translateY(0);pointer-events:auto}}
.back-to-top:hover{{background:#6366F1;color:white}}
@media(max-width:768px){{
  .stats{{gap:8px}}.stat{{padding:12px 16px;min-width:100px}}.stat-value{{font-size:18px}}
  table{{font-size:12px}}thead th,tbody td{{padding:8px 10px}}
  .leaders{{grid-template-columns:1fr 1fr}}
}}
@media(max-width:480px){{.leaders{{grid-template-columns:1fr}}}}
'''

    page_body = nav_css + '''
</style>
</head>
<body>
<div class="scroll-progress" id="scrollProgress"></div>
''' + nav_html + f'''
<section class="hero animate-in">
    <div class="badge">Live Leaderboards</div>
    <h1><span class="material-symbols-outlined" style="font-size:0.7em;vertical-align:-0.04em;margin-right:8px">trophy</span>Leaderboard</h1>
    <p>{benchmark_count} leaderboards, {total_models} model rankings. Who's winning the AI race right now.</p>
</section>
<div class="stats animate-in">
    <div class="stat"><div class="stat-value">{benchmark_count}</div><div class="stat-label">Benchmarks</div></div>
    <div class="stat"><div class="stat-value">{total_models}</div><div class="stat-label">Rankings</div></div>
    <div class="stat"><div class="stat-value">{date_label}</div><div class="stat-label">Last Scraped</div></div>
</div>
<div class="container">
    <div class="section-header animate-in">
        <span class="material-symbols-outlined" style="color:#F59E0B">emoji_events</span>
        <h2>Current Leaders</h2>
        <div class="line"></div>
    </div>
    <div class="leaders animate-in">{hero_cards}</div>
    {sections_html}
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
            <a href="https://x.com/intent/tweet?url=https://www.koda.community/benchmarks/" target="_blank" rel="noopener" style="width:36px;height:36px;border-radius:8px;background:rgba(255,255,255,0.05);display:flex;align-items:center;justify-content:center;color:#8c909f;text-decoration:none" title="Share on X"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg></a>
            <a href="https://www.linkedin.com/sharing/share-offsite/?url=https://www.koda.community/benchmarks/" target="_blank" rel="noopener" style="width:36px;height:36px;border-radius:8px;background:rgba(255,255,255,0.05);display:flex;align-items:center;justify-content:center;color:#8c909f;text-decoration:none" title="Share on LinkedIn"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg></a>
            <button onclick="navigator.clipboard.writeText('https://www.koda.community/benchmarks/')" style="width:36px;height:36px;border-radius:8px;background:rgba(255,255,255,0.05);display:flex;align-items:center;justify-content:center;color:#8c909f;border:none;cursor:pointer" title="Copy link"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg></button>
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
<button class="back-to-top" id="backToTop" onclick="window.scrollTo({{top:0,behavior:'smooth'}})" aria-label="Back to top">
    <span class="material-symbols-outlined">arrow_upward</span>
</button>
<script>
window.addEventListener('scroll',function(){{
  var h=document.documentElement;
  var pct=(h.scrollTop/(h.scrollHeight-h.clientHeight))*100;
  document.getElementById('scrollProgress').style.width=pct+'%';
  var btn=document.getElementById('backToTop');
  if(h.scrollTop>400)btn.classList.add('visible');else btn.classList.remove('visible');
}});
var obs=new IntersectionObserver(function(entries){{
  entries.forEach(function(e){{if(e.isIntersecting)e.target.classList.add('visible')}});
}},{{threshold:0.1}});
document.querySelectorAll('.animate-in').forEach(function(el){{obs.observe(el)}});

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

    return html_head + page_body


def main() -> None:
    parser = argparse.ArgumentParser(description="Build benchmark dashboard")
    parser.add_argument("--input", default=str(Path(__file__).parent / "data.json"))
    parser.add_argument("--output", default=str(Path(__file__).parent / "index.html"))
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: {input_path} not found. Run scrape_benchmarks.py first.")
        sys.exit(1)

    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    html = build_html(data)
    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Built benchmark page: {output_path} ({len(html)} chars)")


if __name__ == "__main__":
    main()
