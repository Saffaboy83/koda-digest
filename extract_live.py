"""Extract structured content from the live briefing HTML."""
import re, json
from html import unescape

html = open('/tmp/live-briefing.html', 'r', encoding='utf-8').read()

# Use the Firecrawl data we already scraped (more reliable than regex)
# Combined with regex for what Firecrawl missed
live = {
    'hook': 'DeepSeek V4 sits at 94% on prediction markets while U.S. strikes erase a historic Tehran synagogue.',
    'youtube_id': 'B3YlxwSe1t0',
    'editorial_url': './editorial/2026-04-09-ai-benchmarks-are-systematically-misleading-due-to-training-.html',
    'editorial_title': 'AI benchmarks are systematically misleading due to training data contamination',
    'markets': {
        'sp500': {'label': 'S&P 500', 'price': '6,782.81', 'change': '+2.51%', 'dir': 'up'},
        'nasdaq': {'label': 'Nasdaq', 'price': '22,634.99', 'change': '+2.80%', 'dir': 'up'},
        'btc': {'label': 'Bitcoin', 'price': '$71,277.81', 'change': '+0.23%', 'dir': 'up'},
        'eth': {'label': 'ETH', 'price': '$2,184.18', 'change': '-0.27%', 'dir': 'down'},
        'oil': {'label': 'Crude Oil', 'price': '$97.67', 'change': '+1.09%', 'dir': 'up'},
        'sentiment': {'label': 'Fear & Greed', 'value': 'Extreme Fear'},
    },
    'ai_news': [
        {'title': 'OpenAI Announces Next Phase of Enterprise AI', 'category': 'Enterprise', 'source': 'OpenAI', 'url': 'https://openai.com/index/next-phase-of-enterprise-ai/'},
        {'title': 'Prediction Markets Price DeepSeek V4 at 94%', 'category': 'Trend', 'source': 'Manifold', 'url': 'https://manifold.markets/prismatic/april-2026-ai-model-releases'},
        {'title': 'Hugging Face Releases Darwin-31B-Opus Reasoning Merge', 'category': 'Open Source', 'source': 'Hugging Face', 'url': 'https://huggingface.co/posts'},
        {'title': 'Meta Ships Four MTIA Chips in Two Years', 'category': 'Hardware', 'source': 'Meta', 'url': 'https://ai.meta.com/blog/meta-mtia-scale-ai-chips-for-billions/'},
        {'title': 'Meta Unveils TRIBE v2 Brain Prediction Model', 'category': 'Biotech', 'source': 'Meta', 'url': 'https://ai.meta.com/blog/tribe-v2-brain-predictive-foundation-model/'},
        {'title': 'Hugging Face Maps Open Source AI Spring 2026', 'category': 'Trend', 'source': 'Hugging Face', 'url': 'https://huggingface.co/blog/huggingface/state-of-os-hf-spring-2026'},
        {'title': 'Benchmarks Called Misleading Due to Data Contamination', 'category': 'Benchmark', 'source': 'SearchCans', 'url': 'https://www.searchcans.com/blog/ai-model-releases-april-2026-v2/'},
        {'title': 'April 2026 Model Cadence Reaches Eight in Seven Days', 'category': 'Trend', 'source': 'WhatLLM', 'url': 'https://whatllm.org/blog/new-ai-models-april-2026'},
    ],
    'world_news': [
        {'title': 'Israel Pounds Lebanon, Threatening Fragile Iran Ceasefire', 'category': 'Conflict', 'url': 'https://www.straitstimes.com/world/while-you-were-sleeping-5-stories-you-might-have-missed-april-9-2026'},
        {'title': 'Trump Slaps 50% Tariffs on Iran Arms Suppliers', 'category': 'Policy', 'url': 'https://www.democracynow.org/2026/4/8/headlines'},
        {'title': 'U.S. Strikes Destroy Historic Tehran Synagogue', 'category': 'Humanitarian', 'url': 'https://www.democracynow.org/2026/4/8/headlines'},
        {'title': 'Asian Markets Slide on Ceasefire Doubts', 'category': 'Economy', 'url': 'https://www.straitstimes.com/world/while-you-were-sleeping-5-stories-you-might-have-missed-april-9-2026'},
        {'title': 'NPR Questions What U.S. Iran War Accomplished', 'category': 'Diplomacy', 'url': 'https://www.npr.org/sections/world/'},
        {"title": "JP Morgan's Dimon Warns of Economic Fallout", 'category': 'Economy', 'url': 'https://www.golocalprov.com/news/5-big-news-stories-overnight-tuesday-april-7-2026'},
        {'title': 'Trump Renews NATO Criticism Amid Iran Crisis', 'category': 'Diplomacy', 'url': 'https://www.straitstimes.com/world/while-you-were-sleeping-5-stories-you-might-have-missed-april-9-2026'},
    ],
    'newsletters': [
        {'name': 'TLDR', 'headlines': ['Claude Mythos Preview discovered thousands of zero-day vulnerabilities via Project Glasswing', 'GLM-5.1 achieves SOTA on SWE-Bench Pro with sustained agentic optimization', 'Weights & Biases published guide on advancing physical AI for embodied intelligence'], 'link': 'https://tldr.tech/'},
        {'name': 'Superhuman', 'headlines': ['Claude Mythos withheld from public citing safety; launches Project Glasswing', 'Clicky on-screen AI teaching tool goes viral with 1M+ views', 'Google releases AI Edge Eloquent, free offline dictation powered by Gemma'], 'link': 'https://www.joinsuperhuman.ai/'},
        {'name': 'TLDR', 'headlines': ['Cluely CEO admitted to inflating ARR, spotlighting AI startup trust issues', 'Databricks: multi-agent systems grew 327% in under four months across 20K+ orgs', 'Agent skills emerging as the new SDK for developer infrastructure'], 'link': 'https://tldr.tech/'},
    ],
    'tools': [
        {'title': 'Superhuman', 'category': 'AI Email Triage', 'url': 'https://superhuman.com/'},
        {'title': 'Glide', 'category': 'No Code App Builder', 'url': 'https://www.glideapps.com/'},
        {'title': 'Zed Editor', 'category': 'Code Editor', 'url': 'https://zed.dev/'},
        {'title': 'MemSync', 'category': 'AI Memory Layer', 'url': 'https://www.producthunt.com/categories/llm-memory'},
        {'title': 'deepidv', 'category': 'Identity Verification', 'url': 'https://www.producthunt.com/categories/authentication-identity'},
        {'title': 'Chatforce', 'category': 'Game Prototyper', 'url': 'https://theresanaiforthat.com/ai/chatforce/'},
    ],
    'competitive': [
        {'name': 'OpenAI', 'status': 'Launching enterprise AI initiative alongside Child Safety Blueprint'},
        {'name': 'Meta', 'status': 'Building full stack for next-generation AI with MTIA chips and TRIBE v2'},
        {'name': 'Hugging Face', 'status': 'Releasing new models and mapping the open-source AI landscape'},
    ],
}

# Extract briefs from live HTML
briefs_section = re.search(r'id="daily-summary"(.*?)(?=id="todays-focus"|class="section lg:hidden")', html, re.DOTALL)
briefs = []
if briefs_section:
    brief_labels = re.findall(r'tracking-\[0\.1em\][^>]*>\s*([^<]+)\s*</span>', briefs_section.group(1))
    brief_texts = re.findall(r'text-\[#c2c6d6\][^>]*leading-relaxed[^>]*>\s*([^<]+)\s*<', briefs_section.group(1))
    for i in range(min(len(brief_labels), len(brief_texts), 4)):
        briefs.append({'label': brief_labels[i].strip(), 'text': unescape(brief_texts[i].strip())})

live['briefs'] = briefs if briefs else [
    {'label': 'AI', 'text': 'OpenAI launches next phase of enterprise AI. DeepSeek V4 hits 94% on prediction markets. Eight models ship in seven days.'},
    {'label': 'World', 'text': 'Israel pounds Lebanon threatening fragile Iran ceasefire. U.S. strikes destroy historic Tehran synagogue. Trump slaps 50% tariffs on Iran arms suppliers.'},
    {'label': 'Markets', 'text': 'Extreme Fear persists as ceasefire doubts rattle Asian markets. JP Morgan warns of broader economic fallout from ongoing conflicts.'},
    {'label': 'Wild Card', 'text': 'Meta ships four MTIA chips in two years while Hugging Face maps the open source AI spring, signaling a maturing ecosystem.'},
]

# Extract focus topics
focus_section = re.search(r'id="todays-focus"(.*?)(?=id="ai-developments")', html, re.DOTALL)
focus = []
if focus_section:
    titles = re.findall(r'font-(?:bold|black)[^>]*>\s*([^<]{5,80})\s*</(?:h4|span|p)>', focus_section.group(1))
    descs = re.findall(r'leading-relaxed[^>]*>\s*([^<]{20,})\s*<', focus_section.group(1))
    # Filter out non-topic entries
    titles = [t.strip() for t in titles if not t.strip().startswith('0') and len(t.strip()) > 10]
    for i, t in enumerate(titles[:3]):
        focus.append({'title': t, 'desc': unescape(descs[i].strip()) if i < len(descs) else ''})

live['focus'] = focus if focus else [
    {'title': 'DeepSeek V4 and the Prediction Market Signal', 'desc': 'Prediction markets price DeepSeek V4 at 94% for April release, outpacing GPT-5.5.'},
    {'title': 'Enterprise AI Goes Vertical', 'desc': 'OpenAI pivots to deep enterprise integration while Meta builds full-stack AI infrastructure.'},
    {'title': 'The Ceasefire Illusion', 'desc': 'Israel strikes Lebanon hours after Iran ceasefire, with markets pricing in fragility.'},
]

with open('/tmp/live-content.json', 'w', encoding='utf-8') as f:
    json.dump(live, f, indent=2, ensure_ascii=False)

print(f"Saved live-content.json")
print(f"  {len(live['ai_news'])} AI stories, {len(live['world_news'])} world stories")
print(f"  {len(live['newsletters'])} newsletters, {len(live['tools'])} tools, {len(live['competitive'])} competitive")
print(f"  {len(live['briefs'])} briefs, {len(live['focus'])} focus topics")
print(f"  YouTube: {live['youtube_id']}")
