"""
Open a browser to NotebookLM, wait for login, and save cookies for notebooklm-py.
No interactive terminal needed — just closes when cookies are captured.
"""
import json
import os
import sys
import time

REQUIRED_COOKIES = {"SID", "HSID", "SSID", "APISID", "SAPISID",
                    "__Secure-1PSID", "__Secure-3PSID"}

def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    out_dir = os.path.expanduser("~/.notebooklm")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "storage_state.json")

    print("Opening browser to NotebookLM...")
    print("Log into your Google account if prompted.")
    print("The browser will close automatically once cookies are captured.\n")

    with sync_playwright() as p:
        # Use a persistent context so existing Edge profile sessions can be leveraged
        browser = p.chromium.launch(
            headless=False,
            channel="msedge",  # Use Edge if available
        )
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://notebooklm.google.com/", wait_until="domcontentloaded")

        print("Waiting for Google authentication cookies...")
        print("(If you see a login page, log in with your Google account)\n")

        # Poll for required cookies (check every 2 seconds, timeout 5 minutes)
        max_wait = 300
        elapsed = 0
        while elapsed < max_wait:
            cookies = context.cookies("https://notebooklm.google.com")
            all_cookies = context.cookies()
            google_cookies = [c for c in all_cookies if ".google.com" in (c.get("domain", ""))]
            found = {c["name"] for c in google_cookies} & REQUIRED_COOKIES

            if found == REQUIRED_COOKIES:
                print(f"All {len(REQUIRED_COOKIES)} required cookies captured!")

                # Save in storage_state format
                storage = context.storage_state()
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(storage, f, indent=2)

                try:
                    os.chmod(out_path, 0o600)
                except OSError:
                    pass

                print(f"Saved to {out_path}")
                browser.close()
                return

            if elapsed % 10 == 0:
                print(f"  Found {len(found)}/{len(REQUIRED_COOKIES)} cookies... "
                      f"({elapsed}s elapsed, waiting up to {max_wait}s)")

            time.sleep(2)
            elapsed += 2

        print(f"\nTIMEOUT: Only found {len(found)}/{len(REQUIRED_COOKIES)} required cookies.")
        print(f"Found: {found}")
        print(f"Missing: {REQUIRED_COOKIES - found}")

        # Save what we have anyway
        storage = context.storage_state()
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(storage, f, indent=2)
        print(f"Saved partial cookies to {out_path} (may not work)")

        browser.close()


if __name__ == "__main__":
    main()
