"""Build signal-prototype.html from live-content.json + the new Stitch layout."""
import json

data = json.load(open('/tmp/live-content.json', 'r', encoding='utf-8'))

# Read existing prototype as template (for header/footer/CSS)
proto = open('signal-prototype.html', 'r', encoding='utf-8').read()

# Extract everything before <main> and after </main> to keep nav/footer
head_end = proto.find('<main')
footer_start = proto.find('</main>')
header = proto[:head_end]
footer_section = proto[footer_start:]

# Color map for categories
cat_colors = {
    'Enterprise': '#3B82F6', 'Trend': '#F59E0B', 'Open Source': '#10B981',
    'Hardware': '#8B5CF6', 'Biotech': '#EC4899', 'Benchmark': '#06B6D4',
    'Policy': '#3B82F6', 'Conflict': '#EF4444', 'Humanitarian': '#F59E0B',
    'Economy': '#10B981', 'Diplomacy': '#8B5CF6',
    'AI Email Triage': '#3B82F6', 'No Code App Builder': '#8B5CF6',
    'Code Editor': '#10B981', 'AI Memory Layer': '#06B6D4',
    'Identity Verification': '#EC4899', 'Game Prototyper': '#F59E0B',
}

def cc(cat):
    return cat_colors.get(cat, '#3B82F6')

def brief_icon(label):
    icons = {'AI': 'smart_toy', 'World': 'public', 'Markets': 'trending_up', 'Wild Card': 'bolt'}
    return icons.get(label, 'fiber_manual_record')

def brief_color(label):
    colors = {'AI': '#3B82F6', 'World': '#EF4444', 'Markets': '#10B981', 'Wild Card': '#F59E0B'}
    return colors.get(label, '#3B82F6')

# Build briefs HTML
briefs_html = ''
for b in data['briefs']:
    color = brief_color(b['label'])
    icon = brief_icon(b['label'])
    briefs_html += f'''            <div class="p-5 hover:bg-white/[0.02] transition-colors">
                <div class="flex items-center gap-2 mb-2">
                    <span class="material-symbols-outlined text-base" style="font-variation-settings:'FILL' 1;color:{color}">{icon}</span>
                    <span class="font-label text-[10px] uppercase tracking-wider font-bold" style="color:{color}">{b['label']}</span>
                </div>
                <p class="text-on-surface-variant text-xs leading-relaxed">{b['text']}</p>
            </div>
'''

# Build markets HTML
mkt = data['markets']
mkt_html = ''
for key in ['sp500', 'nasdaq', 'btc', 'eth', 'oil']:
    m = mkt[key]
    color = '#10B981' if m['dir'] == 'up' else '#EF4444'
    spark = 'sparkline-up' if m['dir'] == 'up' else 'sparkline-down'
    mkt_html += f'''                <div class="p-3 rounded-lg bg-surface-container/60">
                    <p class="font-label text-[9px] text-outline uppercase tracking-widest">{m['label']}</p>
                    <p class="text-lg font-bold mt-1">{m['price']}</p>
                    <p class="text-xs font-bold mt-0.5" style="color:{color}">{m['change']}</p>
                    <div class="h-0.5 w-full {spark} rounded-full mt-2 opacity-60"></div>
                </div>
'''
# Sentiment
mkt_html += f'''                <div class="p-3 rounded-lg bg-surface-container/60 border border-error/20">
                    <p class="font-label text-[9px] text-outline uppercase tracking-widest">Fear &amp; Greed</p>
                    <p class="text-lg font-bold mt-1 text-error fear-pulse">14</p>
                    <p class="text-xs font-bold text-error mt-0.5">{mkt['sentiment']['value']}</p>
                </div>
'''

# Build focus HTML
focus_html = ''
for i, f in enumerate(data['focus']):
    focus_html += f'''                <div class="flex gap-4 items-start group cursor-pointer">
                    <span class="text-2xl font-black text-primary/15 group-hover:text-primary transition-colors leading-none font-label">0{i+1}</span>
                    <div><p class="text-sm font-semibold leading-snug">{f['title']}</p><p class="text-xs text-on-surface-variant mt-1 line-clamp-2">{f['desc']}</p></div>
                </div>
'''

# Build AI Wire feature (first story) + grid (2-3) + sidebar (rest)
ai = data['ai_news']
wire_feature = ai[0] if ai else {'title': '', 'url': '#', 'category': '', 'source': ''}
wire_grid = ai[1:3] if len(ai) > 1 else []
wire_sidebar = ai[3:] if len(ai) > 3 else []

wire_grid_html = ''
for s in wire_grid:
    wire_grid_html += f'''                <a href="{s['url']}" target="_blank" class="space-y-4 group cursor-pointer block">
                    <span class="font-label text-[10px] tracking-widest uppercase font-black" style="color:{cc(s['category'])}">{s['category']}</span>
                    <h4 class="text-xl font-bold leading-tight group-hover:opacity-80 transition-colors">{s['title']}</h4>
                    <p class="text-on-surface-variant leading-relaxed text-sm">{s.get('body','')[:150]}{"..." if len(s.get('body',''))>150 else ""}</p>
                    <p class="text-on-surface-variant text-xs">{s['source']}</p>
                </a>
'''

wire_sidebar_html = ''
colors_cycle = ['#3B82F6', '#8B5CF6', '#EC4899', '#06B6D4', '#10B981', '#F59E0B']
for i, s in enumerate(wire_sidebar):
    c = colors_cycle[i % len(colors_cycle)]
    wire_sidebar_html += f'''            <a href="{s['url']}" target="_blank" class="group cursor-pointer p-6 glass-card rounded-xl border border-outline-variant/20 hover:border-[{c}]/30 transition-all block">
                <span class="font-label text-[10px] tracking-widest uppercase font-black" style="color:{c}">{s['category']}</span>
                <h4 class="text-lg font-bold mt-3 mb-2 group-hover:opacity-80 transition-colors leading-snug">{s['title']}</h4>
                <p class="text-on-surface-variant text-sm leading-relaxed line-clamp-2">{s.get('body','')[:180]}{"..." if len(s.get('body',''))>180 else ""}</p>
                <p class="text-on-surface-variant text-xs mt-2">{s['source']}</p>
            </a>
'''

# Build Globe
world = data['world_news']
globe_feature = world[0] if world else {'title': '', 'url': '#', 'category': ''}
globe_grid = world[1:3] if len(world) > 1 else []
globe_sidebar = world[3:] if len(world) > 3 else []

globe_grid_html = ''
for s in globe_grid:
    globe_grid_html += f'''                <a href="{s['url']}" target="_blank" class="space-y-4 group cursor-pointer block">
                    <span class="font-label text-[10px] tracking-widest uppercase font-black" style="color:{cc(s['category'])}">{s['category']}</span>
                    <h4 class="text-xl font-bold leading-tight group-hover:opacity-80 transition-colors">{s['title']}</h4>
                    <p class="text-on-surface-variant leading-relaxed text-sm">{s.get('body','')[:150]}{"..." if len(s.get('body',''))>150 else ""}</p>
                </a>
'''

globe_sidebar_html = ''
for i, s in enumerate(globe_sidebar):
    c = colors_cycle[i % len(colors_cycle)]
    globe_sidebar_html += f'''            <a href="{s['url']}" target="_blank" class="group cursor-pointer p-6 glass-card rounded-xl border border-outline-variant/20 hover:border-[{c}]/30 transition-all block">
                <span class="font-label text-[10px] tracking-widest uppercase font-black" style="color:{c}">{s['category']}</span>
                <h4 class="text-lg font-bold mt-3 mb-2 group-hover:opacity-80 transition-colors leading-snug">{s['title']}</h4>
                <p class="text-on-surface-variant text-sm leading-relaxed line-clamp-2">{s.get('body','')[:180]}{"..." if len(s.get('body',''))>180 else ""}</p>
            </a>
'''

# Build newsletters
nl_html = ''
nl_colors = ['#3B82F6', '#8B5CF6', '#EC4899']
for i, nl in enumerate(data['newsletters']):
    c = nl_colors[i % len(nl_colors)]
    headlines = ''
    for h in nl['headlines'][:3]:
        headlines += f'                <li class="text-xs text-on-surface-variant leading-relaxed flex gap-2"><span style="color:{c}" class="mt-0.5">&#8226;</span>{h}</li>\n'
    nl_html += f'''        <div class="glass-card rounded-xl border border-outline-variant/20 p-6 flex flex-col">
            <div class="flex items-center justify-between mb-4">
                <span class="text-sm font-extrabold">{nl['name']}</span>
                <span class="font-label text-[9px] text-outline">9 Apr 2026</span>
            </div>
            <ul class="space-y-2 mb-4 flex-grow">
{headlines}            </ul>
            <a href="{nl['link']}" target="_blank" class="text-xs font-bold hover:underline mt-auto" style="color:{c}">Read {nl['name']} &rarr;</a>
        </div>
'''

# Build tools
tools_html = ''
for i, t in enumerate(data['tools']):
    c = colors_cycle[i % len(colors_cycle)]
    url_html = f'<a href="{t["url"]}" target="_blank" class="inline-flex items-center gap-2 font-bold text-sm mt-6 hover:underline" style="color:{c}">Try It <span class="material-symbols-outlined text-sm">arrow_forward</span></a>' if t['url'] else ''
    tools_html += f'''        <article class="group cursor-pointer p-6 glass-card rounded-xl border border-outline-variant/20 hover:border-[{c}]/30 transition-all flex flex-col">
            <span class="px-3 py-1 font-label text-[10px] tracking-widest uppercase w-fit rounded mb-6" style="background:{c}15;color:{c}">{t['category']}</span>
            <h4 class="text-2xl font-bold leading-tight mb-4 group-hover:opacity-80 transition-colors">{t['title']}</h4>
            <p class="text-on-surface-variant text-sm leading-relaxed flex-grow">{t.get("body", "")}</p>
            {url_html}
        </article>
'''

# Build competitive
comp_html = ''
comp_colors = ['#3B82F6', '#10B981', '#F59E0B']
for i, c_entry in enumerate(data['competitive']):
    c = comp_colors[i % len(comp_colors)]
    comp_html += f'''        <div class="p-8 glass-card rounded-xl border-l-4 cinematic-shadow relative overflow-hidden" style="border-left-color:{c}">
            <div class="absolute -top-12 -right-12 w-32 h-32 rounded-full blur-3xl" style="background:{c}08"></div>
            <p class="font-label text-[10px] tracking-widest uppercase font-black mb-4" style="color:{c}">{c_entry['name']}</p>
            <h4 class="text-2xl font-extrabold mb-4">{c_entry['status']}</h4>
        </div>
'''

# Build the main content
yt_id = data['youtube_id']

main_html = f'''<main class="min-h-screen">

<!-- HERO -->
<section class="relative w-full min-h-[70vh] flex items-center px-8 md:px-16 overflow-hidden">
    <div class="absolute inset-0 z-0">
        <img alt="" class="w-full h-full object-cover brightness-[0.3] scale-105" src="./hero-2026-04-09.jpg"/>
        <div class="absolute inset-0 bg-gradient-to-t from-surface via-surface/40 to-transparent"></div>
        <div class="absolute inset-0 bg-gradient-to-r from-surface via-transparent to-transparent"></div>
    </div>
    <div class="relative z-10 max-w-6xl">
        <p class="font-label uppercase tracking-[0.3em] text-primary font-bold mb-4 text-xs opacity-90">Intelligence Report &bull; 09 April 2026</p>
        <h1 class="text-[10vw] md:text-[5rem] leading-[0.95] font-black tracking-tight text-gradient mb-6 drop-shadow-2xl">The Signal</h1>
        <p class="max-w-2xl font-body text-base md:text-lg text-on-surface-variant leading-relaxed mb-8 font-light">{data['hook']}</p>
        <div class="flex flex-wrap gap-4">
            <a href="#lead" class="px-8 py-3 bg-primary text-white font-black rounded-lg hover:brightness-110 active:scale-[0.98] transition-all shadow-xl shadow-primary/20 uppercase tracking-widest text-sm">Read Briefing</a>
            <a href="#markets" class="px-8 py-3 border border-outline-variant text-on-surface font-bold rounded-lg glass-card hover:bg-white/10 transition-all uppercase tracking-widest text-sm">View Markets</a>
        </div>
    </div>
</section>

<!-- LEAD STORY + BRIEF + MARKETS -->
<section id="lead" class="px-6 md:px-12 -mt-12 relative z-20 pb-10">
<div class="max-w-[1440px] mx-auto space-y-6">
    <div class="glass-card rounded-2xl border border-outline-variant/20 overflow-hidden cinematic-shadow">
        <div class="p-6 md:p-8 border-b border-outline-variant/10">
            <div class="flex items-center gap-3 mb-4">
                <span class="inline-block px-2.5 py-1 bg-error/15 text-error font-label text-[10px] tracking-widest uppercase rounded font-bold">Lead Story</span>
                <span class="inline-block px-2.5 py-1 bg-primary/10 text-primary font-label text-[10px] tracking-widest uppercase rounded font-bold">{ai[0]['category'] if ai else ''}</span>
                <span class="font-label text-[10px] text-outline ml-auto">{ai[0].get('source', '') if ai else ''}</span>
            </div>
            <h2 class="text-xl md:text-2xl font-extrabold tracking-tight leading-snug mb-3 text-on-surface">{ai[0]['title'] if ai else ''}</h2>
            <p class="text-on-surface-variant text-sm leading-relaxed max-w-3xl mb-4">{ai[0].get('body', '') if ai else ''}</p>
            <a class="inline-flex items-center gap-2 text-primary font-bold text-sm hover:underline group/link" href="{ai[0]['url'] if ai else '#'}" target="_blank">
                Continue Reading <span class="material-symbols-outlined text-base group-hover/link:translate-x-1 transition-transform">arrow_forward</span>
            </a>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 divide-y sm:divide-y-0 sm:divide-x divide-outline-variant/10">
{briefs_html}        </div>
    </div>

    <div id="markets" class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div class="lg:col-span-2 glass-card rounded-2xl border border-outline-variant/20 p-6">
            <div class="flex items-center justify-between mb-5">
                <h3 class="text-sm font-extrabold uppercase tracking-wider">Market Snapshot</h3>
                <span class="material-symbols-outlined text-outline text-lg">query_stats</span>
            </div>
            <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
{mkt_html}            </div>
        </div>
        <div class="glass-card rounded-2xl border border-outline-variant/20 p-6">
            <h3 class="font-label text-[10px] tracking-[0.2em] uppercase text-primary font-bold mb-5">Today\'s Focus</h3>
            <div class="space-y-4">
{focus_html}            </div>
        </div>
    </div>
</div>
</section>

<!-- LISTEN & WATCH -->
<section class="w-full bg-surface-container-lowest py-10 border-y border-outline-variant/10 relative overflow-hidden">
    <div class="absolute top-0 right-0 w-1/3 h-full bg-gradient-to-l from-primary/5 to-transparent pointer-events-none"></div>
    <div class="max-w-[1440px] mx-auto px-6 md:px-12">
        <div class="flex items-center gap-4 mb-6">
            <h2 class="text-sm font-extrabold uppercase tracking-wider">Listen & Watch</h2>
            <div class="h-px flex-grow bg-outline-variant/15"></div>
            <span class="font-label text-[9px] tracking-widest text-outline uppercase font-bold">Daily Broadcasts</span>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-5">
            <div class="rounded-xl overflow-hidden bg-surface-container/80 border border-outline-variant/10 hover:border-primary/20 transition-all">
                <div class="relative aspect-video overflow-hidden cursor-pointer" onclick="document.getElementById('podcastLightbox').style.display='flex'">
                    <img alt="Daily Deep Dive" class="w-full h-full object-cover object-top" src="https://lfwymyfaeihoglmlvbaj.supabase.co/storage/v1/object/public/koda-media/email-hero-2026-04-09.jpg"/>
                    <div class="absolute inset-0 bg-gradient-to-t from-surface-container via-transparent to-transparent"></div>
                    <div class="absolute top-3 left-3 flex gap-1.5">
                        <span class="px-2 py-0.5 bg-primary/20 backdrop-blur-sm text-primary text-[9px] font-bold uppercase rounded font-label tracking-wider">Podcast</span>
                        <span class="px-2 py-0.5 bg-black/30 backdrop-blur-sm text-white text-[9px] font-bold rounded font-label">~22 min</span>
                    </div>
                </div>
                <div class="p-4">
                    <h4 class="text-sm font-bold mb-1">Daily Deep Dive</h4>
                    <audio controls class="w-full" preload="none" style="height:36px;border-radius:6px"><source src="https://lfwymyfaeihoglmlvbaj.supabase.co/storage/v1/object/public/koda-media/podcast-2026-04-09.mp3" type="audio/mpeg"></audio>
                </div>
            </div>
            <div class="rounded-xl overflow-hidden bg-surface-container/80 border border-outline-variant/10 hover:border-tertiary/20 transition-all group">
                <div class="relative aspect-video cursor-pointer" id="ytPlayer" onclick="this.innerHTML='<iframe width=100% height=100% src=https://www.youtube.com/embed/{yt_id}?autoplay=1 frameborder=0 allow=autoplay allowfullscreen style=position:absolute;inset:0></iframe>';this.onclick=null;this.style.cursor='default'">
                    <img alt="Video Briefing" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" src="https://img.youtube.com/vi/{yt_id}/maxresdefault.jpg"/>
                    <div class="absolute inset-0 flex items-center justify-center bg-black/25 group-hover:bg-black/40 transition-colors">
                        <div class="w-14 h-14 rounded-full bg-white/15 backdrop-blur-sm flex items-center justify-center border border-white/25 group-hover:bg-white/25 transition-colors">
                            <span class="material-symbols-outlined text-white text-3xl" style="font-variation-settings:'FILL' 1">play_arrow</span>
                        </div>
                    </div>
                    <div class="absolute top-3 left-3 flex gap-1.5">
                        <span class="px-2 py-0.5 bg-tertiary/20 backdrop-blur-sm text-tertiary text-[9px] font-bold uppercase rounded font-label tracking-wider">Video</span>
                    </div>
                </div>
                <div class="p-4"><h4 class="text-sm font-bold mb-1">Video Briefing</h4></div>
            </div>
            <div class="rounded-xl overflow-hidden bg-surface-container/80 border border-outline-variant/10 hover:border-secondary/20 transition-all group cursor-pointer" onclick="document.getElementById('infographicLightbox').style.display='flex'">
                <div class="relative aspect-video overflow-hidden">
                    <img alt="Daily Infographic" class="w-full h-full object-cover object-top group-hover:scale-105 transition-transform duration-500" src="https://lfwymyfaeihoglmlvbaj.supabase.co/storage/v1/object/public/koda-media/infographic-2026-04-09.jpg"/>
                    <div class="absolute top-3 left-3 flex gap-1.5">
                        <span class="px-2 py-0.5 bg-secondary/20 backdrop-blur-sm text-secondary text-[9px] font-bold uppercase rounded font-label tracking-wider">Infographic</span>
                    </div>
                </div>
                <div class="p-4"><h4 class="text-sm font-bold mb-1 group-hover:text-secondary transition-colors">Intelligence Map</h4></div>
            </div>
        </div>
    </div>
</section>

<!-- DEEP DIVE -->
<section class="max-w-[1440px] mx-auto px-6 md:px-12 py-10">
    <div class="flex items-center gap-4 mb-6">
        <h2 class="text-sm font-extrabold uppercase tracking-wider">Deep Dive</h2>
        <div class="h-px flex-grow bg-outline-variant/15"></div>
        <a href="./editorial/" class="font-label text-[9px] tracking-widest text-primary uppercase font-bold hover:underline flex items-center gap-1">All Editorials <span class="material-symbols-outlined text-xs">east</span></a>
    </div>
    <a href="{data['editorial_url']}" class="block rounded-2xl overflow-hidden bg-surface-container/80 border border-outline-variant/15 hover:border-primary/30 transition-all group" style="box-shadow:0 20px 60px -15px rgba(0,0,0,0.5)">
        <div class="grid grid-cols-1 md:grid-cols-5">
            <div class="md:col-span-2 relative h-44 md:h-auto overflow-hidden">
                <img src="{data.get('editorial_hero_url','')}" alt="Editorial" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700"/>
                <div class="absolute inset-0 bg-gradient-to-r from-transparent to-[#171f33]/90 hidden md:block"></div>
            </div>
            <div class="md:col-span-3 p-6 flex flex-col justify-center">
                <div class="flex items-center gap-2 mb-2">
                    <span class="material-symbols-outlined text-secondary text-sm" style="font-variation-settings:'FILL' 1">explore</span>
                    <span class="font-label text-[9px] text-secondary uppercase tracking-widest font-bold">Today\'s Editorial</span>
                    <span class="font-label text-[9px] text-outline ml-auto">5 min read</span>
                </div>
                <h3 class="text-lg font-extrabold tracking-tight leading-snug mb-2 group-hover:text-primary transition-colors">{data['editorial_title']}</h3>
                <p class="text-on-surface-variant text-sm leading-relaxed line-clamp-2">{data.get('editorial_desc','')}</p>
                <span class="inline-flex items-center gap-1.5 text-primary text-xs font-bold mt-3 group-hover:underline">Read Full Analysis <span class="material-symbols-outlined text-xs group-hover:translate-x-1 transition-transform">arrow_forward</span></span>
            </div>
        </div>
    </a>
</section>

<!-- THE WIRE -->
<section class="mt-10 px-8 md:px-12 max-w-[1920px] mx-auto pb-14">
    <div class="flex items-baseline justify-between mb-8 border-b border-outline-variant/30 pb-6">
        <h2 class="text-2xl font-extrabold tracking-tight">The Wire</h2>
        <span class="font-label text-xs uppercase tracking-[0.3em] text-on-surface-variant font-bold">AI Intelligence</span>
    </div>
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-8">
        <div class="lg:col-span-7 flex flex-col gap-8">
            <a href="{wire_feature['url']}" target="_blank" class="relative h-[350px] rounded-xl overflow-hidden group shadow-2xl block bg-surface-container-high">
                <div class="absolute inset-0 bg-gradient-to-t from-surface-container-lowest via-surface/30 to-transparent p-12 flex flex-col justify-end">
                    <span class="font-label text-xs uppercase tracking-[0.4em] text-secondary mb-6 font-black">{wire_feature['category']}</span>
                    <h3 class="text-lg font-extrabold tracking-tight mb-4 text-white max-w-2xl leading-[1.1]">{wire_feature['title']}</h3>
                    <span class="text-white/40 text-xs font-bold uppercase tracking-widest">{wire_feature.get('source', '')}</span>
                </div>
            </a>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
{wire_grid_html}            </div>
        </div>
        <div class="lg:col-span-5 flex flex-col gap-6">
{wire_sidebar_html}        </div>
    </div>
</section>

<!-- THE GLOBE -->
<section class="px-8 md:px-12 max-w-[1920px] mx-auto pb-14">
    <div class="flex items-baseline justify-between mb-8 border-b border-outline-variant/30 pb-6">
        <h2 class="text-2xl font-extrabold tracking-tight">The Globe</h2>
        <span class="font-label text-xs uppercase tracking-[0.3em] text-on-surface-variant font-bold">World Affairs</span>
    </div>
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-8">
        <div class="lg:col-span-7">
            <a href="{globe_feature['url']}" target="_blank" class="relative h-[300px] rounded-xl overflow-hidden group shadow-2xl block bg-surface-container-high">
                <div class="absolute inset-0 bg-gradient-to-t from-surface-container-lowest via-surface/40 to-transparent p-12 flex flex-col justify-end">
                    <span class="font-label text-xs uppercase tracking-[0.4em] text-error mb-4 font-black">{globe_feature['category']}</span>
                    <h3 class="text-lg font-extrabold tracking-tight mb-4 text-white leading-[1.1]">{globe_feature['title']}</h3>
                </div>
            </a>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-8 mt-12">
{globe_grid_html}            </div>
        </div>
        <div class="lg:col-span-5 flex flex-col gap-6">
{globe_sidebar_html}        </div>
    </div>
</section>

<!-- THE FEED -->
<section class="px-8 md:px-12 max-w-[1920px] mx-auto pb-14">
    <div class="flex items-baseline justify-between mb-8 border-b border-outline-variant/30 pb-6">
        <h2 class="text-2xl font-extrabold tracking-tight">The Feed</h2>
        <span class="font-label text-xs uppercase tracking-[0.3em] text-on-surface-variant font-bold">Newsletter Intelligence</span>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
{nl_html}    </div>
</section>

<!-- THE LAB -->
<section class="px-8 md:px-12 max-w-[1920px] mx-auto pb-14">
    <div class="flex items-baseline justify-between mb-8 border-b border-outline-variant/30 pb-6">
        <h2 class="text-2xl font-extrabold tracking-tight">The Lab</h2>
        <a class="font-label text-xs uppercase tracking-[0.3em] text-on-surface-variant hover:text-primary transition-all font-bold group flex items-center gap-2" href="./reviews/">All Reviews <span class="material-symbols-outlined text-sm group-hover:translate-x-1 transition-transform">east</span></a>
    </div>
    <div class="mb-8 p-5 rounded-xl bg-surface-container-low/60 border border-primary/10">
        <h3 class="font-label text-[10px] tracking-[0.2em] uppercase text-primary font-bold mb-4 flex items-center gap-2"><span class="material-symbols-outlined text-sm" style="font-variation-settings:\'FILL\' 1">science</span>Today\'s Lab Reports</h3>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <a href="./reviews/2026-04-09-novavoice-control-apps-and-dictate-with-a-single-voice-layer.html" class="flex items-center gap-3 p-3 rounded-lg bg-surface-container/60 hover:bg-surface-container-high/60 transition-colors group">
                <span class="material-symbols-outlined text-primary text-lg" style="font-variation-settings:\'FILL\' 1">mic</span>
                <div><p class="text-sm font-bold group-hover:text-primary transition-colors">NovaVoice</p><p class="text-[10px] text-on-surface-variant">Voice control + dictation layer</p></div>
                <span class="font-label text-[9px] text-primary ml-auto">Lab Report &rarr;</span>
            </a>
            <a href="./reviews/2026-04-09-nebils-test-drive-120-ai-models-in-one-social-feed.html" class="flex items-center gap-3 p-3 rounded-lg bg-surface-container/60 hover:bg-surface-container-high/60 transition-colors group">
                <span class="material-symbols-outlined text-secondary text-lg" style="font-variation-settings:\'FILL\' 1">hub</span>
                <div><p class="text-sm font-bold group-hover:text-secondary transition-colors">Nebils</p><p class="text-[10px] text-on-surface-variant">Test 120+ AI models in one feed</p></div>
                <span class="font-label text-[9px] text-secondary ml-auto">Lab Report &rarr;</span>
            </a>
            <a href="./reviews/2026-04-09-ignitvio-ai-powered-lead-response-for-local-service-businesses.html" class="flex items-center gap-3 p-3 rounded-lg bg-surface-container/60 hover:bg-surface-container-high/60 transition-colors group">
                <span class="material-symbols-outlined text-tertiary text-lg" style="font-variation-settings:\'FILL\' 1">local_fire_department</span>
                <div><p class="text-sm font-bold group-hover:text-tertiary transition-colors">Ignitvio</p><p class="text-[10px] text-on-surface-variant">AI lead response for local businesses</p></div>
                <span class="font-label text-[9px] text-tertiary ml-auto">Lab Report &rarr;</span>
            </a>
        </div>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-10">
{tools_html}    </div>
</section>

<!-- THE ARENA -->
<section class="px-8 md:px-12 max-w-[1920px] mx-auto pb-14">
    <div class="flex items-baseline justify-between mb-8 border-b border-outline-variant/30 pb-6">
        <h2 class="text-lg font-extrabold tracking-tight">The Arena</h2>
        <span class="font-label text-xs uppercase tracking-[0.3em] text-on-surface-variant font-bold">Competitive Intel</span>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-10">
{comp_html}    </div>
</section>

<!-- SUBSCRIBE -->
<section class="px-8 md:px-12 max-w-7xl mx-auto mb-32">
    <div class="bg-surface-container-low p-10 md:p-14 rounded-2xl relative overflow-hidden border border-outline-variant/20 shadow-2xl">
        <div class="absolute -top-48 -right-48 w-[600px] h-[600px] bg-primary/10 rounded-full blur-[120px]"></div>
        <div class="absolute -bottom-48 -left-48 w-[400px] h-[400px] bg-secondary/10 rounded-full blur-[100px]"></div>
        <div class="relative z-10 grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
            <div>
                <h2 class="text-2xl font-extrabold tracking-tight mb-8 leading-tight">Never miss a Signal.</h2>
                <p class="text-on-surface-variant text-xl leading-relaxed font-light">Join intelligence professionals who receive our daily deep-dive into AI, geopolitics, and markets.</p>
            </div>
            <div class="flex flex-col gap-6">
                <div class="flex flex-col md:flex-row gap-0">
                    <input class="flex-grow bg-surface-container-lowest border-0 border-b-2 border-outline-variant focus:ring-0 focus:border-primary transition-all px-6 py-5 text-on-surface text-lg font-light placeholder:text-outline-variant" placeholder="Your email address" type="email"/>
                    <button class="bg-primary text-white font-black px-12 py-5 hover:brightness-110 transition-all uppercase tracking-[0.2em] text-sm">Subscribe</button>
                </div>
                <p class="font-label text-[10px] text-on-surface-variant uppercase tracking-[0.3em] font-black opacity-60">Daily intelligence. No spam. Unsubscribe anytime.</p>
            </div>
        </div>
    </div>
</section>

'''

output = header + main_html + footer_section
with open('signal-prototype.html', 'w', encoding='utf-8') as f:
    f.write(output)

print(f"Built signal-prototype.html ({len(output)} chars)")
print(f"Content from LIVE site: {data['hook'][:60]}...")
