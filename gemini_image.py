"""
Generate an image via Gemini web app using gemini-webapi.
Uses Google account cookies (same pattern as notebooklm-py).

Usage:
  PYTHONUTF8=1 python gemini_image.py --prompt "A dark moody neural network" --output hero.jpg
  PYTHONUTF8=1 python gemini_image.py --prompt "..." --output hero.jpg --cookies ~/.gemini/cookies.json

Exit codes:
  0 = success
  1 = generation failed
  2 = auth expired (re-run gemini_login.py)
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path


DEFAULT_COOKIE_PATH = os.path.expanduser("~/.gemini/cookies.json")


async def generate_image(prompt: str, output_path: str, cookies_path: str) -> bool:
    """Generate an image via Gemini and save it locally. Returns True on success."""
    from gemini_webapi import GeminiClient

    # Load cookies
    cookie_file = Path(cookies_path)
    if not cookie_file.exists():
        print(f"ERROR: Cookie file not found: {cookies_path}")
        print("Run: python gemini_login.py")
        sys.exit(2)

    with open(cookie_file, "r", encoding="utf-8") as f:
        cookie_dict = json.load(f)

    secure_1psid = cookie_dict.get("__Secure-1PSID", "")
    secure_1psidts = cookie_dict.get("__Secure-1PSIDTS", "")

    if not secure_1psid:
        print("ERROR: __Secure-1PSID not found in cookies")
        print("Run: python gemini_login.py")
        sys.exit(2)

    # Initialize client
    try:
        client = GeminiClient(secure_1psid, secure_1psidts, proxy=None)
        await client.init(timeout=120, auto_close=False, auto_refresh=True)
    except Exception as e:
        err_str = str(e).lower()
        if any(kw in err_str for kw in ("cookie", "auth", "expired", "login", "403", "401")):
            print(f"AUTH EXPIRED: {e}")
            print("Run: python gemini_login.py")
            sys.exit(2)
        raise

    # Generate image -- must explicitly ask Gemini to "generate" (not "send")
    generation_prompt = (
        f"Generate an image with the following description. "
        f"Create exactly ONE image. Do not include any text or watermarks in the image.\n\n"
        f"{prompt}"
    )

    print(f"Generating image via Gemini ({len(prompt)} char prompt)...")

    try:
        response = await client.generate_content(generation_prompt)
    except Exception as e:
        err_str = str(e).lower()
        if any(kw in err_str for kw in ("cookie", "auth", "expired", "login", "403", "401")):
            print(f"AUTH EXPIRED during generation: {e}")
            sys.exit(2)
        print(f"ERROR: Image generation failed: {e}")
        return False

    # Look for generated images (not web images)
    if not response.images:
        print("WARNING: No images returned by Gemini")
        if response.text:
            print(f"  Gemini response: {response.text[:300]}")
        return False

    # Save the first generated image
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    saved = False
    for img in response.images:
        # Prefer GeneratedImage over WebImage
        img_type = type(img).__name__
        try:
            result = await img.save(
                path=str(output.parent),
                filename=output.name,
                verbose=True,
            )
            size_kb = output.stat().st_size // 1024 if output.exists() else 0
            print(f"  Image saved: {output} ({size_kb}KB, type={img_type})")
            saved = True
            break
        except Exception as e:
            print(f"  WARNING: Failed to save {img_type}: {e}")
            continue

    if not saved:
        print("ERROR: Could not save any generated image")
        return False

    await client.close()
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate image via Gemini web app")
    parser.add_argument("--prompt", required=True, help="Image generation prompt")
    parser.add_argument("--output", required=True, help="Output file path (e.g., hero.jpg)")
    parser.add_argument("--cookies", default=DEFAULT_COOKIE_PATH, help="Path to cookies JSON")
    args = parser.parse_args()

    success = asyncio.run(generate_image(args.prompt, args.output, args.cookies))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
