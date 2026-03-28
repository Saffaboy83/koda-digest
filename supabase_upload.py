"""
Upload media files to Supabase Storage for the Koda Digest.

Uploads podcast MP3s and infographic JPGs to the 'koda-media' bucket,
returning public URLs for use in HTML and RSS feeds.

Usage:
    python supabase_upload.py --file podcast-2026-03-28.mp3
    python supabase_upload.py --file infographic-2026-03-28.jpg
    python supabase_upload.py --file podcast-2026-03-28.mp3 --file infographic-2026-03-28.jpg

Environment variables (required):
    SUPABASE_URL            - Project URL (https://xxx.supabase.co)
    SUPABASE_SERVICE_ROLE_KEY - Service role key (for upload auth)

Output:
    Prints the public URL for each uploaded file.
    With --json, outputs a JSON object of {filename: public_url}.
"""

import argparse
import json
import mimetypes
import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

# ── Constants ────────────────────────────────────────────────────────────────

BUCKET = "koda-media"

MIME_TYPES = {
    ".mp3": "audio/mpeg",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

# ── Helpers ──────────────────────────────────────────────────────────────────


def get_env(name: str) -> str:
    """Get required environment variable or exit."""
    value = os.environ.get(name)
    if not value:
        print(f"ERROR: {name} environment variable not set.", file=sys.stderr)
        sys.exit(1)
    return value


def get_content_type(filepath: str) -> str:
    """Determine content type from file extension."""
    ext = Path(filepath).suffix.lower()
    ct = MIME_TYPES.get(ext)
    if not ct:
        ct, _ = mimetypes.guess_type(filepath)
    return ct or "application/octet-stream"


def upload_file(filepath: str, supabase_url: str, service_key: str,
                bucket: str = BUCKET) -> str:
    """Upload a file to Supabase Storage and return the public URL.

    Uses upsert (overwrite if exists) so re-runs are safe.
    """
    filename = Path(filepath).name
    content_type = get_content_type(filepath)
    file_size = os.path.getsize(filepath)

    upload_url = f"{supabase_url}/storage/v1/object/{bucket}/{filename}"

    with open(filepath, "rb") as f:
        file_data = f.read()

    req = Request(
        upload_url,
        data=file_data,
        method="POST",
        headers={
            "Authorization": f"Bearer {service_key}",
            "Content-Type": content_type,
            "x-upsert": "true",
        },
    )

    try:
        with urlopen(req) as resp:
            resp.read()
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Upload failed ({e.code}): {body}") from e

    public_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{filename}"

    return public_url


def public_url_for(filename: str, supabase_url: str,
                   bucket: str = BUCKET) -> str:
    """Build the public URL for a file without uploading."""
    return f"{supabase_url}/storage/v1/object/public/{bucket}/{filename}"


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload media files to Supabase Storage"
    )
    parser.add_argument(
        "--file", action="append", required=True,
        help="File(s) to upload (can specify multiple times)"
    )
    parser.add_argument(
        "--bucket", default=BUCKET,
        help=f"Storage bucket name (default: {BUCKET})"
    )
    parser.add_argument(
        "--json", action="store_true", dest="json_output",
        help="Output results as JSON"
    )
    args = parser.parse_args()

    supabase_url = get_env("SUPABASE_URL")
    service_key = get_env("SUPABASE_SERVICE_ROLE_KEY")

    results = {}

    for filepath in args.file:
        if not os.path.exists(filepath):
            print(f"ERROR: File not found: {filepath}", file=sys.stderr)
            sys.exit(1)

        filename = Path(filepath).name
        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        print(f"Uploading {filename} ({size_mb:.1f} MB)...", file=sys.stderr)

        try:
            url = upload_file(filepath, supabase_url, service_key, args.bucket)
            results[filename] = url
            print(f"  OK: {url}", file=sys.stderr)
        except RuntimeError as e:
            print(f"  FAILED: {e}", file=sys.stderr)
            results[filename] = None

    if args.json_output:
        print(json.dumps(results, indent=2))
    else:
        for filename, url in results.items():
            if url:
                print(url)

    failed = [f for f, u in results.items() if u is None]
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
