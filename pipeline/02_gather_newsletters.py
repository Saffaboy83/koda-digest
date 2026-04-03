"""
Step 02: Gather newsletter content from Gmail.

Uses Gmail API directly to search and read newsletters.
Falls back to existing data or an empty placeholder if credentials are unavailable.

Input:  None (or --date flag)
Output: pipeline/data/newsletters.json
"""

import argparse
import base64
import json
import re
import sys
import os
from datetime import datetime

import httpx
from collections import Counter
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import DIGEST_DIR, FIRECRAWL_API_KEY, today_str, write_json, read_json

FIRECRAWL_API_URL = "https://api.firecrawl.dev/v1"

# ── Gmail Config ─────────────────────────────────────────────────────────────

GMAIL_TOKEN_PATH = DIGEST_DIR / ".gmail_token.json"
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]

SEARCH_QUERY = (
    "in:inbox ("
    "from:tldr OR from:superhuman OR from:therundown "
    "OR from:buildfastwithai OR from:bensbites OR from:morningbrew"
    ") newer_than:2d"
)

MAX_NEWSLETTERS = 6

# Known sender display names
SENDER_NAMES = {
    "tldr": "TLDR",
    "tldrai": "TLDR AI",
    "superhuman": "Superhuman",
    "therundown": "The Rundown AI",
    "buildfastwithai": "Build Fast with AI",
    "bensbites": "Ben's Bites",
    "morningbrew": "Morning Brew",
}

SENDER_LINKS = {
    "tldr": "https://tldr.tech",
    "tldrai": "https://tldr.tech/ai",
    "superhuman": "https://www.joinsuperhuman.ai",
    "therundown": "https://www.therundown.ai",
    "buildfastwithai": "https://www.buildfastwithai.com",
    "bensbites": "https://bensbites.beehiiv.com",
    "morningbrew": "https://www.morningbrew.com",
}


def get_gmail_service():
    """Build Gmail API service using stored credentials."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        print("  WARNING: google-auth packages not installed")
        return None

    if not GMAIL_TOKEN_PATH.exists():
        # Try reusing YouTube token's client credentials
        yt_token_path = DIGEST_DIR / ".youtube_token.json"
        if yt_token_path.exists():
            with open(yt_token_path, "r") as f:
                yt_data = json.load(f)
            # Create a Gmail token with the same client but gmail.readonly scope
            client_id = yt_data.get("client_id", "")
            client_secret = yt_data.get("client_secret", "")
            refresh_token = yt_data.get("refresh_token", "")
            if client_id and refresh_token:
                creds = Credentials(
                    token=None,
                    refresh_token=refresh_token,
                    client_id=client_id,
                    client_secret=client_secret,
                    token_uri="https://oauth2.googleapis.com/token",
                    scopes=GMAIL_SCOPES,
                )
                try:
                    creds.refresh(Request())
                    with open(GMAIL_TOKEN_PATH, "w") as f:
                        f.write(creds.to_json())
                    return build("gmail", "v1", credentials=creds)
                except Exception as e:
                    print(f"  WARNING: Could not create Gmail token from YouTube creds: {e}")
        print("  WARNING: No Gmail credentials available")
        return None

    creds = Credentials.from_authorized_user_file(str(GMAIL_TOKEN_PATH), GMAIL_SCOPES)

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(GMAIL_TOKEN_PATH, "w") as f:
                f.write(creds.to_json())
        except Exception as e:
            print(f"  WARNING: Token refresh failed: {e}")
            return None

    if not creds.valid:
        print("  WARNING: Gmail credentials invalid")
        return None

    return build("gmail", "v1", credentials=creds)


def extract_sender_key(from_header):
    """Extract a normalized sender key from the From header."""
    addr = from_header.lower()
    for key in SENDER_NAMES:
        if key in addr:
            return key
    # Try domain extraction
    match = re.search(r'@([^>.\s]+)', addr)
    if match:
        return match.group(1)
    return "unknown"


def get_message_text(payload):
    """Recursively extract plain text from a Gmail message payload."""
    parts = payload.get("parts", [])
    if not parts:
        data = payload.get("body", {}).get("data", "")
        if data and payload.get("mimeType", "").startswith("text/"):
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        return ""

    text = ""
    for part in parts:
        mime = part.get("mimeType", "")
        if mime == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                text += base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        elif mime.startswith("multipart/"):
            text += get_message_text(part)
    return text


def fetch_newsletters(service, date):
    """Search Gmail and read newsletter content."""
    print(f"  Searching Gmail: {SEARCH_QUERY}")
    results = service.users().messages().list(
        userId="me", q=SEARCH_QUERY, maxResults=MAX_NEWSLETTERS
    ).execute()

    messages = results.get("messages", [])
    if not messages:
        print("  No newsletters found")
        return []

    print(f"  Found {len(messages)} messages, reading top {min(len(messages), MAX_NEWSLETTERS)}")

    newsletters = []
    for msg_ref in messages[:MAX_NEWSLETTERS]:
        try:
            msg = service.users().messages().get(
                userId="me", id=msg_ref["id"], format="full"
            ).execute()

            headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
            from_header = headers.get("from", "")
            subject = headers.get("subject", "")
            msg_date = headers.get("date", "")

            sender_key = extract_sender_key(from_header)
            sender_name = SENDER_NAMES.get(sender_key, sender_key.title())
            source_link = SENDER_LINKS.get(sender_key, "")

            content = get_message_text(msg.get("payload", {}))
            # Truncate very long newsletters to avoid token bloat in synthesis
            if len(content) > 8000:
                content = content[:8000] + "\n\n[Truncated]"

            newsletters.append({
                "sender": sender_name,
                "subject": subject,
                "date": msg_date,
                "content": content,
                "source_link": source_link,
            })
            print(f"    Read: {sender_name} - {subject[:60]}")

        except Exception as e:
            print(f"    WARNING: Failed to read message {msg_ref['id']}: {e}")

    return newsletters


# ── URL Cross-Referencing ───────────────────────────────────────────────────

SKIP_DOMAINS = {
    "google.com", "gmail.com", "youtube.com", "twitter.com", "x.com",
    "facebook.com", "instagram.com", "linkedin.com", "reddit.com",
    "beehiiv.com", "substack.com", "mailchimp.com", "convertkit.com",
    "list-manage.com", "email.mg", "eepurl.com", "t.co",
    "unsplash.com", "giphy.com", "bit.ly", "tinyurl.com",
}


def extract_urls_from_text(text: str) -> list[str]:
    """Extract HTTP/HTTPS URLs from plain text, filtering noise."""
    raw_urls = re.findall(r'https?://[^\s<>"\')\]]+', text)
    clean: list[str] = []
    seen: set[str] = set()
    for url in raw_urls:
        url = url.rstrip(".,;:!?")
        domain = urlparse(url).netloc.lower().replace("www.", "")
        if domain in SKIP_DOMAINS:
            continue
        path = urlparse(url).path.strip("/")
        if not path or len(path) < 3:
            continue
        if url in seen:
            continue
        seen.add(url)
        clean.append(url)
    return clean


def cross_reference_urls(newsletters: list[dict], max_scrape: int = 8) -> dict:
    """Extract URLs from all newsletters, count cross-references, scrape top ones.

    Returns dict with:
      - url_counts: {url: count} for URLs appearing in 2+ newsletters
      - scraped: [{url, text, mentioned_in, mention_count}] for top URLs
    """
    url_sources: dict[str, list[str]] = {}
    for nl in newsletters:
        sender = nl.get("sender", "Unknown")
        content = nl.get("content", "")
        urls = extract_urls_from_text(content)
        for url in urls:
            url_sources.setdefault(url, []).append(sender)

    # Find URLs mentioned by 2+ different newsletters
    multi_mention = {
        url: sources for url, sources in url_sources.items()
        if len(set(sources)) >= 2
    }

    if not multi_mention:
        # Fall back to most-mentioned URLs across all newsletters
        all_counts = {url: len(sources) for url, sources in url_sources.items()}
        top_urls = sorted(all_counts.items(), key=lambda x: -x[1])[:max_scrape]
    else:
        top_urls = sorted(multi_mention.items(), key=lambda x: -len(set(x[1])))[:max_scrape]

    print(f"    URLs found: {len(url_sources)} total, {len(multi_mention)} cross-referenced")

    # Scrape top URLs for content
    scraped: list[dict] = []
    if FIRECRAWL_API_KEY and top_urls:
        print(f"    Scraping top {min(len(top_urls), max_scrape)} cross-referenced URLs...")
        headers = {
            "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
            "Content-Type": "application/json",
        }
        for url, sources in top_urls:
            if isinstance(sources, list):
                mention_count = len(set(sources))
                mentioned_in = list(set(sources))
            else:
                mention_count = sources
                mentioned_in = url_sources.get(url, [])

            try:
                resp = httpx.post(
                    f"{FIRECRAWL_API_URL}/scrape",
                    json={"url": url, "formats": ["markdown"], "onlyMainContent": True, "timeout": 15000},
                    headers=headers,
                    timeout=20,
                )
                resp.raise_for_status()
                md = resp.json().get("data", {}).get("markdown", "")
                if md and len(md) > 200:
                    scraped.append({
                        "url": url,
                        "text": md[:3000],
                        "mentioned_in": mentioned_in if isinstance(mentioned_in, list) else [],
                        "mention_count": mention_count,
                    })
                    domain = urlparse(url).netloc.replace("www.", "")
                    print(f"      {domain}: {len(md)} chars ({mention_count} mentions)")
            except Exception as e:
                print(f"      Failed {url}: {e}")

    url_counts = {
        url: len(set(sources)) if isinstance(sources, list) else sources
        for url, sources in top_urls
    }

    return {"url_counts": url_counts, "scraped": scraped}


def main():
    parser = argparse.ArgumentParser(description="Step 02: Gather newsletters")
    parser.add_argument("--date", default=today_str(), help="Date (YYYY-MM-DD)")
    parser.add_argument("--input", help="Path to pre-gathered newsletter JSON (skip Gmail API)")
    args = parser.parse_args()

    print(f"[02] Gathering newsletters for {args.date}")

    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            newsletters_data = json.load(f)
        print(f"  Loaded {len(newsletters_data.get('newsletters', []))} newsletters from {args.input}")
        write_json("newsletters.json", newsletters_data)
        return

    # Check if data already exists from a previous run
    existing = read_json("newsletters.json")
    if existing and existing.get("date") == args.date and existing.get("newsletters"):
        print(f"  Using existing newsletter data ({len(existing['newsletters'])} newsletters)")
        return

    # Try Gmail API
    service = get_gmail_service()
    if service:
        raw_newsletters = fetch_newsletters(service, args.date)
    else:
        print("  Gmail API unavailable, creating empty placeholder")
        raw_newsletters = []

    # Cross-reference URLs across newsletters
    cross_ref = {}
    if raw_newsletters and len(raw_newsletters) >= 2:
        print("  Cross-referencing newsletter URLs...")
        cross_ref = cross_reference_urls(raw_newsletters)
        if cross_ref.get("scraped"):
            print(f"  Scraped {len(cross_ref['scraped'])} cross-referenced articles")

    newsletters_data = {
        "date": args.date,
        "gathered_at": datetime.now().isoformat(),
        "source": "gmail_api" if raw_newsletters else "placeholder",
        "newsletters": raw_newsletters,
        "cross_references": cross_ref,
    }

    path = write_json("newsletters.json", newsletters_data)
    print(f"  Saved {len(raw_newsletters)} newsletters to {path}")


if __name__ == "__main__":
    main()
