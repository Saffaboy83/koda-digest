#!/bin/bash
echo "[entrypoint] Starting Koda Digest pipeline"

# Decode tokens using Python
python3 /app/decode_tokens.py

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
