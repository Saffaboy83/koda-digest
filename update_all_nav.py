"""Refresh Nav V2 component across ALL pages on koda.community.

Replaces nav HTML, CSS, and JS blocks using the canonical markers from
nav_component.py. Handles duplicate/corrupted markers by replacing from
first start to last end.

Usage:
    python update_all_nav.py            # Update all pages
    python update_all_nav.py --dry-run  # Preview without writing
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import NamedTuple

from nav_component import build_nav_v2

DIGEST_DIR = Path(__file__).resolve().parent

# ── Page definitions ──
# (glob_pattern, current_page, url_prefix, page_subtitle, page_icon)

PageSpec = NamedTuple(
    "PageSpec",
    [
        ("glob_pattern", str),
        ("current_page", str),
        ("url_prefix", str),
        ("page_subtitle", str),
        ("page_icon", str),
    ],
)

PAGE_SPECS: list[PageSpec] = [
    # Root: undated briefing
    PageSpec("morning-briefing-koda.html", "signal", "./", "The Signal", "bolt"),
    # Root: dated briefings
    PageSpec("morning-briefing-koda-????-??-??.html", "signal", "./", "The Signal", "bolt"),
    # Root: landing page
    PageSpec("index.html", "", "./", "", ""),
    # Editorial
    PageSpec("editorial/index.html", "editorial", "../", "Deep Dive", "explore"),
    PageSpec("editorial/????-??-??-*.html", "editorial", "../", "Deep Dive", "explore"),
    # Reviews
    PageSpec("reviews/index.html", "reviews", "../", "The Lab", "science"),
    PageSpec("reviews/????-??-??-*.html", "reviews", "../", "The Lab", "science"),
    # Pricing
    PageSpec("pricing/index.html", "pricing", "../", "Token Tracker", "monitoring"),
    # Benchmarks
    PageSpec("benchmarks/index.html", "benchmarks", "../", "Leaderboard", "trophy"),
    # Changelog
    PageSpec("changelog/index.html", "changelog", "../", "Pulse", "pulse_alert"),
    # Archive
    PageSpec("archive/index.html", "archive", "../", "The Vault", "lock_open"),
]

# Directories to skip entirely (already have correct nav)
SKIP_DIRS = {"dojo"}


def _build_share_url(filepath: Path) -> str:
    """Derive the public share URL from a file path."""
    rel = filepath.relative_to(DIGEST_DIR)
    return f"https://www.koda.community/{rel.as_posix()}"


def _replace_nav_html(html: str, new_nav: str) -> tuple[str, bool]:
    """Replace the nav HTML block between V2 markers.

    Handles corrupted files with duplicate start/end markers by replacing
    from the FIRST start marker to the LAST end marker.
    """
    start_marker = "<!-- koda-nav-v2-start -->"
    end_marker = "<!-- koda-nav-v2-end -->"

    first_start = html.find(start_marker)
    last_end = html.rfind(end_marker)

    if first_start == -1 or last_end == -1:
        return html, False

    # Replace from first start to end of last end marker
    after_end = last_end + len(end_marker)
    replaced = html[:first_start] + new_nav + html[after_end:]
    return replaced, True


def _replace_nav_css(html: str, new_css: str) -> tuple[str, bool]:
    """Replace the nav CSS block between V2 CSS markers."""
    pattern = r"/\* -- Koda Nav V2 -- \*/.*?/\* -- End Koda Nav V2 -- \*/"
    css_block = new_css.rstrip() + "\n/* -- End Koda Nav V2 -- */"
    new_html, count = re.subn(pattern, css_block, html, count=1, flags=re.DOTALL)
    return new_html, count > 0


def _replace_nav_js(html: str, new_js: str) -> tuple[str, bool]:
    """Replace the nav JS block between V2 JS markers."""
    pattern = r"<!-- koda-nav-v2-js-start -->.*?<!-- koda-nav-v2-js-end -->"
    new_html, count = re.subn(pattern, new_js, html, count=1, flags=re.DOTALL)
    return new_html, count > 0


def update_file(
    filepath: Path,
    current_page: str,
    url_prefix: str,
    page_subtitle: str,
    page_icon: str,
    dry_run: bool,
) -> str:
    """Update a single file's nav. Returns status string."""
    html = filepath.read_text(encoding="utf-8")
    rel_path = filepath.relative_to(DIGEST_DIR).as_posix()

    # Check for V2 markers
    has_nav_markers = "koda-nav-v2-start" in html
    has_css_markers = "/* -- Koda Nav V2 -- */" in html and "/* -- End Koda Nav V2 -- */" in html
    has_js_markers = "koda-nav-v2-js-start" in html

    if not has_nav_markers:
        return f"  SKIP (no nav markers): {rel_path}"

    if not has_css_markers:
        return f"  SKIP (no CSS markers): {rel_path}"

    if not has_js_markers:
        return f"  SKIP (no JS markers): {rel_path}"

    share_url = _build_share_url(filepath)

    # Extract date for briefing pages (enables date picker in nav)
    date_picker_date = ""
    if current_page == "signal":
        import re as _re
        m = _re.search(r"(\d{4}-\d{2}-\d{2})", filepath.name)
        if m:
            date_picker_date = m.group(1)
        else:
            # Undated briefing (morning-briefing-koda.html) — use today
            from datetime import date
            date_picker_date = date.today().isoformat()

    css, nav_html, nav_js = build_nav_v2(
        current_page=current_page,
        url_prefix=url_prefix,
        page_subtitle=page_subtitle,
        page_icon=page_icon,
        share_url=share_url,
        date_picker_date=date_picker_date,
    )

    # Replace nav HTML (handles duplicates)
    html, html_ok = _replace_nav_html(html, nav_html)
    if not html_ok:
        return f"  WARN (nav HTML replace failed): {rel_path}"

    # Replace CSS
    html, css_ok = _replace_nav_css(html, css)
    if not css_ok:
        return f"  WARN (CSS replace failed): {rel_path}"

    # Replace JS
    html, js_ok = _replace_nav_js(html, nav_js)
    if not js_ok:
        return f"  WARN (JS replace failed): {rel_path}"

    if dry_run:
        return f"  WOULD UPDATE: {rel_path}"

    filepath.write_text(html, encoding="utf-8")
    return f"  UPDATED: {rel_path}"


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("=== DRY RUN MODE (no files will be modified) ===\n")
    else:
        print("=== Updating Nav V2 across all pages ===\n")

    updated = 0
    skipped = 0
    warned = 0
    total = 0

    for spec in PAGE_SPECS:
        files = sorted(DIGEST_DIR.glob(spec.glob_pattern))
        if not files:
            continue

        # Section header
        section = spec.glob_pattern.split("/")[0] if "/" in spec.glob_pattern else "root"
        print(f"[{section}] {spec.glob_pattern} ({len(files)} file(s))")

        for filepath in files:
            # Safety: skip files in excluded directories
            if any(part in SKIP_DIRS for part in filepath.relative_to(DIGEST_DIR).parts):
                status = f"  SKIP (excluded dir): {filepath.relative_to(DIGEST_DIR).as_posix()}"
                skipped += 1
            else:
                status = update_file(
                    filepath,
                    current_page=spec.current_page,
                    url_prefix=spec.url_prefix,
                    page_subtitle=spec.page_subtitle,
                    page_icon=spec.page_icon,
                    dry_run=dry_run,
                )

                if "UPDATED" in status or "WOULD UPDATE" in status:
                    updated += 1
                elif "SKIP" in status:
                    skipped += 1
                elif "WARN" in status:
                    warned += 1

            total += 1
            print(status)

        print()

    # Summary
    print("=" * 50)
    print(f"Total files scanned: {total}")
    if dry_run:
        print(f"  Would update: {updated}")
    else:
        print(f"  Updated:      {updated}")
    print(f"  Skipped:      {skipped}")
    if warned:
        print(f"  Warnings:     {warned}")
    print("=" * 50)


if __name__ == "__main__":
    main()
