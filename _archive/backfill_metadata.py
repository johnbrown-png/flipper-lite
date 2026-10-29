"""
Backfill Script: Add Duration and is_song to Existing Caption Files

This script updates all existing caption JSON files to add:
1. duration: Video duration in seconds (from YouTube API)
2. is_song: Boolean flag indicating if video is a song (based on title analysis)

Run this once before re-running the chunking pipeline.
"""

import os
import json
import re
from pathlib import Path
from googleapiclient.discovery import build
from dotenv import load_dotenv

# Load environment
load_dotenv()
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')


def is_song_title(title: str) -> bool:
    """
    Determine if a video is likely a song based on title keywords
    
    Args:
        title: Video title
    
    Returns:
        True if title suggests it's a song
    """
    title_lower = title.lower()
    
    # Keywords that indicate songs
    song_keywords = [
        'song', 'sing', 'singing', 'music', 'musical',
        'rhyme', 'nursery rhyme', 'lullaby', 'melody',
        'anthem', 'tune', 'karaoke', '🎵', '🎶', '♪', '♫'
    ]
    
    return any(keyword in title_lower for keyword in song_keywords)


def parse_duration(duration_str: str) -> int:
    """
    Parse ISO 8601 duration to seconds
    
    Args:
        duration_str: ISO 8601 duration (e.g., PT1M30S)
    
    Returns:
        Duration in seconds
    """
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
    if match:
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        return hours * 3600 + minutes * 60 + seconds
    return 0


def get_video_durations(youtube, video_ids: list) -> dict:
    """
    Get durations for a batch of videos from YouTube API
    
    Args:
        youtube: YouTube API client
        video_ids: List of video IDs
    
    Returns:
        Dictionary mapping video_id to duration in seconds
    """
    durations = {}
    
    # Process in batches of 50 (API limit)
    for i in range(0, len(video_ids), 50):
        batch_ids = video_ids[i:i+50]
        
        try:
            request = youtube.videos().list(
                part='contentDetails',
                id=','.join(batch_ids)
            )
            response = request.execute()
            
            for item in response.get('items', []):
                video_id = item['id']
                duration_str = item['contentDetails']['duration']
                durations[video_id] = parse_duration(duration_str)
            
            print(f"  ✓ Fetched durations for batch {i//50 + 1} ({len(batch_ids)} videos)")
            
        except Exception as e:
            print(f"  ✗ Error fetching durations for batch {i//50 + 1}: {e}")
    
    return durations


def backfill_caption_files(captions_dir: Path, youtube):
    """
    Backfill all caption files with duration and is_song metadata
    
    Args:
        captions_dir: Directory containing caption files
        youtube: YouTube API client
    """
    # Find all caption JSON files
    json_files = list(captions_dir.rglob('*.json'))
    json_files = [f for f in json_files if not f.name.endswith('_chunked.json')]
    
    if not json_files:
        print("No caption files found!")
        return
    
    print(f"\n📄 Found {len(json_files)} caption files")
    print("=" * 60)
    
    # Collect all video IDs
    video_id_to_files = {}
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                video_id = data.get('video_id')
                if video_id:
                    if video_id not in video_id_to_files:
                        video_id_to_files[video_id] = []
                    video_id_to_files[video_id].append(json_file)
        except Exception as e:
            print(f"  ⚠ Error reading {json_file.name}: {e}")
    
    print(f"\n🎬 Found {len(video_id_to_files)} unique videos")
    
    # Fetch durations from YouTube API
    print("\n📡 Fetching video durations from YouTube API...")
    video_ids = list(video_id_to_files.keys())
    durations = get_video_durations(youtube, video_ids)
    
    print(f"\n✓ Retrieved {len(durations)} durations")
    
    # Update caption files
    print("\n📝 Updating caption files...")
    updated_count = 0
    skipped_count = 0
    
    for json_file in json_files:
        try:
            # Read file
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            video_id = data.get('video_id')
            title = data.get('title', '')
            
            # Check if already has both fields
            has_duration = 'duration' in data
            has_is_song = 'is_song' in data
            
            if has_duration and has_is_song:
                skipped_count += 1
                continue
            
            # Add duration
            if not has_duration and video_id in durations:
                data['duration'] = durations[video_id]
            
            # Add is_song
            if not has_is_song:
                data['is_song'] = is_song_title(title)
            
            # Write back
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            updated_count += 1
            
            if updated_count % 100 == 0:
                print(f"  ✓ Updated {updated_count} files...")
        
        except Exception as e:
            print(f"  ✗ Error updating {json_file.name}: {e}")
    
    print(f"\n" + "=" * 60)
    print(f"✅ BACKFILL COMPLETE!")
    print(f"  Updated: {updated_count} files")
    print(f"  Skipped (already had data): {skipped_count} files")
    print(f"  Total: {len(json_files)} files")
    print("=" * 60)


def main():
    """Main entry point"""
    print("=" * 60)
    print("METADATA BACKFILL SCRIPT")
    print("=" * 60)
    
    if not YOUTUBE_API_KEY:
        print("✗ ERROR: YOUTUBE_API_KEY not found in .env file")
        return
    
    # Initialize YouTube API
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    
    # Backfill caption files - check data/captions_output first (primary location)
    captions_dir = Path('data/captions_output')
    if not captions_dir.exists():
        captions_dir = Path('captions_output')
    
    if not captions_dir.exists():
        print(f"✗ ERROR: Directory not found: {captions_dir}")
        return
    
    backfill_caption_files(captions_dir, youtube)
    
    print("\n✅ Next steps:")
    print("  1. Open the GUI (launch_gui.py)")
    print("  2. Click 'Chunk Transcripts'")
    print("  3. Click 'Generate Embeddings'")
    print("  4. Click 'Build Search Index'")
    print("  5. Restart flipper.py to see new features!")


if __name__ == '__main__':
    main()
