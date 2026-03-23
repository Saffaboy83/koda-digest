# Koda Daily AI Digest

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
- Today's Focus: derived from TOP NEWS STORIES, not personal calendar/email

## Key Design Decisions

### Landing Page & Search (index.html)
- `index.html` serves as the site landing page at `/`
- Centered hero: CSS animated gradient orbs, search bar, CTAs, stats
- Prominent search bar in hero for cross-day full-text search (all sections indexed)
- Archive grid below shows all historical digests from `manifest.json`
- `build-index.py` (Python stdlib only) generates `manifest.json` + `search-index.json`
- **MUST run `python build-index.py` after each daily digest** to update the index
- Search index covers: Focus, AI Developments, World News, Markets, Newsletters, Competitive, Tools
- Search results deep-link to specific sections (e.g., `briefing.html#ai-developments`)
- `/today` route redirects to `morning-briefing-koda.html`
- Dark mode toggle shares `koda-theme` localStorage key with digest pages

### Section IDs & Deep-Linking
- Every digest section MUST have an `id` attribute for search deep-linking:
  `todays-focus`, `ai-developments`, `world-news`, `market-snapshot`,
  `newsletter-intelligence`, `competitive-landscape`, `ai-tool-guide`
- Sections need `scroll-margin-top: 80px` in CSS to offset the fixed topbar
- Each digest includes JS that reads `location.hash` and scrolls to the target after page load

### Home Navigation
- Every digest topbar includes a blue gradient "← Home" button linking to `./index.html`
- The topbar brand ("Koda Digest") is also a clickable link to `./index.html`
- All internal navigation (landing page ↔ briefings) stays in the same tab (no target="_blank")

### Media Serving: Vercel-direct (not GitHub Releases)
- GitHub Releases URLs use 302 redirects
- Mobile browsers (iOS Safari, Android Chrome) silently fail on `<audio>` with 302 redirects
- **Solution**: Commit MP3 + JPG to git, Vercel serves directly with proper Content-Type
- Trade-off: ~12MB/day added to repo. Acceptable for now. Consider Vercel Blob Storage long-term.

### NotebookLM: Single Permanent Notebook
- Notebook ID: `f928d89b-2520-4180-a71a-d93a75a5487c`
- Old text sources are deleted daily to keep it clean
- Old audio/infographic/video artifacts are NEVER deleted (archive value)
- Avoids hitting NotebookLM's notebook count limit

### Audio Download: Chrome Browser MCP
- NotebookLM audio URLs (`lh3.googleusercontent.com`) require authentication
- Cannot use curl/wget — Google CDN rejects unauthenticated requests
- **Solution**: Use Chrome MCP (which has Google session cookies) to click the Download button
- The three-dot menu on each audio artifact has a "Download" option
- Downloaded as .m4a to ~/Downloads, then moved to Digest folder

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

### Newsletter Email: Auto-send via Chrome
- No `gmail_send_draft` MCP tool exists
- **Workaround**: Create draft via `gmail_create_draft`, then navigate to Gmail in Chrome and click Send
- Voice profile: Punchy, direct, Hormozi-style ("Look.", "The reality is,", imperatives)
- Distribution list: cazmarincowitz@outlook.com, markmarincowitz9@gmail.com, charlene@vanillasky.co.za, Arno_marincowitz@yahoo.co.uk, saffaboyjm@gmail.com

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

### Chrome download fails
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

- Generated daily via `video_overview_create` (format: explainer, visual_style: auto_select)
- Kicked off in Step 2A alongside audio, cooks in background during Steps 2B-2C
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
