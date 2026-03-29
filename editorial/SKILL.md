---
name: koda-daily-editorial
description: >
  Generate a daily long-form editorial article for koda.community/editorial/.
  Picks one angle from today's digest, applies expert-routed Koda Voice,
  fact-checks all claims, generates visuals, and renders publication-ready HTML.
triggers:
  - "run the editorial"
  - "write today's editorial"
  - "generate the blog post"
  - "daily editorial"
  - "koda editorial"
model: opus
---

# Koda Daily Editorial — Skill

## Overview

This skill generates a daily 1,200-1,800 word editorial article for the Koda blog.
It picks one high-thesis angle from today's digest data, applies the Koda Voice
(blended from 6 content creators with expert routing), fact-checks every claim,
generates supporting visuals, and renders a self-contained HTML page.

## Prerequisites

Before running this skill:
1. Today's digest data must exist at `pipeline/data/digest-content.json`
2. The voice guide must exist at `editorial/koda-voice-guide.md`
3. The fact-check framework must exist at `editorial/fact-check-framework.md`
4. The HTML template must exist at `editorial/template-editorial.html`

## Pipeline

### Step 01E: Topic Selection

**Read** `pipeline/data/digest-content.json` and `pipeline/data/newsletters.json`.

**Evaluate** each story/section against these criteria:
- Does it have a counterintuitive angle? (prefer YES)
- Does it affect builders? (prefer YES)
- Is there quantitative data to anchor the argument? (prefer YES)
- Can you name a framework around it? (prefer YES)
- Would a reader share it? (prefer YES)

**Select** the single highest-scoring topic.

**Determine expert overlay** using this routing table:

| Topic Category | Expert Overlay |
|---------------|---------------|
| AI tools, automation, no-code, APIs, agents | Jack Roberts |
| Monetization, side hustles, business models | Paul J Lipsky |
| Scaling, leadership, SaaS, hiring, delegation | Dan Martell |
| Strategy, career, investing, long-term bets | theMITmonk (elevated) |
| Content creation, personal brand, social growth | Sabrina Ramonov (elevated) |
| Sales, pricing, offers, marketing | Alex Hormozi (elevated) |

**Output**: Topic statement (1 sentence), expert overlay name, 3 key data points.

### Step 02E: Deep Research

**Run the `research-assistant` skill** (or use Perplexity deep research) to gather:
- 3-5 additional data points beyond what the digest provides
- At least 1 contrarian perspective or counterargument
- Primary source URLs for all major claims
- Any relevant historical context or precedent

**Run Perplexity search** for:
- The specific topic (exact names, numbers, dates)
- Contrarian takes ("why X might fail," "the case against X")
- Related data (market size, adoption rates, benchmark comparisons)

**Target**: 5-8 verified data points with source URLs.

### Step 03E: Draft Article

**Read** `editorial/koda-voice-guide.md` for the full voice system.

**Write the article** using this exact structure:

```
1. THE HOOK (50-100 words)
   Voice: Hormozi base layer
   - Lead with the most surprising number or counterintuitive claim
   - Proof, Promise, Plan structure
   - Third-grade reading level
   - No throat-clearing

2. THE FRAMEWORK (150-250 words)
   Voice: Dan Martell base layer
   - Name the principle. Give it a label.
   - Explain the mental model in 2-3 paragraphs
   - This is what makes the article memorable

3. THE DEEP DIVE (500-800 words)
   Voice: {{EXPERT_OVERLAY}} (from Step 01E)
   - Apply the specific vocabulary, analogies, and teaching style
     of the activated expert overlay
   - Include 2-3 data points with inline citations
   - Translate technical details into business impact
   - Insert a pull quote or data visualization here

4. THE ZOOM OUT (200-300 words)
   Voice: theMITmonk base layer
   - Where does this fit in the 5-year arc?
   - What is the asymmetric bet?
   - Use a contrast pair to crystallize the insight

5. THE BUILD (150-200 words)
   Voice: Sabrina Ramonov base layer
   - "Here is what to build this weekend."
   - 3-5 concrete, actionable steps
   - Link to relevant tools from the digest
   - "Get your reps in" energy
```

**Word count target**: 1,200-1,800 words total.

**Mandatory constraints** (from voice guide anti-slop checklist):
- Zero em dashes
- No banned phrases (see voice guide for full list)
- No paragraph longer than 4 sentences
- No sentence over 30 words
- Every section has at least one specific number, name, or date
- At least one editorial opinion ("I think...")
- At least one hedge ("It is unclear whether...")
- Named sources for every factual claim

### Step 04E: Voice Review

**Run a self-review** against the voice guide:
1. Read the anti-slop checklist. Fix any violations.
2. Check: does the opening hook make you want to read paragraph 2?
3. Check: is the framework named and memorable?
4. Check: does the deep dive use the expert overlay's vocabulary?
5. Check: does the zoom-out add genuine strategic value?
6. Check: is the practical close actionable this week?
7. Read aloud mentally. Does it sound like a person or a machine?

**If any check fails**: rewrite that section before proceeding.

### Step 04F: Fact-Check Gate

**Read** `editorial/fact-check-framework.md` for the full framework.

**Extract claims**: Identify every verifiable claim in the article.
For each claim, note its type (statistic, attribution, event, comparison, temporal).

**Verify claims in parallel**:
- Use `perplexity_ask` for each HIGH priority claim
- Use `firecrawl_scrape` on primary source URLs
- Use web search for exact numbers and quotes

**Score each claim**:
- VERIFIED (95%+): 2+ independent sources confirm
- HIGH CONFIDENCE (80-94%): 1 Tier 1 source + logical consistency
- MODERATE (60-79%): 1 Tier 2 source, or minor discrepancy
- LOW (<60%): Cannot confirm independently
- DISPUTED: Sources contradict

**Decision**:
- All VERIFIED/HIGH: proceed to visuals
- Any MODERATE: rewrite that claim (hedge language, find better source, or remove)
- Any LOW: remove the claim entirely
- Any DISPUTED: acknowledge the dispute in the article text

**Common pitfalls to check**:
- Model name/version confusion (GPT-4 vs GPT-4o vs GPT-5) -- always verify the LATEST model name via web search before publishing. Never use cached/outdated names from search results.
- Parameter count vs token count (different numbers)
- Open-source vs open-weight (different things)
- "Raised $X" vs "valued at $X" (different claims)
- Benchmark scores without benchmark name (meaningless)
- Relative dates ("last week") not converted to absolute dates
- Tool descriptions with specific model names (e.g., "Perplexity gives access to GPT-4o") -- verify current supported models. If unsure, describe capabilities generically ("access to frontier models") rather than risk naming outdated versions.

### Step 05E: Generate Visuals

**Hero image**: Generate a prompt for a dark, premium, abstract visual that
represents the article's theme. Use the same image generation approach as
the digest infographic (Leonardo API or similar).

Style: Dark background, abstract geometric or flowing shapes, Koda color palette
(indigo #6366F1, blue #3B82F6, purple #8B5CF6). No text overlay. No faces.
No political figures. 16:9 aspect ratio.

**Inline visuals** (include 1-2 as needed):
- Data visualization: if the article references numerical comparisons,
  build an inline SVG/HTML chart. Use Koda color palette.
- Pull quote: style the most important insight as a pull quote block.
- Comparison table: if comparing 2-3 items, use an HTML table.

**Upload hero image** to Supabase Storage bucket `koda-media`:
- Filename: `editorial-hero-YYYY-MM-DD.jpg`
- Use `supabase_upload.py` with same env vars as the digest

### Step 06E: Render HTML

**Read** `editorial/template-editorial.html`.

**Replace all template variables**:
- `{{TITLE}}` - Article headline (under 70 chars, contains perspective + news hook)
- `{{META_DESCRIPTION}}` - 150-char SEO description
- `{{DATE_ISO}}` - YYYY-MM-DD format
- `{{DATE_DISPLAY}}` - "29 March 2026" format
- `{{FILENAME}}` - `YYYY-MM-DD-slug.html`
- `{{READ_MINUTES}}` - Estimated read time (word count / 250)
- `{{WORD_COUNT}}` - Actual word count
- `{{EXPERT_OVERLAY_TAG}}` - "AI Tools" / "Monetization" / "Strategy" / etc.
- `{{HERO_IMAGE_URL}}` - Supabase public URL
- `{{HERO_IMAGE_ALT}}` - Descriptive alt text
- `{{OG_IMAGE_URL}}` - Same as hero image URL
- `{{HOOK_CONTENT}}` - Section 1 HTML
- `{{FRAMEWORK_TITLE}}` - Named framework
- `{{FRAMEWORK_CONTENT}}` - Section 2 HTML
- `{{DEEP_DIVE_TITLE}}` - Deep dive heading
- `{{DEEP_DIVE_CONTENT}}` - Section 3 HTML (includes pull quotes, data viz, tables)
- `{{ZOOM_OUT_TITLE}}` - Zoom out heading
- `{{ZOOM_OUT_CONTENT}}` - Section 4 HTML
- `{{BUILD_CONTENT}}` - Section 5 HTML
- `{{SOURCE_LIST}}` - `<li>` elements for each source cited

**Save** two files:
1. `editorial/YYYY-MM-DD-slug.html` (permanent archive)
2. Verify the editorial directory exists: `ls editorial/`

### Step 07E: Link from Digest

**Add an "Editorial" card** to today's digest HTML (BOTH morning-briefing-koda.html AND the dated archive copy).

**Placement**: Directly after the Infographic section (right after the `<div class="infographic-overlay">...</div>`), NOT at the bottom of the main column.

**Also update these files**:
- `editorial/index.html` — add the new article card at the TOP of the grid (newest first)
- `index.html` (landing page) — replace the "Daily Editorial" card with today's article (title, date, excerpt, read time, link)

Format for the digest card:

```html
<section class="section" id="todays-editorial">
    <div class="flex items-center gap-1.5 mb-4">
        <span class="material-symbols-outlined text-sm text-[#8B5CF6]">edit_note</span>
        <span class="text-xs font-black tracking-[0.15em] uppercase text-[#8c909f]">Today's Editorial</span>
    </div>
    <a href="./editorial/YYYY-MM-DD-slug.html" target="_blank" class="block p-5 bg-[#131b2e] hover:bg-[#171f33] border-l-4 border-[#8B5CF6] transition-colors no-underline group">
        <div class="flex flex-wrap items-center gap-2 mb-2.5">
            <span class="text-[10px] font-bold uppercase tracking-widest bg-[#8B5CF6]/10 text-[#8B5CF6] px-2 py-0.5 rounded">{{TAG}}</span>
            <span class="text-[11px] text-[#8c909f]">{{READ_MINUTES}} min read</span>
        </div>
        <h3 class="text-[15px] font-bold text-[#dae2fd] leading-snug mb-3 group-hover:text-white transition-colors">{{TITLE}}</h3>
        <span class="text-[11px] font-bold uppercase tracking-widest text-[#8B5CF6]">Read Analysis &rarr;</span>
    </a>
</section>
```

### Step 08E: Update Search Index

**Run** `python build-index.py` to update `manifest.json` and `search-index.json`
so the editorial is discoverable via the landing page search.

Note: `build-index.py` may need to be extended to scan the `editorial/` directory.
If it does not already index editorials, add that capability.

### Step 09E: Git Commit & Deploy

```bash
git add editorial/YYYY-MM-DD-slug.html morning-briefing-koda*.html
git add manifest.json search-index.json
git commit -m "editorial: {{TITLE}}"
git push origin main
```

Vercel auto-deploys on push. The editorial will be live at:
`https://www.koda.community/editorial/YYYY-MM-DD-slug.html`

---

## Newsletter Integration

The editorial's hook paragraph + framework name becomes the newsletter teaser.
This slots into Step 07 of the main digest skill (newsletter send).

Format:
```
TODAY'S DEEP CUT

{{HOOK_PARAGRAPH}}

Read the full analysis: [link]
```

---

## Quality Targets

- Word count: 1,200-1,800 words
- Read time: 5-8 minutes
- Fact-check pass rate: 100% of claims VERIFIED or HIGH CONFIDENCE
- Voice consistency: passes all 6 questions in the voice guide checklist
- Anti-slop: zero banned phrases, zero em dashes
- Visuals: 1 hero image + 1-2 inline visuals
- SEO: title < 70 chars, meta description < 160 chars, 1-2 target keywords

## Graceful Degradation

- If hero image generation fails: use a CSS gradient hero (no image)
- If fact-check blocks >3 claims: pick a different topic (return to Step 01E)
- If the digest data is thin (few stories): write a "tools deep dive" or
  "newsletter synthesis" instead of a news analysis
- If Perplexity/research tools are unavailable: proceed with digest data only,
  but add a "Sources limited to daily digest data" note in the footer
