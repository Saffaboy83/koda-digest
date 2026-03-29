# Koda Daily AI Digest

## Startup Routine

1. Read all files in `context/` if present. This is your foundation.
2. Read `MEMORY.md` in the memory directory. This is what you have learned over time.
3. Use both to shape every task.

## Memory System

When you are corrected or learn something new, update the relevant section in MEMORY.md:

- **Voice** - tone, phrasing, writing corrections
- **Process** - how tasks should be done
- **People** - who people are, relationships
- **Projects** - active work, current tasks, status
- **Output** - formats, naming, delivery preferences
- **Tools** - which tools to use and how

Keep MEMORY.md current. When something changes, update it in place. Replace outdated info, do not just append below it. The file should always reflect the latest state.

## What This Is

A fully automated daily intelligence dashboard at **koda.community** (Vercel).
Covers AI developments, world news, markets, newsletters, competitive landscape,
and AI tools — with a NotebookLM podcast, cinematic video (YouTube), and infographic.

## Architecture

```
Data Sources (parallel)          NotebookLM (sequential + parallel)
  - WebSearch x4 (AI, world,      - Permanent notebook: f928d89b-2520-4180-a71a-d93a75a5487c
    markets, competitive)          - Audio: deep_dive podcast (~22 min)
  - Gmail (newsletters ONLY)      - Infographic: landscape, detailed
  - NO calendar, NO personal       - Video: cinematic explainer → YouTube
    email queries
         |                                  |
         v                                  v
   HTML Dashboard                  Chrome Download + ffmpeg + YouTube API
   (13 sections, single file)      (compress m4a -> mp3, upload mp4 via API)
   NO Schedule Timeline            infographic saved as jpg
         |                                  |
         v                                  v
   morning-briefing-koda.html      podcast-YYYY-MM-DD.mp3
   morning-briefing-koda-YYYY-MM-DD.html   infographic-YYYY-MM-DD.jpg
         |                          YouTube iframe (video)
         +----------------------------------+
         |
         v
   git commit + push -> Vercel auto-deploy (www.koda.community)
         |
         v
   Newsletter email -> 5-person distribution list (auto-send via Chrome)
```

## Depersonalization (IMPORTANT)

This digest is PUBLIC-FACING. Do NOT include any personal data:
- NO "Good Morning, Arno" — use "Koda Intelligence Briefing" instead
- NO Meetings Today / Unread Emails KPIs — use AI Stories / World Events / Market Mood / Tools Featured
- NO Schedule Timeline section
- NO Google Calendar queries
- NO personal email (unread count) queries — only newsletter searches
- NO NotebookLM notebook ID (f928d89b...) in any public-facing HTML or links
- NO direct links to notebooklm.google.com — remove all href links to NotebookLM
- Footer sources: "Web Search, Newsletter feeds, NotebookLM" — no Gmail, no Calendar
- NO YouTube video titles containing personal identifiers
- NO political figures in any media (video, infographic, images). No faces of presidents, prime ministers, generals, or named political leaders. Use abstract representations: empty podiums, building exteriors, flags, hardware, documents.
- Today's Focus: derived from TOP NEWS STORIES, not personal calendar/email

## Key Design Decisions

### Landing Page & Search (index.html)
- `index.html` serves as the site landing page at `/`
- Centered hero: CSS animated gradient orbs, search bar, CTAs, stats
- Prominent search bar in hero for cross-day full-text search (all sections indexed)
- Archive grid below shows all historical digests from `manifest.json`
- `build-index.py` (Python stdlib only) generates `manifest.json` + `search-index.json`
- **MUST run `python build-index.py` after each daily digest** to update the index
- Search index covers: Daily Summary, Focus, AI Developments, World News, Markets, Newsletters, Competitive, Tools
- Search results deep-link to specific sections (e.g., `briefing.html#ai-developments`)
- `/today` route redirects to `morning-briefing-koda.html`
- Dark mode toggle shares `koda-theme` localStorage key with digest pages

### Section IDs & Deep-Linking
- Every digest section MUST have an `id` attribute for search deep-linking:
  `daily-summary`, `todays-focus`, `ai-developments`, `world-news`, `market-snapshot`,
  `newsletter-intelligence`, `competitive-landscape`, `ai-tool-guide`
- Sections need `scroll-margin-top: 80px` in CSS to offset the fixed topbar
- Each digest includes JS that reads `location.hash` and scrolls to the target after page load

### Home Navigation
- Every digest topbar includes a blue gradient "← Home" button linking to `./index.html`
- The topbar brand ("Koda Digest") is also a clickable link to `./index.html`
- All internal navigation (landing page ↔ briefings) stays in the same tab (no target="_blank")

### Media Serving: Supabase Storage
- Podcast MP3s and infographic JPGs served from Supabase Storage bucket `koda-media`
- Public URL pattern: `https://lfwymyfaeihoglmlvbaj.supabase.co/storage/v1/object/public/koda-media/{filename}`
- Direct URLs, no redirects, proper Content-Type headers (audio/mpeg, image/jpeg)
- Mobile browsers (iOS Safari, Android Chrome) work correctly
- Upload via `supabase_upload.py` using service_role key
- Env vars required: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
- MP3/JPG files are gitignored -- no longer committed to the repo
- Older digests (pre-2026-03-28) still use relative paths served by Vercel (files remain in git history)
- Migration path to Cloudflare R2 if needed: swap URL prefix (same S3-compatible API)

### NotebookLM: Single Permanent Notebook
- Notebook ID: `f928d89b-2520-4180-a71a-d93a75a5487c`
- Old text sources are deleted daily to keep it clean
- Old audio/infographic/video artifacts are NEVER deleted (archive value)
- Avoids hitting NotebookLM's notebook count limit

### Media Generation: notebooklm-py API (Primary)
- **Primary method**: `notebooklm_media.py` uses the unofficial `notebooklm-py` Python wrapper
- Handles source management, audio/infographic/video generation, and download — all via API
- No Chrome browser needed for normal operation
- Auth via Google cookies stored at `~/.notebooklm/storage_state.json`
- Cookies last days-to-weeks; when expired, re-run `python notebooklm_login.py`
- Usage: `PYTHONUTF8=1 python notebooklm_media.py --text-file news.txt --date YYYY-MM-DD`
- Infographic quality: pass `--infographic-focus "..."` with a dynamic prompt built from the day's top 4 stories (see SKILL for template). The default prompt requests a dark premium 2x2 grid with Koda branding. Custom prompts override the default.
- Source text should be structured with `## SECTION` headers and `**Headline** -- key stat` format for best infographic output
- Outputs: `podcast-YYYY-MM-DD.mp3`, `infographic-YYYY-MM-DD.jpg`, `video-YYYY-MM-DD.mp4`
- Status written to `media-status.json` after each run

### Media Generation: Chrome MCP (Fallback)
- If `notebooklm-py` auth expires mid-run or API breaks, fall back to Chrome MCP
- The script prints clear instructions for which steps need Chrome-based manual generation
- Chrome MCP uses Google session cookies to click Download buttons in NotebookLM UI
- This is the legacy approach — only use when the API fails

### Cookie Re-authentication
- Run `python notebooklm_login.py` — opens Edge, captures Google cookies automatically
- No interactive terminal needed (unlike `notebooklm login` CLI)
- Verify with: `PYTHONUTF8=1 notebooklm auth check --test`

### Video Serving: YouTube (not Vercel)
- Videos are typically 20-50MB — too large to commit to git daily
- YouTube provides free hosting, CDN, and adaptive bitrate streaming
- Embedded as `<iframe>` in the HTML dashboard — no local file needed after upload
- Trade-off: YouTube dependency. If YouTube is down, video section is simply skipped.
- AI-generated content disclosure is MANDATORY on every upload (YouTube policy)

### YouTube Upload: YouTube Data API v3
- Fully automated via `youtube_upload.py` in the Digest folder
- Uses OAuth 2.0 Desktop client ("GWS CLI") from Google Cloud project `gen-lang-client-0610910477`
- Token stored at `Digest/.youtube_token.json` (auto-refreshes)
- Client secret at `Digest/client_secret.json` (gitignored)
- First run opens browser for consent; all subsequent runs are headless
- YouTube channel: "Koda"
- Titles are hook-based and theme-driven (not generic)

### ffmpeg Path (Windows)
```
$HOME/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-8.1-full_build/bin/ffmpeg.exe
```
Compresses ~42MB m4a to ~11MB mp3 (64kbps mono, 22050Hz). Voice audio doesn't need high bitrate.

### GitHub CLI Path (Windows)
```
/c/Program Files/GitHub CLI/gh.exe
```
Authenticated as Saffaboy83. Used for creating releases (legacy) and general GitHub operations.

### Newsletter Email: Gmail API (automated in pipeline)
- Step 07 sends via Gmail API with OAuth token (no Chrome needed)
- Premium dark-mode HTML email matching the site's design system
- Distribution list: cazmarincowitz@outlook.com, markmarincowitz9@gmail.com, charlene@vanillasky.co.za, Arno_marincowitz@yahoo.co.uk, saffaboyjm@gmail.com

### Email Signup: Beehiiv
- Publication: koda.beehiiv.com (slug: "koda")
- Embed forms use a Vercel serverless function (`/api/subscribe`) that proxies to Beehiiv API
- Keeps the custom inline form design (no Beehiiv iframe)
- Env vars: `BEEHIIV_API_KEY`, `BEEHIIV_PUBLICATION_ID`
- Forms in: `index.html` (3 locations), `templates/briefing.html` (1 location)

### All External Links: target="_blank"
- Every `<a href>` in the HTML dashboard opens in a new tab
- Prevents navigation away from the digest

## File Structure

```
C:\Users\arno_\Digest\
  index.html                          # Landing page (hero, search, archive)
  morning-briefing-koda.html          # Always-current (overwritten daily)
  morning-briefing-koda-YYYY-MM-DD.html  # Dated archive (permanent)
  manifest.json                       # Archive metadata (auto-generated by build-index.py)
  search-index.json                   # Search content (auto-generated by build-index.py)
  build-index.py                      # Generates manifest.json + search-index.json
  podcast-YYYY-MM-DD.mp3              # Committed to git, served by Vercel
  infographic-YYYY-MM-DD.jpg          # Committed to git, served by Vercel
  video-YYYY-MM-DD.mp4                # TEMPORARY — uploaded to YouTube then deleted
  notebooklm_media.py                 # NotebookLM API media generator (primary)
  notebooklm_login.py                 # Cookie capture for notebooklm-py auth
  extract_cookies.py                  # Alt cookie extraction from Edge (requires admin)
  youtube_upload.py                   # YouTube Data API upload script (automated)
  client_secret.json                  # OAuth client secret (gitignored)
  .youtube_token.json                 # OAuth refresh token (gitignored)
  vercel.json                         # Vercel config
  .gitignore                          # Excludes *.m4a, *.mp4, client_secret.json, .youtube_token.json
  SKILL-updated.md                    # Source of truth for the skill
  CLAUDE.md                           # This file
```

## Skill Location

- **Source of truth**: `C:\Users\arno_\Digest\SKILL-updated.md`
- **Installed in Cowork**: `AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\b846f492-...\skills\koda-morning-digest\SKILL.md`
- **Packaged**: `C:\Users\arno_\OneDrive\Desktop\Claude Skills\koda-morning-digest.skill`

All three must be kept in sync. After editing SKILL-updated.md, copy to the Cowork path
and repackage the .skill file.

## Deployment

- **Repo**: github.com/Saffaboy83/koda-digest (main branch)
- **Hosting**: Vercel auto-deploy on push
- **Domain**: www.koda.community
- **Day navigation**: JS uses `fetch HEAD` to check if adjacent dated files exist — no manifest needed

## Design System

- **Fonts**: Inter (300-800) + JetBrains Mono (400-700) via Google Fonts
- **Default**: Light mode with dark mode toggle (persisted in localStorage as `koda-theme`)
- **Cards**: `backdrop-filter:blur(12px)`, `border:1px solid var(--border)`, `border-radius:16-20px`
- **Colors**: `--blue:#3B82F6 --purple:#8B5CF6 --red:#EF4444 --amber:#F59E0B --emerald:#10B981 --indigo:#6366F1 --pink:#EC4899 --cyan:#06B6D4`
- **Animations**: IntersectionObserver fade-in (opacity 0->1, translateY 16px->0)
- **Self-contained**: All CSS/JS inline, only external dep is Google Fonts

## Troubleshooting

### Audio doesn't play on mobile
- Check the `<audio src>` uses a relative path (`./podcast-YYYY-MM-DD.mp3`), NOT a GitHub Releases URL
- Verify the MP3 is committed to git and deployed to Vercel
- Test: `curl -I https://www.koda.community/podcast-YYYY-MM-DD.mp3` should return `Content-Type: audio/mpeg`

### notebooklm-py auth expired
- Symptom: `notebooklm_media.py` exits with code 2 and prints "AUTH EXPIRED"
- Fix: Run `python notebooklm_login.py` (opens Edge, captures cookies automatically)
- Verify: `PYTHONUTF8=1 notebooklm auth check --test`
- Cookies typically last days to weeks before needing refresh

### notebooklm-py API breaks (method IDs changed)
- Symptom: `RPCError` or `UnknownRPCMethodError` during generation
- Fix: Update the library: `pip install --upgrade notebooklm-py`
- If still broken: fall back to Chrome MCP (the script prints instructions)

### Chrome download fails (legacy fallback)
- The skill has graceful degradation — if download fails, HTML shows a "Listen in NotebookLM" link button instead
- Common cause: NotebookLM page hasn't finished loading. Increase wait time in Step 2B.

### git push fails
- May fail due to sandbox proxy restrictions (403)
- Manual fallback: run `git push origin main` from the Digest folder

### Email send fails
- Draft is still created in Gmail — can be sent manually
- Common cause: Gmail compose window didn't load. Increase wait time in Step 6.

### Video doesn't appear in digest
- Check if `video_overview_create` completed in NotebookLM (poll `studio_status`)
- Check Chrome download succeeded (look in ~/Downloads for .mp4 files)
- Check YouTube upload succeeded (navigate to YouTube Studio to verify)
- If any step failed, the skill degrades gracefully — no video section is shown
- Common cause: NotebookLM video generation timeout (>8 minutes). Try again next day.

### YouTube upload fails
- Check `youtube_upload.py` output for errors
- If token expired, delete `.youtube_token.json` and re-run (will open browser for re-auth)
- If `client_secret.json` missing, download from Google Cloud Console (project `gen-lang-client-0610910477`, OAuth client "GWS CLI")
- Verify the "Koda" channel exists and is in good standing
- The skill has graceful degradation — HTML omits video section, digest is otherwise complete

## Video Briefing

- Generated daily as **cinematic** (Veo 3) via `generate_cinematic_video()` in notebooklm-py
- IMPORTANT: Must use `generate_cinematic_video()` method, NOT `generate_video()` with `VideoFormat.CINEMATIC` -- different parameter structure (no style arg). The MCP `video_overview_create` tool does NOT support cinematic -- must use Python.
- Two sources drive video quality: (1) the news text, (2) a dedicated **Visual Production Script** source added to the notebook with scene-by-scene descriptions, camera directions, color grades, and transitions
- Cinematic videos take **30-45 minutes** to render via Veo 3 (vs ~8 min for explainers). Railway timeout must accommodate this.
- Falls back to explainer format via MCP tool if cinematic generation fails
- Downloaded from NotebookLM via Chrome (three-dot menu, same as audio/infographic)
- Uploaded to YouTube via `youtube_upload.py` (Data API v3, fully headless)
- YouTube titles are hook-based and theme-driven from the day's news (not generic)
- Embedded in HTML dashboard as responsive YouTube iframe (16:9)
- YouTube channel: "Koda"
- If any step fails, video section is silently omitted (graceful degradation)

### Legal considerations
- Must label as AI-generated content (YouTube policy) — checkbox checked during upload
- Description includes disclaimer: "Generated with AI assistance via NotebookLM"
- NotebookLM ToS generally allows using generated outputs
- Facts aren't copyrightable; the video is transformative synthesis
- For scale/monetization, get proper legal advice

### YouTube API: Setup Details
- Script: `Digest/youtube_upload.py`
- OAuth client: "GWS CLI" (Desktop), Client ID `252978099526-8tjvq17odf9m9k39vv1ffe252m0mhkig`
- Scopes: `youtube.upload`
- Token auto-refreshes; if token is deleted, re-run the script and authorize in browser
- Dependencies: `google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2`

## Skill Sync Procedure

After any edit to `SKILL-updated.md`:
```bash
# 1. Copy to Cowork installed location
cp ~/Digest/SKILL-updated.md "C:/Users/arno_/AppData/Roaming/Claude/local-agent-mode-sessions/skills-plugin/b846f492-f03f-43b1-ab51-3ff8a49cd0c7/5efa7340-df2f-45df-b5e9-3c18a77aaf47/skills/koda-morning-digest/SKILL.md"

# 2. Repackage .skill file
cp ~/Digest/SKILL-updated.md /tmp/koda-morning-digest/SKILL.md
powershell.exe -Command "Remove-Item '...koda-morning-digest.skill' -Force; Compress-Archive -Path '...\koda-morning-digest\*' -DestinationPath '...koda-morning-digest.zip' -Force; Rename-Item '...zip' 'koda-morning-digest.skill' -Force"

# 3. Verify
diff ~/Digest/SKILL-updated.md [Cowork installed path]
```
