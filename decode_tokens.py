"""Decode base64 environment variables into credential files."""
import os
import base64
import pathlib
import sys
import traceback

TOKENS = {
    "GMAIL_TOKEN_B64": "/app/.gmail_token.json",
    "YOUTUBE_TOKEN_B64": "/app/.youtube_token.json",
    "NOTEBOOKLM_COOKIES_B64": "/root/.notebooklm/storage_state.json",
}

def main():
    for env_var, dest in TOKENS.items():
        raw = os.environ.get(env_var, "")
        if not raw:
            print(f"[decode] {env_var} not set", flush=True)
            continue

        print(f"[decode] {env_var}: length={len(raw)}, first_20={repr(raw[:20])}", flush=True)

        try:
            # Strip any whitespace, newlines, quotes
            cleaned = raw.strip().strip('"').strip("'")
            cleaned = cleaned.replace("\n", "").replace("\r", "").replace(" ", "")

            # Add padding if needed
            padding = 4 - len(cleaned) % 4
            if padding != 4:
                cleaned += "=" * padding

            data = base64.b64decode(cleaned)
            pathlib.Path(dest).parent.mkdir(parents=True, exist_ok=True)
            pathlib.Path(dest).write_bytes(data)
            print(f"[decode] {env_var} -> {dest} ({len(data)} bytes)", flush=True)
        except Exception as e:
            print(f"[decode] FAILED {env_var}: {e}", flush=True)
            traceback.print_exc()

if __name__ == "__main__":
    main()
