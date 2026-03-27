"""
Step 07: Send the daily newsletter email.

Generates HTML email from digest-content.json and sends via Gmail API.
Falls back to saving a draft JSON if Gmail credentials aren't available.

Input:  pipeline/data/digest-content.json, pipeline/data/media-status.json
Output: Sent email (or email-draft.json if credentials missing)
"""

import argparse
import base64
import json
import sys
import os
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.config import EMAIL_RECIPIENTS, DIGEST_DIR, today_str, write_json, read_json

GMAIL_TOKEN_PATH = DIGEST_DIR / ".gmail_token.json"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def build_email_subject(digest):
    """Generate a hook-based email subject line."""
    summary = digest.get("summary", {})
    hook = summary.get("hook", "Daily Intelligence")

    # Shorten hook if needed
    if len(hook) > 40:
        hook = hook[:37] + "..."

    date_label = digest.get("date_label", digest["date"])
    return f"Koda Daily Digest — {hook} — {date_label}"


def build_email_html(digest, media_status):
    """Generate the newsletter email HTML body."""
    date_label = digest.get("date_label", digest["date"])
    date = digest.get("date", "")
    summary = digest.get("summary", {})
    hook = summary.get("hook", "Your daily AI intelligence briefing is ready.")
    markets = digest.get("markets", {})
    media = media_status.get("media", {}) if media_status else {}

    # Build briefs section
    briefs_html = ""
    for brief in summary.get("briefs", []):
        briefs_html += f"""<tr>
          <td style="padding:6px 12px;font-weight:700;color:#3B82F6;width:80px">{brief['label']}</td>
          <td style="padding:6px 12px;color:#CBD5E1">{brief['text']}</td>
        </tr>"""

    # Build market table
    market_rows = ""
    ticker_map = {"sp500": "S&P 500", "nasdaq": "NASDAQ", "btc": "Bitcoin",
                  "eth": "Ethereum", "oil": "Oil Brent", "sentiment": "Sentiment"}
    for key, label in ticker_map.items():
        data = markets.get(key, {})
        if isinstance(data, dict):
            price = data.get("price", data.get("value", "N/A"))
            change = data.get("change", data.get("label", ""))
            color = "#10B981" if "+" in str(change) else "#EF4444" if "-" in str(change) else "#94A3B8"
            market_rows += f"""<tr>
              <td style="padding:6px 12px;color:#E2E8F0;font-weight:600">{label}</td>
              <td style="padding:6px 12px;color:#E2E8F0;text-align:right">{price}</td>
              <td style="padding:6px 12px;color:{color};text-align:right">{change}</td>
            </tr>"""

    # Media buttons
    media_buttons = ""
    if media.get("podcast"):
        media_buttons += f"""<a href="https://www.koda.community/podcast-{date}.mp3"
          style="display:inline-block;padding:12px 24px;background:#8B5CF6;color:white;
          text-decoration:none;border-radius:8px;font-weight:700;margin:4px">
          Listen to Podcast</a>"""

    # Check for YouTube video
    video_result_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "youtube-result.json")
    if os.path.exists(video_result_path):
        try:
            with open(video_result_path, "r") as f:
                vr = json.load(f)
            yt_url = vr.get("url", "")
            if yt_url:
                media_buttons += f"""<a href="{yt_url}"
                  style="display:inline-block;padding:12px 24px;background:#EF4444;color:white;
                  text-decoration:none;border-radius:8px;font-weight:700;margin:4px">
                  Watch Video</a>"""
        except Exception:
            pass

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#0F172A;font-family:Arial,Helvetica,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;background:#1E293B">
  <tr><td style="padding:32px 24px;text-align:center;
    background:linear-gradient(135deg,#1E293B 0%,#312E81 100%)">
    <h1 style="margin:0;color:white;font-size:24px">Koda Intelligence</h1>
    <p style="margin:8px 0 0;color:#94A3B8;font-size:14px">{date_label}</p>
  </td></tr>

  <tr><td style="padding:24px">
    <p style="color:#E2E8F0;font-size:18px;font-weight:700;margin:0 0 12px">
      {hook}
    </p>
    <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #334155;border-radius:8px;overflow:hidden">
      {briefs_html}
    </table>
  </td></tr>

  <tr><td style="padding:0 24px 24px">
    <p style="color:#94A3B8;font-size:13px;text-transform:uppercase;letter-spacing:1px;margin:0 0 8px">Market Pulse</p>
    <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #334155;border-radius:8px;overflow:hidden">
      {market_rows}
    </table>
  </td></tr>

  <tr><td style="padding:0 24px;text-align:center">
    <a href="https://www.koda.community/morning-briefing-koda-{date}.html"
      style="display:inline-block;padding:14px 32px;background:linear-gradient(135deg,#3B82F6,#8B5CF6);
      color:white;text-decoration:none;border-radius:8px;font-weight:700;font-size:16px">
      READ THE FULL DIGEST</a>
  </td></tr>

  <tr><td style="padding:16px 24px;text-align:center">
    {media_buttons}
  </td></tr>

  <tr><td style="padding:24px;text-align:center;border-top:1px solid #334155">
    <p style="color:#64748B;font-size:12px;margin:0">
      Koda Intelligence | <a href="https://www.koda.community" style="color:#3B82F6">koda.community</a>
    </p>
  </td></tr>
</table>
</body></html>"""

    return html


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
        print("  DRY RUN — email not sent")
        preview_path = os.path.join(os.path.dirname(str(path)), "email-preview.html")
        with open(preview_path, "w", encoding="utf-8") as f:
            f.write(html_body)
        print(f"  Preview: {preview_path}")
        return

    # Send via Gmail API
    print("  Sending via Gmail API...")
    sent = send_email_gmail_api(subject, html_body, EMAIL_RECIPIENTS)
    if not sent:
        print("  Gmail API send failed — draft saved to email-draft.json")
        print("  To authorize Gmail send, run: python pipeline/07_send_email.py --date <date>")
        print("  (A browser window will open for one-time OAuth authorization)")


if __name__ == "__main__":
    main()
