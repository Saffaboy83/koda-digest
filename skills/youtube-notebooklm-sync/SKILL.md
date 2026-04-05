---
name: youtube-notebooklm-sync
description: Sync recent YouTube videos from a channel into a NotebookLM notebook. Uses YouTube RSS feeds (via Firecrawl) to discover new videos and adds them as sources.
triggers:
  - sync youtube
  - update notebook
  - youtube notebooklm
  - new videos
  - youtube sync
arguments:
  - name: channel
    description: "YouTube channel ID, handle (@AlexHormozi), or alias (alexhormozi)"
    required: true
  - name: notebook
    description: "NotebookLM notebook name or ID"
    required: true
  - name: since
    description: "Only add videos published after this date (YYYY-MM-DD). Default: 14 days ago"
    required: false
---

# YouTube -> NotebookLM Sync

Discovers new YouTube videos from a channel and adds them to a NotebookLM notebook.

## Architecture

```
YouTube RSS Feed (via Firecrawl)
        |
        v
  Parse XML -> Extract video IDs, titles, dates
        |
        v
  NotebookLM notebook_get -> Get existing source titles
        |
        v
  Diff: find videos NOT already in notebook
        |
        v
  notebook_add_url for each new video
        |
        v
  Summary: X videos added, notebook now has Y sources
```

## Known Channel IDs (verified 2026-04-05)

| Alias | Channel | Channel ID | Handle |
|-------|---------|------------|--------|
| alexhormozi | Alex Hormozi | UCUyDOdBWhC1MCxEjC46d-zw | @AlexHormozi |
| gregisenberg | Greg Isenberg | UCPjNBjflYl0-HQtUvOx0Ibw | @GregIsenberg |
| jackroberts | Jack Roberts | UCxVxcTULO9cFU6SB9qVaisQ | @Itssssss_Jack |
| pauljlipsky | Paul J Lipsky | UCmeU2DYiVy80wMBGZzEWnbw | @PaulJLipsky |
| danmartell | Dan Martell | UCA-mWX9CvCTVFWRMb9bKc9w | @danmartell |
| sabrina | Sabrina Ramonov | UCiGWNa6QK6CiKPvv5-YPv8g | @sabrina_ramonov |
| themitmonk | theMITmonk | UC4ZVkG3RQPzvZk7alIVjcCg | @theMITmonk |

## Known Notebooks (updated 2026-04-05)

| Name | Notebook ID | Sources |
|------|-------------|---------|
| Alex Hormozi | 816f2ab1-24ce-451a-ab3f-c0ea443262db | 305+ |
| Greg Isenberg | d3200f9f-89c0-497f-a528-b3257c068a3e | 304 |
| Jack Roberts | 4a42e6e8-49fa-434e-ba7a-9f3a974dae7f | 106 |
| Paul J Lipsky | b5378ff0-5df5-4edb-8ebe-c9c7fa425131 | 311 |
| Dan Martell | 4ec27c46-1097-48b0-a782-e2bd2389936b | 301 |
| Sabrina Ramonov | 59016dfa-e84a-4fa9-aa32-7a9ba8e3dddd | 200 |
| theMITmonk | 56b3a441-a655-4c26-8f54-01db68a5cf57 | 52 |

## Scheduled Task

- **Task ID**: `youtube-notebooklm-sync`
- **Schedule**: Tuesdays and Fridays at 9:43 AM local time
- **Cron**: `43 9 * * 2,5`

## Steps

### Step 1: Resolve channel ID

If the user provides a handle (e.g. `@AlexHormozi`) or alias, resolve it to a channel ID using the table above. If unknown, search YouTube to find the channel ID.

### Step 2: Fetch RSS feed via Firecrawl

Use `firecrawl_scrape` to fetch the RSS feed:

```
URL: https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}
Format: markdown (returns raw XML as text)
```

The RSS feed returns the **15 most recent videos** with:
- `<yt:videoId>` - the video ID
- `<title>` - video title
- `<published>` - exact ISO 8601 publish date

### Step 3: Parse RSS and extract videos

Save the RSS XML to a temp file, then run:

```bash
PYTHONUTF8=1 python ~/Digest/youtube_rss_sync.py parse --xml-file /tmp/rss.xml --since YYYY-MM-DD
```

This outputs JSON:
```json
[
  {"video_id": "abc123", "title": "Video Title", "published": "2026-04-01", "url": "https://..."}
]
```

If the `--since` flag is omitted, all 15 videos are returned.

### Step 4: Check existing notebook sources

Use `notebook_get` with the notebook ID to retrieve current sources. Extract source titles and URLs. Compare against the parsed video list to find new videos.

Alternatively, use the `diff` command:
```bash
PYTHONUTF8=1 python ~/Digest/youtube_rss_sync.py diff --xml-file /tmp/rss.xml --known-file /tmp/sources.json --since YYYY-MM-DD
```

Where `sources.json` is a JSON array of `{"title": "...", "url": "..."}` from the notebook.

### Step 5: Add new videos

For each new video, call `notebook_add_url`:
- notebook_id: the target notebook
- url: `https://www.youtube.com/watch?v={video_id}`

Add videos in parallel (up to 5 at a time) for speed.

### Step 6: Report results

Print a summary:
```
YouTube -> NotebookLM Sync Complete
Channel: Alex Hormozi (@AlexHormozi)
Notebook: Alex Hormozi (816f2ab1-...)
Period: Since 2026-03-22

Added 5 new videos:
  1. [2026-04-04] My Most Useful Advice For Anyone
  2. [2026-04-03] Helping 4 Educational Business Owners Scale in 25 Minutes
  3. [2026-04-01] How to Win With AI in 2026
  4. [2026-03-27] Helping E-Commerce Business Owners Scale
  5. [2026-03-24] How to Get Your Customers to Stay FOREVER

Notebook now has 304 sources.
```

## Shorts Filtering

The RSS feed includes both long-form videos AND Shorts. To filter:
- **RSS clue**: Shorts have `<link rel="alternate" href="https://www.youtube.com/shorts/..."/>` in their entry
- **Chrome Videos tab**: Only shows long-form videos (not Shorts)
- **Default behavior**: Only add long-form videos unless the user requests Shorts too
- The `youtube_rss_sync.py` parser does NOT filter Shorts -- do it manually by checking the alternate link, or cross-reference with the Chrome Videos tab

To detect Shorts from the raw XML, check if the entry's alternate link contains `/shorts/`.

## Limits & Notes

- YouTube RSS feeds return only the **15 most recent videos** (including Shorts). For deeper history or filtering by type, use the Chrome Videos tab or YouTube Data API v3.
- NotebookLM has a **300 source limit** per notebook. Check before adding.
- If a notebook is at 300 sources and new videos need adding, warn the user -- they may need to remove old sources first.
- The RSS feed updates within minutes of a new upload.
- No authentication is needed for RSS feeds (public data).
- Firecrawl is used to fetch RSS because direct HTTP from this machine may be blocked by YouTube.
- For channels that post many Shorts (like Hormozi: ~3 Shorts/day), the RSS 15-video window may only cover 3-4 days. Run syncs at least weekly to avoid missing long-form videos.

## Scheduling

This skill can be scheduled to run weekly:
```
/schedule weekly "Sync Alex Hormozi YouTube to NotebookLM"
```

Or run on-demand:
```
/youtube-notebooklm-sync alexhormozi "Alex Hormozi" --since 2026-03-22
```
