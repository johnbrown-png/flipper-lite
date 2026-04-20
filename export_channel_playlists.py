"""
Export all public playlists for a YouTube channel to CSV.

Output columns:
- channel_id
- channel_name
- playlist_id
- playlist_name
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urlparse

from dotenv import load_dotenv
from googleapiclient.discovery import build


def parse_input_channel(value: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (channel_id, handle) parsed from user input."""
    value = value.strip()

    if value.startswith("UC") and len(value) >= 24:
        return value, None

    if value.startswith("@"):
        return None, value[1:]

    if value.startswith("http://") or value.startswith("https://"):
        parsed = urlparse(value)
        path = parsed.path.rstrip("/")
        parts = [p for p in path.split("/") if p]

        if not parts:
            return None, None

        if parts[0].startswith("@"):
            return None, parts[0][1:]

        if parts[0] == "channel" and len(parts) > 1 and parts[1].startswith("UC"):
            return parts[1], None

        if parts[0] in {"c", "user"} and len(parts) > 1:
            return None, parts[1]

    return None, value


def resolve_channel_id(youtube, channel_input: str) -> str:
    """Resolve channel ID from channel URL, handle, or channel ID."""
    channel_id, handle = parse_input_channel(channel_input)
    if channel_id:
        return channel_id

    if not handle:
        raise ValueError("Could not parse channel input. Provide channel URL, @handle, or channel ID.")

    # Preferred path for modern channel handles.
    request = youtube.channels().list(part="id", forHandle=handle, maxResults=1)
    response = request.execute()
    items = response.get("items", [])
    if items:
        return items[0]["id"]

    # Fallback to channel search for custom URL names.
    search_request = youtube.search().list(
        part="snippet",
        q=handle,
        type="channel",
        maxResults=5,
    )
    search_response = search_request.execute()

    search_items = search_response.get("items", [])
    if not search_items:
        raise ValueError(f"No channel found for input: {channel_input}")

    return search_items[0]["snippet"]["channelId"]


def get_channel_name(youtube, channel_id: str) -> str:
    request = youtube.channels().list(part="snippet", id=channel_id, maxResults=1)
    response = request.execute()
    items = response.get("items", [])
    if not items:
        raise ValueError(f"Channel not found for ID: {channel_id}")
    return items[0]["snippet"]["title"]


def get_all_playlists(youtube, channel_id: str) -> List[Tuple[str, str]]:
    playlists: List[Tuple[str, str]] = []
    next_page_token: Optional[str] = None

    while True:
        request = youtube.playlists().list(
            part="id,snippet",
            channelId=channel_id,
            maxResults=50,
            pageToken=next_page_token,
        )
        response = request.execute()

        for item in response.get("items", []):
            playlist_id = item.get("id", "")
            playlist_name = item.get("snippet", {}).get("title", "")
            if playlist_id:
                playlists.append((playlist_id, playlist_name))

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    return playlists


def write_csv(
    output_path: Path,
    channel_id: str,
    channel_name: str,
    playlists: List[Tuple[str, str]],
) -> None:
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["channel_id", "channel_name", "playlist_id", "playlist_name"])

        for playlist_id, playlist_name in playlists:
            writer.writerow([channel_id, channel_name, playlist_id, playlist_name])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export all public playlists for a YouTube channel to CSV."
    )
    parser.add_argument(
        "channel",
        help="Channel URL, @handle, custom name, or channel ID (UC...).",
    )
    parser.add_argument(
        "--output",
        default="channel_playlists.csv",
        help="Output CSV path (default: channel_playlists.csv)",
    )

    args = parser.parse_args()

    load_dotenv()
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise ValueError("YOUTUBE_API_KEY not found in .env")

    youtube = build("youtube", "v3", developerKey=api_key)

    channel_id = resolve_channel_id(youtube, args.channel)
    channel_name = get_channel_name(youtube, channel_id)
    playlists = get_all_playlists(youtube, channel_id)

    output_path = Path(args.output)
    write_csv(output_path, channel_id, channel_name, playlists)

    print(f"Channel ID: {channel_id}")
    print(f"Channel Name: {channel_name}")
    print(f"Playlists exported: {len(playlists)}")
    print(f"CSV saved to: {output_path.resolve()}")


if __name__ == "__main__":
    main()
