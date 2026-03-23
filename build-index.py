#!/usr/bin/env python3
"""
Build manifest.json and search-index.json from dated Koda digest HTML files.

Uses Python stdlib only (no pip installs). Parses all
morning-briefing-koda-YYYY-MM-DD.html files and extracts metadata
for the archive browser and searchable text for cross-day search.

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

    # Extract KPIs: kpi-value + kpi-label pairs
    kpi_pattern = re.compile(
        r'class="kpi-value"[^>]*>(.*?)</div>\s*<div\s+class="kpi-label"[^>]*>(.*?)</div>',
        re.DOTALL,
    )
    for value_html, label_html in kpi_pattern.findall(html):
        value = strip_html(value_html)
        label = strip_html(label_html)
        label_lower = label.lower()
        if "ai" in label_lower and "stor" in label_lower:
            result["kpis"]["aiStories"] = value
        elif "world" in label_lower:
            result["kpis"]["worldEvents"] = value
        elif "market" in label_lower or "mood" in label_lower:
            mood_match = re.search(r"(Bearish|Bullish|Neutral|Cautious\w*)", label, re.IGNORECASE)
            result["kpis"]["marketMood"] = mood_match.group(1) if mood_match else value
        elif "tool" in label_lower:
            result["kpis"]["toolsFeatured"] = value

    # Extract focus topics: look for focus-content blocks with either
    # div.focus-title + div.focus-desc (March 22) or h3 + p (March 21)
    focus_pattern_v2 = re.compile(
        r'class="focus-title"[^>]*>(.*?)</div>\s*'
        r'.*?class="focus-desc"[^>]*>(.*?)</div>',
        re.DOTALL,
    )
    focus_pattern_v1 = re.compile(
        r'class="focus-content"[^>]*>\s*<h3>(.*?)</h3>\s*<p>(.*?)</p>',
        re.DOTALL,
    )

    focus_matches = focus_pattern_v2.findall(html)
    if not focus_matches:
        focus_matches = focus_pattern_v1.findall(html)

    for title_html, desc_html in focus_matches:
        title = strip_html(title_html)
        desc = strip_html(desc_html)
        if title:
            result["focusTopics"].append({"title": title, "desc": desc})

    # Extract YouTube video ID
    yt_match = re.search(r"youtube\.com/embed/([a-zA-Z0-9_-]+)", html)
    if yt_match:
        result["youtubeId"] = yt_match.group(1)

    # Extract sections with their cards
    # Find all section-title markers first
    section_title_pattern = re.compile(
        r'class="section-title"[^>]*>(.*?)</(?:h2|div)>',
        re.DOTALL,
    )

    # Split HTML into sections by finding section-title positions
    section_starts = []
    for m in section_title_pattern.finditer(html):
        raw_title = strip_html(m.group(1))
        # Remove emoji/icon characters
        raw_title = re.sub(r"[\U0001F300-\U0001FAFF\U00002702-\U000027B0]", "", raw_title).strip()
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

        # Pattern 1: card-title + card-text (March 22 AI Developments, World News)
        for m in re.finditer(
            r'class="card-title"[^>]*>(.*?)</div>.*?class="card-text"[^>]*>(.*?)</div>',
            section_html, re.DOTALL,
        ):
            items.append({"headline": strip_html(m.group(1)), "text": strip_html(m.group(2))})

        # Pattern 2: news-card/comp-card/tool-card with h3 + p (March 21)
        for m in re.finditer(
            r'class="(?:news-card|comp-card|tool-card)[^"]*"[^>]*>.*?<h3>(.*?)</h3>\s*<p>(.*?)</p>',
            section_html, re.DOTALL,
        ):
            items.append({"headline": strip_html(m.group(1)), "text": strip_html(m.group(2))})

        # Pattern 3: comp-name + comp-text (March 22 Competitive Landscape)
        for m in re.finditer(
            r'class="comp-name"[^>]*>(.*?)</(?:span|div)>.*?class="comp-text"[^>]*>(.*?)</div>',
            section_html, re.DOTALL,
        ):
            items.append({"headline": strip_html(m.group(1)), "text": strip_html(m.group(2))})

        # Pattern 4: tip-title + tip-text (March 22 AI Tool Guide)
        for m in re.finditer(
            r'class="tip-title"[^>]*>(.*?)</div>.*?class="tip-text"[^>]*>(.*?)</div>',
            section_html, re.DOTALL,
        ):
            items.append({"headline": strip_html(m.group(1)), "text": strip_html(m.group(2))})

        # Pattern 5: market-ticker + market-price + market-change (Market Snapshot)
        for m in re.finditer(
            r'class="market-ticker"[^>]*>(.*?)</div>\s*'
            r'.*?class="market-price[^"]*"[^>]*>(.*?)</div>\s*'
            r'.*?class="market-change[^"]*"[^>]*>(.*?)</div>',
            section_html, re.DOTALL,
        ):
            ticker = strip_html(m.group(1))
            price = strip_html(m.group(2))
            change = strip_html(m.group(3))
            items.append({"headline": ticker, "text": f"{price} ({change})"})

        # Pattern 6: newsletter-card — split by card boundaries, extract h4 + content
        card_splits = re.split(r'<div\s+class="newsletter-card"', section_html)
        for card_chunk in card_splits[1:]:  # skip first chunk (before first card)
            name_m = re.search(r"<h4[^>]*>(.*?)</h4>", card_chunk, re.DOTALL)
            name = strip_html(name_m.group(1)).split("\n")[0].strip() if name_m else ""
            # Remove date badge from name
            name = re.sub(r"\s*Mar \d+\s*$", "", name).strip()
            subj_m = re.search(r'class="nl-subject"[^>]*>(.*?)</div>', card_chunk, re.DOTALL)
            subject = strip_html(subj_m.group(1)) if subj_m else ""
            texts = [strip_html(t.group(1)) for t in re.finditer(
                r'class="nl-section-text"[^>]*>(.*?)</div>', card_chunk, re.DOTALL)]
            for q in re.finditer(r'class="nl-quote"[^>]*>(.*?)</div>', card_chunk, re.DOTALL):
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
    has_podcast = os.path.exists(os.path.join(base_dir, f"podcast-{date_str}.mp3"))
    has_infographic = os.path.exists(os.path.join(base_dir, f"infographic-{date_str}.jpg"))

    manifest_entry = {
        "date": data["date"],
        "dayOfWeek": data["dayOfWeek"],
        "focusTopics": [t["title"] for t in data["focusTopics"][:3]],
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


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    pattern = os.path.join(base_dir, "morning-briefing-koda-????-??-??.html")
    files = sorted(glob.glob(pattern), reverse=True)

    if not files:
        print("No dated digest HTML files found.")
        return

    print(f"Found {len(files)} digest file(s)")

    manifest_entries = []
    search_entries = []

    for filepath in files:
        print(f"  Parsing {os.path.basename(filepath)}...")
        manifest_entry, search_entry = parse_html_file(filepath)
        manifest_entries.append(manifest_entry)
        search_entries.append(search_entry)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Write manifest.json
    manifest = {"generated": now, "digests": manifest_entries}
    manifest_path = os.path.join(base_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"Wrote {manifest_path} ({len(manifest_entries)} entries)")

    # Write search-index.json
    search_index = {"generated": now, "days": search_entries}
    search_path = os.path.join(base_dir, "search-index.json")
    with open(search_path, "w", encoding="utf-8") as f:
        json.dump(search_index, f, indent=2, ensure_ascii=False)
    print(f"Wrote {search_path} ({len(search_entries)} days)")


if __name__ == "__main__":
    main()
