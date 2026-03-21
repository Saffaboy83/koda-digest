#!/bin/bash
# Koda Digest Auto-Deploy
# Run this after each digest generation, or set up as a cron job
# Usage: ./deploy.sh

cd "$(dirname "$0")"

# Stage all HTML files and config
git add morning-briefing-koda.html morning-briefing-koda-*.html vercel.json .gitignore 2>/dev/null

# Check if there are changes to commit
if git diff --cached --quiet; then
    echo "No new changes to deploy."
    exit 0
fi

# Commit with today's date
DATE=$(date +%Y-%m-%d)
git commit -m "Digest $DATE"

# Push to GitHub
git push origin main

echo "✅ Deployed! Vercel will auto-build in ~30 seconds."
