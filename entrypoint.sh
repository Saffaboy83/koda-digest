#!/bin/bash
echo "[entrypoint] Starting Koda Digest pipeline"

# Use Python to decode base64 tokens (more reliable than bash base64)
python3 -c "
import os, base64, pathlib

tokens = {
    'GMAIL_TOKEN_B64': '/app/.gmail_token.json',
    'YOUTUBE_TOKEN_B64': '/app/.youtube_token.json',
    'NOTEBOOKLM_COOKIES_B64': '/root/.notebooklm/storage_state.json',
}

for env_var, dest in tokens.items():
    raw = os.environ.get(env_var, '')
    if not raw:
        print(f'[entrypoint] {env_var} not set')
        continue
    try:
        cleaned = raw.strip().replace('\n', '').replace('\r', '').replace(' ', '')
        data = base64.b64decode(cleaned)
        pathlib.Path(dest).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(dest).write_bytes(data)
        print(f'[entrypoint] {env_var} decoded ({len(data)} bytes) -> {dest}')
    except Exception as e:
        print(f'[entrypoint] WARNING: {env_var} decode failed: {e}')
        print(f'[entrypoint]   raw length: {len(raw)}, first 20 chars: {repr(raw[:20])}')
"

# Configure git for deploy step
if [ -n "$GIT_TOKEN" ]; then
    git config --global credential.helper store
    echo "https://x-access-token:${GIT_TOKEN}@github.com" > /root/.git-credentials
    git config --global user.email "digest@koda.community"
    git config --global user.name "Koda Digest Bot"
    echo "[entrypoint] Git credentials configured"
fi

echo "[entrypoint] Launching pipeline..."
exec python -m pipeline.run_all "$@"
