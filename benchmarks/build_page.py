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

    # Build leaderboard sections
    sections_html = ""
    for bench in data.get("benchmarks", []):
        name = bench.get("benchmark", "")
        category = bench.get("category", "General")
        description = bench.get("description", "")
        color = CATEGORY_COLORS.get(category, "#3B82F6")
        icon = CATEGORY_ICONS.get(category, "leaderboard")
        models = bench.get("models", [])
        source_url = bench.get("source_url", "")

        rows = ""
        for m in models[:20]:
            rank = m.get("rank", "")
            model_name = m.get("model_name", "")
            score = m.get("score") or m.get("elo_score") or ""
            provider = m.get("provider", "")

            # Medal for top 3
            medal = ""
            if rank == 1:
                medal = '<span style="margin-right:4px">&#129351;</span>'
            elif rank == 2:
                medal = '<span style="margin-right:4px">&#129352;</span>'
            elif rank == 3:
                medal = '<span style="margin-right:4px">&#129353;</span>'

            score_display = f"{score}" if score else "N/A"
            rows += f'''<tr>
<td style="text-align:center;font-weight:700;color:{color}">{medal}{rank}</td>
<td class="font-mono text-[13px]">{model_name}</td>
<td style="color:#8c909f">{provider}</td>
<td style="text-align:right;font-weight:600">{score_display}</td>
</tr>'''

        sections_html += f'''
    <div class="bench-section animate-in">
        <div class="section-header">
            <span class="material-symbols-outlined" style="color:{color}">{icon}</span>
            <h2>{name}</h2>
            <span class="text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded-full" style="color:{color};background:{color}15">{category}</span>
            <div class="line"></div>
            <a href="{source_url}" target="_blank" rel="noopener" class="source-link">Source &nearr;</a>
        </div>
        <p style="color:#8c909f;font-size:13px;margin-bottom:16px">{description}</p>
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th style="text-align:center;width:60px">Rank</th>
                        <th>Model</th>
                        <th>Provider</th>
                        <th style="text-align:right">Score</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
    </div>'''

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

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Benchmark Dashboard | Koda Intelligence</title>
<meta name="description" content="Live AI model benchmark rankings across {benchmark_count} leaderboards. Updated daily by Koda Intelligence.">
<meta property="og:title" content="AI Benchmark Dashboard | Koda Intelligence">
<meta property="og:url" content="https://www.koda.community/benchmarks/">
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
.nav-link-home:hover{{box-shadow:0 4px 16px rgba(59,130,246,0.3)}}
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
.bench-section{{margin-bottom:48px}}
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
</style>
</head>
<body>
<div class="scroll-progress" id="scrollProgress"></div>
<header class="topbar">
<div class="topbar-inner">
    <a href="../index.html" class="brand"><div class="brand-icon">K</div><div><div class="brand-text">Koda Intelligence</div><div class="brand-sub">AI Benchmarks</div></div></a>
    <div class="nav-links">
        <a href="../morning-briefing-koda.html" class="nav-link nav-link-secondary">Digest</a>
        <a href="../pricing/" class="nav-link nav-link-secondary">Pricing</a>
        <a href="../index.html" class="nav-link nav-link-home">&larr; Home</a>
    </div>
</div>
</header>
<section class="hero animate-in">
    <div class="badge">Live Leaderboards</div>
    <h1>AI Benchmark Dashboard</h1>
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
<footer><div class="inner">
    <div><span style="font-size:14px;font-weight:700;color:#3B82F6">Koda Intelligence</span>
    <p style="font-size:11px;color:#c2c6d6;margin-top:4px">Rankings scraped from official leaderboard pages via Firecrawl.</p></div>
    <div style="display:flex;gap:24px;font-size:11px;text-transform:uppercase;letter-spacing:0.08em">
        <a href="../index.html" style="color:#c2c6d6;text-decoration:none">Home</a>
        <a href="../pricing/" style="color:#c2c6d6;text-decoration:none">Pricing</a>
        <span style="color:#64748B">&copy; 2026 Koda Intelligence</span>
    </div>
</div></footer>
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
</script>
</body>
</html>'''


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
