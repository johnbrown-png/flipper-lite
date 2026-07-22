"""
Check YouTube video availability for videos in qa.csv or precomputed recommendations.

This script checks whether videos are still accessible on YouTube by querying the
YouTube Data API v3. It detects deleted, private, embedding-disabled, and region-restricted
videos.

Usage:
    python check_video_availability.py --source qa
    python check_video_availability.py --source precomputed
    python check_video_availability.py --source qa --output reports/availability_check.csv

Output files:
    - video_availability_report.csv: Full report with status for all videos
    - unavailable_videos.csv: Only videos that are unavailable (for quick action)
    - videos_to_delete_additions.csv: Videos to append to videos_to_delete.csv

API Quota Usage:
    - Batches 50 videos per request (1 quota unit per request)
    - ~110 requests for 5,500 videos = 110 quota units (well within 10,000/day limit)
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Set, Tuple

import pandas as pd
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# Project paths
PROJECT_ROOT = Path(__file__).parent
QA_CSV = PROJECT_ROOT / "qa" / "qa.csv"
PRECOMPUTED_CSV = PROJECT_ROOT / "precomputed_recommendations_flat_qa.csv"
VIDEOS_TO_DELETE_CSV = PROJECT_ROOT / "videos_to_delete" / "videos_to_delete.csv"


def clean_text(value: object) -> str:
    """Clean text value, handling None and nan."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    return "" if text.lower() in ("nan", "none", "") else text


def load_video_ids_from_qa(qa_path: Path) -> List[Dict[str, str]]:
    """
    Load video IDs from qa.csv current_1/2/3 columns.
    
    Returns:
        List of dicts with keys: video_id, video_title, channel, source_step, source_position
    """
    if not qa_path.exists():
        raise FileNotFoundError(f"QA file not found: {qa_path}")
    
    df = pd.read_csv(qa_path)
    videos = []
    
    for _, row in df.iterrows():
        small_step_id = clean_text(row.get("small_step_id", ""))
        small_step_name = clean_text(row.get("small_step_name", ""))
        
        # Check current_1, current_2, current_3
        for position in [1, 2, 3]:
            video_id = clean_text(row.get(f"current_{position}_video_id", ""))
            if video_id:
                videos.append({
                    "video_id": video_id,
                    "video_title": clean_text(row.get(f"current_{position}_video_title", "")),
                    "channel": clean_text(row.get(f"current_{position}_channel", "")),
                    "source_step": small_step_id,
                    "source_step_name": small_step_name,
                    "source_position": f"current_{position}",
                })
    
    return videos


def load_video_ids_from_precomputed(precomputed_path: Path) -> List[Dict[str, str]]:
    """
    Load video IDs from precomputed_recommendations_flat_qa.csv.
    
    Returns:
        List of dicts with keys: video_id, video_title, channel, source_step, source_position
    """
    if not precomputed_path.exists():
        raise FileNotFoundError(f"Precomputed file not found: {precomputed_path}")
    
    df = pd.read_csv(precomputed_path)
    videos = []
    
    for _, row in df.iterrows():
        video_id = clean_text(row.get("video_id", ""))
        if video_id:
            videos.append({
                "video_id": video_id,
                "video_title": clean_text(row.get("video_title", "") or row.get("title", "")),
                "channel": clean_text(row.get("channel", "")),
                "source_step": clean_text(row.get("small_step_id", "")),
                "source_step_name": clean_text(row.get("small_step_name", "")),
                "source_position": f"rank_{clean_text(row.get('rank', ''))}",
            })
    
    return videos


def deduplicate_videos(videos: List[Dict[str, str]]) -> Tuple[List[Dict[str, str]], int]:
    """
    Deduplicate videos by video_id, keeping first occurrence.
    
    Returns:
        (deduplicated_list, duplicate_count)
    """
    seen_ids: Set[str] = set()
    unique_videos = []
    duplicate_count = 0
    
    for video in videos:
        video_id = video["video_id"]
        if video_id not in seen_ids:
            seen_ids.add(video_id)
            unique_videos.append(video)
        else:
            duplicate_count += 1
    
    return unique_videos, duplicate_count


def batch_check_videos(youtube, video_ids: List[str]) -> Dict[str, Dict[str, any]]:
    """
    Check video availability in batches of 50 (YouTube API limit).
    
    Returns:
        Dict mapping video_id to status info:
        {
            'video_id': str,
            'status': 'available' | 'deleted' | 'private' | 'embedding_disabled' | 'unknown',
            'privacy_status': str,
            'embeddable': bool,
            'upload_status': str,
            'title': str (if available)
        }
    """
    BATCH_SIZE = 50
    results = {}
    
    for i in range(0, len(video_ids), BATCH_SIZE):
        batch = video_ids[i:i + BATCH_SIZE]
        batch_str = ",".join(batch)
        
        try:
            response = youtube.videos().list(
                part="status,snippet",
                id=batch_str,
                maxResults=50
            ).execute()
            
            # Process returned videos (these exist)
            returned_ids = set()
            for item in response.get("items", []):
                video_id = item["id"]
                returned_ids.add(video_id)
                
                status = item.get("status", {})
                snippet = item.get("snippet", {})
                
                privacy_status = status.get("privacyStatus", "unknown")
                embeddable = status.get("embeddable", True)
                upload_status = status.get("uploadStatus", "unknown")
                
                # Determine overall status
                if upload_status == "deleted":
                    overall_status = "deleted"
                elif privacy_status == "private":
                    overall_status = "private"
                elif not embeddable:
                    overall_status = "embedding_disabled"
                else:
                    overall_status = "available"
                
                results[video_id] = {
                    "video_id": video_id,
                    "status": overall_status,
                    "privacy_status": privacy_status,
                    "embeddable": embeddable,
                    "upload_status": upload_status,
                    "title": snippet.get("title", ""),
                }
            
            # Videos not returned are deleted/not found
            for video_id in batch:
                if video_id not in returned_ids:
                    results[video_id] = {
                        "video_id": video_id,
                        "status": "deleted",
                        "privacy_status": "deleted",
                        "embeddable": False,
                        "upload_status": "deleted",
                        "title": "",
                    }
            
            # Rate limiting - be respectful
            time.sleep(0.5)
            
        except HttpError as e:
            print(f"  ⚠️  API error for batch starting at index {i}: {e}")
            # Mark this batch as unknown
            for video_id in batch:
                if video_id not in results:
                    results[video_id] = {
                        "video_id": video_id,
                        "status": "api_error",
                        "privacy_status": "unknown",
                        "embeddable": False,
                        "upload_status": "unknown",
                        "title": "",
                    }
    
    return results


def merge_results(
    videos: List[Dict[str, str]], 
    api_results: Dict[str, Dict[str, any]]
) -> List[Dict[str, str]]:
    """
    Merge original video metadata with API check results.
    
    Returns:
        List of dicts with all original fields plus:
        - status
        - privacy_status
        - embeddable
        - upload_status
        - api_title (title from API, if different)
    """
    merged = []
    
    for video in videos:
        video_id = video["video_id"]
        api_data = api_results.get(video_id, {})
        
        merged_record = {
            **video,
            "status": api_data.get("status", "not_checked"),
            "privacy_status": api_data.get("privacy_status", "unknown"),
            "embeddable": api_data.get("embeddable", False),
            "upload_status": api_data.get("upload_status", "unknown"),
            "api_title": api_data.get("title", ""),
        }
        
        merged.append(merged_record)
    
    return merged


def save_full_report(results: List[Dict[str, str]], output_path: Path) -> None:
    """Save full availability report to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    df = pd.DataFrame(results)
    df.to_csv(output_path, index=False)
    print(f"  ✅ Full report saved: {output_path}")


def save_unavailable_report(results: List[Dict[str, str]], output_path: Path) -> None:
    """Save report of only unavailable videos."""
    unavailable = [r for r in results if r["status"] != "available"]
    
    if not unavailable:
        print(f"  ℹ️  No unavailable videos found - skipping {output_path.name}")
        return
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(unavailable)
    df.to_csv(output_path, index=False)
    print(f"  ⚠️  Unavailable videos report saved: {output_path} ({len(unavailable)} videos)")


def save_deletion_candidates(results: List[Dict[str, str]], output_path: Path) -> None:
    """
    Save videos that should be added to videos_to_delete.csv.
    Only includes deleted and private videos (not embedding_disabled).
    """
    candidates = [
        r for r in results 
        if r["status"] in ("deleted", "private")
    ]
    
    if not candidates:
        print(f"  ℹ️  No deletion candidates found - skipping {output_path.name}")
        return
    
    # Format for videos_to_delete.csv (video_id, video_title, channel)
    deletion_records = [
        {
            "video_id": r["video_id"],
            "video_title": r["video_title"],
            "channel": r["channel"],
        }
        for r in candidates
    ]
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(deletion_records)
    df.to_csv(output_path, index=False)
    print(f"  🗑️  Deletion candidates saved: {output_path} ({len(deletion_records)} videos)")


def print_summary(results: List[Dict[str, str]]) -> None:
    """Print summary statistics."""
    total = len(results)
    
    status_counts = {}
    for result in results:
        status = result["status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    
    print("\n" + "=" * 70)
    print("VIDEO AVAILABILITY CHECK SUMMARY")
    print("=" * 70)
    print(f"Total videos checked: {total}")
    print()
    print("Status breakdown:")
    
    status_emojis = {
        "available": "✅",
        "deleted": "❌",
        "private": "🔒",
        "embedding_disabled": "🚫",
        "api_error": "⚠️",
        "not_checked": "❓",
    }
    
    for status in sorted(status_counts.keys()):
        count = status_counts[status]
        emoji = status_emojis.get(status, "•")
        percentage = (count / total) * 100
        print(f"  {emoji} {status:20} {count:5} ({percentage:5.1f}%)")
    
    unavailable_count = sum(
        count for status, count in status_counts.items() 
        if status != "available"
    )
    
    print()
    if unavailable_count > 0:
        print(f"⚠️  ACTION REQUIRED: {unavailable_count} videos need attention")
    else:
        print("✅ All videos are available!")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Check YouTube video availability for Flipper videos"
    )
    parser.add_argument(
        "--source",
        choices=["qa", "precomputed"],
        default="qa",
        help="Source to check: 'qa' (qa.csv current videos) or 'precomputed' (all recommendations)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "video_availability_report.csv",
        help="Output path for full report CSV"
    )
    parser.add_argument(
        "--no-retry",
        action="store_true",
        help="Skip retry of failed videos"
    )
    
    args = parser.parse_args()
    
    # Setup
    load_dotenv()
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        print("❌ Error: YOUTUBE_API_KEY not found in .env file")
        sys.exit(1)
    
    youtube = build("youtube", "v3", developerKey=api_key)
    
    # Load videos
    print("\n" + "=" * 70)
    print(f"Loading videos from: {args.source}")
    print("=" * 70)
    
    if args.source == "qa":
        videos = load_video_ids_from_qa(QA_CSV)
        print(f"  Loaded {len(videos)} video entries from qa.csv")
    else:
        videos = load_video_ids_from_precomputed(PRECOMPUTED_CSV)
        print(f"  Loaded {len(videos)} video entries from precomputed recommendations")
    
    # Deduplicate
    videos, duplicate_count = deduplicate_videos(videos)
    print(f"  Unique videos: {len(videos)} (removed {duplicate_count} duplicates)")
    
    # Extract video IDs
    video_ids = [v["video_id"] for v in videos]
    
    # Check availability
    print("\n" + "=" * 70)
    print("Checking video availability via YouTube API...")
    print("=" * 70)
    print(f"  Videos to check: {len(video_ids)}")
    print(f"  API requests needed: ~{(len(video_ids) + 49) // 50} (batches of 50)")
    print()
    
    start_time = time.time()
    api_results = batch_check_videos(youtube, video_ids)
    elapsed = time.time() - start_time
    
    print(f"\n  ✅ API check completed in {elapsed:.1f} seconds")
    
    # Retry failed videos once
    if not args.no_retry:
        failed_ids = [
            vid for vid, result in api_results.items() 
            if result["status"] == "api_error"
        ]
        if failed_ids:
            print(f"\n  🔄 Retrying {len(failed_ids)} failed videos...")
            time.sleep(5)  # Wait before retry
            retry_results = batch_check_videos(youtube, failed_ids)
            api_results.update(retry_results)
    
    # Merge results
    merged_results = merge_results(videos, api_results)
    
    # Save reports
    print("\n" + "=" * 70)
    print("Saving reports...")
    print("=" * 70)
    
    # Full report
    save_full_report(merged_results, args.output)
    
    # Unavailable videos only
    unavailable_path = args.output.parent / f"unavailable_{args.output.name}"
    save_unavailable_report(merged_results, unavailable_path)
    
    # Deletion candidates
    deletion_path = args.output.parent / f"deletion_candidates_{args.output.name}"
    save_deletion_candidates(merged_results, deletion_path)
    
    # Print summary
    print_summary(merged_results)
    
    print(f"\nReport timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
