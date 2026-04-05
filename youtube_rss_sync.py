#!/usr/bin/env python3
"""
YouTube RSS -> NotebookLM Sync Tool

Parses YouTube RSS XML (from file or stdin) and outputs new videos
not yet in a NotebookLM notebook.

Two modes:
  1. Parse mode: parse RSS XML and output video list as JSON
     python youtube_rss_sync.py parse --xml-file rss.xml --since 2026-03-22

  2. Diff mode: compare RSS videos against known source titles
     python youtube_rss_sync.py diff --xml-file rss.xml --known-file sources.json --since 2026-03-22

No external dependencies (stdlib only).
RSS XML is fetched externally (via Firecrawl MCP or curl) and passed in.
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional


ATOM_NS = "http://www.w3.org/2005/Atom"
YT_NS = "http://www.youtube.com/xml/schemas/2015"


def parse_rss(xml_text: str) -> list[dict]:
    """Parse YouTube RSS XML into a list of video dicts."""
    root = ET.fromstring(xml_text)
    videos = []

    for entry in root.findall(f"{{{ATOM_NS}}}entry"):
        video_id_el = entry.find(f"{{{YT_NS}}}videoId")
        title_el = entry.find(f"{{{ATOM_NS}}}title")
        published_el = entry.find(f"{{{ATOM_NS}}}published")

        if video_id_el is None or title_el is None:
            continue

        video_id = video_id_el.text.strip()
        title = title_el.text.strip()
        published = published_el.text.strip() if published_el is not None else ""

        pub_date: Optional[datetime] = None
        if published:
            try:
                pub_date = datetime.fromisoformat(published.replace("Z", "+00:00"))
            except ValueError:
                pass

        videos.append({
            "video_id": video_id,
            "title": title,
            "published": published,
            "pub_date": pub_date,
            "url": f"https://www.youtube.com/watch?v={video_id}",
        })

    return videos


def filter_since(videos: list[dict], since_date: str) -> list[dict]:
    """Filter videos published on or after since_date (YYYY-MM-DD)."""
    cutoff = datetime.strptime(since_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return [v for v in videos if v.get("pub_date") and v["pub_date"] >= cutoff]


def cmd_parse(args: argparse.Namespace) -> None:
    """Parse RSS XML and output video list."""
    if args.xml_file == "-":
        xml_text = sys.stdin.read()
    else:
        with open(args.xml_file, "r", encoding="utf-8") as f:
            xml_text = f.read()

    videos = parse_rss(xml_text)

    if args.since:
        videos = filter_since(videos, args.since)

    output = [{
        "video_id": v["video_id"],
        "title": v["title"],
        "published": v["published"][:10] if v["published"] else "",
        "url": v["url"],
    } for v in videos]

    print(json.dumps(output, indent=2))


def cmd_diff(args: argparse.Namespace) -> None:
    """Diff RSS videos against known sources."""
    if args.xml_file == "-":
        xml_text = sys.stdin.read()
    else:
        with open(args.xml_file, "r", encoding="utf-8") as f:
            xml_text = f.read()

    videos = parse_rss(xml_text)

    if args.since:
        videos = filter_since(videos, args.since)

    # Load known sources (list of titles or video IDs)
    known_ids: set[str] = set()
    known_titles: set[str] = set()

    if args.known_file:
        with open(args.known_file, "r", encoding="utf-8") as f:
            known = json.load(f)
        for item in known:
            if isinstance(item, str):
                known_titles.add(item.lower())
            elif isinstance(item, dict):
                if "video_id" in item:
                    known_ids.add(item["video_id"])
                if "title" in item:
                    known_titles.add(item["title"].lower())
                if "url" in item:
                    # Extract video ID from URL
                    url = item["url"]
                    if "watch?v=" in url:
                        vid = url.split("watch?v=")[1].split("&")[0]
                        known_ids.add(vid)

    # Filter out known videos
    new_videos = []
    for v in videos:
        if v["video_id"] in known_ids:
            continue
        if v["title"].lower() in known_titles:
            continue
        new_videos.append(v)

    output = [{
        "video_id": v["video_id"],
        "title": v["title"],
        "published": v["published"][:10] if v["published"] else "",
        "url": v["url"],
    } for v in new_videos]

    if not output:
        print(json.dumps({"status": "up_to_date", "new_videos": []}))
    else:
        print(json.dumps({"status": "new_videos_found", "count": len(output), "new_videos": output}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="YouTube RSS sync helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Parse command
    parse_p = subparsers.add_parser("parse", help="Parse RSS XML to JSON")
    parse_p.add_argument("--xml-file", required=True, help="RSS XML file (or - for stdin)")
    parse_p.add_argument("--since", help="Filter by publish date (YYYY-MM-DD)")

    # Diff command
    diff_p = subparsers.add_parser("diff", help="Find new videos not in known sources")
    diff_p.add_argument("--xml-file", required=True, help="RSS XML file (or - for stdin)")
    diff_p.add_argument("--known-file", help="JSON file with known source titles/IDs")
    diff_p.add_argument("--since", help="Filter by publish date (YYYY-MM-DD)")

    args = parser.parse_args()

    if args.command == "parse":
        cmd_parse(args)
    elif args.command == "diff":
        cmd_diff(args)


if __name__ == "__main__":
    main()
