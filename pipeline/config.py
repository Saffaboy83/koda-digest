"""Shared configuration for the Koda Digest pipeline."""

import os
import json
import shutil
from datetime import datetime
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────

DIGEST_DIR = Path(os.environ.get("DIGEST_DIR", Path(__file__).parent.parent))
PIPELINE_DIR = DIGEST_DIR / "pipeline"
TEMPLATES_DIR = DIGEST_DIR / "templates"
DATA_DIR = DIGEST_DIR / "pipeline" / "data"

# ── Load .env ────────────────────────────────────────────────────────────────

def load_env():
    """Load .env file from DIGEST_DIR if it exists."""
    env_path = DIGEST_DIR / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())

load_env()

# ── API Keys ─────────────────────────────────────────────────────────────────

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
LEONARDO_API_KEY = os.environ.get("LEONARDO_API_KEY", "")

# ── Constants ────────────────────────────────────────────────────────────────

NOTEBOOK_ID = os.environ.get(
    "NOTEBOOK_ID", "f928d89b-2520-4180-a71a-d93a75a5487c"
)

# FFmpeg: use env var, then system PATH, then Windows fallback
FFMPEG_PATH = os.environ.get("FFMPEG_PATH", "") or shutil.which("ffmpeg") or os.path.expanduser(
    "~/AppData/Local/Microsoft/WinGet/Packages/"
    "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/"
    "ffmpeg-8.1-full_build/bin/ffmpeg.exe"
)

EMAIL_RECIPIENTS = os.environ.get("EMAIL_RECIPIENTS", "").split(",") if os.environ.get("EMAIL_RECIPIENTS") else [
    "cazmarincowitz@outlook.com",
    "markmarincowitz9@gmail.com",
    "charlene@vanillasky.co.za",
    "Arno_marincowitz@yahoo.co.uk",
    "saffaboyjm@gmail.com",
]

# ── Helpers ──────────────────────────────────────────────────────────────────

def today_str():
    """Return today's date as YYYY-MM-DD."""
    return datetime.now().strftime("%Y-%m-%d")


def today_label():
    """Return today's date as a human-readable label."""
    return datetime.now().strftime("%d %B %Y")


def ensure_data_dir():
    """Ensure the pipeline data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def read_json(filename):
    """Read a JSON file from the data directory."""
    path = DATA_DIR / filename
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(filename, data):
    """Write a JSON file to the data directory."""
    ensure_data_dir()
    path = DATA_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path
