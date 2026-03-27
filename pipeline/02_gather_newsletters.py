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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import DIGEST_DIR, today_str, write_json, read_json

# ── Gmail Config ─────────────────────────────────────────────────────────────

GMAIL_TOKEN_PATH = DIGEST_DIR / ".gmail_token.json"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

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

    newsletters_data = {
        "date": args.date,
        "gathered_at": datetime.now().isoformat(),
        "source": "gmail_api" if raw_newsletters else "placeholder",
        "newsletters": raw_newsletters,
    }

    path = write_json("newsletters.json", newsletters_data)
    print(f"  Saved {len(raw_newsletters)} newsletters to {path}")


if __name__ == "__main__":
    main()
