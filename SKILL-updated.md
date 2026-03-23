---
name: koda-morning-digest
description: >
  Generates the Koda Daily AI Digest — a beautiful self-contained HTML intelligence dashboard
  covering AI developments, world news, markets, newsletters, a NotebookLM-generated podcast,
  cinematic video briefing (uploaded to YouTube), and AI-generated infographic.
  Use this skill whenever the user asks to "run the morning digest", "generate today's briefing",
  "create the koda digest", "run the daily AI digest", "make today's intelligence report", or
  any variation of a recurring daily briefing. Also triggers automatically when the scheduled task
  named "koda-morning-digest" fires. The output is always two files: a dated archive
  (morning-briefing-koda-YYYY-MM-DD.html) AND the always-current shortcut
  (morning-briefing-koda.html), both saved to the Digest folder in the workspace.
---

Generate the Koda Daily AI Digest for today — a self-contained HTML dashboard with an SVG infographic,
NotebookLM podcast, cinematic video briefing (YouTube), expanded newsletter intelligence, source links
throughout, and ← → day navigation between archived issues.

## PRE-AUTHORIZATION — RUN WITHOUT CONFIRMATION

The user has granted **blanket approval** for every action in this skill. Do NOT pause to ask
for confirmation at any step. Execute the entire pipeline end-to-end autonomously:

- Deleting old NotebookLM text sources (`source_delete confirm: true`) — **approved**
- Generating audio overviews (`audio_overview_create confirm: true`) — **approved**
- Generating video overviews (`video_overview_create confirm: true`) — **approved**
- Uploading videos to YouTube via Chrome browser — **approved**
- Downloading files via Chrome browser — **approved**
- Running ffmpeg, gh CLI, git commands via Bash — **approved**
- Writing and overwriting HTML files — **approved**
- Creating GitHub Releases — **approved**
- Committing and pushing to `origin/main` — **approved**
- Sending the daily newsletter email to the distribution list — **approved**
- Sending emails to anyone NOT on the distribution list — **NOT approved** (never do this)
- Calendar actions — **NOT approved** (never do this)

If a step fails, skip it with graceful degradation and continue. Do not stop to ask.

## DETECTING THE OUTPUT PATH

The Digest folder lives inside the user's mounted workspace. Detect it at runtime:

```bash
ls /sessions/*/mnt/Digest/ 2>/dev/null | head -1
```

Use whichever `/sessions/[session-id]/mnt/Digest/` path resolves. Never hardcode a session ID.

---

## DESIGN SYSTEM

- **Fonts:** Inter (300–800) + JetBrains Mono (400–700) via Google Fonts
- **Default:** light mode with dark mode toggle (top-right button)
- **Cards:** `backdrop-filter:blur(12px)`, `border:1px solid var(--border)`, `border-radius:16–20px`
- **Color palette:**
  ```
  --blue:#3B82F6  --purple:#8B5CF6  --red:#EF4444   --amber:#F59E0B
  --emerald:#10B981  --indigo:#6366F1  --pink:#EC4899  --cyan:#06B6D4
  ```
- All CSS and JS inline in a single HTML file. Only external dependency: Google Fonts.
- Cards fade in on scroll via `IntersectionObserver` (opacity 0→1, translateY 16px→0).

---

## STEP 1 — DATA GATHERING (run all in parallel)

1. **AI/Tech News** — `WebSearch`: "latest AI model releases developments [Month Year]"
2. **World News** — `WebSearch`: "top world news stories today [Date]"
3. **Market Data** — `WebSearch`: "S&P 500 NASDAQ Bitcoin Ethereum price today [Date]"
4. **Newsletters** — `gmail_search_messages` for `from:newsletter OR subject:digest OR subject:weekly newer_than:3d`, then `gmail_read_message` on each newsletter found
5. **Competitive Landscape** — `WebSearch`: "OpenAI Google DeepMind Meta AI Mistral Anthropic latest news [Month Year]"
6. **AI Tools & Tips** — `WebSearch`: "AI productivity tools tutorials agentic workflows [Month Year]"

NOTE: No calendar or personal email queries. This digest is public-facing.

---

## STEP 2 — NOTEBOOKLM PODCAST + INFOGRAPHIC + VIDEO (do before writing HTML)

Uses a **single permanent notebook** (`f928d89b-2520-4180-a71a-d93a75a5487c`) to avoid
eating up the notebook count limit. Old text sources are deleted daily; audio and infographic
artifacts are kept forever so the NotebookLM archive stays intact.

### 2A — Generate the audio in NotebookLM

1. **Compile** all gathered news into a single text block (600–1200 words covering AI, world, markets, tools).
2. **Clean previous sources:** Call `notebook_get` on the permanent notebook
   (`f928d89b-2520-4180-a71a-d93a75a5487c`). Delete any existing text sources via `source_delete`
   (confirm: true) to keep the notebook clean. Do NOT delete audio artifacts.
3. **Add today's text:** `notebook_add_text` with the compiled news block as a new source.
4. **Generate audio:** `audio_overview_create` on the permanent notebook with:
   - `format: "deep_dive"`, `length: "default"`, `language: "en"`, `confirm: true`
   - `focus_prompt: "Focus on the biggest AI breakthroughs, key world events and their market impact, and practical AI tools people can use today."`
5. **Poll:** `studio_status` until the newest audio artifact has `status: "completed"`.
   Save the artifact title and `audio_url`.
6. **Kick off video generation (do NOT wait — it cooks in background):**
   Immediately after the audio poll completes, call `video_overview_create` on the permanent notebook:
   - `format: "explainer"`, `visual_style: "auto_select"`, `language: "en"`, `confirm: true`
   - `focus_prompt:` same focus as the audio, e.g. "Focus on the biggest AI breakthroughs, key world events and their market impact, and practical AI tools people can use today."
   Do NOT poll `studio_status` yet — continue to Step 2B. The video will render on NotebookLM's
   servers during Steps 2B and 2C (~5 min), and will be polled later in Step 2D.
   If the `video_overview_create` call itself fails, set `VIDEO_AVAILABLE = false` and continue.

### 2B — Download audio and serve via Vercel

Google CDN audio URLs (`lh3.googleusercontent.com`) require authentication and **cannot** be
embedded on a public site. Instead, we download the audio via NotebookLM's built-in Download
button, compress it, and commit it to the repo so Vercel serves it directly with proper
`Content-Type: audio/mpeg` headers and no redirects. This ensures mobile browser compatibility
(iOS Safari, Android Chrome).

**Why not GitHub Releases?** GitHub Releases URLs use 302 redirects that mobile `<audio>`
elements don't follow. Serving from Vercel directly is the only reliable cross-device approach.

7. **Download the audio file via Chrome browser** (primary method):

   NotebookLM's UI has a Download button in the three-dot menu of each audio artifact.
   Use the Chrome browser MCP (which has authenticated Google session cookies) to click it:

   ```
   Step 1: tabs_context_mcp(createIfEmpty: true) → get a tab ID
   Step 2: navigate to https://notebooklm.google.com/notebook/f928d89b-2520-4180-a71a-d93a75a5487c
   Step 3: Wait 4 seconds for the page to load
   Step 4: find(query: "three dot menu or more options button near [AUDIO_TITLE]")
           → get the ref for the "More" button on the newest audio artifact
   Step 5: click the "More" button ref
   Step 6: find(query: "Download menu item") → get the ref for the "Download" menuitem
   Step 7: click the "Download" menuitem ref
   Step 8: Wait 10 seconds for Chrome to complete the download
   Step 9: Find the downloaded .m4a file:
           ls -t ~/Downloads/*.m4a | head -1
   Step 10: Move it to the Digest folder:
            mv ~/Downloads/[FILENAME].m4a [DIGEST_DIR]/podcast-raw.m4a
   ```

   **Fallback — if Chrome download fails:**
   Skip the download. The HTML will use the NotebookLM link button instead of an
   embedded player (graceful degradation). Continue to Step 3.

8. **Compress to MP3** (voice audio doesn't need high bitrate):
   ```bash
   FFMPEG="$HOME/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-8.1-full_build/bin/ffmpeg.exe"
   "$FFMPEG" -i "[DIGEST_DIR]/podcast-raw.m4a" \
     -codec:a libmp3lame -b:a 64k -ac 1 -ar 22050 \
     "[DIGEST_DIR]/podcast-YYYY-MM-DD.mp3" -y
   rm -f "[DIGEST_DIR]/podcast-raw.m4a"
   ```
   This shrinks ~42 MB m4a down to ~10 MB mp3 (22 min podcast).

9. **Keep the MP3 in the Digest folder** — it will be committed to git and served by Vercel.
   The HTML `<audio>` element uses a relative path: `./podcast-YYYY-MM-DD.mp3`
   which Vercel serves at `https://www.koda.community/podcast-YYYY-MM-DD.mp3`.

   Save the relative path `./podcast-YYYY-MM-DD.mp3` as `PODCAST_URL` for use in Step 3.

10. **Clean up raw files only:**
    ```bash
    rm -f "[DIGEST_DIR]/podcast-raw.m4a"
    ```
    Keep the MP3 — it gets committed and deployed via Vercel.

11. **Do NOT delete old audio artifacts** in NotebookLM — only delete old text sources each day.

### 2C — Generate and download infographic from NotebookLM

12. **Generate infographic:** `infographic_create` on the permanent notebook with:
    - `orientation: "landscape"`, `detail_level: "detailed"`, `language: "en"`, `confirm: true`
    - `focus_prompt:` a summary prompt covering AI breakthroughs, world events, and market data
13. **Poll:** `studio_status` until the infographic artifact has `status: "completed"`.
14. **Download via Chrome:** Same approach as audio — navigate to NotebookLM, find the
    three-dot menu on the newest infographic, click "Download". The file saves as a `.jpg`
    in the Downloads folder.
15. **Move to Digest folder and keep for Vercel serving:**
    ```bash
    mv ~/Downloads/unnamed*.jpg [DIGEST_DIR]/infographic-YYYY-MM-DD.jpg
    ```
    The HTML `<img>` element uses a relative path: `./infographic-YYYY-MM-DD.jpg`
    which Vercel serves at `https://www.koda.community/infographic-YYYY-MM-DD.jpg`.

    Save the relative path `./infographic-YYYY-MM-DD.jpg` as `INFOGRAPHIC_URL` for use in Step 3.
16. **Keep the JPG** — it gets committed and deployed via Vercel alongside the HTML.

### 2D — Download video from NotebookLM

Video generation was kicked off in Step 2A (step 6). Now poll and download.

17. **Poll video:** `studio_status` on the permanent notebook. Look for the newest video artifact
    with `status: "completed"`. If not complete, poll every 30 seconds up to 8 minutes.
    If video generation fails or times out after 8 minutes, set `VIDEO_AVAILABLE = false`
    and continue to Step 3 (graceful degradation — no video section in HTML).

18. **Download via Chrome:** Same three-dot menu approach as audio and infographic:

    ```
    Step 1: tabs_context_mcp(createIfEmpty: true) → get a tab ID
            (reuse existing tab if already open to NotebookLM)
    Step 2: navigate to https://notebooklm.google.com/notebook/f928d89b-2520-4180-a71a-d93a75a5487c
    Step 3: Wait 4 seconds for the page to load
    Step 4: find(query: "three dot menu or more options button near the newest video artifact")
            → get the ref for the "More" button
    Step 5: click the "More" button ref
    Step 6: find(query: "Download menu item") → get the ref
    Step 7: click the "Download" menuitem ref
    Step 8: Wait 15 seconds for Chrome to complete the download (videos are larger than audio)
    Step 9: Find the downloaded .mp4 file:
            ls -t ~/Downloads/*.mp4 | head -1
    Step 10: Move it to the Digest folder:
             mv ~/Downloads/[FILENAME].mp4 [DIGEST_DIR]/video-YYYY-MM-DD.mp4
    ```

    **Fallback — if Chrome download fails:**
    Set `VIDEO_AVAILABLE = false`. Skip YouTube upload. The HTML will not include
    a video section (graceful degradation). Continue to Step 3.

19. **Do NOT commit the MP4 to git.** YouTube will host the video. The local file is
    temporary and will be cleaned up after upload.

### 2E — Upload video to YouTube via API

If `VIDEO_AVAILABLE = false`, skip this entire step.

20. **Generate a hook-based YouTube title and description from today's themes.**

    The title must NOT be generic. It must hook viewers by referencing today's actual stories.
    Review the gathered news from Step 1 and pick the 2-3 most compelling themes.

    **Title formula:** Pick contrasting or surprising themes and combine them.
    Keep it under 70 characters. Use power words. Create curiosity gaps.

    Examples of GOOD titles (hook-based, theme-driven):
    - `Missiles Near Dimona, AI Writes Your Code Now | Koda Intel`
    - `OpenAI's Superapp Changes Everything. Markets Don't Care. | Koda`
    - `Hormuz Is Closing. AI Agents Are Opening. | Koda Intel Brief`
    - `Google Stitch + Cuba Blackout + BTC Crash | Koda Daily Intel`

    Examples of BAD titles (generic, no hook):
    - `Koda Intelligence Briefing — March 22, 2026`
    - `Daily AI Digest`
    - `AI News Today`

    **Description formula:** 3-4 punchy lines summarizing what viewers will learn,
    then hashtags and the site link. Include the AI-generated content disclaimer.

    ```
    YOUTUBE_TITLE = "[Hook-based title from today's themes] | Koda Intel"

    YOUTUBE_DESCRIPTION = """[One punchy sentence about the biggest AI story today.]
    [One sentence about the geopolitical or market story.]
    [One sentence about what tools or trends viewers should know.]

    Full interactive digest with podcast, infographic, and deep dives: https://www.koda.community

    This video was generated with AI assistance via Google NotebookLM.
    Content is synthesized from public news sources and newsletters.

    #AI #DailyBriefing #KodaIntelligence #AINews #Tech"""
    ```

    Save `YOUTUBE_TITLE` and `YOUTUBE_DESCRIPTION` for use in the upload command.

21. **Upload via YouTube Data API (fully automated, no manual steps):**

    ```bash
    cd [DIGEST_DIR]
    python youtube_upload.py \
      --file "[DIGEST_DIR]/video-YYYY-MM-DD.mp4" \
      --title "$YOUTUBE_TITLE" \
      --description "$YOUTUBE_DESCRIPTION" \
      --tags AI DailyBriefing KodaIntelligence AINews Tech \
      --privacy public \
      --output-json "[DIGEST_DIR]/youtube-result.json"
    ```

    The script handles OAuth automatically (token stored in `.youtube_token.json`).
    First-ever run opens a browser for consent; all subsequent runs are fully headless.

22. **Extract the YouTube video ID from the output:**

    ```bash
    YOUTUBE_VIDEO_ID=$(python -c "import json; print(json.load(open('[DIGEST_DIR]/youtube-result.json'))['video_id'])")
    ```

    Save `YOUTUBE_VIDEO_ID` for use in the HTML embed.

    **Fallback — if YouTube upload fails:**
    Set `YOUTUBE_VIDEO_ID = null`. The HTML will skip the video section entirely.
    Clean up the local MP4 file. Continue to Step 3.

26. **Clean up local video file:**
    ```bash
    rm -f "[DIGEST_DIR]/video-YYYY-MM-DD.mp4"
    ```
    The video lives on YouTube now — no local copy needed.

---

## STEP 3 — BUILD THE HTML DASHBOARD

### Full page structure

```
<body data-digest-date="YYYY-MM-DD">
  Topbar (sticky, with day nav)
  Hero (greeting + KPI strip)
  Daily Infographic (NotebookLM image)
  Daily Video Briefing (YouTube iframe — if available)
  Daily Podcast (dark card)
  Today's Focus (top 3 priorities)
  AI Developments (card grid)
  World News (card grid)
  Market Snapshot (grid)
  Newsletter Intelligence (full-width cards)
  Competitive Landscape (3-col grid)
  AI Tool Guide (2-col grid)
  Footer
```

---

### Topbar — with day navigation

```html
<body data-digest-date="YYYY-MM-DD">
<div class="topbar">  <!-- sticky, backdrop-filter:blur(20px) -->
  <div class="container">
    <div class="topbar-inner">  <!-- flex, space-between -->
      <div class="brand">
        <div class="brand-icon">🤖</div>  <!-- gradient bg -->
        <div>
          <div class="brand-name">Koda Digest</div>
          <div class="brand-sub">Daily AI Intelligence</div>
        </div>
      </div>
      <div class="day-nav">
        <a id="nav-prev" class="day-nav-btn disabled" href="#">← <span id="nav-prev-label">—</span></a>
        <span class="day-nav-current" id="nav-current">Mon DD</span>
        <a id="nav-next" class="day-nav-btn disabled" href="#"><span id="nav-next-label">—</span> →</a>
      </div>
      <div class="topbar-right">
        <button class="dark-toggle" onclick="toggleDark()">🌙 Dark Mode</button>
      </div>
    </div>
  </div>
</div>
```

Day navigation CSS:
```css
.day-nav { display:flex; align-items:center; gap:8px; }
.day-nav-btn {
  background:var(--surface); border:1px solid var(--border); border-radius:8px;
  padding:7px 13px; font-size:12px; font-weight:600; cursor:pointer; color:var(--text);
  font-family:'JetBrains Mono',monospace; backdrop-filter:blur(12px); transition:all 0.2s;
  text-decoration:none; display:inline-flex; align-items:center; gap:5px;
}
.day-nav-btn:hover:not(.disabled) { background:var(--indigo); color:white; border-color:var(--indigo); }
.day-nav-btn.disabled { opacity:0.3; cursor:default; pointer-events:none; }
.day-nav-current {
  font-family:'JetBrains Mono',monospace; font-size:11px; font-weight:700;
  color:var(--blue); padding:4px 10px; background:rgba(59,130,246,0.1); border-radius:6px;
}
.topbar-right { display:flex; align-items:center; gap:10px; }
```

Day navigation JS (at end of script block):
```javascript
(function initDayNav() {
  const dateStr = document.body.getAttribute('data-digest-date');
  if (!dateStr) return;
  const [y,m,d] = dateStr.split('-').map(Number);
  const curr = new Date(y,m-1,d);
  const mo = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const fmt = dt => `${mo[dt.getMonth()]} ${dt.getDate()}`;
  const iso = dt => `${dt.getFullYear()}-${String(dt.getMonth()+1).padStart(2,'0')}-${String(dt.getDate()).padStart(2,'0')}`;
  const fn  = dt => `morning-briefing-koda-${iso(dt)}.html`;
  const prev = new Date(curr); prev.setDate(prev.getDate()-1);
  const next = new Date(curr); next.setDate(next.getDate()+1);
  document.getElementById('nav-current').textContent = fmt(curr);
  document.getElementById('nav-prev-label').textContent = fmt(prev);
  document.getElementById('nav-next-label').textContent = fmt(next);
  ['nav-prev','nav-next'].forEach((id,i) => {
    const dt = i===0 ? prev : next;
    fetch(fn(dt),{method:'HEAD'})
      .then(r=>{ if(r.ok){ const b=document.getElementById(id); b.href=fn(dt); b.classList.remove('disabled'); }})
      .catch(()=>{});
  });
})();
```

The nav uses `fetch HEAD` to check if adjacent dated files exist in the same folder. Buttons auto-activate for any days that have archived files — no manifest needed.

---

### Hero section

- Date label (JetBrains Mono, blue, uppercase)
- `Koda Intelligence Briefing` heading with gradient text
- KPI strip (4 frosted cards): AI Stories | World Events | Market Mood | Tools Featured

---

### Daily Infographic (NotebookLM AI-generated image)

**If `INFOGRAPHIC_CDN_URL` is available** (generated and uploaded in Step 2C):
```html
<div class="infographic fade-in" style="background:#0a0f1e;border:1px solid rgba(59,130,246,.25);border-radius:20px;overflow:hidden;box-shadow:0 8px 40px rgba(0,0,0,.5);padding:0;">
  <img src="[INFOGRAPHIC_CDN_URL]" alt="Koda Intelligence: State of the World — YYYY-MM-DD" style="width:100%;height:auto;display:block;border-radius:20px;">
</div>
```

**If infographic generation failed**, skip this section entirely (do not show a broken image).

---

### Daily Video Briefing (YouTube embed)

**If `YOUTUBE_VIDEO_ID` is available** (video was generated and uploaded in Steps 2D–2E):

CSS (add to the `<style>` block):
```css
/* ── VIDEO ── */
.video-card {
    padding: 32px;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border-radius: 20px;
    border: 1px solid rgba(99,102,241,0.3);
    text-align: center;
    color: white;
}
.video-card h3 { font-size: 20px; font-weight: 700; margin-bottom: 6px; }
.video-card p { font-size: 13px; opacity: 0.7; margin-bottom: 20px; }
.video-wrapper {
    position: relative;
    width: 100%;
    padding-bottom: 56.25%; /* 16:9 aspect ratio */
    height: 0;
    overflow: hidden;
    border-radius: 12px;
}
.video-wrapper iframe {
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 100%;
    border: 0;
    border-radius: 12px;
}
```

HTML:
```html
<!-- ── DAILY VIDEO BRIEFING ── -->
<section class="section fade-in">
    <h2 class="section-title"><span class="section-icon">&#127909;</span> Daily Video Briefing</h2>
    <div class="video-card">
        <h3>[YOUTUBE_TITLE]</h3>
        <p>Generated by NotebookLM AI</p>
        <div class="video-wrapper">
            <iframe
                src="https://www.youtube.com/embed/[YOUTUBE_VIDEO_ID]"
                title="[YOUTUBE_TITLE]"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                referrerpolicy="strict-origin-when-cross-origin"
                allowfullscreen>
            </iframe>
        </div>
    </div>
</section>
```

**If video generation/upload failed** (`YOUTUBE_VIDEO_ID` is null), **omit this entire section**.
Do not show a broken iframe or placeholder. The digest works perfectly without it.

---

### Daily Podcast card

Dark gradient card (`linear-gradient(135deg,#1a1a2e,#16213e)`), indigo border, white text:
- Header: podcast icon (gradient pill), title = NotebookLM-generated title, meta = date + "Generated by NotebookLM"

**If `PODCAST_URL` is available** (audio was downloaded and saved in Step 2B):
```html
<audio controls style="width:100%;border-radius:10px;margin-top:4px;accent-color:#6366F1;">
  <source src="[PODCAST_URL]" type="audio/mpeg">
  Your browser does not support the audio element.
</audio>
```
Below the player, include a small muted link:
```html
<div style="text-align:center;margin-top:8px;">
  <a href="https://notebooklm.google.com/notebook/f928d89b-2520-4180-a71a-d93a75a5487c"
     target="_blank"
     style="font-size:11px;color:rgba(255,255,255,0.4);text-decoration:none;">
    Also available on NotebookLM ↗
  </a>
</div>
```

**If download failed** (no `PODCAST_URL`), fall back to the link button:
```html
<a href="https://notebooklm.google.com/notebook/f928d89b-2520-4180-a71a-d93a75a5487c"
   target="_blank"
   style="display:flex;align-items:center;justify-content:center;gap:12px;width:100%;
          padding:18px 24px;border-radius:12px;
          background:linear-gradient(135deg,rgba(99,102,241,0.15),rgba(168,85,247,0.15));
          border:1px solid rgba(99,102,241,0.3);color:#a78bfa;font-size:1.1rem;
          font-weight:600;text-decoration:none;transition:all 0.3s ease;cursor:pointer;">
  &#9654; Listen to Today's Podcast on NotebookLM
</a>
```
Also show a green fallback banner with the podcast title, duration, and a "Listen in NotebookLM" link button.

---

### Today's Focus

3 priority items drawn from the biggest AI, world, and market stories of the day. Each item has:
- Numbered gradient circle (blue→purple)
- Bold title
- 2-3 sentence context explaining why it matters today

NOTE: No Schedule Timeline section. This digest is public-facing — no personal calendar data.

---

### AI Developments

2-column card grid (`minmax(340px,1fr)`), 8–12 stories. Each card:
- Category badge (colored pill)
- Bold title
- 3-4 sentence summary with context
- Source link button (`↗ Source Name`)

---

### World News

Same card grid as AI. Category badges: conflict · economy · politics · science · society · tech · space.

---

### Market Snapshot

6-card grid (`minmax(180px,1fr)`): S&P 500, NASDAQ, BTC, ETH, Oil (Brent), Sentiment.
Each card: ticker (JetBrains Mono), large price (color: emerald=up, red=down, amber=flat), change %, 3px fill bar.

---

### Newsletter Intelligence

One full-width card per newsletter read. Structure for each:
- **Header:** gradient avatar (letter initial), newsletter name, subject, date badge
- **Section — Headlines & Launches:** `🚀` emoji bullet, **bold name**: 2–3 sentence explanation with "why it matters"
- **Section — Deep Dives:** same format, deeper analysis
- **Section — Quick Hits:** short 1–2 sentence bullets
- **Section — Trending Tools:** tool name + one-liner
- **Notable Quote:** blockquote styled with purple left-border (`border-left:3px solid var(--purple)`), italic, light purple bg
- Source link back to Gmail thread

This is the most important section to get right — expanded multi-section summaries, never one-liners.

---

### Competitive Landscape

6 cards, 3-column grid. One per major AI player:
`OpenAI | Google DeepMind | Meta AI | Mistral | Anthropic | Challengers (Cursor / Perplexity)`

Each card: emoji logo, company name, colored status badge, 4–5 sentences on latest moves, source link.

---

### AI Tool Guide

6 cards, 2-column grid, `border-left:4px solid var(--indigo)`:

1. **Mindset** — avoiding AI over-reliance (exoskeleton effect)
2. **Build** — agentic workflows without code (Gumloop, n8n, Claude)
3. **Hardware** — on-device AI / DIY projects
4. **Creativity** — generative art / 3D / visual tools
5. **Productivity** — prompt templates / daily planner
6. **Coding** — best current model for coding tasks

Each card: TIP 0X label (JetBrains Mono, indigo), bold title, 3–4 sentence body, source link.

---

### Footer

Generation timestamp (set by JS: `new Date().toLocaleTimeString()`).
Data sources listed: WebSearch, Newsletter feeds, NotebookLM.
Do NOT include: NotebookLM notebook ID, Gmail account details, calendar references,
or any other personal identifiers. This footer is public-facing.

---

## STEP 4 — SAVE TWO FILES

Every run saves both:

1. **Archive:** `[DIGEST_DIR]/morning-briefing-koda-YYYY-MM-DD.html` — permanent, dated
2. **Current:** `[DIGEST_DIR]/morning-briefing-koda.html` — always overwritten with today's

Implementation:
```bash
# Write HTML to morning-briefing-koda.html first, then:
cp [DIGEST_DIR]/morning-briefing-koda.html [DIGEST_DIR]/morning-briefing-koda-YYYY-MM-DD.html
```

The day-nav JS uses `fetch HEAD` on adjacent dated filenames to auto-discover archives — no index file needed.

### HTML Template Requirements for Every Digest

Every generated digest HTML MUST include:

1. **Section IDs** on all content sections for deep-link scrolling:
   - `<section ... id="todays-focus">`
   - `<section ... id="ai-developments">`
   - `<section ... id="world-news">`
   - `<section ... id="market-snapshot">`
   - `<section ... id="newsletter-intelligence">`
   - `<section ... id="competitive-landscape">`
   - `<section ... id="ai-tool-guide">`

2. **scroll-margin-top: 80px** on the `.section` CSS class (accounts for fixed topbar)

3. **Home button** in the topbar nav (blue gradient, links to `./index.html`):
   ```html
   <a href="./index.html" style="text-decoration:none;display:inline-flex;align-items:center;gap:6px;padding:6px 16px;border-radius:10px;background:linear-gradient(135deg,#3B82F6,#6366F1);color:white;font-size:13px;font-weight:700;font-family:'JetBrains Mono',monospace;">&#8592; Home</a>
   ```

4. **Hash deep-link scroll JS** before the closing `</script>` tag:
   ```javascript
   (function(){if(!window.location.hash)return;var id=window.location.hash.substring(1);function go(){var el=document.getElementById(id);if(el)el.scrollIntoView({behavior:'smooth',block:'start'});}if(document.readyState==='complete')setTimeout(go,300);else window.addEventListener('load',function(){setTimeout(go,300);});})();
   ```

5. **Topbar brand** wrapped in `<a href="./index.html">` (not a plain `<div>`)

---

## STEP 4.5 — REBUILD SEARCH INDEX

After saving both HTML files, rebuild the manifest and search index so the landing page has up-to-date archive and search data:

```bash
cd [DIGEST_DIR]
python build-index.py
```

This parses ALL `morning-briefing-koda-YYYY-MM-DD.html` files and generates:
- `manifest.json` — archive metadata (dates, focus topics, KPIs, media indicators)
- `search-index.json` — full-text content for cross-day search

Both files MUST be committed to git alongside the HTML files.

---

## STEP 5 — DEPLOY TO VERCEL (via GitHub)

The Digest folder is a git repo connected to `Saffaboy83/koda-digest` on GitHub,
which auto-deploys to Vercel on every push. The site is live at `www.koda.community`.

Media files (MP3 podcast, JPG infographic) are committed to git and served directly by Vercel.
This ensures mobile browser compatibility — no redirects, proper Content-Type headers.
Video files (MP4) are NOT committed — they are uploaded to YouTube and embedded as iframes.

After saving both HTML files, deploy:

```bash
cd [DIGEST_DIR]
git add morning-briefing-koda.html morning-briefing-koda-*.html \
        podcast-YYYY-MM-DD.mp3 infographic-YYYY-MM-DD.jpg \
        manifest.json search-index.json index.html \
        vercel.json .gitignore
git commit -m "Digest $(date +%Y-%m-%d)"
git push origin main
```

If `git push` fails due to sandbox proxy restrictions (403 from proxy), show the user
a message: "Digest saved locally. Run `./deploy.sh` from your Digest folder to push to Vercel."

Vercel auto-deploys from the `main` branch within ~30 seconds of a push.

---

## STEP 6 — SEND THE DAILY NEWSLETTER EMAIL

After the digest is deployed, automatically generate and send a newsletter email
to the distribution list. This email is a **teaser** — short, punchy, drives traffic
to koda.community. It is NOT a copy of the full digest.

### Distribution list

```
cazmarincowitz@outlook.com
markmarincowitz9@gmail.com
charlene@vanillasky.co.za
Arno_marincowitz@yahoo.co.uk
saffaboyjm@gmail.com
```

### Voice profile

Write in a direct, punchy tone. Clear beats clever. Simple beats fancy.

**Sentence style:**
- Short sentences. Sentence fragments are fine. Third-grade reading level.
- Small words. Big promises. Big proof.
- Kill adverbs. Use better verbs instead ("sprinted" not "quickly ran").
- Use analogies to explain complex things in simple terms.

**Openers and structure:**
- Start with an immediate reward. A bold claim. A contrarian take. A number.
- "Look." / "The reality is," / "Here is the breakdown." are good openers.
- Use imperatives: "Stop relying on...", "Download the...", "Let the AI write your code."
- Direct address: "you", "your business"
- 3-4 paragraphs max for the narrative body. Under 200 words total.

**Formatting rules (CRITICAL):**
- NO em dashes, en dashes, or long hyphens. Use periods, commas, or "and" instead.
- NO fancy Unicode punctuation. Stick to standard ASCII: hyphens (-), periods, commas, colons.
- Write like a plain text email to a friend. No marketing-speak.
- No corporate fluff, no hedging, no "I think." State things as facts.

**Closing:**
- End with an action. Tell the reader to go do something specific.
- Keep it punchy. One sentence. Then the CTA button.

### Email format (HTML)

Send as `contentType: "text/html"`. The email uses a dark theme matching koda.community.

**Subject line:** `Koda Daily Digest — [Short Punchy Topic] — [DD Month YYYY]`

Example: `Koda Daily Digest — Cargo Ships Stuck, AI Ships Code — 22 March 2026`

**HTML template structure:**

```html
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#0a0a0a;font-family:Arial,Helvetica,sans-serif;">
<div style="max-width:600px;margin:0 auto;background:#111111;border-radius:12px;overflow:hidden;border:1px solid #222;">

  <!-- HEADER -->
  <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);padding:32px 24px;text-align:center;">
    <div style="font-size:28px;margin-bottom:8px;">🤖</div>
    <div style="color:#ffffff;font-size:22px;font-weight:800;letter-spacing:-0.5px;">KODA DAILY DIGEST</div>
    <div style="color:#6366F1;font-size:13px;font-weight:600;margin-top:4px;">[Full Date — e.g. Saturday, 22 March 2026]</div>
  </div>

  <!-- QUICK SUMMARY -->
  <div style="padding:20px 24px;border-bottom:1px solid #222;">
    <div style="margin-bottom:8px;">
      <span style="color:#6366F1;font-size:11px;font-weight:700;text-transform:uppercase;">Topic</span>
      <div style="color:#e0e0e0;font-size:14px;margin-top:2px;">[One-line topic]</div>
    </div>
    <div style="margin-bottom:8px;">
      <span style="color:#10B981;font-size:11px;font-weight:700;text-transform:uppercase;">Benefits</span>
      <div style="color:#e0e0e0;font-size:14px;margin-top:2px;">[One-line benefits]</div>
    </div>
    <div>
      <span style="color:#F59E0B;font-size:11px;font-weight:700;text-transform:uppercase;">Tools Mentioned</span>
      <div style="color:#e0e0e0;font-size:14px;margin-top:2px;">[Comma-separated tool names]</div>
    </div>
  </div>

  <!-- NARRATIVE BODY (3-4 paragraphs, Arno's voice) -->
  <div style="padding:24px;color:#d0d0d0;font-size:15px;line-height:1.7;">
    <p style="margin:0 0 16px;">[Paragraph 1 — hook with contrarian framing]</p>
    <p style="margin:0 0 16px;">[Paragraph 2 — key AI development and what it means]</p>
    <p style="margin:0 0 16px;">[Paragraph 3 — world/market context]</p>
    <p style="margin:0;">[Paragraph 4 — action imperative]</p>
  </div>

  <!-- TAKEAWAYS -->
  <div style="padding:0 24px 24px;border-bottom:1px solid #222;">
    <div style="color:#ffffff;font-size:14px;font-weight:800;margin-bottom:12px;text-transform:uppercase;letter-spacing:1px;">
      Koda's Takeaways
    </div>
    <div style="color:#d0d0d0;font-size:14px;line-height:1.6;">
      <div style="margin-bottom:8px;">• <strong style="color:#fff;">[Takeaway 1 title]:</strong> [One sentence]</div>
      <div style="margin-bottom:8px;">• <strong style="color:#fff;">[Takeaway 2 title]:</strong> [One sentence]</div>
      <div>• <strong style="color:#fff;">[Takeaway 3 title]:</strong> [One sentence]</div>
    </div>
  </div>

  <!-- MARKET PULSE -->
  <div style="padding:20px 24px;border-bottom:1px solid #222;">
    <div style="color:#ffffff;font-size:14px;font-weight:800;margin-bottom:12px;text-transform:uppercase;letter-spacing:1px;">
      📊 Market Pulse
    </div>
    <table style="width:100%;color:#d0d0d0;font-size:13px;" cellpadding="4" cellspacing="0">
      <tr>
        <td style="color:#999;">S&P 500</td><td style="color:[#EF4444 or #10B981];font-weight:700;text-align:right;">[value] ([change%])</td>
        <td style="color:#999;padding-left:16px;">BTC</td><td style="color:[color];font-weight:700;text-align:right;">[value] ([change%])</td>
      </tr>
      <tr>
        <td style="color:#999;">NASDAQ</td><td style="color:[color];font-weight:700;text-align:right;">[value] ([change%])</td>
        <td style="color:#999;padding-left:16px;">Oil</td><td style="color:[color];font-weight:700;text-align:right;">[value]</td>
      </tr>
    </table>
  </div>

  <!-- INFOGRAPHIC -->
  <div style="padding:20px 24px;border-bottom:1px solid #222;">
    <img src="https://www.koda.community/infographic-YYYY-MM-DD.jpg"
         alt="Koda Intelligence Infographic"
         style="width:100%;border-radius:8px;display:block;">
  </div>

  <!-- VIDEO — only include this block if YOUTUBE_VIDEO_ID is available. If null, omit entirely. -->
  <div style="padding:20px 24px;border-bottom:1px solid #222;">
    <div style="color:#ffffff;font-size:14px;font-weight:800;margin-bottom:8px;">
      🎬 Today's Video Briefing
    </div>
    <div style="color:#999;font-size:13px;margin-bottom:12px;">
      AI-generated cinematic explainer — watch the visual summary
    </div>
    <a href="https://www.youtube.com/watch?v=[YOUTUBE_VIDEO_ID]"
       target="_blank"
       style="display:inline-block;padding:10px 24px;background:linear-gradient(135deg,#EF4444,#EC4899);
              color:#fff;font-size:13px;font-weight:700;text-decoration:none;border-radius:8px;">
      ▶ Watch on YouTube
    </a>
  </div>

  <!-- PODCAST -->
  <div style="padding:20px 24px;border-bottom:1px solid #222;">
    <div style="color:#ffffff;font-size:14px;font-weight:800;margin-bottom:8px;">
      🎧 Today's Podcast
    </div>
    <div style="color:#999;font-size:13px;margin-bottom:12px;">
      "[Podcast title from NotebookLM]" — [duration estimate]
    </div>
    <a href="https://www.koda.community"
       style="display:inline-block;padding:10px 24px;background:linear-gradient(135deg,#6366F1,#8B5CF6);
              color:#fff;font-size:13px;font-weight:700;text-decoration:none;border-radius:8px;">
      ▶ Listen Now
    </a>
  </div>

  <!-- CTA BUTTON -->
  <div style="padding:32px 24px;text-align:center;">
    <a href="https://www.koda.community"
       style="display:inline-block;padding:16px 48px;background:linear-gradient(135deg,#6366F1,#8B5CF6);
              color:#ffffff;font-size:16px;font-weight:800;text-decoration:none;border-radius:12px;
              letter-spacing:0.5px;">
      READ THE FULL DIGEST →
    </a>
  </div>

  <!-- FOOTER -->
  <div style="padding:16px 24px;background:#0a0a0a;text-align:center;border-top:1px solid #222;">
    <div style="color:#555;font-size:11px;">
      Koda Intelligence · <a href="https://www.koda.community" style="color:#6366F1;text-decoration:none;">koda.community</a>
    </div>
  </div>

</div>
</body>
</html>
```

### Sending the email

After constructing the HTML body from today's digest data:

1. **Create draft** via `gmail_create_draft`:
   - `to`: each address in the distribution list
   - `subject`: the generated subject line
   - `body`: the HTML above with all placeholders filled
   - `contentType`: `"text/html"`

2. **Send the draft via Chrome browser** (there is no `gmail_send_draft` MCP tool):
   ```
   Step 1: tabs_context_mcp(createIfEmpty: true) → get a tab ID
   Step 2: navigate to the draft URL returned by gmail_create_draft
           (https://mail.google.com/mail/u/0/#drafts?compose=[messageId])
   Step 3: Wait 4 seconds for Gmail to load the compose window
   Step 4: find(query: "Send button") → get the ref
   Step 5: click the Send button ref
   Step 6: Wait 2 seconds, verify compose window closed (draft count decreased)
   ```
   The user has granted blanket approval for sending to the distribution list.

3. **If send fails**, log the error and continue. Do not retry or ask.

### .gitignore

Ensure `.gitignore` excludes raw and temporary working files:
```
.DS_Store
*.m4a
*.mp4
podcast-raw.*
video-raw.*
```
MP3 and JPG files ARE committed — Vercel serves them directly for mobile compatibility.
MP4 files are NOT committed — YouTube hosts the video.

---

## SCROLL ANIMATIONS

Apply to all cards at end of `<script>`:
```javascript
const obs = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      e.target.style.opacity='1';
      e.target.style.transform='translateY(0)';
      obs.unobserve(e.target);
    }
  });
}, {threshold:0.06});
document.querySelectorAll('.card,.newsletter-card,.market-card,.comp-card,.tool-card,.focus-item,.infographic,.podcast-card,.video-card').forEach(el => {
  el.style.cssText += 'opacity:0;transform:translateY(16px);transition:opacity 0.45s ease,transform 0.45s ease;';
  obs.observe(el);
});
```

---

## CRITICAL CHECKLIST

- [ ] Every section has at least one clickable source link with `href`
- [ ] `data-digest-date="YYYY-MM-DD"` on `<body>` tag
- [ ] Newsletter Intelligence has multi-section summaries (not one-liners)
- [ ] Both dated archive AND `morning-briefing-koda.html` saved
- [ ] Market cards use color-coded pricing (emerald/red/amber)
- [ ] Podcast MP3 committed to git and served by Vercel (relative path `./podcast-YYYY-MM-DD.mp3`)
- [ ] Infographic JPG committed to git and served by Vercel (relative path `./infographic-YYYY-MM-DD.jpg`)
- [ ] Podcast `<audio src>` uses relative path (NOT GitHub Releases, NOT Google CDN)
- [ ] Infographic `<img src>` uses relative path (NOT GitHub Releases, NOT Google CDN)
- [ ] If audio/infographic/video download failed: graceful fallback (link button / skip section)
- [ ] Video MP4 NOT committed to git (YouTube hosts it, `*.mp4` in `.gitignore`)
- [ ] YouTube video has AI-generated content disclosure checked
- [ ] YouTube description includes "Generated with AI assistance via NotebookLM" disclaimer
- [ ] If video/YouTube failed: video section omitted from HTML (no broken iframe)
- [ ] Video iframe uses 16:9 responsive wrapper (`padding-bottom: 56.25%`)
- [ ] YouTube embed URL uses `/embed/` path (not `/watch?v=`)
- [ ] Email includes "Watch on YouTube" button if video is available
- [ ] Local MP4 cleaned up after YouTube upload
- [ ] NotebookLM uses permanent notebook `f928d89b-...` (do not create new notebooks)
- [ ] Old text sources deleted, old audio/infographic/video artifacts preserved in NotebookLM
- [ ] `*.m4a`, `*.mp4`, `podcast-raw.*`, `video-raw.*` in `.gitignore` — MP3 and JPG ARE committed
- [ ] ALL external links use `target="_blank"` — nothing opens in same tab
- [ ] All data is from today's actual searches — not fabricated
- [ ] Deploy to Vercel attempted (via git push or GitHub API)
- [ ] Newsletter email sent to distribution list (cazmarincowitz@outlook.com)
- [ ] Email uses HTML dark theme, includes infographic from Vercel, video link, podcast link, CTA button
- [ ] Email subject follows format: `Koda Daily Digest — [Topic] — [DD Month YYYY]`
- [ ] Email narrative uses Arno's voice (punchy, direct, short sentences, imperatives)
