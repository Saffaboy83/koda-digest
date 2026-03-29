"""
Step 07: Send the daily newsletter email.

Sends via Beehiiv Create Post API (primary) to all subscribers.
Falls back to Gmail API (secondary) for the 5-person distribution list.

Input:  pipeline/data/digest-content.json, pipeline/data/media-status.json
Output: Beehiiv post (sent to all subscribers) or Gmail email (fallback)
"""

import argparse
import base64
import json
import sys
import os
import httpx
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import (EMAIL_RECIPIENTS, DIGEST_DIR, SUPABASE_URL,
                              BEEHIIV_API_KEY, BEEHIIV_PUBLICATION_ID,
                              today_str, write_json, read_json)

GMAIL_TOKEN_PATH = DIGEST_DIR / ".gmail_token.json"
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]


def build_email_subject(digest):
    """Generate a hook-based email subject line."""
    summary = digest.get("summary", {})
    hook = summary.get("hook", "Daily Intelligence")

    # Shorten hook if needed
    if len(hook) > 40:
        hook = hook[:37] + "..."

    date_label = digest.get("date_label", digest["date"])
    return f"Koda Daily Digest | {hook} | {date_label}"


def build_email_html(digest, media_status):
    """Generate the newsletter email HTML body with premium dark-mode design."""
    date_label = digest.get("date_label", digest["date"])
    date = digest.get("date", "")
    summary = digest.get("summary", {})
    hook = summary.get("hook", "Your daily AI intelligence briefing is ready.")
    markets = digest.get("markets", {})
    media = media_status.get("media", {}) if media_status else {}
    ai_news = digest.get("ai_news", [])[:3]
    world_news = digest.get("world_news", [])[:2]

    # Brief cards with color-coded left borders (matching site)
    brief_colors = {"ai": "#3B82F6", "world": "#EF4444", "markets": "#10B981", "wildcard": "#F59E0B"}
    briefs_html = ""
    for brief in summary.get("briefs", []):
        color = brief_colors.get(brief.get("icon", ""), "#3B82F6")
        label = brief.get("label", "")
        text = brief.get("text", "")
        briefs_html += f"""<tr><td style="padding:0 0 8px 0">
          <table width="100%" cellpadding="0" cellspacing="0" style="background:#131B2E;border-left:3px solid {color}">
            <tr>
              <td style="padding:12px 16px">
                <span style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:{color}">{label}</span>
                <p style="margin:4px 0 0;font-size:14px;color:#C2C6D6;line-height:1.5">{text}</p>
              </td>
            </tr>
          </table>
        </td></tr>"""

    # Market ticker row (compact 3-column layout)
    ticker_map = {"sp500": "S&P", "nasdaq": "NDX", "btc": "BTC",
                  "eth": "ETH", "oil": "Oil", "sentiment": "Mood"}
    market_cells = ""
    for key, label in ticker_map.items():
        data = markets.get(key, {})
        if isinstance(data, dict):
            price = data.get("price", data.get("value", "N/A"))
            change = data.get("change", data.get("label", ""))
            direction = data.get("direction", "neutral")
            color = "#10B981" if direction == "up" else "#EF4444" if direction == "down" else "#F59E0B"
            market_cells += f"""<td style="padding:8px 4px;text-align:center;width:33%">
              <span style="display:block;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#8C909F">{label}</span>
              <span style="display:block;font-size:13px;font-weight:700;color:#E2E8F0;font-family:'Courier New',monospace">{price}</span>
              <span style="display:block;font-size:10px;font-family:'Courier New',monospace;color:{color}">{change}</span>
            </td>"""

    # Split market cells into 2 rows of 3
    market_items = list(ticker_map.items())
    market_row1 = ""
    market_row2 = ""
    for i, (key, label) in enumerate(market_items):
        data = markets.get(key, {})
        if isinstance(data, dict):
            price = data.get("price", data.get("value", "N/A"))
            change = data.get("change", data.get("label", ""))
            direction = data.get("direction", "neutral")
            color = "#10B981" if direction == "up" else "#EF4444" if direction == "down" else "#F59E0B"
            cell = f"""<td style="padding:10px 4px;text-align:center;width:33%;background:#131B2E">
              <span style="display:block;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#8C909F;margin-bottom:2px">{label}</span>
              <span style="display:block;font-size:14px;font-weight:700;color:#E2E8F0;font-family:'Courier New',monospace">{price}</span>
              <span style="display:block;font-size:11px;font-family:'Courier New',monospace;color:{color}">{change}</span>
            </td>"""
            if i < 3:
                market_row1 += cell
            else:
                market_row2 += cell

    # Top stories preview (drives click-through)
    stories_html = ""
    cat_colors = {
        "Model Release": "#3B82F6", "Benchmark": "#8B5CF6", "Agents": "#6366F1",
        "Hardware": "#F59E0B", "Enterprise": "#10B981", "Policy": "#EF4444",
        "Conflict": "#EF4444", "Diplomacy": "#3B82F6", "Economy": "#10B981",
    }
    for story in (ai_news + world_news)[:4]:
        cat = story.get("category", "")
        color = cat_colors.get(cat, "#3B82F6")
        title = story.get("title", "")
        body = story.get("body", "")
        if len(body) > 120:
            body = body[:117] + "..."
        stories_html += f"""<tr><td style="padding:0 0 8px 0">
          <table width="100%" cellpadding="0" cellspacing="0" style="background:#131B2E">
            <tr><td style="padding:14px 16px">
              <span style="font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:{color};background:rgba(59,130,246,0.08);padding:2px 8px;display:inline-block;margin-bottom:6px">{cat}</span>
              <p style="margin:0 0 4px;font-size:15px;font-weight:700;color:#E2E8F0">{title}</p>
              <p style="margin:0;font-size:13px;color:#94A3B8;line-height:1.4">{body}</p>
            </td></tr>
          </table>
        </td></tr>"""

    # Media buttons
    media_html = ""
    podcast_url = ""
    yt_url = ""
    if media.get("podcast"):
        podcast_url = f"{SUPABASE_URL}/storage/v1/object/public/koda-media/podcast-{date}.mp3" if SUPABASE_URL else f"https://www.koda.community/podcast-{date}.mp3"

    video_result_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "youtube-result.json")
    if os.path.exists(video_result_path):
        try:
            with open(video_result_path, "r") as f:
                vr = json.load(f)
            yt_url = vr.get("url", "")
        except Exception:
            pass

    if podcast_url or yt_url:
        buttons = ""
        if podcast_url:
            buttons += f"""<td style="padding:0 4px;width:50%">
              <a href="{podcast_url}" style="display:block;padding:14px 8px;background:#6366F1;color:white;text-decoration:none;text-align:center;font-weight:700;font-size:13px">&#9654; Listen to Podcast</a>
            </td>"""
        if yt_url:
            buttons += f"""<td style="padding:0 4px;width:50%">
              <a href="{yt_url}" style="display:block;padding:14px 8px;background:#EC4899;color:white;text-decoration:none;text-align:center;font-weight:700;font-size:13px">&#9654; Watch Video</a>
            </td>"""
        media_html = f"""<tr><td style="padding:0 24px 20px">
          <table width="100%" cellpadding="0" cellspacing="0"><tr>{buttons}</tr></table>
        </td></tr>"""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta name="color-scheme" content="dark"><meta name="supported-color-schemes" content="dark">
<title>Koda Intelligence | {date_label}</title></head>
<body style="margin:0;padding:0;background:#0B1326;font-family:Arial,Helvetica,sans-serif;-webkit-font-smoothing:antialiased">

<!-- Outer wrapper -->
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0B1326">
<tr><td align="center" style="padding:16px 12px">

<!-- Inner card -->
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#0F172A">

  <!-- Header with gradient -->
  <tr><td style="padding:28px 24px 24px;text-align:center;background:linear-gradient(135deg,#1E293B 0%,#312E81 50%,#1E293B 100%)">
    <!-- K badge -->
    <table cellpadding="0" cellspacing="0" style="margin:0 auto 12px"><tr>
      <td style="width:36px;height:36px;background:linear-gradient(135deg,#3B82F6,#8B5CF6);text-align:center;line-height:36px;color:white;font-weight:900;font-size:16px">K</td>
    </tr></table>
    <h1 style="margin:0;color:white;font-size:22px;font-weight:800;letter-spacing:-0.5px">Koda Intelligence</h1>
    <p style="margin:6px 0 0;color:#94A3B8;font-size:12px;text-transform:uppercase;letter-spacing:2px">{date_label}</p>
  </td></tr>

  <!-- Accent line -->
  <tr><td style="padding:0"><table width="100%" cellpadding="0" cellspacing="0"><tr>
    <td style="height:2px;background:linear-gradient(90deg,#3B82F6,#8B5CF6,#EC4899)"></td>
  </tr></table></td></tr>

  <!-- Hook -->
  <tr><td style="padding:24px 24px 8px">
    <p style="margin:0;color:#E2E8F0;font-size:20px;font-weight:800;line-height:1.3;letter-spacing:-0.3px">{hook}</p>
  </td></tr>

  <!-- The Briefing -->
  <tr><td style="padding:16px 24px 4px">
    <p style="margin:0 0 10px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:2px;color:#8C909F">The Briefing</p>
    <table width="100%" cellpadding="0" cellspacing="0">
      {briefs_html}
    </table>
  </td></tr>

  <!-- Market Pulse -->
  <tr><td style="padding:16px 24px">
    <p style="margin:0 0 10px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:2px;color:#8C909F">Market Pulse</p>
    <table width="100%" cellpadding="0" cellspacing="4" style="border-spacing:4px">
      <tr>{market_row1}</tr>
      <tr>{market_row2}</tr>
    </table>
  </td></tr>

  <!-- Top Stories -->
  <tr><td style="padding:8px 24px 4px">
    <p style="margin:0 0 10px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:2px;color:#8C909F">Top Stories</p>
    <table width="100%" cellpadding="0" cellspacing="0">
      {stories_html}
    </table>
  </td></tr>

  <!-- Media Buttons -->
  {media_html}

  <!-- CTA Button -->
  <tr><td style="padding:8px 24px 28px;text-align:center">
    <a href="https://www.koda.community/morning-briefing-koda-{date}.html"
      style="display:inline-block;padding:16px 40px;background:#3B82F6;color:white;text-decoration:none;font-weight:800;font-size:15px;letter-spacing:0.5px">READ THE FULL DIGEST</a>
  </td></tr>

  <!-- Footer -->
  <tr><td style="padding:20px 24px;border-top:1px solid #1E293B;text-align:center">
    <p style="margin:0 0 6px;font-size:12px;font-weight:700;color:#3B82F6">Koda Intelligence</p>
    <p style="margin:0;font-size:11px;color:#64748B">
      <a href="https://www.koda.community" style="color:#64748B;text-decoration:none">koda.community</a>
    </p>
  </td></tr>

</table>
</td></tr>
</table>
</body></html>"""

    return html


def send_via_beehiiv(subject, html_body):
    """Send newsletter via Beehiiv Create Post API. Returns True on success."""
    if not BEEHIIV_API_KEY or not BEEHIIV_PUBLICATION_ID:
        print("  Beehiiv: not configured (missing API key or publication ID)")
        return False

    pub_id = BEEHIIV_PUBLICATION_ID
    if not pub_id.startswith("pub_"):
        pub_id = f"pub_{pub_id}"

    try:
        resp = httpx.post(
            f"https://api.beehiiv.com/v2/publications/{pub_id}/posts",
            headers={
                "Authorization": f"Bearer {BEEHIIV_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "title": subject,
                "body_content": html_body,
                "status": "confirmed",
            },
            timeout=30,
        )

        if resp.status_code in (200, 201):
            data = resp.json().get("data", {})
            post_id = data.get("id", "unknown")
            print(f"  Beehiiv: sent! Post ID: {post_id}")
            return True

        print(f"  Beehiiv: failed ({resp.status_code}): {resp.text[:300]}")
        return False

    except Exception as e:
        print(f"  Beehiiv: error: {e}")
        return False


def get_gmail_credentials():
    """Get Gmail API credentials, reusing YouTube OAuth client."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("  WARNING: google-auth packages not installed.")
        print("  Run: pip install google-auth google-auth-oauthlib google-api-python-client")
        return None

    creds = None

    # Try loading existing Gmail token
    if GMAIL_TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(GMAIL_TOKEN_PATH), GMAIL_SCOPES)

    # Refresh or get new token
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(GMAIL_TOKEN_PATH, "w") as f:
                f.write(creds.to_json())
        except Exception as e:
            print(f"  Token refresh failed: {e}")
            creds = None

    if not creds or not creds.valid:
        # Reuse the YouTube OAuth client credentials
        yt_token_path = DIGEST_DIR / ".youtube_token.json"
        if not yt_token_path.exists():
            print("  No YouTube token found to extract OAuth client from.")
            return None

        with open(yt_token_path) as f:
            yt_data = json.load(f)

        client_config = {
            "installed": {
                "client_id": yt_data["client_id"],
                "client_secret": yt_data["client_secret"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": yt_data["token_uri"],
                "redirect_uris": ["http://localhost"],
            }
        }

        flow = InstalledAppFlow.from_client_config(client_config, GMAIL_SCOPES)
        creds = flow.run_local_server(port=0)

        with open(GMAIL_TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
        print(f"  Gmail token saved to {GMAIL_TOKEN_PATH}")

    return creds


def send_email_gmail_api(subject, html_body, recipients):
    """Send email via Gmail API. Returns True on success."""
    creds = get_gmail_credentials()
    if not creds:
        return False

    try:
        from googleapiclient.discovery import build
    except ImportError:
        print("  WARNING: google-api-python-client not installed.")
        return False

    service = build("gmail", "v1", credentials=creds)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = "me"
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    result = service.users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()

    print(f"  Sent! Message ID: {result.get('id')}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Step 07: Send newsletter email")
    parser.add_argument("--date", default=today_str(), help="Date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Generate email but don't send")
    args = parser.parse_args()

    print(f"[07] Preparing newsletter email for {args.date}")

    digest = read_json("digest-content.json")
    media_status = read_json("media-status.json")

    if not digest:
        print("  ERROR: digest-content.json not found. Run 03_synthesize_content.py first.")
        sys.exit(1)

    subject = build_email_subject(digest)
    html_body = build_email_html(digest, media_status)

    print(f"  Subject: {subject}")
    print(f"  Recipients: {len(EMAIL_RECIPIENTS)}")
    print(f"  HTML body: {len(html_body)} chars")

    # Save email for reference
    email_data = {
        "date": args.date,
        "subject": subject,
        "recipients": EMAIL_RECIPIENTS,
        "html_body": html_body,
        "generated_at": datetime.now().isoformat(),
    }
    path = write_json("email-draft.json", email_data)
    print(f"  Saved draft to {path}")

    if args.dry_run:
        print("  DRY RUN | email not sent")
        preview_path = os.path.join(os.path.dirname(str(path)), "email-preview.html")
        with open(preview_path, "w", encoding="utf-8") as f:
            f.write(html_body)
        print(f"  Preview: {preview_path}")
        return

    # Primary: Send via Beehiiv (reaches all website subscribers)
    print("  Sending via Beehiiv...")
    beehiiv_sent = send_via_beehiiv(subject, html_body)

    # Fallback: Send via Gmail API to distribution list
    if not beehiiv_sent:
        print("  Falling back to Gmail API...")
        gmail_sent = send_email_gmail_api(subject, html_body, EMAIL_RECIPIENTS)
        if not gmail_sent:
            print("  Both Beehiiv and Gmail failed | draft saved to email-draft.json")


if __name__ == "__main__":
    main()
