#!/bin/bash
set -e

# Decode credential files from base64 environment variables
# Use tr to strip any whitespace/CRLF from the base64 string
if [ -n "$GMAIL_TOKEN_B64" ]; then
    echo "$GMAIL_TOKEN_B64" | tr -d '[:space:]' | base64 -d > /app/.gmail_token.json
    echo "[entrypoint] Gmail token decoded"
fi

if [ -n "$YOUTUBE_TOKEN_B64" ]; then
    echo "$YOUTUBE_TOKEN_B64" | tr -d '[:space:]' | base64 -d > /app/.youtube_token.json
    echo "[entrypoint] YouTube token decoded"
fi

if [ -n "$NOTEBOOKLM_COOKIES_B64" ]; then
    mkdir -p /root/.notebooklm
    echo "$NOTEBOOKLM_COOKIES_B64" | tr -d '[:space:]' | base64 -d > /root/.notebooklm/storage_state.json
    echo "[entrypoint] NotebookLM cookies decoded"
fi

# Configure git for deploy step
if [ -n "$GIT_TOKEN" ]; then
    git config --global credential.helper store
    echo "https://x-access-token:${GIT_TOKEN}@github.com" > /root/.git-credentials
    git config --global user.email "digest@koda.community"
    git config --global user.name "Koda Digest Bot"
    echo "[entrypoint] Git credentials configured"
fi

# Run the pipeline
exec python -m pipeline.run_all "$@"
