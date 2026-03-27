#!/bin/bash

echo "[entrypoint] Starting Koda Digest pipeline"

# Decode credential files from base64 environment variables
if [ -n "$GMAIL_TOKEN_B64" ]; then
    if echo "$GMAIL_TOKEN_B64" | tr -d '[:space:]' | base64 -d > /app/.gmail_token.json 2>/dev/null; then
        echo "[entrypoint] Gmail token decoded ($(wc -c < /app/.gmail_token.json) bytes)"
    else
        echo "[entrypoint] WARNING: Gmail token base64 decode failed"
        rm -f /app/.gmail_token.json
    fi
else
    echo "[entrypoint] GMAIL_TOKEN_B64 not set"
fi

if [ -n "$YOUTUBE_TOKEN_B64" ]; then
    if echo "$YOUTUBE_TOKEN_B64" | tr -d '[:space:]' | base64 -d > /app/.youtube_token.json 2>/dev/null; then
        echo "[entrypoint] YouTube token decoded ($(wc -c < /app/.youtube_token.json) bytes)"
    else
        echo "[entrypoint] WARNING: YouTube token base64 decode failed"
        rm -f /app/.youtube_token.json
    fi
else
    echo "[entrypoint] YOUTUBE_TOKEN_B64 not set"
fi

if [ -n "$NOTEBOOKLM_COOKIES_B64" ]; then
    mkdir -p /root/.notebooklm
    if echo "$NOTEBOOKLM_COOKIES_B64" | tr -d '[:space:]' | base64 -d > /root/.notebooklm/storage_state.json 2>/dev/null; then
        echo "[entrypoint] NotebookLM cookies decoded ($(wc -c < /root/.notebooklm/storage_state.json) bytes)"
    else
        echo "[entrypoint] WARNING: NotebookLM cookies base64 decode failed"
        rm -f /root/.notebooklm/storage_state.json
    fi
else
    echo "[entrypoint] NOTEBOOKLM_COOKIES_B64 not set"
fi

# Configure git for deploy step
if [ -n "$GIT_TOKEN" ]; then
    git config --global credential.helper store
    echo "https://x-access-token:${GIT_TOKEN}@github.com" > /root/.git-credentials
    git config --global user.email "digest@koda.community"
    git config --global user.name "Koda Digest Bot"
    echo "[entrypoint] Git credentials configured"
else
    echo "[entrypoint] GIT_TOKEN not set"
fi

echo "[entrypoint] Launching pipeline..."
exec python -m pipeline.run_all "$@"
