"""
Subprocess wrapper for generating the email sketch-note infographic via NotebookLM.

Runs in a separate process to avoid OOM kills in the main pipeline process
(step 07) which has accumulated memory from steps 04/04E/04R.

Usage:
    python -m pipeline.generate_sketch_note --date 2026-04-09 --instructions "..." --output /path/to/hero.jpg

Exit codes:
    0 = success (prints Supabase URL to stdout)
    1 = generation failed (non-fatal, email sends without hero)
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import DIGEST_DIR, SUPABASE_URL

NOTEBOOK_ID = "f928d89b-2520-4180-a71a-d93a75a5487c"
MEDIA_PUBLIC_BASE = "https://www.koda.community/media"


def _media_url(filename: str) -> str:
    return f"{MEDIA_PUBLIC_BASE}/{filename}"


def _upload_to_supabase(hero_path: Path, date: str) -> str | None:
    """Upload hero to Supabase, return public URL."""
    import httpx

    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not SUPABASE_URL or not service_key:
        return _media_url(f"email-hero-{date}.jpg")

    filename = f"email-hero-{date}.jpg"
    upload_url = f"{SUPABASE_URL}/storage/v1/object/koda-media/{filename}"

    with open(hero_path, "rb") as f:
        img_bytes = f.read()

    resp = httpx.put(
        upload_url,
        content=img_bytes,
        headers={
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "image/jpeg",
            "x-upsert": "true",
        },
        timeout=60.0,
    )
    resp.raise_for_status()
    url = _media_url(filename)
    print(f"  Uploaded to Supabase: {url}", file=sys.stderr)
    return url


async def generate(instructions: str, hero_path: Path) -> None:
    from notebooklm import NotebookLMClient, InfographicOrientation, InfographicDetail

    client_cm = await NotebookLMClient.from_storage()
    client = await client_cm.__aenter__()
    try:
        print("  Generating sketch-note infographic via NotebookLM (square, concise)...", file=sys.stderr)
        status = await client.artifacts.generate_infographic(
            NOTEBOOK_ID,
            instructions=instructions,
            orientation=InfographicOrientation.SQUARE,
            detail_level=InfographicDetail.CONCISE,
        )
        print(f"  Infographic generation started (task: {status.task_id})", file=sys.stderr)

        await client.artifacts.wait_for_completion(
            NOTEBOOK_ID, status.task_id, timeout=300.0
        )

        png_path = hero_path.with_suffix(".png")
        await client.artifacts.download_infographic(NOTEBOOK_ID, str(png_path))
        print(f"  Downloaded infographic PNG: {png_path.stat().st_size // 1024}KB", file=sys.stderr)

        try:
            from PIL import Image
            with Image.open(png_path) as img:
                rgb = img.convert("RGB")
                rgb.save(str(hero_path), "JPEG", quality=90)
            png_path.unlink(missing_ok=True)
            print(f"  Converted to JPG: {hero_path.stat().st_size // 1024}KB", file=sys.stderr)
        except ImportError:
            png_path.rename(hero_path)
    finally:
        await client_cm.__aexit__(None, None, None)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate email sketch-note hero")
    parser.add_argument("--date", required=True)
    parser.add_argument("--instructions", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    hero_path = Path(args.output)

    if hero_path.exists():
        print(f"  Email sketch-note already exists: {hero_path.name}", file=sys.stderr)
    else:
        asyncio.run(generate(args.instructions, hero_path))

    url = _upload_to_supabase(hero_path, args.date)
    if url:
        print(url)  # stdout = URL for parent process to capture
    else:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"  WARNING: sketch-note generation failed: {e}", file=sys.stderr)
        sys.exit(1)
