"""
Generate an image via Google Gemini API (Imagen 3).
Uses API key authentication -- no browser cookies needed.

Usage:
  python gemini_image.py --prompt "A dark moody neural network" --output hero.jpg

Exit codes:
  0 = success
  1 = generation failed
  2 = API key missing or invalid
"""
import argparse
import os
import sys
from pathlib import Path


def generate_image(prompt: str, output_path: str, api_key: str) -> bool:
    """Generate an image via Gemini Imagen 3 and save it locally."""
    from google import genai

    client = genai.Client(api_key=api_key)

    generation_prompt = (
        f"Generate an image with the following description. "
        f"Create exactly ONE image. Do not include any text or watermarks in the image.\n\n"
        f"{prompt}"
    )

    print(f"Generating image via Gemini Imagen 3 ({len(prompt)} char prompt)...")

    try:
        response = client.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt=generation_prompt,
            config={"number_of_images": 1},
        )
    except Exception as e:
        err_str = str(e).lower()
        if any(kw in err_str for kw in ("api key", "api_key", "unauthorized", "403", "401", "invalid")):
            print(f"AUTH ERROR: {e}")
            sys.exit(2)
        print(f"ERROR: Image generation failed: {e}")
        return False

    if not response.generated_images:
        print("WARNING: No images returned by Gemini")
        return False

    # Save the first image
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    image_data = response.generated_images[0].image.image_bytes
    with open(output, "wb") as f:
        f.write(image_data)

    size_kb = output.stat().st_size // 1024
    print(f"  Image saved: {output} ({size_kb}KB)")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate image via Gemini API")
    parser.add_argument("--prompt", required=True, help="Image generation prompt")
    parser.add_argument("--output", required=True, help="Output file path (e.g., hero.jpg)")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY environment variable not set")
        print("Get a free key: https://aistudio.google.com/apikey")
        sys.exit(2)

    success = generate_image(args.prompt, args.output, api_key)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
