#!/usr/bin/env python3
"""
Build manifest.json and search-index.json from dated Koda digest HTML files
and editorial articles.

Uses Python stdlib only (no pip installs). Parses all
morning-briefing-koda-YYYY-MM-DD.html files + editorial/*.html articles
and extracts metadata for the archive browser and unified searchable text.

Usage:
    python build-index.py
"""

import glob
import json
import os
import re
from datetime import datetime, timezone
from html.parser import HTMLParser


def clean_text(text):
    """Normalize whitespace and strip."""
    return re.sub(r"\s+", " ", text).strip()


def strip_html(html_str):
    """Remove HTML tags from a string."""
    text = re.sub(r"<[^>]+>", "", html_str)
    text = text.replace("&mdash;", "\u2014").replace("&ndash;", "\u2013")
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)
    return clean_text(text)


def parse_with_regex(filepath):
    """Parse a digest HTML file using regex. Reliable across both HTML formats."""
    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()

    result = {
        "date": "",
        "dayOfWeek": "",
        "focusTopics": [],
        "kpis": {},
        "youtubeId": "",
        "sections": [],
    }

    # Extract date from body data-digest-date attribute
    date_match = re.search(r'data-digest-date="(\d{4}-\d{2}-\d{2})"', html)
    if date_match:
        result["date"] = date_match.group(1)
    else:
        fname_match = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(filepath))
        if fname_match:
            result["date"] = fname_match.group(1)

    # Compute day of week
    if result["date"]:
        try:
            dt = datetime.strptime(result["date"], "%Y-%m-%d")
            result["dayOfWeek"] = dt.strftime("%A")
        except ValueError:
            pass

    # Extract KPIs: collect kpi-value and kpi-label elements independently
    # Handles both old (div, value-first) and new (span, label-first) formats
    kpi_values = []
    for m in re.finditer(r'class="[^"]*\bkpi-value\b[^"]*"[^>]*>(.*?)</(?:div|span)>', html, re.DOTALL):
        kpi_values.append(strip_html(m.group(1)))
    kpi_labels = []
    for m in re.finditer(r'class="[^"]*\bkpi-label\b[^"]*"[^>]*>(.*?)</(?:div|span)>', html, re.DOTALL):
        kpi_labels.append(strip_html(m.group(1)))

    for i, label in enumerate(kpi_labels):
        value = kpi_values[i] if i < len(kpi_values) else ""
        label_lower = label.lower()
        if "ai" in label_lower and "stor" in label_lower:
            result["kpis"]["aiStories"] = value
        elif "world" in label_lower:
            result["kpis"]["worldEvents"] = value
        elif "market" in label_lower or "mood" in label_lower:
            mood_match = re.search(r"(Bearish|Bullish|Neutral|Cautious\w*|Extreme\s*\w*|Mixed)", value, re.IGNORECASE)
            result["kpis"]["marketMood"] = mood_match.group(1) if mood_match else value
        elif "tool" in label_lower:
            result["kpis"]["toolsFeatured"] = value

    # Extract focus topics: multiple HTML formats across digest versions
    # v3: focus-content-title + focus-content-body (March 23+)
    # v2: focus-title + focus-desc (March 22)
    # v1: focus-content > h3 + p (March 21)
    focus_pattern_v3 = re.compile(
        r'class="[^"]*\bfocus-content-title\b[^"]*"[^>]*>(.*?)</div>\s*'
        r'.*?class="[^"]*\bfocus-content-body\b[^"]*"[^>]*>(.*?)</div>',
        re.DOTALL,
    )
    focus_pattern_v2 = re.compile(
        r'class="[^"]*\bfocus-title\b[^"]*"[^>]*>(.*?)</div>\s*'
        r'.*?class="[^"]*\bfocus-desc\b[^"]*"[^>]*>(.*?)</div>',
        re.DOTALL,
    )
    focus_pattern_v1 = re.compile(
        r'class="[^"]*\bfocus-content\b[^"]*"[^>]*>\s*<h3>(.*?)</h3>\s*<p>(.*?)</p>',
        re.DOTALL,
    )

    focus_matches = focus_pattern_v3.findall(html)
    if not focus_matches:
        focus_matches = focus_pattern_v2.findall(html)
    if not focus_matches:
        focus_matches = focus_pattern_v1.findall(html)

    for title_html, desc_html in focus_matches:
        title = strip_html(title_html)
        desc = strip_html(desc_html)
        if title:
            result["focusTopics"].append({"title": title, "desc": desc})

    # Extract YouTube video ID (try data attribute first, then embed URL)
    yt_match = re.search(r'data-youtube-id="([a-zA-Z0-9_-]+)"', html)
    if not yt_match:
        yt_match = re.search(r"youtube\.com/embed/([a-zA-Z0-9_-]+)", html)
    if not yt_match:
        yt_match = re.search(r"youtube\.com/watch\?v=([a-zA-Z0-9_-]+)", html)
    if yt_match:
        result["youtubeId"] = yt_match.group(1)

    # Extract sections with their cards
    # Find all section-title markers first
    section_title_pattern = re.compile(
        r'class="[^"]*\bsection-title\b[^"]*"[^>]*>(.*?)</(?:h[1-6]|div|span)>',
        re.DOTALL,
    )

    # Split HTML into sections by finding section-title positions
    section_starts = []
    for m in section_title_pattern.finditer(html):
        raw_title = strip_html(m.group(1))
        # Remove emoji/icon characters and common HTML entity remnants
        raw_title = re.sub(r"[\U0001F300-\U0001FAFF\U00002702-\U000027B0\u2600-\u27FF\u2B50]", "", raw_title).strip()
        # Remove leading/trailing punctuation and whitespace
        raw_title = re.sub(r"^[\s\u26A1\u2764\u2728]+|[\s]+$", "", raw_title).strip()
        section_starts.append((m.start(), m.end(), raw_title))

    # Skip media sections
    skip_sections = {
        "Daily Intelligence Infographic",
        "Daily Video Briefing",
        "Daily Podcast",
        "Daily Infographic",
    }

    # For each section, find cards within it using all known patterns
    for i, (start, end, title) in enumerate(section_starts):
        if title in skip_sections:
            continue

        # Get HTML from this section title to the next section title
        next_start = section_starts[i + 1][0] if i + 1 < len(section_starts) else len(html)
        section_html = html[end:next_start]

        items = []

        # Pattern 1: card-title + card-text/card-body (AI Developments, World News)
        for m in re.finditer(
            r'class="[^"]*\bcard-title\b[^"]*"[^>]*>(.*?)</(?:div|h[1-6])>.*?class="[^"]*\bcard-body\b[^"]*"[^>]*>(.*?)</(?:div|p)>',
            section_html, re.DOTALL,
        ):
            items.append({"headline": strip_html(m.group(1)), "text": strip_html(m.group(2))})

        # Pattern 2: news-card/comp-card/tool-card with h3 + p (March 21)
        for m in re.finditer(
            r'class="(?:news-card|comp-card|tool-card)[^"]*"[^>]*>.*?<h3>(.*?)</h3>\s*<p>(.*?)</p>',
            section_html, re.DOTALL,
        ):
            items.append({"headline": strip_html(m.group(1)), "text": strip_html(m.group(2))})

        # Pattern 3: comp-name + comp-text/comp-body (Competitive Landscape)
        for m in re.finditer(
            r'class="[^"]*\bcomp-name\b[^"]*"[^>]*>(.*?)</(?:span|div)>.*?class="[^"]*\bcomp-body\b[^"]*"[^>]*>(.*?)</(?:div|p)>',
            section_html, re.DOTALL,
        ):
            items.append({"headline": strip_html(m.group(1)), "text": strip_html(m.group(2))})

        # Pattern 4: tip-title/tool-title + tip-text/tool-body (AI Tool Guide)
        for m in re.finditer(
            r'class="[^"]*\b(?:tip-title|tool-title)\b[^"]*"[^>]*>(.*?)</(?:div|strong)>.*?class="[^"]*\b(?:tip-text|tool-body)\b[^"]*"[^>]*>(.*?)</(?:div|span)>',
            section_html, re.DOTALL,
        ):
            items.append({"headline": strip_html(m.group(1)), "text": strip_html(m.group(2))})

        # Pattern 5: market-ticker + market-price + market-change (Market Snapshot)
        for m in re.finditer(
            r'class="[^"]*\bmarket-ticker\b[^"]*"[^>]*>(.*?)</(?:div|span)>\s*'
            r'.*?class="[^"]*\bmarket-price\b[^"]*"[^>]*>(.*?)</(?:div|span)>\s*'
            r'.*?class="[^"]*\bmarket-change\b[^"]*"[^>]*>(.*?)</(?:div|span)>',
            section_html, re.DOTALL,
        ):
            ticker = strip_html(m.group(1))
            price = strip_html(m.group(2))
            change = strip_html(m.group(3))
            items.append({"headline": ticker, "text": f"{price} ({change})"})

        # Pattern 6: newsletter-card — split by card boundaries, extract name + content
        card_splits = re.split(r'<div\s+class="[^"]*\bnewsletter-card\b', section_html)
        for card_chunk in card_splits[1:]:  # skip first chunk (before first card)
            # Try multiple name patterns: h4, newsletter-name div
            name_m = re.search(r"<h4[^>]*>(.*?)</h4>", card_chunk, re.DOTALL)
            if not name_m:
                name_m = re.search(r'class="[^"]*\bnewsletter-name\b[^"]*"[^>]*>(.*?)</div>', card_chunk, re.DOTALL)
            name = strip_html(name_m.group(1)).split("\n")[0].strip() if name_m else ""
            # Remove date badge from name
            name = re.sub(r"\s*Mar \d+\s*$", "", name).strip()
            # Try multiple subject patterns
            subj_m = re.search(r'class="[^"]*\b(?:nl-subject|newsletter-subject)\b[^"]*"[^>]*>(.*?)</(?:div|span)>', card_chunk, re.DOTALL)
            subject = strip_html(subj_m.group(1)) if subj_m else ""
            # Try multiple content patterns (div, li, span)
            texts = [strip_html(t.group(1)) for t in re.finditer(
                r'class="[^"]*\b(?:nl-section-text|newsletter-item)\b[^"]*"[^>]*>(.*?)</(?:div|li|span)>', card_chunk, re.DOTALL)]
            for q in re.finditer(r'class="[^"]*\b(?:nl-quote|newsletter-quote)\b[^"]*"[^>]*>(.*?)</(?:div|blockquote)>', card_chunk, re.DOTALL):
                texts.append(strip_html(q.group(1)))
            full_text = (subject + " | " if subject else "") + " ".join(texts)
            if name and full_text.strip():
                items.append({"headline": name, "text": full_text})

        # Pattern 7: March 21 newsletter (nl-card with h3 + nl-body)
        for m in re.finditer(
            r'class="nl-card[^"]*"[^>]*>.*?<h3[^>]*>(.*?)</h3>.*?class="nl-body"[^>]*>(.*?)</div>',
            section_html, re.DOTALL,
        ):
            items.append({"headline": strip_html(m.group(1)), "text": strip_html(m.group(2))})

        # Pattern 8: March 21 tool-card (tool-header h3 + tool-body p)
        for m in re.finditer(
            r'class="tool-header"[^>]*>\s*<h3>(.*?)</h3>.*?<p>(.*?)</p>',
            section_html, re.DOTALL,
        ):
            items.append({"headline": strip_html(m.group(1)), "text": strip_html(m.group(2))})

        # Pattern 9: Daily Summary — summary-hook + summary-brief-text
        hook_m = re.search(
            r'class="summary-hook"[^>]*>(.*?)</div>',
            section_html, re.DOTALL,
        )
        if hook_m:
            items.append({"headline": "Summary", "text": strip_html(hook_m.group(1))})
        for m in re.finditer(
            r'class="summary-brief-label"[^>]*>(.*?)</span>.*?class="summary-brief-text"[^>]*>(.*?)</div>',
            section_html, re.DOTALL,
        ):
            items.append({"headline": strip_html(m.group(1)), "text": strip_html(m.group(2))})

        if items:
            result["sections"].append({"title": title, "items": items})

    return result


def parse_html_file(filepath):
    """Parse a single HTML file and return manifest entry + search data."""
    data = parse_with_regex(filepath)

    date_str = data["date"]
    base_dir = os.path.dirname(filepath) or "."
    # Check local file OR Supabase URL in HTML
    with open(filepath, "r", encoding="utf-8") as f:
        html_content = f.read()
    has_podcast = (
        os.path.exists(os.path.join(base_dir, f"podcast-{date_str}.mp3"))
        or f"podcast-{date_str}.mp3" in html_content
    )
    has_infographic = (
        os.path.exists(os.path.join(base_dir, f"infographic-{date_str}.jpg"))
        or f"infographic-{date_str}.jpg" in html_content
    )

    manifest_entry = {
        "date": data["date"],
        "dayOfWeek": data["dayOfWeek"],
        "focusTopics": [
            {"title": t["title"], "desc": t.get("desc", "")}
            for t in data["focusTopics"][:3]
        ],
        "kpis": {
            "aiStories": data["kpis"].get("aiStories", ""),
            "worldEvents": data["kpis"].get("worldEvents", ""),
            "marketMood": data["kpis"].get("marketMood", ""),
            "toolsFeatured": data["kpis"].get("toolsFeatured", ""),
        },
        "hasPodcast": has_podcast,
        "hasInfographic": has_infographic,
        "hasVideo": bool(data["youtubeId"]),
        "youtubeId": data["youtubeId"],
        "file": os.path.basename(filepath),
    }

    # Build search entry: focus topics as first section + all other sections
    search_sections = []
    if data["focusTopics"]:
        focus_items = [
            {"headline": t["title"], "text": t.get("desc", "")}
            for t in data["focusTopics"]
        ]
        search_sections.append({"title": "Today's Focus", "items": focus_items})

    search_sections.extend(data["sections"])

    search_entry = {
        "date": data["date"],
        "sections": search_sections,
    }

    return manifest_entry, search_entry


def parse_editorial_file(filepath: str) -> dict | None:
    """Parse an editorial HTML file and return a search entry with type='editorial'."""
    basename = os.path.basename(filepath)
    # Skip template and index files
    if basename in ("template-editorial.html", "index.html"):
        return None

    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()

    # Extract date from filename (YYYY-MM-DD-slug.html)
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", basename)
    if not date_match:
        # Try datePublished from JSON-LD
        ld_match = re.search(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})"', html)
        if not ld_match:
            return None
        date_str = ld_match.group(1)
    else:
        date_str = date_match.group(1)

    # Extract title from <h1 class="hero-title">
    title_match = re.search(
        r'class="hero-title"[^>]*>(.*?)</h1>', html, re.DOTALL
    )
    title = strip_html(title_match.group(1)) if title_match else ""

    # Extract subtitle/description from hero-subtitle
    subtitle_match = re.search(
        r'class="hero-subtitle"[^>]*>(.*?)</p>', html, re.DOTALL
    )
    subtitle = strip_html(subtitle_match.group(1)) if subtitle_match else ""

    # Extract tag (e.g., "Strategy")
    tag_match = re.search(r'class="tag"[^>]*>(.*?)</span>', html, re.DOTALL)
    tag = strip_html(tag_match.group(1)) if tag_match else ""

    # Extract article body sections by h2/h3 headings
    body_match = re.search(
        r'<article\s+class="article-body">(.*?)</article>', html, re.DOTALL
    )
    if not body_match:
        # Fallback: just index the title + subtitle
        return {
            "date": date_str,
            "type": "editorial",
            "file": "editorial/" + basename,
            "title": title,
            "tag": tag,
            "sections": [
                {
                    "title": title,
                    "items": [{"headline": title, "text": subtitle}],
                }
            ],
        }

    body_html = body_match.group(1)

    # Split body into sections by h2 headings
    sections: list[dict] = []
    # Find all h2/h3 positions
    heading_pattern = re.compile(
        r"<(h[23])[^>]*>(.*?)</\1>", re.DOTALL
    )
    headings = [(m.start(), m.end(), strip_html(m.group(2))) for m in heading_pattern.finditer(body_html)]

    # Collect paragraphs before the first heading as intro
    if headings:
        intro_html = body_html[: headings[0][0]]
    else:
        intro_html = body_html

    intro_paras = re.findall(r"<p[^>]*>(.*?)</p>", intro_html, re.DOTALL)
    intro_text = " ".join(strip_html(p) for p in intro_paras).strip()
    if intro_text:
        sections.append({
            "title": "Introduction",
            "items": [{"headline": title, "text": intro_text[:500]}],
        })

    # Process each heading section
    for i, (start, end, heading_text) in enumerate(headings):
        next_start = headings[i + 1][0] if i + 1 < len(headings) else len(body_html)
        section_html = body_html[end:next_start]
        paras = re.findall(r"<p[^>]*>(.*?)</p>", section_html, re.DOTALL)
        text = " ".join(strip_html(p) for p in paras).strip()
        if text:
            sections.append({
                "title": heading_text,
                "items": [{"headline": heading_text, "text": text[:500]}],
            })

    return {
        "date": date_str,
        "type": "editorial",
        "file": "editorial/" + basename,
        "title": title,
        "tag": tag,
        "sections": sections,
    }


def parse_review_file(filepath: str) -> dict | None:
    """Parse a Lab review HTML file and return a search entry with type='review'."""
    basename = os.path.basename(filepath)
    if basename == "index.html":
        return None

    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()

    # Extract date from filename
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", basename)
    if not date_match:
        return None
    date_str = date_match.group(1)

    # Extract title from <h1>
    title_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL)
    title = strip_html(title_match.group(1)) if title_match else ""

    # Extract sections by known section IDs
    known_sections = [
        ("verdict", "Verdict"),
        ("pricing", "Pricing"),
        ("features", "Key Features"),
        ("integrations", "Integrations"),
        ("usecases", "Use Cases"),
        ("limitations", "Limitations"),
    ]

    sections: list[dict] = []
    for section_id, section_label in known_sections:
        # Find <section ... id="section_id">
        pattern = re.compile(
            rf'<section[^>]*\bid="{section_id}"[^>]*>(.*?)</section>',
            re.DOTALL,
        )
        match = pattern.search(html)
        if not match:
            continue

        section_html = match.group(1)
        items: list[dict] = []

        if section_id == "verdict":
            # Verdict card paragraph
            for p in re.finditer(r"<p[^>]*>(.*?)</p>", section_html, re.DOTALL):
                text = strip_html(p.group(1))
                if text:
                    items.append({"headline": title, "text": text[:500]})
                    break
        elif section_id == "pricing":
            # Pricing plans: pricing-plan + pricing-price
            for m in re.finditer(
                r'class="pricing-plan"[^>]*>(.*?)</div>.*?'
                r'class="pricing-price"[^>]*>(.*?)</div>',
                section_html, re.DOTALL,
            ):
                plan = strip_html(m.group(1))
                price = strip_html(m.group(2))
                items.append({"headline": plan, "text": price})
        elif section_id == "features":
            # Feature cards: h3 + p
            for m in re.finditer(
                r"<h3[^>]*>(.*?)</h3>\s*<p[^>]*>(.*?)</p>",
                section_html, re.DOTALL,
            ):
                items.append({"headline": strip_html(m.group(1)), "text": strip_html(m.group(2))[:300]})
        else:
            # integrations, usecases, limitations: extract paragraphs and list items
            texts = []
            for p in re.finditer(r"<p[^>]*>(.*?)</p>", section_html, re.DOTALL):
                t = strip_html(p.group(1))
                if t:
                    texts.append(t)
            for li in re.finditer(r"<li[^>]*>(.*?)</li>", section_html, re.DOTALL):
                t = strip_html(li.group(1))
                if t:
                    texts.append(t)
            if texts:
                items.append({"headline": section_label, "text": " ".join(texts)[:500]})

        if items:
            sections.append({"title": section_label, "anchor": section_id, "items": items})

    if not sections:
        return None

    return {
        "date": date_str,
        "type": "review",
        "file": "reviews/" + basename,
        "title": title,
        "sections": sections,
    }


def build_pricing_entries(filepath: str) -> list[dict]:
    """Build search entries from pricing/data.json."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    date_str = data.get("generated_at", "")[:10]
    sections: list[dict] = []

    for provider in data.get("providers", []):
        items: list[dict] = []
        for model in provider.get("models", []):
            name = model.get("model_name", "")
            inp = model.get("input_price_per_1m_tokens", "")
            out = model.get("output_price_per_1m_tokens", "")
            ctx = model.get("context_window", "")
            text = f"Input: ${inp}/1M | Output: ${out}/1M | Context: {ctx}"
            items.append({"headline": name, "text": text})
        if items:
            sections.append({"title": provider.get("provider", ""), "items": items})

    if not sections:
        return []

    return [{
        "date": date_str,
        "type": "pricing",
        "file": "pricing/index.html",
        "sections": sections,
    }]


def build_benchmark_entries(filepath: str) -> list[dict]:
    """Build search entries from benchmarks/data.json."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    date_str = data.get("generated_at", "")[:10]
    sections: list[dict] = []

    for bench in data.get("benchmarks", []):
        items: list[dict] = []
        for model in bench.get("models", []):
            name = model.get("model_name", "")
            rank = model.get("rank", "")
            provider = model.get("provider", "")
            score = model.get("elo_score", model.get("score", ""))
            ctx = model.get("context_window", "")
            text = f"#{rank} | {provider} | Score: {score}"
            if ctx:
                text += f" | Context: {ctx}"
            items.append({"headline": name, "text": text})
        if items:
            sections.append({"title": bench.get("benchmark", ""), "items": items})

    if not sections:
        return []

    return [{
        "date": date_str,
        "type": "benchmark",
        "file": "benchmarks/index.html",
        "sections": sections,
    }]


def build_changelog_entries(filepath: str) -> list[dict]:
    """Build search entries from changelog/data.json -- one entry per changelog item."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    entries: list[dict] = []
    for item in data.get("entries", []):
        company = item.get("company", "")
        title = item.get("title", "")
        summary = item.get("summary", "")
        date_str = item.get("date", "")
        category = item.get("category", "")

        if not title or not date_str:
            continue

        text = summary
        if category:
            text = f"[{category}] {summary}"

        entries.append({
            "date": date_str,
            "type": "changelog",
            "file": "changelog/index.html",
            "sections": [
                {"title": company, "items": [{"headline": title, "text": text[:500]}]}
            ],
        })

    return entries


def build_dojo_entries(filepath: str) -> list[dict]:
    """Build search entries from a dojo data.json file."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    dojo_name = data.get("metadata", {}).get("name", "dojo")
    date_str = data.get("metadata", {}).get("lastUpdated", "")
    entries: list[dict] = []

    for module in data.get("modules", []):
        items: list[dict] = []
        items.append({
            "headline": module.get("title", ""),
            "text": module.get("description", ""),
        })
        for prompt in module.get("prompts", []):
            label = prompt.get("label", "")
            prompt_text = prompt.get("prompt", "")[:300]
            if label:
                items.append({"headline": label, "text": prompt_text})

        if items:
            entries.append({
                "date": date_str,
                "type": "dojo",
                "file": f"dojo/{dojo_name.replace('-dojo', '').replace('dojo-', '')}/index.html",
                "title": f"Module {module.get('number', '')}: {module.get('title', '')}",
                "sections": [{
                    "title": f"Module {module.get('number', '')}: {module.get('title', '')}",
                    "anchor": module.get("id", ""),
                    "items": items,
                }],
            })

    return entries


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # --- Digests ---
    pattern = os.path.join(base_dir, "morning-briefing-koda-????-??-??.html")
    files = sorted(glob.glob(pattern), reverse=True)

    print(f"Found {len(files)} digest file(s)")

    manifest_entries = []
    search_entries = []

    for filepath in files:
        print(f"  Parsing {os.path.basename(filepath)}...")
        manifest_entry, search_entry = parse_html_file(filepath)
        manifest_entries.append(manifest_entry)
        # Tag digest search entries
        search_entry["type"] = "digest"
        search_entry["file"] = manifest_entry["file"]
        search_entries.append(search_entry)

    # --- Editorials ---
    editorial_dir = os.path.join(base_dir, "editorial")
    editorial_files = sorted(
        glob.glob(os.path.join(editorial_dir, "????-??-??-*.html")), reverse=True
    )

    print(f"Found {len(editorial_files)} editorial file(s)")

    editorial_entries = []
    for filepath in editorial_files:
        print(f"  Parsing editorial/{os.path.basename(filepath)}...")
        entry = parse_editorial_file(filepath)
        if entry:
            search_entries.append(entry)
            editorial_entries.append({
                "date": entry["date"],
                "title": entry["title"],
                "tag": entry.get("tag", ""),
                "file": entry["file"],
            })

    # --- Reviews (The Lab) ---
    review_dir = os.path.join(base_dir, "reviews")
    review_count = 0
    if os.path.isdir(review_dir):
        review_files = sorted(
            glob.glob(os.path.join(review_dir, "????-??-??-*.html")), reverse=True
        )
        print(f"Found {len(review_files)} review file(s)")
        for filepath in review_files:
            print(f"  Parsing reviews/{os.path.basename(filepath)}...")
            entry = parse_review_file(filepath)
            if entry:
                search_entries.append(entry)
                review_count += 1

    # --- Changelog (Pulse) ---
    changelog_path = os.path.join(base_dir, "changelog", "data.json")
    changelog_count = 0
    if os.path.exists(changelog_path):
        print("Parsing changelog/data.json...")
        changelog_entries = build_changelog_entries(changelog_path)
        search_entries.extend(changelog_entries)
        changelog_count = len(changelog_entries)
        print(f"  {changelog_count} changelog entries")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Write manifest.json (digests + editorials)
    manifest = {
        "generated": now,
        "digests": manifest_entries,
        "editorials": editorial_entries,
    }
    manifest_path = os.path.join(base_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"Wrote {manifest_path} ({len(manifest_entries)} digests, {len(editorial_entries)} editorials)")

    # Write search-index.json (unified: digests + editorials, each tagged with type)
    search_index = {"generated": now, "entries": search_entries}
    search_path = os.path.join(base_dir, "search-index.json")
    with open(search_path, "w", encoding="utf-8") as f:
        json.dump(search_index, f, indent=2, ensure_ascii=False)
    print(f"Wrote {search_path} ({len(search_entries)} entries: "
          f"{len(manifest_entries)} digests, {len(editorial_entries)} editorials, "
          f"{review_count} reviews, {changelog_count} changelog)")


if __name__ == "__main__":
    main()
