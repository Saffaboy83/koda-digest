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
        git init -b main
        git remote add origin "https://x-access-token:${GIT_TOKEN}@github.com/Saffaboy83/koda-digest.git"
        git fetch --depth 1 --filter=blob:limit=50k origin main
        git reset origin/main
        echo "[entrypoint] Git repo initialized on branch main"
    fi
fi

# Hard timeout: 120 minutes max to prevent zombie containers
# Media generation runs all three (audio, infographic, video) in parallel -- Veo 3 cinematic
# takes 30-45 min, and Steps 01-03 + 05-07 need ~25 min total on top of that.
# PYTHONUNBUFFERED ensures all print output reaches Railway logs immediately
export PYTHONUNBUFFERED=1
TIMEOUT=7200
echo "[entrypoint] Launching pipeline (timeout: ${TIMEOUT}s / 120min)..."
timeout $TIMEOUT python -u -m pipeline.run_all "$@"
EXIT_CODE=$?

if [ $EXIT_CODE -eq 124 ]; then
    echo "[entrypoint] TIMEOUT: Pipeline exceeded ${TIMEOUT}s (120min) limit"
fi

echo "[entrypoint] Pipeline exited with code $EXIT_CODE at $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
exit $EXIT_CODE
