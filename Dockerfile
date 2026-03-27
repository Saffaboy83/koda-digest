FROM python:3.12-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright browser for notebooklm-py
RUN playwright install chromium && playwright install-deps chromium

# Copy project
COPY . .

# Ensure data directory and entrypoint are ready
RUN mkdir -p /app/pipeline/data && chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
