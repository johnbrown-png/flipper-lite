"""
Export Video Inventory to CSV

This script generates a CSV report of all video holdings with the following columns:
- video_id: YouTube video ID
- channel: Channel name
- title: Video title
- language: Language code
- is_song: Boolean flag indicating if video is a song
- duration: Total video duration in seconds

Usage (from the project root): python acquisition/export_video_inventory.py
Output: video_inventory/video_inventory.csv (read by precompute and the QA GUI)
"""

import os
import csv
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def format_duration(seconds: int) -> str:
    """
    Format duration in seconds to HH:MM:SS
    
    Args:
        seconds: Duration in seconds (None will be treated as 0)
    
    Returns:
        Formatted duration string (HH:MM:SS)        from search_app.curriculum_assistant import CurriculumAssistant
        assistant = CurriculumAssistant()
        results = assistant.search("multiplication carrying", top_k=5)        from search_app.curriculum_assistant import CurriculumAssistant
        assistant = CurriculumAssistant()
        results = assistant.search("multiplication carrying", top_k=5)
    """
    # Handle None values
    if seconds is None:
        seconds = 0
    seconds = int(seconds)
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def get_channel_from_path(file_path: Path) -> str:
    """
    Extract channel name from file path
    
    Args:
        file_path: Path to caption JSON file
    
    Returns:
        Channel name (folder name)
    """
    # The parent directory is the channel name
    return file_path.parent.name


def load_channels_mapping(channels_csv: Path) -> dict:
    """
    Load channel ID to name mapping from channels.csv
    
    Args:
        channels_csv: Path to channels.csv file
    
    Returns:
        Dictionary mapping channel_id to channel_name
    """
    mapping = {}
    if channels_csv.exists():
        try:
            with open(channels_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    mapping[row['channel_id']] = row['channel_name']
        except Exception as e:
            print(f"⚠ Warning: Could not read channels.csv: {e}")
    return mapping


def export_video_inventory():
    """
    Export video inventory to CSV
    """
    print("=" * 70)
    print("VIDEO INVENTORY EXPORT")
    print("=" * 70)
    
    # Find all caption files - check data/captions_output first (primary location)
    captions_dir = PROJECT_ROOT / 'data' / 'captions_output'
    if not captions_dir.exists():
        captions_dir = PROJECT_ROOT / 'captions_output'
    
    if not captions_dir.exists():
        print(f"✗ ERROR: Caption directory not found: {captions_dir}")
        return
    
    json_files = list(captions_dir.rglob('*.json'))
    json_files = [f for f in json_files if not f.name.endswith('_chunked.json')]
    
    if not json_files:
        print("✗ ERROR: No caption files found!")
        return
    
    print(f"\n📄 Found {len(json_files)} video caption files")
    
    # Load channel mapping (optional)
    channels_mapping = load_channels_mapping(PROJECT_ROOT / 'channels.csv')
    
    # Collect video data
    print("\n📊 Processing video data...")
    videos = []
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract channel name from folder structure
            channel = get_channel_from_path(json_file)
            
            # Get video metadata
            duration = data.get('duration') or 0  # Convert None to 0
            video_data = {
                'video_id': data.get('video_id', ''),
                'channel': channel,
                'title': data.get('title', ''),
                'language': data.get('language', ''),
                'is_song': data.get('is_song', False),
                'duration_seconds': duration,
                'duration_formatted': format_duration(duration)
            }
            
            videos.append(video_data)
            
        except Exception as e:
            print(f"  ⚠ Error processing {json_file.name}: {e}")
    
    # Sort by channel, then title
    videos.sort(key=lambda x: (x['channel'], x['title']))
    
    print(f"✓ Processed {len(videos)} videos")
    
    # Write CSV
    output_file = PROJECT_ROOT / 'video_inventory' / 'video_inventory.csv'
    output_file.parent.mkdir(exist_ok=True)
    print(f"\n💾 Writing to {output_file}...")
    
    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'video_id',
                'channel',
                'title',
                'language',
                'is_song',
                'duration_seconds',
                'duration_formatted'
            ]
            
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(videos)
        
        print(f"✅ SUCCESS!")
        print(f"\n📈 Summary:")
        print(f"  Total videos: {len(videos)}")
        print(f"  Unique channels: {len(set(v['channel'] for v in videos))}")
        print(f"  Songs: {sum(1 for v in videos if v['is_song'])}")
        print(f"  Non-songs: {sum(1 for v in videos if not v['is_song'])}")
        print(f"  Total duration: {format_duration(sum(v['duration_seconds'] for v in videos))}")
        print(f"\n📁 Output file: {output_file.absolute()}")
        
        # Show sample by channel
        print(f"\n📊 Videos by channel:")
        channel_counts = {}
        for video in videos:
            channel = video['channel']
            channel_counts[channel] = channel_counts.get(channel, 0) + 1
        
        for channel, count in sorted(channel_counts.items()):
            print(f"  {channel}: {count} videos")
        
    except Exception as e:
        print(f"✗ ERROR writing CSV: {e}")
        return
    
    print("\n" + "=" * 70)
    print("✅ Export complete! You can now open video_inventory.csv")
    print("=" * 70)


if __name__ == '__main__':
    export_video_inventory()
