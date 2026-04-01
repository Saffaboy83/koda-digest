#!/usr/bin/env python3
"""
YouTube Upload Script for Koda Daily AI Digest.

Uploads a video to YouTube with metadata via the YouTube Data API v3.
Handles OAuth 2.0 authentication with automatic token refresh.

Usage:
    python youtube_upload.py --file video.mp4 --title "Title" --description "Desc"

First run opens a browser for OAuth consent. Subsequent runs use the saved token.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# OAuth 2.0 scopes required for YouTube uploads
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# Paths for credentials and token storage
SCRIPT_DIR = Path(__file__).parent
CLIENT_SECRET_PATH = SCRIPT_DIR / "client_secret.json"
TOKEN_PATH = SCRIPT_DIR / ".youtube_token.json"


def get_authenticated_service():
    """Build an authenticated YouTube API service."""
    creds = None

    # Load saved token if it exists
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    # Refresh or run OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired token...")
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET_PATH.exists():
                print(f"ERROR: {CLIENT_SECRET_PATH} not found.")
                print("Download it from Google Cloud Console:")
                print("  https://console.cloud.google.com/apis/credentials")
                print(f"  Project: gen-lang-client-0610910477")
                print(f"  Save as: {CLIENT_SECRET_PATH}")
                sys.exit(1)

            print("Opening browser for OAuth consent...")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRET_PATH), SCOPES
            )
            creds = flow.run_local_server(port=8090, open_browser=True)

        # Save the token for next time
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
        print(f"Token saved to {TOKEN_PATH}")

    return build("youtube", "v3", credentials=creds)


def upload_video(youtube, file_path, title, description, tags=None, privacy="public"):
    """Upload a video to YouTube and return the video ID."""
    if not os.path.exists(file_path):
        print(f"ERROR: Video file not found: {file_path}")
        sys.exit(1)

    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    print(f"Uploading: {file_path} ({file_size_mb:.1f} MB)")
    print(f"Title: {title}")
    print(f"Privacy: {privacy}")

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or ["AI", "DailyBriefing", "KodaIntelligence", "AINews"],
            "categoryId": "28",  # Science & Technology
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        file_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=5 * 1024 * 1024,  # 5MB chunks
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    # Execute with progress tracking
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"  Upload progress: {pct}%")

    video_id = response["id"]
    print(f"\nUpload complete!")
    print(f"Video ID: {video_id}")
    print(f"URL: https://www.youtube.com/watch?v={video_id}")
    print(f"Embed: https://www.youtube.com/embed/{video_id}")

    return video_id


def main():
    parser = argparse.ArgumentParser(description="Upload video to YouTube (Koda Digest)")
    parser.add_argument("--file", required=True, help="Path to video file (.mp4)")
    parser.add_argument("--title", required=True, help="Video title (hook-based)")
    parser.add_argument("--description", required=True, help="Video description")
    parser.add_argument(
        "--tags",
        nargs="+",
        default=["AI", "DailyBriefing", "KodaIntelligence", "AINews"],
        help="Video tags",
    )
    parser.add_argument(
        "--privacy",
        default="public",
        choices=["public", "unlisted", "private"],
        help="Privacy status",
    )
    parser.add_argument(
        "--output-json",
        help="Write result JSON to this path (for automation)",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Date stamp (YYYY-MM-DD) to include in result JSON for freshness validation",
    )
    args = parser.parse_args()

    youtube = get_authenticated_service()
    video_id = upload_video(
        youtube,
        file_path=args.file,
        title=args.title,
        description=args.description,
        tags=args.tags,
        privacy=args.privacy,
    )

    result = {
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "embed_url": f"https://www.youtube.com/embed/{video_id}",
    }
    if args.date:
        result["date"] = args.date

    if args.output_json:
        with open(args.output_json, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Result written to {args.output_json}")

    # Also print JSON to stdout for piping
    print(json.dumps(result))
    return video_id


if __name__ == "__main__":
    main()
