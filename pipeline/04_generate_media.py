"""
Step 04: Generate media (podcast, infographic, video) via NotebookLM.

Reads digest-content.json, compiles a text summary for NotebookLM,
then calls notebooklm_media.py to generate and download media.

Input:  pipeline/data/digest-content.json
Output: podcast-{date}.mp3, infographic-{date}.jpg, video-{date}.mp4
        pipeline/data/media-status.json
"""

import argparse
import json
import subprocess
import sys
import os
import httpx
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import (DIGEST_DIR, OPENROUTER_API_KEY, SUPABASE_URL,
                              SUPABASE_SERVICE_ROLE_KEY, today_str,
                              write_json, read_json)


def _first_sentences(text: str, n: int = 2) -> str:
    """Return the first *n* sentences of *text* (split on '. ')."""
    parts = text.split(". ")
    kept = ". ".join(parts[:n])
    if not kept.endswith("."):
        kept += "."
    return kept


def _extract_key_stat(body: str) -> str:
    """Pull a short stat/number phrase from the body for the headline suffix."""
    import re
    # Look for patterns like "1 trillion parameters", "$100/barrel", "1-million-token"
    m = re.search(
        r"(\d[\d,.]*[\s-]*(trillion|billion|million|thousand|percent|%|point|"
        r"token|parameter|user|download|dollar|barrel)[s]?"
        r"(?:\s+\w+){0,2})",
        body, re.IGNORECASE,
    )
    if m:
        return m.group(0).strip().rstrip(".,;")
    # Fallback: dollar amounts or percentages only (avoid bare numbers)
    m = re.search(r"(\$[\d,.]+(?:\s*(?:billion|million|trillion))?|[\d,.]+%)", body)
    if m:
        return m.group(0).strip().rstrip(".,;")
    return ""


def compile_text_for_notebooklm(digest: dict) -> str:
    """Compile digest content into structured text for NotebookLM source.

    Uses markdown headers and bold headlines to create narrative beats
    that Veo 3's Gemini creative director can parse into visual scenes.
    """
    date_label = digest.get("date_label", digest["date"])
    sections: list[str] = []

    sections.append(f"# Koda Daily Intelligence Brief -- {date_label}\n")

    # Summary hook as blockquote
    summary = digest.get("summary", {})
    if summary.get("hook"):
        sections.append(f"> TODAY'S THEME: {summary['hook']}\n")

    # AI News -- structured with bold headlines and prose
    ai_news = digest.get("ai_news", [])
    if ai_news:
        sections.append("## AI DEVELOPMENTS\n")
        for story in ai_news[:8]:
            title = story["title"]
            body = story.get("body", "")
            stat = _extract_key_stat(body)
            headline = f"**{title}**"
            if stat:
                headline += f" -- {stat}"
            prose = _first_sentences(body, 2)
            sections.append(f"{headline}\n{prose}\n")

    # World News
    world_news = digest.get("world_news", [])
    if world_news:
        sections.append("## WORLD NEWS\n")
        for story in world_news[:6]:
            title = story["title"]
            body = story.get("body", "")
            stat = _extract_key_stat(body)
            headline = f"**{title}**"
            if stat:
                headline += f" -- {stat}"
            prose = _first_sentences(body, 2)
            sections.append(f"{headline}\n{prose}\n")

    # Markets -- flowing narrative paragraph
    markets = digest.get("markets", {})
    if markets:
        sections.append("## MARKET SNAPSHOT\n")
        market_parts: list[str] = []
        for key, data in markets.items():
            if isinstance(data, dict) and "price" in data:
                change = data.get("change", "")
                change_str = f" ({change})" if change else ""
                market_parts.append(f"{key.upper()}: {data['price']}{change_str}")
        if market_parts:
            sections.append(". ".join(market_parts) + ".")
        mood = summary.get("kpis", {}).get("market_mood") if summary else None
        if not mood:
            mood = digest.get("summary", {}).get("kpis", {}).get("market_mood")
        if mood:
            sections.append(f"Sentiment: {mood}.")
        sections.append("")

    # Tools -- structured
    tools = digest.get("tools", [])
    if tools:
        sections.append("## AI TOOLS & PRODUCTS\n")
        for tool in tools[:4]:
            title = tool["title"]
            body = tool.get("body", "")
            prose = _first_sentences(body, 2)
            sections.append(f"**{title}**\n{prose}\n")

    text = "\n".join(sections)

    # NotebookLM handles 500K+ chars; allow richer source material for better media
    if len(text) > 12000:
        text = text[:12000] + "\n\n[Content trimmed for generation]"

    return text


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
LLM_MODEL = "anthropic/claude-opus-4-6"

# ── Scene Template Library ────────────────────────────────────────────────
# Maps story categories (from digest-content.json) to Veo 3 visual profiles.
# Each profile guides the Visual Production Script generator with camera,
# color, lighting, environment, stabilizers, and atmosphere per scene type.

SCENE_TEMPLATES: dict[str, dict[str, str]] = {
    "Conflict": {
        "camera": "handheld urgency, 35mm lens, slight dutch angle for unease",
        "color_grade": "warm amber-red, desaturated shadows, high contrast",
        "lighting": "golden hour through smoke haze, harsh directional light",
        "environment": "aerial drone of strategic chokepoints, naval formations on open water, empty government halls with long shadows",
        "stabilizers": "maintain horizon line stability despite handheld motion, consistent shadow direction, prevent warping on rapid pans",
        "atmosphere": "distant rumble of machinery, dust motes in shafts of light, heat shimmer on tarmac, muffled radio chatter",
    },
    "Humanitarian": {
        "camera": "slow handheld, close-ups on hands and objects, 50mm lens shallow DOF",
        "color_grade": "muted warm tones, lifted blacks, desaturated",
        "lighting": "overcast diffused light, single harsh overhead in interiors",
        "environment": "crowded corridors, supply crates, tent structures, empty roads stretching to horizon",
        "stabilizers": "maintain subject center-frame on close-ups, consistent skin tone rendering, preserve fabric texture detail",
        "atmosphere": "ambient crowd murmur fading to silence, wind through canvas, footsteps on gravel",
    },
    "Diplomacy": {
        "camera": "slow dolly push-in, symmetrical framing, locked-off wide shots",
        "color_grade": "muted institutional tones, cool gray with warm wood accents",
        "lighting": "soft overhead panel lighting, warm pools from desk lamps",
        "environment": "long empty corridors with polished floors, rows of flags, conference tables with nameplates, document close-ups",
        "stabilizers": "maintain perfect symmetry on architectural shots, consistent reflection rendering on polished surfaces, lock text legibility on documents",
        "atmosphere": "silence with distant footsteps, pen scratching on paper, quiet air conditioning hum",
    },
    "Policy": {
        "camera": "steady tripod, slow lateral tracking, 35mm lens eye level",
        "color_grade": "neutral with subtle blue undertone, clean and institutional",
        "lighting": "even fluorescent overhead, natural window light from one side",
        "environment": "press briefing rooms without people, policy documents fanning on a desk, regulatory building exteriors, gavel close-ups",
        "stabilizers": "lock text legibility on documents and screens, maintain architectural geometry, consistent lighting across cuts",
        "atmosphere": "quiet room tone, clock ticking, shuffling papers, distant murmur of voices behind closed doors",
    },
    "Economy": {
        "camera": "rack focus between screens and physical space, 35mm lens, smooth dolly",
        "color_grade": "cool blue-green base with red flashes on downturns, warm gold on gains",
        "lighting": "mixed neon and fluorescent, screen glow illuminating faces in dark rooms",
        "environment": "trading floors with cascading tickers, commodity price screens, cargo ships in port, oil infrastructure at twilight",
        "stabilizers": "maintain screen text legibility during rack focus, consistent ticker scroll direction, prevent color banding on gradients",
        "atmosphere": "electronic tension hum, rapid keyboard clicks, distant phone rings, the low drone of financial data feeds",
    },
    "Model Release": {
        "camera": "smooth dolly and crane movements, 35mm lens, symmetrical framing for scale",
        "color_grade": "cool blue-cyan, clean whites, subtle purple highlights",
        "lighting": "volumetric light through server racks, LED status glow, cool fluorescent precision",
        "environment": "vast data center interiors stretching to vanishing point, GPU racks with blinking lights, code scrolling on screens reflected in glass, holographic neural network visualizations",
        "stabilizers": "maintain vanishing point alignment on data center shots, consistent LED blink pattern, preserve code text legibility on screen reflections",
        "atmosphere": "deep server fan hum, electrical crackle of cooling systems, subtle high-frequency data transfer tone",
    },
    "Trend": {
        "camera": "smooth crane pullback for scale reveal, slow zoom-out, 24mm wide lens",
        "color_grade": "cool blue transitioning to warm amber, gradient shift across the scene",
        "lighting": "soft volumetric light with rim lighting for depth",
        "environment": "abstract data landscapes, flowing particle systems representing adoption curves, interconnected nodes growing outward",
        "stabilizers": "maintain particle coherence across frames, consistent light direction on abstract forms, smooth interpolation on zoom transitions",
        "atmosphere": "rising orchestral tone, subtle digital pulse growing in intensity, wind-like data flow sound",
    },
    "Open Source": {
        "camera": "slow zoom-out revealing massive scale, crane ascending, 24mm wide lens",
        "color_grade": "warm-to-cool gradient, dawn light growing from horizon, greens and golds",
        "lighting": "dawn light building from darkness, golden rim lighting on structures",
        "environment": "vast open landscapes with branching tree structures, code repositories visualized as growing ecosystems, collaborative networks lighting up sequentially",
        "stabilizers": "maintain consistent growth direction in animations, preserve branching geometry, smooth light transition from warm to cool",
        "atmosphere": "growing ambient tone from silence, birdsong mixed with digital chimes, wind through open spaces",
    },
    "Agents": {
        "camera": "POV tracking shot, first-person perspective, smooth steadicam, 28mm lens",
        "color_grade": "electric blue with orange accent highlights, neon on dark",
        "lighting": "neon edge lighting, screen glow, sharp rim lights in dark space",
        "environment": "workflow visualizations as physical spaces, autonomous processes as assembly lines, decision trees as branching corridors, tool interfaces floating in space",
        "stabilizers": "maintain subject tracking stability on POV shots, consistent neon color temperature, preserve interface text legibility",
        "atmosphere": "synthetic pulse rhythm, mechanical servo sounds, data processing clicks, a sense of purposeful autonomous motion",
    },
    "China": {
        "camera": "symmetrical tracking shots, slow lateral movement, 35mm lens",
        "color_grade": "deep red accents on cool gray base, neon reflections, high contrast",
        "lighting": "neon signage reflections in wet surfaces, cool overhead mixed with warm accent",
        "environment": "dense urban tech districts at night, rain-slicked streets reflecting neon, massive server facilities, shipping container ports under floodlights",
        "stabilizers": "maintain symmetry on architectural shots, consistent rain particle direction, preserve neon reflection accuracy on wet surfaces",
        "atmosphere": "ambient rain on pavement, distant traffic hum, electronic signage buzz, splashing footsteps",
    },
    "_default": {
        "camera": "smooth dolly push-in, 35mm lens, eye level, steady and precise",
        "color_grade": "neutral with subtle warm highlights, balanced contrast",
        "lighting": "soft key light with ambient fill, clean and professional",
        "environment": "abstract information space, floating data points, clean minimalist backgrounds, soft gradients",
        "stabilizers": "maintain subject center-frame stability, consistent shadow direction, prevent horizon warping, preserve geometry on all surfaces",
        "atmosphere": "ambient electronic tone, subtle particle movement, quiet room presence",
    },
}


def build_differentiation_text(recent_themes, today_hook):
    """Build editorial direction text telling NotebookLM what NOT to repeat."""
    if not recent_themes:
        return None

    lines = ["EDITORIAL DIRECTION FOR TODAY'S EPISODE\n"]
    lines.append("In the last few days, this show covered these themes and angles:")

    for date in sorted(recent_themes.keys(), reverse=True):
        data = recent_themes[date]
        lines.append(f"\n{date}:")
        lines.append(f"  Theme: {data.get('hook', 'N/A')}")
        themes = data.get("top_themes", [])
        if themes:
            lines.append(f"  Key angles: {', '.join(themes)}")
        stories = data.get("top_stories", [])
        if stories:
            lines.append(f"  Lead stories: {', '.join(stories[:3])}")

    lines.append(f"\nToday's theme: {today_hook}")
    lines.append(
        "\nIMPORTANT PRODUCTION RULES:"
        "\n- Take a FRESH angle today. Do NOT repeat previous framing or conclusions."
        "\n- If a story continues from a previous day, focus on what CHANGED overnight."
        "\n- Prioritize today's unique developments over ongoing narratives."
        "\n- Use different examples, metaphors, and structure than previous episodes."
        "\n- Open with something surprising or new, not a recap."
    )

    return "\n".join(lines)


def generate_dynamic_focus(digest: dict, recent_themes: dict) -> str | None:
    """Generate a day-specific AUDIO_FOCUS via a fast Sonnet call."""
    today_hook = digest.get("summary", {}).get("hook", "")
    ai_titles = [s.get("title", "") for s in digest.get("ai_news", [])[:5]]
    world_titles = [s.get("title", "") for s in digest.get("world_news", [])[:3]]

    recent_summary = ""
    if recent_themes:
        for date in sorted(recent_themes.keys(), reverse=True)[:3]:
            data = recent_themes[date]
            recent_summary += f"\n{date}: {data.get('hook', '')} -- angles: {', '.join(data.get('top_themes', []))}"

    prompt = f"""You are the executive producer of a daily AI news video show.

Today's hook: {today_hook}
Today's top AI stories: {json.dumps(ai_titles)}
Today's top world stories: {json.dumps(world_titles)}

Recent episodes covered:{recent_summary if recent_summary else " (first episode, no history)"}

Write 2-3 sentences of AUDIO FOCUS instructions for today's episode host.
Tell them exactly what angle to take that is DIFFERENT from recent episodes.
Be specific about what to emphasize and what to skip or downplay.
Do NOT use em dashes. Keep it punchy and direct.

Reply with ONLY the instructions, no preamble."""

    return _sonnet_call(prompt, max_tokens=300, temperature=0.5)


def _sonnet_call(prompt: str, max_tokens: int = 300,
                  temperature: float = 0.5) -> str | None:
    """Make a single Sonnet call via OpenRouter. Returns text or None."""
    if not OPENROUTER_API_KEY:
        return None
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://koda.community",
            "X-Title": "Koda Digest Pipeline",
        }
        payload = {
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        resp = httpx.post(OPENROUTER_URL, json=payload, headers=headers, timeout=45)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"  Warning: Sonnet call failed: {e}")
        return None


def generate_visual_production_script(
    digest: dict, scene_templates: dict[str, dict[str, str]]
) -> str | None:
    """Generate a day-specific Visual Production Script via Sonnet.

    Returns a 400-800 word scene-by-scene script for Veo 3 cinematic video,
    or None if generation fails.
    """
    hook = digest.get("summary", {}).get("hook", "Today's intelligence briefing")
    focus_titles = [
        t.get("title", "") for t in
        digest.get("summary", {}).get("focus_topics", [])[:3]
    ]

    # Pick lead stories for Act 1 (world) and Act 2 (AI)
    world_news = digest.get("world_news", [])
    ai_news = digest.get("ai_news", [])
    act1_story = world_news[0] if world_news else {"title": "Global Events", "body": "", "category": "_default"}
    act2_story = ai_news[0] if ai_news else {"title": "AI Developments", "body": "", "category": "_default"}

    act1_cat = act1_story.get("category", "_default")
    act2_cat = act2_story.get("category", "_default")
    act1_vis = scene_templates.get(act1_cat, scene_templates["_default"])
    act2_vis = scene_templates.get(act2_cat, scene_templates["_default"])

    act1_body = act1_story.get("body", "")[:200]
    act2_body = act2_story.get("body", "")[:200]

    prompt = f"""You are a cinematic video director for a daily AI intelligence briefing.
Write a Visual Production Script for today's episode. This script will guide Google's
Veo 3 AI video model to generate a cinematic documentary-style video.

TODAY'S THEME: {hook}
FOCUS TOPICS: {', '.join(focus_titles)}

ACT 1 -- CRISIS/WORLD ({act1_story['title']}):
Story context: {act1_body}
Visual profile to use:
  Camera: {act1_vis['camera']}
  Color grade: {act1_vis['color_grade']}
  Lighting: {act1_vis['lighting']}
  Environment: {act1_vis['environment']}
  Motion constraints: {act1_vis['stabilizers']}
  Sound design: {act1_vis['atmosphere']}

ACT 2 -- TECHNOLOGY ({act2_story['title']}):
Story context: {act2_body}
Visual profile to use:
  Camera: {act2_vis['camera']}
  Color grade: {act2_vis['color_grade']}
  Lighting: {act2_vis['lighting']}
  Environment: {act2_vis['environment']}
  Motion constraints: {act2_vis['stabilizers']}
  Sound design: {act2_vis['atmosphere']}

Write the script in EXACTLY this format. Each scene block MUST include all 6 sub-fields.
Be vivid and specific in your scene descriptions. Target 400-800 words.

VISUAL PRODUCTION SCRIPT -- Koda Daily Briefing
Format: Cinematic documentary (Veo 3)

STRICT RULE: NO POLITICAL FIGURES in any scene. No recognizable political leaders,
heads of state, politicians, or government officials. Use abstract representations:
empty podiums, building exteriors, flags, diplomatic tables, military hardware
without identifiable personnel, policy documents, press briefing rooms without people.

=== COLD OPEN (0:00-0:15) ===
SCENE: [Describe the opening visual -- the most dramatic image of the day. Be specific
about what the camera sees, lighting, mood, and camera movement.]
NARRATION HOOK: [One-line hook that starts mid-action]

=== ACT 1: [TITLE] (0:15-1:30) ===
SCENE: [Wide establishing shot, then close-up, then scale reveal]
KEY VISUALS: [3-4 specific visual elements for Veo 3]
COLOR GRADE: [Per the visual profile above]
CAMERA FEEL: [Per the visual profile above]
MOTION CONSTRAINTS: [Per the visual profile above]
SOUND DESIGN: [Per the visual profile above]

=== ACT 2: [TITLE] (1:30-3:00) ===
SCENE: [Contrast transition from Act 1, then technology visualization, then human element]
KEY VISUALS: [3-4 specific visual elements for Veo 3]
COLOR GRADE: [Per the visual profile above]
CAMERA FEEL: [Per the visual profile above]
MOTION CONSTRAINTS: [Per the visual profile above]
SOUND DESIGN: [Per the visual profile above]

=== ACT 3: COLLISION (3:00-4:00) ===
SCENE: [Visual juxtaposition -- intercut or morph between Act 1 and Act 2 worlds]
KEY VISUALS: [How the two worlds merge visually]
COLOR GRADE: [Mixed palette from both acts]
CAMERA FEEL: [Accelerating pace]
MOTION CONSTRAINTS: [Smooth interpolation on all morphing transitions, maintain geometry]
SOUND DESIGN: [Both soundscapes bleeding together, rising tension]

=== CLOSE (4:00-4:30) ===
FINAL FRAME: [Single powerful image that encapsulates the day's theme. Hold the shot.]
SOUND DESIGN: [Silence except a sustained tone fading to black]

Reply with ONLY the script, no preamble or explanation."""

    return _sonnet_call(prompt, max_tokens=2500, temperature=0.7)


def generate_dynamic_video_focus(digest: dict) -> str:
    """Build day-specific video focus instructions (deterministic, no LLM call).

    These instructions become the `instructions` parameter for
    generate_cinematic_video(), telling Gemini how to direct the video.
    """
    hook = digest.get("summary", {}).get("hook", "Today's AI intelligence briefing")

    world_news = digest.get("world_news", [])
    ai_news = digest.get("ai_news", [])
    act1_title = world_news[0]["title"] if world_news else "Global Events"
    act2_title = ai_news[0]["title"] if ai_news else "AI Developments"

    return (
        "Create a cinematic intelligence briefing using the Visual Production Script "
        "source as your scene-by-scene guide. Follow the shot descriptions, color "
        "grades, camera movements, and sound design specified in the script.\n\n"
        f"TODAY'S THEME: {hook}\n"
        f"Act 1 focuses on: {act1_title} -- use warm/urgent palette\n"
        f"Act 2 focuses on: {act2_title} -- use cool/precise palette\n"
        "Act 3: show where these two worlds collide with visual juxtaposition\n\n"
        "TECHNICAL STABILIZERS (apply to ALL scenes):\n"
        "- Maintain subject center-frame stability in all shots\n"
        "- Consistent shadow direction within each act\n"
        "- Prevent horizon warping on drone and crane movements\n"
        "- Preserve architectural geometry in all environment shots\n"
        "- Lock screen text legibility on any data visualizations\n"
        "- Smooth interpolation on all transitions -- dissolves over hard cuts\n\n"
        "STRICT RULE -- NO POLITICAL FIGURES: Do NOT show any recognizable political "
        "figures, heads of state, politicians, or government officials. No faces of "
        "presidents, prime ministers, generals, or named political leaders. Use abstract "
        "representations: empty podiums, building exteriors, flags, military hardware "
        "without identifiable personnel.\n\n"
        "Push Veo 3 visual quality to maximum. Every frame should feel like it belongs "
        "in a Netflix documentary or Bloomberg Originals film."
    )


def generate_infographic_source(digest: dict) -> str | None:
    """Generate an Infographic Visual Direction source document via Opus LLM.

    This text is added as a SEPARATE NotebookLM source alongside the news text.
    NotebookLM's infographic AI reads both sources and produces the visual.
    The key insight: a dedicated creative brief source produces far better results
    than the `instructions` parameter alone.
    """
    ai_news = digest.get("ai_news", [])
    world_news = digest.get("world_news", [])
    tools = digest.get("tools", [])
    date_label = digest.get("date_label", digest.get("date", "Today"))

    # Pick 4 featured stories: 2 AI, 1 world, 1 tool/wildcard
    featured: list[dict] = []
    for story in ai_news[:2]:
        featured.append(story)
    for story in world_news[:1]:
        featured.append(story)
    if tools:
        featured.append(tools[0])
    elif len(ai_news) > 2:
        featured.append(ai_news[2])
    elif len(world_news) > 1:
        featured.append(world_news[1])

    # Build story summaries for the LLM
    story_briefs: list[str] = []
    positions = ["TOP-LEFT", "TOP-RIGHT", "BOTTOM-LEFT", "BOTTOM-RIGHT"]
    for i, story in enumerate(featured[:4]):
        title = story.get("title", "Featured Story")
        body = story.get("body", "")[:250]
        cat = story.get("category", "")
        stat = _extract_key_stat(story.get("body", ""))
        stat_str = f" | Key stat: {stat}" if stat else ""
        story_briefs.append(
            f"  {positions[i]}: \"{title}\" (Category: {cat}){stat_str}\n"
            f"  Context: {body}"
        )

    stories_text = "\n\n".join(story_briefs)

    prompt = f"""You are the creative director for "Koda Daily AI Digest", a premium daily intelligence
infographic. Write an INFOGRAPHIC VISUAL DIRECTION document that will be added as a source
to NotebookLM. NotebookLM's AI will read this source alongside the news text and generate
the infographic visual.

DATE: {date_label}

TODAY'S 4 FEATURED STORIES (arranged in a 2x2 grid):
{stories_text}

Write the visual direction document in EXACTLY this structure. Be vivid and specific about
what each quadrant should look like. The illustration descriptions are the most important
part -- they must be detailed, story-specific, and visually compelling.

---

INFOGRAPHIC VISUAL DIRECTION -- Koda Daily AI Digest, {date_label}

TITLE BANNER:
"AI DIGEST * {date_label}" -- large, clean sans-serif type, centered at top.
Subtle star-field particle texture in the dark background behind the title.

CANVAS:
Dark premium background (#0a0e1a deep navy). Subtle noise texture and faint star particles
across the full canvas. The overall feel is Bloomberg Terminal meets Wired magazine.

GRID: 2x2 card layout with even spacing. Each card has:
- Glowing purple-blue gradient border (subtle, not overwhelming)
- Dark card interior slightly lighter than background
- Bold headline in white/light text at top
- Rich AI-generated illustration (the star of each card)
- 2-3 data callouts (stats, percentages, trend indicators)
- Concise 1-2 sentence description text

QUADRANT 1 -- TOP-LEFT: [Story 1 title]
Headline: [Bold, punchy version of the title]
Illustration: [DETAILED description of a rich, contextual AI-generated illustration.
NOT clip-art. Think editorial magazine quality. Describe the specific visual elements,
colors, lighting, and composition. e.g. "A massive GPU chip rendered in iridescent
purple and blue, floating above a performance graph showing a steep upward curve.
Circuit traces glow with electric blue energy. Data streams flow upward from the chip."]
Data callouts: [2-3 specific stats from the story, styled as bold callout text with
trend arrows or mini visualizations]
Description: [1-2 sentences about the story]

QUADRANT 2 -- TOP-RIGHT: [Story 2 title]
Headline: [Bold version]
Illustration: [Same level of detail -- describe what the AI should generate as the
hero visual for this story. Be specific about objects, actions, colors, composition.]
Data callouts: [stats]
Description: [1-2 sentences]

QUADRANT 3 -- BOTTOM-LEFT: [Story 3 title]
Headline: [Bold version]
Illustration: [Detailed visual description]
Data callouts: [stats]
Description: [1-2 sentences]

QUADRANT 4 -- BOTTOM-RIGHT: [Story 4 title]
Headline: [Bold version]
Illustration: [Detailed visual description]
Data callouts: [stats]
Description: [1-2 sentences]

COLOR PALETTE:
Primary accents: electric blue (#3B82F6), vivid purple (#8B5CF6), bright emerald (#10B981)
Support: soft pink/magenta for highlights, white for text, muted gray for secondary text
Each card border should have a subtle glow effect using the accent colors

TYPOGRAPHY:
Clean sans-serif (Inter or DM Sans style). Clear size hierarchy:
- Title: extra-large, bold
- Card headlines: large, bold
- Data callouts: medium, bold with accent color
- Description text: small, regular weight, slightly muted

BRAND FOOTER:
Bottom strip with soft pink-to-purple gradient.
"From Koda" with paw-print icon -- bottom-left, clean white text.
"koda.community" -- bottom-right, clean white text.

STRICT RULES:
- Do NOT depict any recognizable political figures, heads of state, or government officials.
  Use abstract representations: empty podiums, building exteriors, flags, policy documents,
  military hardware silhouettes.
- Every illustration must be SPECIFIC to the story -- no generic stock imagery.
- Data visualizations should feel alive: styled mini-charts, animated-looking trend arrows,
  percentage callouts with glow effects.

---

Reply with ONLY the completed visual direction document. Fill in ALL quadrant details
with vivid, specific illustration descriptions based on the stories provided.
Do NOT use em dashes."""

    return _sonnet_call(prompt, max_tokens=2000, temperature=0.6)


def upload_to_supabase(date, media):
    """Upload podcast and infographic to Supabase Storage."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        print("\n  Supabase: skipping (credentials not set)")
        return

    sys.path.insert(0, str(DIGEST_DIR))
    try:
        from supabase_upload import upload_file
    except ImportError:
        print("\n  Supabase: skipping (supabase_upload.py not found)")
        return

    print("\n  Uploading media to Supabase Storage...")
    for filename in [f"podcast-{date}.mp3", f"infographic-{date}.jpg"]:
        filepath = DIGEST_DIR / filename
        if not filepath.exists():
            print(f"    Skipping {filename} (not found)")
            continue
        size_mb = filepath.stat().st_size / (1024 * 1024)
        print(f"    Uploading {filename} ({size_mb:.1f} MB)...")
        try:
            url = upload_file(str(filepath), SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
            print(f"    OK: {url}")
        except Exception as e:
            print(f"    FAILED: {e}")


def upload_to_youtube(date, digest, media):
    """Upload video to YouTube and write youtube-result.json for step 05."""
    video_path = DIGEST_DIR / f"video-{date}.mp4"
    if not video_path.exists():
        print("\n  YouTube: skipping (no video file)")
        return

    print("\n  Uploading video to YouTube...")

    # Generate a hook-based title from digest content
    hook = digest.get("summary", {}).get("hook", "Daily AI Intelligence Briefing")
    if len(hook) > 70:
        hook = hook[:67] + "..."
    title = f"{hook} | Koda Digest {date}"

    date_label = digest.get("date_label", date)
    description = (
        f"Koda Daily AI Intelligence Briefing for {date_label}.\n\n"
        f"Full digest: https://www.koda.community/morning-briefing-koda-{date}.html\n\n"
        f"Generated with AI assistance via NotebookLM.\n"
        f"Subscribe at https://www.koda.community for daily briefings."
    )

    cmd = [
        sys.executable, str(DIGEST_DIR / "youtube_upload.py"),
        "--file", str(video_path),
        "--title", title,
        "--description", description,
        "--privacy", "public",
        "--output-json", str(DIGEST_DIR / "youtube-result.json"),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode == 0:
            print(f"    YouTube upload complete")
            # Verify the result file and stamp with today's date
            yt_result_path = DIGEST_DIR / "youtube-result.json"
            if yt_result_path.exists():
                with open(yt_result_path, "r") as f:
                    yt_data = json.load(f)
                yt_data["date"] = args.date  # stamp so step 05 can validate freshness
                with open(yt_result_path, "w") as f:
                    json.dump(yt_data, f)
                print(f"    Video ID: {yt_data.get('video_id', 'unknown')}")
                print(f"    URL: {yt_data.get('url', 'unknown')}")
        else:
            print(f"    YouTube upload failed (exit code {result.returncode})")
            if result.stderr:
                print(f"    {result.stderr[-300:]}")
    except subprocess.TimeoutExpired:
        print("    YouTube upload timed out (600s)")
    except Exception as e:
        print(f"    YouTube upload error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Step 04: Generate media")
    parser.add_argument("--date", default=today_str(), help="Date (YYYY-MM-DD)")
    parser.add_argument("--skip-video", action="store_true", help="Skip video generation")
    args = parser.parse_args()

    print(f"[04] Generating media for {args.date}")

    # Load digest content
    digest = read_json("digest-content.json")
    if not digest:
        print("  ERROR: digest-content.json not found. Run 03_synthesize_content.py first.")
        sys.exit(1)

    # Compile text for NotebookLM
    text = compile_text_for_notebooklm(digest)
    print(f"  Compiled {len(text)} chars for NotebookLM")
    if len(text) < 4000:
        print(f"  WARNING: Source text only {len(text)} chars (below 4KB threshold)")
        print(f"  Media quality may be reduced. Consider re-running Step 01 with broader queries.")

    # Write text to temp file
    text_file = DIGEST_DIR / "pipeline" / "data" / "notebooklm-text.txt"
    with open(text_file, "w", encoding="utf-8") as f:
        f.write(text)

    # ── Cross-day differentiation ─────────────────────────────────────
    # Read from repo root (committed to git for cross-day persistence)
    ledger_path = DIGEST_DIR / "recent-themes.json"
    recent_themes = {}
    if ledger_path.exists():
        with open(ledger_path, "r", encoding="utf-8") as f:
            recent_themes = json.load(f)
    # Exclude today from recent themes (avoid self-reference)
    prior_themes = {d: v for d, v in recent_themes.items() if d != args.date}

    diff_file = None
    focus_str = None

    if prior_themes:
        print(f"  Theme ledger: {len(prior_themes)} prior days loaded")

        # Build differentiation source for NotebookLM
        today_hook = digest.get("summary", {}).get("hook", "")
        diff_text = build_differentiation_text(prior_themes, today_hook)
        if diff_text:
            diff_file = DIGEST_DIR / "pipeline" / "data" / "notebooklm-diff.txt"
            with open(diff_file, "w", encoding="utf-8") as f:
                f.write(diff_text)
            print(f"  Differentiation context: {len(diff_text)} chars")

        # Generate dynamic audio focus
        print("  Generating dynamic audio focus...")
        focus_str = generate_dynamic_focus(digest, prior_themes)
        if focus_str:
            print(f"  Dynamic audio focus: {focus_str[:100]}...")
        else:
            print("  Using default audio focus (no prior themes or API error)")
    else:
        print("  No prior themes found, using default focus")

    # ── Dynamic media enhancements ───────────────────────────────────
    # Generate infographic visual direction source (Opus LLM call)
    infographic_source_file = None
    if OPENROUTER_API_KEY:
        print("  Generating infographic visual direction source...")
        ig_source = generate_infographic_source(digest)
        if ig_source:
            infographic_source_file = DIGEST_DIR / "pipeline" / "data" / "infographic-source.txt"
            with open(infographic_source_file, "w", encoding="utf-8") as f:
                f.write(ig_source)
            print(f"  Infographic source: {len(ig_source)} chars")
        else:
            print("  Infographic source generation failed, using default prompt only")

    # Generate dynamic video focus (deterministic, no API call)
    video_focus_str = generate_dynamic_video_focus(digest)
    print(f"  Dynamic video focus: {video_focus_str[:80]}...")

    # Generate visual production script (Opus LLM call)
    visual_script_file = None
    if OPENROUTER_API_KEY and not args.skip_video:
        print("  Generating visual production script...")
        script = generate_visual_production_script(digest, SCENE_TEMPLATES)
        if script:
            visual_script_file = DIGEST_DIR / "pipeline" / "data" / "visual-script.txt"
            with open(visual_script_file, "w", encoding="utf-8") as f:
                f.write(script)
            print(f"  Visual script: {len(script)} chars")
        else:
            print("  Visual script generation failed, using defaults")
    elif args.skip_video:
        print("  Skipping visual script (--skip-video)")

    # Call notebooklm_media.py
    cmd = [
        sys.executable, str(DIGEST_DIR / "notebooklm_media.py"),
        "--text-file", str(text_file),
        "--date", args.date,
        "--output-dir", str(DIGEST_DIR),
    ]
    if args.skip_video:
        cmd.append("--skip-video")
    if diff_file:
        cmd.extend(["--diff-file", str(diff_file)])
    if focus_str:
        cmd.extend(["--focus", focus_str])
    if infographic_source_file:
        cmd.extend(["--infographic-source-file", str(infographic_source_file)])
    if video_focus_str:
        cmd.extend(["--video-focus", video_focus_str])
    if visual_script_file:
        cmd.extend(["--visual-script-file", str(visual_script_file)])

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"

    print(f"  Running notebooklm_media.py...")
    # Cinematic video (Veo 3) takes 30-45 min to render; allow 60 min total
    result = subprocess.run(cmd, env=env, capture_output=False, timeout=3600)

    # Read the status file that notebooklm_media.py writes
    status_path = DIGEST_DIR / "media-status.json"
    if status_path.exists():
        with open(status_path, "r", encoding="utf-8") as f:
            status = json.load(f)
        # Copy to pipeline data dir
        write_json("media-status.json", status)
        print(f"\n  Media generation {'completed' if result.returncode == 0 else 'had failures'}")
        print(f"  Exit code: {result.returncode}")
    else:
        print(f"  WARNING: No media-status.json generated")
        status = {
            "date": args.date,
            "exit_code": result.returncode,
            "steps": [],
            "media": {},
        }
        write_json("media-status.json", status)

    # ── Upload media to external services ─────────────────────────────
    # This must happen BEFORE step 05 (HTML generation) so that
    # youtube-result.json exists for the embed and Supabase URLs are live.

    media = status.get("media", {})

    # Upload podcast + infographic to Supabase Storage
    upload_to_supabase(args.date, media)

    # Upload video to YouTube
    if not args.skip_video:
        upload_to_youtube(args.date, digest, media)

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
