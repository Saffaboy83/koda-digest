# Koda Daily AI Digest

## What This Is

A fully automated daily intelligence dashboard at **koda.community** (Vercel).
Covers AI developments, world news, markets, newsletters, competitive landscape,
and AI tools — with a NotebookLM podcast and infographic.

## Architecture

```
Data Sources (parallel)          NotebookLM (sequential)
  - WebSearch x4 (AI, world,      - Permanent notebook: f928d89b-2520-4180-a71a-d93a75a5487c
    markets, competitive)          - Audio: deep_dive podcast (~22 min)
  - Gmail (newsletters ONLY)      - Infographic: landscape, detailed
  - NO calendar, NO personal       - Video: cinematic explainer (TODO)
    email queries
         |                                  |
         v                                  v
   HTML Dashboard                  Chrome Download + ffmpeg
   (12 sections, single file)      (compress m4a -> mp3)
   NO Schedule Timeline            infographic saved as jpg
         |                                  |
         v                                  v
   morning-briefing-koda.html      podcast-YYYY-MM-DD.mp3
   morning-briefing-koda-YYYY-MM-DD.html   infographic-YYYY-MM-DD.jpg
         |                                  |
         +----------------------------------+
         |
         v
   git commit + push -> Vercel auto-deploy (www.koda.community)
         |
         v
   Newsletter email -> cazmarincowitz@outlook.com (auto-send via Chrome)
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
- Today's Focus: derived from TOP NEWS STORIES, not personal calendar/email

## Key Design Decisions

### Media Serving: Vercel-direct (not GitHub Releases)
- GitHub Releases URLs use 302 redirects
- Mobile browsers (iOS Safari, Android Chrome) silently fail on `<audio>` with 302 redirects
- **Solution**: Commit MP3 + JPG to git, Vercel serves directly with proper Content-Type
- Trade-off: ~12MB/day added to repo. Acceptable for now. Consider Vercel Blob Storage long-term.

### NotebookLM: Single Permanent Notebook
- Notebook ID: `f928d89b-2520-4180-a71a-d93a75a5487c`
- Old text sources are deleted daily to keep it clean
- Old audio/infographic artifacts are NEVER deleted (archive value)
- Avoids hitting NotebookLM's notebook count limit

### Audio Download: Chrome Browser MCP
- NotebookLM audio URLs (`lh3.googleusercontent.com`) require authentication
- Cannot use curl/wget — Google CDN rejects unauthenticated requests
- **Solution**: Use Chrome MCP (which has Google session cookies) to click the Download button
- The three-dot menu on each audio artifact has a "Download" option
- Downloaded as .m4a to ~/Downloads, then moved to Digest folder

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
- Distribution list: cazmarincowitz@outlook.com

### All External Links: target="_blank"
- Every `<a href>` in the HTML dashboard opens in a new tab
- Prevents navigation away from the digest

## File Structure

```
C:\Users\arno_\Digest\
  morning-briefing-koda.html          # Always-current (overwritten daily)
  morning-briefing-koda-YYYY-MM-DD.html  # Dated archive (permanent)
  podcast-YYYY-MM-DD.mp3              # Committed to git, served by Vercel
  infographic-YYYY-MM-DD.jpg          # Committed to git, served by Vercel
  vercel.json                         # Vercel config
  .gitignore                          # Excludes only *.m4a and podcast-raw.*
  SKILL-updated.md                    # Source of truth for the skill (673 lines)
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

## TODO — Cinematic Video (Next Session)

NotebookLM can generate cinematic videos via `video_overview_create`. The plan:

### What's ready
- YouTube Data API v3 is **enabled** on project `gen-lang-client-0610910477`
- YouTube scope (`...auth/youtube`) is **configured** in OAuth consent screen
- Existing OAuth client: "GWS CLI" (Desktop type), client ID: `252978099526-8tjvq17odf9m9k39vv1ffe252m0mhkig.apps.googleusercontent.com`
- Client secret exists but is **masked** — may need to create a new one via "+ Add secret"

### Recommended approach: Chrome upload (v1)
Instead of YouTube API (complex OAuth setup), use Chrome MCP to upload:
1. `video_overview_create` in NotebookLM (format: explainer, visual_style: classic/auto_select)
2. Poll `studio_status` until completed
3. Download video via Chrome (same three-dot menu approach as podcast)
4. Navigate to youtube.com/upload in Chrome
5. Upload video file via file input
6. Fill title: "Koda Intelligence Briefing — [Date]"
7. Fill description with digest summary + link to koda.community
8. **Check the AI-generated content disclosure checkbox** (MANDATORY)
9. Add disclaimer: "Generated with AI assistance via NotebookLM"
10. Set visibility (Public or Unlisted)
11. Click Publish
12. Grab YouTube URL, embed as `<iframe>` in HTML dashboard

### YouTube channel
- Channel name: "Koda Intelligence" (to be created)
- User has approved auto-publish (add to skill pre-auth when implementing)
- One video per day — no spam risk

### Legal considerations
- Must label as AI-generated content (YouTube policy)
- Must add description disclaimer
- NotebookLM ToS generally allows using generated outputs
- Facts aren't copyrightable; the video is transformative synthesis
- For scale/monetization, get proper legal advice

### Future: YouTube API (v2)
- More reliable than Chrome UI automation
- Requires: new client secret, Python script with google-api-python-client, OAuth refresh token
- Google Cloud project: `gen-lang-client-0610910477` (Default Gemini Project)
- Migrate when Chrome approach proves too fragile

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
