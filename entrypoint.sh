#!/bin/bash

echo "[entrypoint] Starting Koda Digest pipeline"
echo "[entrypoint] Date: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"

# Decode tokens using Python
python3 /app/decode_tokens.py || { echo "[entrypoint] Token decode failed"; exit 1; }

# Configure git for deploy step
if [ -n "$GIT_TOKEN" ]; then
    git config --global credential.helper store
    echo "https://x-access-token:${GIT_TOKEN}@github.com" > /root/.git-credentials
    git config --global user.email "digest@koda.community"
    git config --global user.name "Koda Digest Bot"
    echo "[entrypoint] Git credentials configured"

    # Initialize git repo (Docker COPY doesn't include .git)
    if [ ! -d "/app/.git" ]; then
        cd /app
        git init
        git remote add origin "https://x-access-token:${GIT_TOKEN}@github.com/Saffaboy83/koda-digest.git"
        git fetch origin main
        git reset origin/main
        echo "[entrypoint] Git repo initialized and synced with remote"
    fi
fi

# Hard timeout: 45 minutes max to prevent zombie containers
# Media is skipped until NotebookLM auth is proven to work on Railway
TIMEOUT=2700
echo "[entrypoint] Launching pipeline (timeout: ${TIMEOUT}s, media: skipped)..."
timeout $TIMEOUT python -m pipeline.run_all --skip-media "$@"
EXIT_CODE=$?

if [ $EXIT_CODE -eq 124 ]; then
    echo "[entrypoint] TIMEOUT: Pipeline exceeded ${TIMEOUT}s limit"
fi

echo "[entrypoint] Pipeline exited with code $EXIT_CODE at $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
exit $EXIT_CODE
