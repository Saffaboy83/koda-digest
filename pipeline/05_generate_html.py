"""
Step 05: Generate HTML dashboard from digest content.

Reads digest-content.json + media-status.json and renders the full
HTML dashboard. Saves both dated archive and current shortcut.

Input:  pipeline/data/digest-content.json, pipeline/data/media-status.json
Output: morning-briefing-koda.html, morning-briefing-koda-{date}.html
"""

import argparse
import json
import sys
import os
import shutil
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import DIGEST_DIR, today_str, read_json

# ── Template Loader ──────────────────────────────────────────────────────────

TEMPLATE_PATH = DIGEST_DIR / "templates" / "briefing.html"


def load_template():
    """Load the HTML template. Falls back to generating from current design."""
    if TEMPLATE_PATH.exists():
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return None


# ── HTML Generation Functions ────────────────────────────────────────────────

def render_kpi_strip(summary):
    """Render the KPI strip (4 cards)."""
    kpis = summary.get("kpis", {})
    colors = [("var(--blue)", "AI Stories", kpis.get("ai_stories", "0")),
              ("var(--red)", "World Events", kpis.get("world_events", "0")),
              ("var(--emerald)", "Market Mood", kpis.get("market_mood", "Mixed")),
              ("var(--purple)", "Tools Featured", kpis.get("tools_featured", "0"))]

    cards = ""
    for color, label, value in colors:
        cards += f'''<div class="kpi-card">
            <div class="kpi-value" style="color:{color}">{value}</div>
            <div class="kpi-label">{label}</div>
        </div>\n'''
    return f'<div class="kpi-strip">{cards}</div>'


def render_summary(summary):
    """Render the executive summary section."""
    hook = summary.get("hook", "")
    icons = {"ai": "🤖", "world": "🌍", "markets": "📊", "wildcard": "⚡"}
    colors = {"ai": "var(--blue)", "world": "var(--red)", "markets": "var(--emerald)", "wildcard": "var(--amber)"}

    briefs_html = ""
    for brief in summary.get("briefs", []):
        icon = icons.get(brief.get("icon", ""), "📌")
        color = colors.get(brief.get("icon", ""), "var(--blue)")
        briefs_html += f'''<div class="summary-brief" style="border-left:3px solid {color};padding:10px 16px;margin:10px 0;background:var(--bg-card);border-radius:0 12px 12px 0;">
            <div style="font-size:13px;font-weight:700;color:{color};margin-bottom:4px">{icon} {brief.get("label","")}</div>
            <div class="summary-brief-text" style="font-size:14px;color:var(--text-secondary)">{brief.get("text","")}</div>
        </div>\n'''

    return f'''<div class="section" id="daily-summary">
        <div class="section-title"><span class="section-icon">📋</span> Executive Summary</div>
        <div style="background:var(--bg-card);backdrop-filter:blur(12px);border:1px solid var(--border);border-radius:20px;padding:28px;box-shadow:0 4px 16px var(--shadow);">
            <div class="summary-hook" style="font-size:20px;font-weight:800;margin-bottom:18px;line-height:1.4">{hook}</div>
            {briefs_html}
        </div>
    </div>'''


def render_focus(summary):
    """Render Today's Focus section (3 numbered cards)."""
    topics = summary.get("focus_topics", [])
    if not topics:
        return ""

    cards = ""
    colors = ["var(--blue)", "var(--purple)", "var(--emerald)"]
    for i, topic in enumerate(topics):
        color = colors[i % len(colors)]
        cards += f'''<div style="background:var(--bg-card);backdrop-filter:blur(12px);border:1px solid var(--border);border-radius:16px;padding:24px;box-shadow:0 2px 8px var(--shadow);">
            <div style="font-size:32px;font-weight:800;color:{color};font-family:'JetBrains Mono',monospace;margin-bottom:8px">{topic.get("number", i+1)}</div>
            <div class="focus-content-title" style="font-size:16px;font-weight:700;margin-bottom:8px">{topic.get("title","")}</div>
            <div class="focus-content-body" style="font-size:14px;color:var(--text-secondary);line-height:1.6">{topic.get("description","")}</div>
        </div>\n'''

    return f'''<div class="section" id="todays-focus">
        <div class="section-title"><span class="section-icon">🎯</span> Today's Focus</div>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;">{cards}</div>
    </div>'''


def render_ai_news(stories):
    """Render AI Developments section."""
    if not stories:
        return ""

    category_colors = {
        "Model Release": "var(--blue)", "Benchmark": "var(--purple)", "Agents": "var(--indigo)",
        "Hardware": "var(--amber)", "Enterprise": "var(--emerald)", "Policy": "var(--red)",
        "Biotech": "var(--pink)", "Design": "var(--cyan)", "Trend": "var(--purple)",
        "China": "var(--red)", "Consolidation": "var(--amber)", "Open Source": "var(--emerald)",
    }

    cards = ""
    for story in stories:
        cat = story.get("category", "Trend")
        color = category_colors.get(cat, "var(--blue)")
        source_link = ""
        if story.get("source_url"):
            source_link = f' <a href="{story["source_url"]}" target="_blank" style="color:{color};font-size:11px;text-decoration:none;">Source →</a>'
        cards += f'''<div style="background:var(--bg-card);backdrop-filter:blur(12px);border:1px solid var(--border);border-radius:16px;padding:22px;box-shadow:0 2px 8px var(--shadow);">
            <div style="display:inline-block;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:{color};background:rgba(59,130,246,0.08);padding:3px 10px;border-radius:6px;margin-bottom:10px;">{cat}</div>
            <div class="card-title" style="font-size:15px;font-weight:700;margin-bottom:8px">{story.get("title","")}</div>
            <div class="card-body" style="font-size:13px;color:var(--text-secondary);line-height:1.6">{story.get("body","")}{source_link}</div>
        </div>\n'''

    return f'''<div class="section" id="ai-developments">
        <div class="section-title"><span class="section-icon">🤖</span> AI Developments</div>
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:16px;">{cards}</div>
    </div>'''


def render_world_news(stories):
    """Render World News section."""
    if not stories:
        return ""

    category_colors = {
        "Conflict": "var(--red)", "Diplomacy": "var(--blue)", "Economy": "var(--emerald)",
        "Policy": "var(--purple)", "Humanitarian": "var(--amber)", "Infrastructure": "var(--cyan)",
        "Climate": "var(--emerald)", "Technology": "var(--indigo)",
    }

    cards = ""
    for story in stories:
        cat = story.get("category", "World")
        color = category_colors.get(cat, "var(--blue)")
        source_link = ""
        if story.get("source_url"):
            source_link = f' <a href="{story["source_url"]}" target="_blank" style="color:{color};font-size:11px;text-decoration:none;">Source →</a>'
        cards += f'''<div style="background:var(--bg-card);backdrop-filter:blur(12px);border:1px solid var(--border);border-radius:16px;padding:22px;box-shadow:0 2px 8px var(--shadow);">
            <div style="display:inline-block;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:{color};background:rgba(59,130,246,0.08);padding:3px 10px;border-radius:6px;margin-bottom:10px;">{cat}</div>
            <div class="card-title" style="font-size:15px;font-weight:700;margin-bottom:8px">{story.get("title","")}</div>
            <div class="card-body" style="font-size:13px;color:var(--text-secondary);line-height:1.6">{story.get("body","")}{source_link}</div>
        </div>\n'''

    return f'''<div class="section" id="world-news">
        <div class="section-title"><span class="section-icon">🌍</span> World News</div>
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:16px;">{cards}</div>
    </div>'''


def render_markets(markets):
    """Render Market Snapshot section."""
    if not markets:
        return ""

    ticker_config = [
        ("sp500", "S&P 500", "📈"),
        ("nasdaq", "NASDAQ", "📊"),
        ("btc", "BTC", "₿"),
        ("eth", "ETH", "◆"),
        ("oil", "Oil Brent", "🛢"),
        ("sentiment", "Sentiment", "🧠"),
    ]

    cards = ""
    for key, label, icon in ticker_config:
        data = markets.get(key, {})
        if not isinstance(data, dict):
            continue
        price = data.get("price", data.get("value", "N/A"))
        change = data.get("change", data.get("label", ""))
        direction = data.get("direction", "neutral")
        color = "var(--emerald)" if direction == "up" else "var(--red)" if direction == "down" else "var(--amber)"

        cards += f'''<div style="background:var(--bg-card);backdrop-filter:blur(12px);border:1px solid var(--border);border-radius:16px;padding:20px;box-shadow:0 2px 8px var(--shadow);text-align:center;">
            <div style="font-size:20px;margin-bottom:4px">{icon}</div>
            <div class="market-ticker" style="font-size:11px;font-weight:700;color:var(--text-secondary);text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">{label}</div>
            <div class="market-price" style="font-size:22px;font-weight:800;font-family:'JetBrains Mono',monospace">{price}</div>
            <div class="market-change" style="font-size:13px;font-weight:700;color:{color};margin-top:4px">{change}</div>
        </div>\n'''

    return f'''<div class="section" id="market-snapshot">
        <div class="section-title"><span class="section-icon">📊</span> Market Snapshot</div>
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:16px;">{cards}</div>
    </div>'''


def render_newsletters(newsletters):
    """Render Newsletter Intelligence section."""
    if not newsletters:
        return ""

    cards = ""
    for nl in newsletters:
        name = nl.get("name", "Newsletter")
        date_badge = nl.get("date_badge", "")

        headlines = ""
        for h in nl.get("headlines", []):
            headlines += f'<li style="margin:4px 0;font-size:13px">{h}</li>'

        deep_dives = nl.get("deep_dives", "")
        quick_hits = ""
        for q in nl.get("quick_hits", []):
            quick_hits += f'<li style="margin:4px 0;font-size:13px">{q}</li>'

        tools_html = ""
        for t in nl.get("tools", []):
            if t:
                tools_html += f'<span style="display:inline-block;font-size:11px;font-weight:600;background:rgba(99,102,241,0.1);color:var(--indigo);padding:3px 10px;border-radius:6px;margin:2px 4px 2px 0">{t}</span>'

        quote = nl.get("quote", "")
        quote_html = f'''<blockquote class="newsletter-quote" style="border-left:3px solid var(--purple);padding:10px 16px;margin:12px 0;font-style:italic;color:var(--text-secondary);font-size:13px">"{quote}"</blockquote>''' if quote else ""

        source_link = nl.get("source_link", "")
        source_html = f'<a href="{source_link}" target="_blank" style="font-size:11px;color:var(--blue);text-decoration:none">View original →</a>' if source_link else ""

        cards += f'''<div style="background:var(--bg-card);backdrop-filter:blur(12px);border:1px solid var(--border);border-radius:20px;padding:28px;box-shadow:0 4px 16px var(--shadow);margin-bottom:16px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
                <div class="newsletter-name" style="font-size:16px;font-weight:700">{name}</div>
                <div style="font-size:11px;font-weight:600;color:var(--blue);background:rgba(59,130,246,0.1);padding:3px 10px;border-radius:6px">{date_badge}</div>
            </div>
            {"<div style='margin-bottom:12px'><div style=\"font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--text-secondary);margin-bottom:6px\">Headlines</div><ul style=\"list-style:none;padding:0\">" + headlines + "</ul></div>" if headlines else ""}
            {"<div style='margin-bottom:12px'><div style=\"font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--text-secondary);margin-bottom:6px\">Deep Dives</div><div class=\"newsletter-item\" style=\"font-size:13px;color:var(--text-secondary)\">" + deep_dives + "</div></div>" if deep_dives else ""}
            {"<div style='margin-bottom:12px'><div style=\"font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--text-secondary);margin-bottom:6px\">Quick Hits</div><ul style=\"list-style:none;padding:0\">" + quick_hits + "</ul></div>" if quick_hits else ""}
            {"<div style='margin-bottom:12px'><div style=\"font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--text-secondary);margin-bottom:6px\">Trending Tools</div>" + tools_html + "</div>" if tools_html else ""}
            {quote_html}
            {source_html}
        </div>\n'''

    return f'''<div class="section" id="newsletter-intelligence">
        <div class="section-title"><span class="section-icon">📬</span> Newsletter Intelligence</div>
        {cards}
    </div>'''


def render_competitive(companies):
    """Render Competitive Landscape section."""
    if not companies:
        return ""

    cards = ""
    for comp in companies:
        source_link = ""
        if comp.get("source_url"):
            source_link = f' <a href="{comp["source_url"]}" target="_blank" style="color:var(--blue);font-size:11px;text-decoration:none;">Source →</a>'
        cards += f'''<div style="background:var(--bg-card);backdrop-filter:blur(12px);border:1px solid var(--border);border-radius:16px;padding:22px;box-shadow:0 2px 8px var(--shadow);">
            <div class="comp-name" style="font-size:15px;font-weight:700;margin-bottom:4px">{comp.get("name","")}</div>
            <div style="font-size:12px;font-weight:600;color:var(--blue);margin-bottom:10px">{comp.get("status","")}</div>
            <div class="comp-body" style="font-size:13px;color:var(--text-secondary);line-height:1.6">{comp.get("body","")}{source_link}</div>
        </div>\n'''

    return f'''<div class="section" id="competitive-landscape">
        <div class="section-title"><span class="section-icon">🏢</span> Competitive Landscape</div>
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;">{cards}</div>
    </div>'''


def render_tools(tools):
    """Render AI Tool Guide section."""
    if not tools:
        return ""

    category_icons = {
        "Mindset": "🧠", "Build": "🔨", "Hardware": "💻", "Creativity": "🎨",
        "Productivity": "⚡", "Coding": "💻",
    }

    cards = ""
    for i, tool in enumerate(tools):
        cat = tool.get("category", "Tool")
        icon = category_icons.get(cat, "🔧")
        url = tool.get("url", "")
        link_html = f' <a href="{url}" target="_blank" style="color:var(--blue);font-size:11px;text-decoration:none">Try it →</a>' if url else ""

        cards += f'''<div style="background:var(--bg-card);backdrop-filter:blur(12px);border:1px solid var(--border);border-radius:16px;padding:22px;box-shadow:0 2px 8px var(--shadow);">
            <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--purple);margin-bottom:8px">{icon} TIP {str(i+1).zfill(2)}</div>
            <div class="tool-title" style="font-size:15px;font-weight:700;margin-bottom:8px">{tool.get("title","")}</div>
            <div class="tool-body" style="font-size:13px;color:var(--text-secondary);line-height:1.6">{tool.get("body","")}{link_html}</div>
        </div>\n'''

    return f'''<div class="section" id="ai-tool-guide">
        <div class="section-title"><span class="section-icon">🧰</span> AI Tool Guide</div>
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:16px;">{cards}</div>
    </div>'''


def render_media_strip(date, media_status):
    """Render the podcast and video media strip."""
    media = media_status.get("media", {}) if media_status else {}

    # Also check if files exist on disk (fallback if media-status.json is missing)
    podcast_file = DIGEST_DIR / f"podcast-{date}.mp3"
    has_podcast = media.get("podcast") or podcast_file.exists()

    podcast_html = ""
    if has_podcast:
        podcast_html = f'''<div class="media-banner">
            <div class="media-banner-icon">🎧</div>
            <div class="media-banner-title">Daily Podcast</div>
            <div class="media-banner-sub">AI-generated deep-dive briefing</div>
            <button class="media-banner-btn podcast-btn" onclick="togglePodcast()">▶ Listen Now</button>
            <div class="podcast-player-wrap" id="podcastPlayer">
                <audio controls style="width:100%;margin-top:10px" preload="none">
                    <source src="./podcast-{date}.mp3" type="audio/mpeg">
                </audio>
            </div>
        </div>'''
    else:
        podcast_html = '''<div class="media-banner">
            <div class="media-banner-icon">🎧</div>
            <div class="media-banner-title">Daily Podcast</div>
            <div class="media-banner-sub">Not available for today</div>
        </div>'''

    # Check for YouTube video
    video_html = ""
    yt_result_path = DIGEST_DIR / "youtube-result.json"
    if yt_result_path.exists():
        try:
            with open(yt_result_path, "r") as f:
                yt = json.load(f)
            video_id = yt.get("video_id", "")
            if video_id:
                video_html = f'''<div class="media-banner">
                    <div class="media-banner-icon">🎬</div>
                    <div class="media-banner-title">Video Briefing</div>
                    <div class="media-banner-sub">AI-generated cinematic explainer</div>
                    <a href="https://www.youtube.com/watch?v={video_id}" target="_blank" class="media-banner-btn video-btn">▶ Watch on YouTube</a>
                    <button class="media-banner-btn expand-btn" onclick="toggleVideo()">▶ Watch Inline</button>
                    <div class="video-overlay" id="videoOverlay" onclick="if(event.target===this)toggleVideo()">
                        <div class="video-overlay-inner">
                            <iframe id="videoFrame" width="100%" style="aspect-ratio:16/9;border:none;border-radius:12px" allowfullscreen></iframe>
                        </div>
                    </div>
                </div>'''
        except Exception:
            pass

    if not video_html:
        video_html = '''<div class="media-banner">
            <div class="media-banner-icon">🎬</div>
            <div class="media-banner-title">Video Briefing</div>
            <div class="media-banner-sub">Not available for today</div>
        </div>'''

    return f'<div class="media-strip">{podcast_html}{video_html}</div>'


def render_infographic(date, media_status):
    """Render the infographic section."""
    media = media_status.get("media", {}) if media_status else {}
    infographic_file = DIGEST_DIR / f"infographic-{date}.jpg"
    if not media.get("infographic") and not infographic_file.exists():
        return ""

    return f'''<div class="section" id="infographic">
        <div class="section-title"><span class="section-icon">📊</span> Daily Infographic</div>
        <div style="background:var(--bg-card);backdrop-filter:blur(12px);border:1px solid var(--border);border-radius:20px;padding:16px;box-shadow:0 4px 16px var(--shadow);text-align:center">
            <img src="./infographic-{date}.jpg" alt="Koda Daily Infographic — {date}" style="max-width:100%;border-radius:12px">
        </div>
    </div>'''


# ── CSS Template ─────────────────────────────────────────────────────────────

def get_css():
    """Return the full CSS for the briefing page.

    Reads from templates/briefing.css (canonical source of truth) to avoid
    the self-referencing bug where morning-briefing-koda.html overwrites
    itself with mismatched CSS variables.
    """
    css_template = DIGEST_DIR / "templates" / "briefing.css"
    if css_template.exists():
        with open(css_template, "r", encoding="utf-8") as f:
            return f.read()
    # Fallback: read from latest briefing (legacy behaviour)
    latest = DIGEST_DIR / "morning-briefing-koda.html"
    if latest.exists():
        with open(latest, "r", encoding="utf-8") as f:
            content = f.read()
        start = content.find("<style>")
        end = content.find("</style>")
        if start >= 0 and end >= 0:
            return content[start + 7:end]
    # Last-resort minimal CSS
    return """*{margin:0;padding:0;box-sizing:border-box;}
:root{--blue:#3B82F6;--purple:#8B5CF6;--red:#EF4444;--amber:#F59E0B;--emerald:#10B981;--indigo:#6366F1;--pink:#EC4899;--cyan:#06B6D4;--bg:#FFFFFF;--bg-secondary:#F8FAFC;--bg-card:rgba(255,255,255,0.7);--text:#0F172A;--text-secondary:#475569;--border:rgba(0,0,0,0.08);--shadow:rgba(0,0,0,0.04);}
html.dark-mode{--bg:#0F172A;--bg-secondary:#1E293B;--bg-card:rgba(30,41,59,0.8);--text:#F1F5F9;--text-secondary:#94A3B8;--border:rgba(255,255,255,0.08);--shadow:rgba(0,0,0,0.3);}
body{font-family:'Inter',-apple-system,sans-serif;background:var(--bg);color:var(--text);line-height:1.6;}
.container{max-width:1200px;margin:0 auto;padding:0 24px;}
.section{scroll-margin-top:80px;margin-bottom:40px;}"""


def get_js():
    """Return the JavaScript for the briefing page."""
    return """
    // Dark mode
    (function(){
        const saved = localStorage.getItem('koda-theme');
        if(saved==='dark') document.documentElement.classList.add('dark-mode');
    })();
    function toggleDark(){
        document.documentElement.classList.toggle('dark-mode');
        localStorage.setItem('koda-theme',
            document.documentElement.classList.contains('dark-mode')?'dark':'light');
        document.getElementById('darkBtn').textContent =
            document.documentElement.classList.contains('dark-mode')?'☀ Light':'🌙 Dark';
    }

    // Podcast player
    function togglePodcast(){
        const w=document.getElementById('podcastPlayer');
        if(w){w.classList.toggle('active');}
    }

    // Video overlay
    function toggleVideo(){
        const o=document.getElementById('videoOverlay');
        const f=document.getElementById('videoFrame');
        if(!o)return;
        if(o.classList.contains('active')){
            o.classList.remove('active');
            if(f)f.src='';
        }else{
            o.classList.add('active');
            const ytId=document.body.getAttribute('data-youtube-id');
            if(f&&ytId)f.src='https://www.youtube.com/embed/'+ytId+'?autoplay=1';
        }
    }

    // Day navigation
    (function(){
        const d=document.body.getAttribute('data-digest-date');
        if(!d)return;
        const dt=new Date(d+'T12:00:00');
        const prev=new Date(dt);prev.setDate(prev.getDate()-1);
        const next=new Date(dt);next.setDate(next.getDate()+1);
        const fmt=d2=>`${d2.getFullYear()}-${String(d2.getMonth()+1).padStart(2,'0')}-${String(d2.getDate()).padStart(2,'0')}`;
        const pf='morning-briefing-koda-'+fmt(prev)+'.html';
        const nf='morning-briefing-koda-'+fmt(next)+'.html';
        const pb=document.getElementById('prevBtn'),nb=document.getElementById('nextBtn');
        fetch(pf,{method:'HEAD'}).then(r=>{if(r.ok&&pb){pb.href=pf;pb.classList.remove('disabled');}}).catch(()=>{});
        fetch(nf,{method:'HEAD'}).then(r=>{if(r.ok&&nb){nb.href=nf;nb.classList.remove('disabled');}}).catch(()=>{});
    })();

    // Scroll animations
    const obs=new IntersectionObserver((entries)=>{
        entries.forEach(e=>{if(e.isIntersecting){e.target.style.opacity='1';e.target.style.transform='translateY(0)';obs.unobserve(e.target);}});
    },{threshold:0.08});
    document.querySelectorAll('.section').forEach(s=>{s.style.opacity='0';s.style.transform='translateY(16px)';s.style.transition='opacity 0.45s ease,transform 0.45s ease';obs.observe(s);});

    // Hash scrolling
    if(window.location.hash){
        const el=document.querySelector(window.location.hash);
        if(el)setTimeout(()=>el.scrollIntoView({behavior:'smooth'}),300);
    }
    """


# ── Main Assembly ────────────────────────────────────────────────────────────

def generate_html(digest, media_status, date):
    """Generate the complete HTML dashboard."""
    date_label = digest.get("date_label", date)
    summary = digest.get("summary", {})

    # Check for YouTube video ID
    yt_id = ""
    yt_path = DIGEST_DIR / "youtube-result.json"
    if yt_path.exists():
        try:
            with open(yt_path, "r") as f:
                yt_id = json.load(f).get("video_id", "")
        except Exception:
            pass

    sections = [
        render_kpi_strip(summary),
        render_media_strip(date, media_status),
        render_summary(summary),
        render_infographic(date, media_status),
        render_focus(summary),
        render_ai_news(digest.get("ai_news", [])),
        render_world_news(digest.get("world_news", [])),
        render_markets(digest.get("markets", {})),
        render_newsletters(digest.get("newsletters", [])),
        render_competitive(digest.get("competitive", [])),
        render_tools(digest.get("tools", [])),
    ]

    body_content = "\n".join(s for s in sections if s)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Koda Intelligence Briefing — {date_label}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
    <style>{get_css()}</style>
</head>
<body data-digest-date="{date}" data-youtube-id="{yt_id}">

<!-- Topbar -->
<div class="topbar">
    <div class="topbar-inner">
        <a href="./index.html" class="brand">
            <div class="brand-icon">K</div>
            <div><div class="brand-name">Koda Digest</div><div class="brand-sub">Intelligence Briefing</div></div>
        </a>
        <div class="day-nav">
            <a id="prevBtn" class="day-nav-btn disabled" href="#">← Yesterday</a>
            <span class="day-nav-current">{date}</span>
            <a id="nextBtn" class="day-nav-btn disabled" href="#">Tomorrow →</a>
        </div>
        <div class="topbar-right">
            <button class="dark-toggle" id="darkBtn" onclick="toggleDark()">🌙 Dark</button>
            <a href="./index.html" class="home-btn">← Home</a>
        </div>
    </div>
</div>

<!-- Hero -->
<div class="hero">
    <div class="container">
        <div class="hero-date">{date_label}</div>
        <h1 class="hero-title">Koda Intelligence Briefing</h1>
        <p class="hero-sub">AI developments, world news, markets, and tools — synthesized daily.</p>
    </div>
</div>

<!-- Content -->
<div class="container">
    {body_content}
</div>

<!-- Footer -->
<footer style="text-align:center;padding:40px 24px;border-top:1px solid var(--border);margin-top:40px">
    <div style="font-size:14px;font-weight:700;margin-bottom:4px">Koda Intelligence</div>
    <div style="font-size:12px;color:var(--text-secondary)">Generated {generated_at} | Sources: Web Search, Newsletter feeds, NotebookLM</div>
    <div style="font-size:11px;color:var(--text-secondary);margin-top:8px">© {datetime.now().year} Koda Community</div>
</footer>

<script>{get_js()}</script>
</body>
</html>'''

    return html


def main():
    parser = argparse.ArgumentParser(description="Step 05: Generate HTML dashboard")
    parser.add_argument("--date", default=today_str(), help="Date (YYYY-MM-DD)")
    args = parser.parse_args()

    print(f"[05] Generating HTML for {args.date}")

    digest = read_json("digest-content.json")
    media_status = read_json("media-status.json")

    if not digest:
        print("  ERROR: digest-content.json not found. Run 03_synthesize_content.py first.")
        sys.exit(1)

    html = generate_html(digest, media_status, args.date)
    print(f"  Generated {len(html)} chars of HTML")

    # Save dated archive
    dated_path = DIGEST_DIR / f"morning-briefing-koda-{args.date}.html"
    with open(dated_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Saved: {dated_path}")

    # Save current shortcut
    current_path = DIGEST_DIR / "morning-briefing-koda.html"
    with open(current_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Saved: {current_path}")


if __name__ == "__main__":
    main()
