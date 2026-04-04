"""
Build the pricing comparison HTML page from scraped data.
Uses the Koda Digest design system for consistent look and feel.

Usage:
    python pricing/build_page.py
    python pricing/build_page.py --input pricing/data.json --output pricing/index.html
"""

import argparse
import json
import sys
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROVIDER_COLORS: dict[str, str] = {
    "OpenAI": "#10B981",
    "Anthropic": "#D97706",
    "Google Gemini": "#3B82F6",
    "Mistral": "#F97316",
    "Groq": "#EC4899",
    "Together AI": "#8B5CF6",
    "xAI": "#6366F1",
    "Perplexity": "#06B6D4",
    "Cohere": "#EF4444",
    "AWS Bedrock": "#F59E0B",
}


def format_price(price: float | int | None) -> str:
    if price is None:
        return '<span style="color:#64748B">N/A</span>'
    if price == 0:
        return '<span style="color:#10B981">Free</span>'
    if price < 0.01:
        return f"${price:.4f}"
    if price < 1:
        return f"${price:.2f}"
    return f"${price:,.2f}"


def build_html(data: dict) -> str:
    generated_at = data.get("generated_at", "")
    try:
        dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        date_label = dt.strftime("%B %d, %Y")
    except Exception:
        date_label = generated_at[:10] if generated_at else "Unknown"

    provider_count = data.get("provider_count", 0)
    total_models = data.get("total_models", 0)

    # Collect all models
    all_models: list[dict] = []
    providers_set: set[str] = set()
    types_set: set[str] = set()
    for p in data.get("providers", []):
        provider = p.get("provider", "")
        providers_set.add(provider)
        for m in p.get("models", []):
            model_type = m.get("model_type", "chat") or "chat"
            types_set.add(model_type)
            all_models.append({
                "provider": provider,
                "model": m.get("model_name", ""),
                "input": m.get("input_price_per_1m_tokens"),
                "output": m.get("output_price_per_1m_tokens"),
                "context": m.get("context_window", ""),
                "type": model_type,
            })

    all_models.sort(key=lambda x: (x["input"] is None, x["input"] or 999999))

    # Build takeaways: cheapest per major type
    cheapest: dict[str, dict] = {}
    for m in all_models:
        t = m["type"]
        inp = m["input"]
        if inp and inp > 0 and (t not in cheapest or inp < cheapest[t]["input"]):
            cheapest[t] = m

    takeaway_types = ["chat", "reasoning", "embedding", "image"]
    takeaway_cards = ""
    takeaway_icons = {"chat": "forum", "reasoning": "psychology", "embedding": "data_array", "image": "image"}
    takeaway_colors = {"chat": "#3B82F6", "reasoning": "#8B5CF6", "embedding": "#06B6D4", "image": "#EC4899"}
    for t in takeaway_types:
        if t in cheapest:
            c = cheapest[t]
            color = takeaway_colors.get(t, "#3B82F6")
            icon = takeaway_icons.get(t, "star")
            takeaway_cards += f'''
            <div class="p-4 bg-[#131b2e] border border-white/[0.06] rounded-xl hover:bg-[#171f33] transition-colors duration-300">
                <div class="flex items-center gap-2 mb-2">
                    <span class="material-symbols-outlined text-lg" style="color:{color}">{icon}</span>
                    <span class="text-[10px] uppercase tracking-wider font-bold" style="color:{color}">Cheapest {t}</span>
                </div>
                <div class="text-sm font-bold text-[#dae2fd]">{c["model"]}</div>
                <div class="text-xs text-[#8c909f] mt-0.5">{c["provider"]}</div>
                <div class="text-lg font-black mt-2" style="color:{color}">{format_price(c["input"])}<span class="text-[10px] font-normal text-[#8c909f]"> / 1M input</span></div>
            </div>'''

    # Provider filter buttons
    provider_buttons = ""
    for prov in sorted(providers_set):
        color = PROVIDER_COLORS.get(prov, "#94A3B8")
        provider_buttons += f'<button class="filter-btn" data-filter="provider" data-value="{prov}" style="--btn-color:{color}" onclick="toggleFilter(this)">{prov}</button>\n'

    # Type filter buttons
    type_buttons = ""
    for t in sorted(types_set):
        type_buttons += f'<button class="filter-btn" data-filter="type" data-value="{t}" onclick="toggleFilter(this)">{t}</button>\n'

    # Table rows
    rows_html = ""
    for m in all_models:
        color = PROVIDER_COLORS.get(m["provider"], "#94A3B8")
        ctx = m["context"] or "N/A"
        ctx_class = ' style="color:#64748B"' if ctx == "N/A" else ""
        rows_html += f'''<tr data-provider="{m['provider']}" data-type="{m['type']}">
<td><span style="color:{color};font-weight:600">{m['provider']}</span></td>
<td class="font-mono text-[13px]">{m['model']}</td>
<td class="text-right">{format_price(m['input'])}</td>
<td class="text-right">{format_price(m['output'])}</td>
<td class="text-center"{ctx_class}>{ctx}</td>
<td class="text-center"><span class="text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded-full" style="color:{color};background:{color}15">{m['type']}</span></td>
</tr>'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Token Tracker | Koda Intelligence</title>
<meta name="description" content="Live comparison of AI API pricing across {provider_count} providers and {total_models} models. Updated weekly by Koda Intelligence.">
<meta property="og:title" content="Token Tracker | Koda Intelligence">
<meta property="og:description" content="{provider_count} providers, {total_models} models compared. Updated {date_label}.">
<meta property="og:url" content="https://www.koda.community/pricing/">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Inter',sans-serif;background:#0b1326;color:#dae2fd;min-height:100vh;overflow-x:hidden}}
.material-symbols-outlined{{font-variation-settings:'FILL' 0,'wght' 400,'GRAD' 0,'opsz' 24;display:inline-block;vertical-align:middle}}

/* ── Scroll progress ── */
.scroll-progress{{position:fixed;top:0;left:0;width:0%;height:3px;background:linear-gradient(90deg,#3B82F6,#8B5CF6);z-index:1001;transition:width 0.1s linear;pointer-events:none}}

/* ── Topbar ── */
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

/* ── Hero ── */
.hero{{padding:100px 24px 40px;text-align:center;background:radial-gradient(ellipse 80% 50% at 20% 60%,rgba(59,130,246,0.12) 0%,transparent 100%),radial-gradient(ellipse 60% 40% at 80% 30%,rgba(139,92,246,0.08) 0%,transparent 100%)}}
.hero h1{{font-size:clamp(28px,5vw,48px);font-weight:900;background:linear-gradient(135deg,#3B82F6 0%,#8B5CF6 50%,#EC4899 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:8px;letter-spacing:-0.02em}}
.hero p{{color:#c2c6d6;font-size:15px;max-width:600px;margin:0 auto}}
.hero .badge{{display:inline-block;padding:4px 14px;border-radius:9999px;border:1px solid rgba(173,198,255,0.2);background:rgba(173,198,255,0.05);color:#adc6ff;font-size:10px;text-transform:uppercase;letter-spacing:0.2em;font-weight:700;margin-bottom:16px}}

/* ── Stats strip ── */
.stats{{display:flex;gap:16px;justify-content:center;flex-wrap:wrap;padding:0 24px;margin-bottom:32px}}
.stat{{background:rgba(23,31,51,0.4);backdrop-filter:blur(20px);border:1px solid rgba(173,198,255,0.1);border-radius:12px;padding:16px 24px;text-align:center;min-width:120px}}
.stat-value{{font-size:24px;font-weight:800;color:#dae2fd}}
.stat-label{{font-size:11px;color:#8c909f;margin-top:2px;text-transform:uppercase;letter-spacing:0.05em}}

/* ── Main container ── */
.container{{max-width:1280px;margin:0 auto;padding:0 24px 64px}}

/* ── Section headers ── */
.section-header{{display:flex;align-items:center;gap:16px;margin-bottom:24px;margin-top:40px}}
.section-header h2{{font-size:20px;font-weight:900;text-transform:uppercase;letter-spacing:-0.01em;white-space:nowrap}}
.section-header .line{{height:1px;flex-grow:1;background:rgba(255,255,255,0.06)}}

/* ── Takeaway cards ── */
.takeaways{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin-bottom:32px}}

/* ── Filter bar ── */
.filters{{margin-bottom:20px}}
.filter-group{{margin-bottom:12px}}
.filter-label{{font-size:11px;color:#8c909f;text-transform:uppercase;letter-spacing:0.1em;font-weight:600;margin-bottom:8px;display:flex;align-items:center;gap:6px}}
.filter-pills{{display:flex;flex-wrap:wrap;gap:6px}}
.filter-btn{{font-size:11px;font-weight:600;padding:5px 12px;border-radius:9999px;border:1px solid rgba(255,255,255,0.08);background:rgba(255,255,255,0.03);color:#c2c6d6;cursor:pointer;transition:all 0.2s;font-family:'Inter',sans-serif}}
.filter-btn:hover{{background:rgba(255,255,255,0.08);color:#dae2fd}}
.filter-btn.active{{background:var(--btn-color,#3B82F6);color:white;border-color:var(--btn-color,#3B82F6)}}
.filter-btn[data-filter="type"].active{{background:#3B82F6;border-color:#3B82F6}}
.search-wrap{{position:relative;margin-bottom:16px}}
.search-wrap .material-symbols-outlined{{position:absolute;left:14px;top:50%;transform:translateY(-50%);color:#64748B;font-size:20px}}
.search-input{{width:100%;padding:10px 16px 10px 42px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;color:#dae2fd;font-size:14px;font-family:'Inter',sans-serif;outline:none;transition:border-color 0.2s}}
.search-input:focus{{border-color:#3B82F6;box-shadow:0 0 0 3px rgba(59,130,246,0.1)}}
.search-input::placeholder{{color:#64748B}}

/* ── Table ── */
.table-wrap{{border-radius:16px;border:1px solid rgba(255,255,255,0.06);overflow:hidden;background:rgba(23,31,51,0.3);backdrop-filter:blur(12px)}}
table{{width:100%;border-collapse:collapse;font-size:14px}}
thead th{{text-align:left;padding:14px 16px;color:#8c909f;font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:0.08em;background:rgba(11,19,38,0.6);position:sticky;top:56px;z-index:10;border-bottom:1px solid rgba(255,255,255,0.06)}}
tbody tr{{border-bottom:1px solid rgba(255,255,255,0.03);transition:background 0.15s}}
tbody tr:hover{{background:rgba(59,130,246,0.05)}}
tbody td{{padding:12px 16px}}
.font-mono{{font-family:'JetBrains Mono',monospace}}
.text-right{{text-align:right}}
.text-center{{text-align:center}}
.count-badge{{font-size:12px;color:#8c909f;margin-top:8px;text-align:center}}

/* ── Footer ── */
footer{{background:#060e20;border-top:1px solid rgba(255,255,255,0.06);margin-top:auto}}
footer .inner{{max-width:1280px;margin:0 auto;display:flex;flex-direction:column;align-items:center;padding:32px 24px;gap:12px;text-align:center}}
@media(min-width:768px){{footer .inner{{flex-direction:row;justify-content:space-between;text-align:left}}}}

/* ── Animations ── */
.animate-in{{opacity:0;transform:translateY(24px);transition:opacity 0.7s cubic-bezier(0.16,1,0.3,1),transform 0.7s cubic-bezier(0.16,1,0.3,1)}}
.animate-in.visible{{opacity:1;transform:translateY(0)}}

/* ── Back to top ── */
.back-to-top{{position:fixed;bottom:24px;right:24px;width:44px;height:44px;border-radius:50%;background:rgba(23,31,51,0.9);backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,0.08);color:#dae2fd;font-size:18px;cursor:pointer;z-index:999;opacity:0;transform:translateY(12px);transition:opacity 0.3s,transform 0.3s,background 0.2s;pointer-events:none;display:flex;align-items:center;justify-content:center}}
.back-to-top.visible{{opacity:1;transform:translateY(0);pointer-events:auto}}
.back-to-top:hover{{background:#6366F1;color:white}}

@media(max-width:768px){{
  .stats{{gap:8px}}
  .stat{{padding:12px 16px;min-width:100px}}
  .stat-value{{font-size:18px}}
  table{{font-size:12px}}
  thead th,tbody td{{padding:8px 10px}}
  .takeaways{{grid-template-columns:1fr 1fr}}
}}
@media(max-width:480px){{
  .takeaways{{grid-template-columns:1fr}}
}}
</style>
</head>
<body>

<div class="scroll-progress" id="scrollProgress"></div>

<!-- ── Topbar ── -->
<header class="topbar">
<div class="topbar-inner">
    <a href="../index.html" class="brand">
        <div class="brand-icon">K</div>
        <div>
            <div class="brand-text">Koda Intelligence</div>
            <div class="brand-sub"><span class="material-symbols-outlined" style="font-size:11px;vertical-align:-1px;margin-right:2px">monitoring</span>Token Tracker</div>
        </div>
    </a>
    <div class="nav-links">
        <a href="../morning-briefing-koda.html" class="nav-link nav-link-secondary"><span class="material-symbols-outlined" style="font-size:13px;vertical-align:-2px;margin-right:2px">bolt</span>The Signal</a>
        <a href="../editorial/" class="nav-link nav-link-secondary" style="display:none"><span class="material-symbols-outlined" style="font-size:13px;vertical-align:-2px;margin-right:2px">explore</span>Deep Dive</a>
        <a href="../index.html" class="nav-link nav-link-home">&larr; Home</a>
    </div>
</div>
</header>

<!-- ── Hero ── -->
<section class="hero animate-in">
    <div class="badge">Updated Weekly</div>
    <h1><span class="material-symbols-outlined" style="font-size:0.7em;vertical-align:-0.04em;margin-right:8px">monitoring</span>Token Tracker</h1>
    <p>{provider_count} providers, {total_models} models compared side by side. Sorted by cost. Updated {date_label}.</p>
</section>

<!-- ── Stats ── -->
<div class="stats animate-in">
    <div class="stat">
        <div class="stat-value">{provider_count}</div>
        <div class="stat-label">Providers</div>
    </div>
    <div class="stat">
        <div class="stat-value">{total_models}</div>
        <div class="stat-label">Models</div>
    </div>
    <div class="stat">
        <div class="stat-value">{date_label}</div>
        <div class="stat-label">Last Scraped</div>
    </div>
</div>

<div class="container">

    <!-- ── Key Takeaways ── -->
    <div class="section-header animate-in">
        <span class="material-symbols-outlined" style="color:#F59E0B">insights</span>
        <h2>Key Takeaways</h2>
        <div class="line"></div>
    </div>
    <div class="takeaways animate-in">
        {takeaway_cards}
    </div>

    <!-- ── Filters ── -->
    <div class="section-header animate-in">
        <span class="material-symbols-outlined" style="color:#3B82F6">filter_alt</span>
        <h2>Compare Models</h2>
        <div class="line"></div>
    </div>

    <div class="filters animate-in">
        <div class="search-wrap">
            <span class="material-symbols-outlined">search</span>
            <input type="text" class="search-input" placeholder="Search models, providers... (e.g. gpt, claude, gemini, llama)" oninput="applyFilters()">
        </div>
        <div class="filter-group">
            <div class="filter-label"><span class="material-symbols-outlined text-sm">business</span> Provider</div>
            <div class="filter-pills" id="providerFilters">
                <button class="filter-btn active" data-filter="provider" data-value="all" onclick="toggleFilter(this)">All</button>
                {provider_buttons}
            </div>
        </div>
        <div class="filter-group">
            <div class="filter-label"><span class="material-symbols-outlined text-sm">category</span> Type</div>
            <div class="filter-pills" id="typeFilters">
                <button class="filter-btn active" data-filter="type" data-value="all" onclick="toggleFilter(this)">All</button>
                {type_buttons}
            </div>
        </div>
    </div>

    <!-- ── Table ── -->
    <div class="table-wrap animate-in">
        <table id="pricingTable">
            <thead>
                <tr>
                    <th>Provider</th>
                    <th>Model</th>
                    <th class="text-right">Input / 1M</th>
                    <th class="text-right">Output / 1M</th>
                    <th class="text-center">Context</th>
                    <th class="text-center">Type</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
    <div class="count-badge" id="countBadge">Showing {total_models} of {total_models} models</div>

</div>

<!-- ── Subscribe CTA ── -->
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

<!-- ── Footer ── -->
<footer style="border-top:1px solid rgba(255,255,255,0.05);padding:64px 24px;position:relative;overflow:hidden">
    <div style="position:absolute;bottom:0;left:50%;transform:translateX(-50%);width:500px;height:200px;background:linear-gradient(to top,rgba(139,92,246,0.04),transparent);border-radius:50%;filter:blur(48px);pointer-events:none"></div>
    <div style="max-width:40rem;margin:0 auto;text-align:center;position:relative;z-index:1">
        <div style="display:flex;align-items:center;justify-content:center;gap:12px;margin-bottom:24px">
            <a href="https://x.com/intent/tweet?url=https://www.koda.community/pricing/" target="_blank" rel="noopener" style="width:36px;height:36px;border-radius:8px;background:rgba(255,255,255,0.05);display:flex;align-items:center;justify-content:center;color:#8c909f;text-decoration:none" title="Share on X"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg></a>
            <a href="https://www.linkedin.com/sharing/share-offsite/?url=https://www.koda.community/pricing/" target="_blank" rel="noopener" style="width:36px;height:36px;border-radius:8px;background:rgba(255,255,255,0.05);display:flex;align-items:center;justify-content:center;color:#8c909f;text-decoration:none" title="Share on LinkedIn"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg></a>
            <button onclick="navigator.clipboard.writeText('https://www.koda.community/pricing/')" style="width:36px;height:36px;border-radius:8px;background:rgba(255,255,255,0.05);display:flex;align-items:center;justify-content:center;color:#8c909f;border:none;cursor:pointer" title="Copy link"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg></button>
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

<!-- ── Back to top ── -->
<button class="back-to-top" id="backToTop" onclick="window.scrollTo({{top:0,behavior:'smooth'}})" aria-label="Back to top">
    <span class="material-symbols-outlined">arrow_upward</span>
</button>

<script>
// ── Scroll progress ──
window.addEventListener('scroll',function(){{
  var h=document.documentElement;
  var pct=(h.scrollTop/(h.scrollHeight-h.clientHeight))*100;
  document.getElementById('scrollProgress').style.width=pct+'%';
  var btn=document.getElementById('backToTop');
  if(h.scrollTop>400)btn.classList.add('visible');else btn.classList.remove('visible');
}});

// ── Animations ──
var obs=new IntersectionObserver(function(entries){{
  entries.forEach(function(e){{if(e.isIntersecting)e.target.classList.add('visible')}});
}},{{threshold:0.1}});
document.querySelectorAll('.animate-in').forEach(function(el){{obs.observe(el)}});

// ── Filters ──
var activeProvider='all', activeType='all';

function toggleFilter(btn){{
  var group=btn.dataset.filter;
  var value=btn.dataset.value;
  var container=btn.parentElement;
  container.querySelectorAll('.filter-btn').forEach(function(b){{b.classList.remove('active')}});
  btn.classList.add('active');
  if(group==='provider')activeProvider=value;
  if(group==='type')activeType=value;
  applyFilters();
}}

function applyFilters(){{
  var q=(document.querySelector('.search-input')||{{}}).value||'';
  q=q.toLowerCase();
  var rows=document.querySelectorAll('#pricingTable tbody tr');
  var shown=0;
  rows.forEach(function(r){{
    var matchProvider=activeProvider==='all'||r.dataset.provider===activeProvider;
    var matchType=activeType==='all'||r.dataset.type===activeType;
    var matchSearch=!q||r.textContent.toLowerCase().includes(q);
    if(matchProvider&&matchType&&matchSearch){{r.style.display='';shown++}}
    else{{r.style.display='none'}}
  }});
  document.getElementById('countBadge').textContent='Showing '+shown+' of {total_models} models';
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
</body>
</html>'''


def main() -> None:
    parser = argparse.ArgumentParser(description="Build pricing comparison page")
    parser.add_argument("--input", default=str(Path(__file__).parent / "data.json"))
    parser.add_argument("--output", default=str(Path(__file__).parent / "index.html"))
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: {input_path} not found. Run scrape_pricing.py first.")
        sys.exit(1)

    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    html = build_html(data)
    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Built pricing page: {output_path} ({len(html)} chars)")


if __name__ == "__main__":
    main()
