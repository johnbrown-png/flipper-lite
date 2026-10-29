"""
List video IDs from the video inventory or API cache

Usage:
  python list_video_ids.py                  # List first 20 video IDs from inventory
  python list_video_ids.py --limit 50       # List first 50 video IDs
  python list_video_ids.py --search math    # Search for videos with 'math' in title
  python list_video_ids.py --random 10      # Show 10 random video IDs
  python list_video_ids.py --source api_cache  # Use API cache instead of inventory
"""

import json
import csv
import argparse
import random
from pathlib import Path


def load_from_inventory(inventory_file='video_inventory.csv'):
    """Load videos from video_inventory.csv"""
    inventory_path = Path(inventory_file)
    if not inventory_path.exists():
        raise FileNotFoundError(f"Video inventory not found: {inventory_file}")
    
    videos = []
    with open(inventory_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            video_id = row.get('video_id', '').strip()
            if not video_id:
                continue
            
            videos.append({
                'video_id': video_id,
                'title': row.get('title', ''),
                'channel': row.get('channel', ''),
                'duration': int(row.get('duration', 0)) if row.get('duration', '').isdigit() else 0
            })
    
    return videos


def load_from_api_cache(cache_file='data/api_cache.json'):
    """Load videos from API cache"""
    cache_path = Path(cache_file)
    if not cache_path.exists():
        raise FileNotFoundError(f"API cache not found: {cache_file}")
    
    with open(cache_path, 'r', encoding='utf-8') as f:
        cache = json.load(f)
    
    # Collect all videos
    videos = []
    for key, video_list in cache.get('videos', {}).items():
        if isinstance(video_list, list):
            videos.extend(video_list)
    
    return videos


def main():
    parser = argparse.ArgumentParser(description='List video IDs from inventory or API cache')
    parser.add_argument('--limit', type=int, default=20, help='Number of videos to show')
    parser.add_argument('--search', type=str, help='Search term for video titles')
    parser.add_argument('--random', type=int, help='Show N random videos')
    parser.add_argument('--channel', type=str, help='Filter by channel name')
    parser.add_argument('--source', choices=['inventory', 'api_cache'], default='inventory',
                       help='Video source (default: inventory)')
    parser.add_argument('--inventory', default='video_inventory.csv', help='Video inventory file path')
    parser.add_argument('--api-cache', default='data/api_cache.json', help='API cache file path')
    
    args = parser.parse_args()
    
    # Load videos from selected source
    try:
        if args.source == 'inventory':
            all_videos = load_from_inventory(args.inventory)
            source_name = f"inventory ({args.inventory})"
        else:
            all_videos = load_from_api_cache(args.api_cache)
            source_name = f"API cache ({args.api_cache})"
    except Exception as e:
        print(f"❌ Error loading videos: {e}")
        return 1
    
    if not all_videos:
        print(f"❌ No videos found in {source_name}")
        return 1
    
    print(f"📹 Found {len(all_videos)} total videos in {source_name}\n")
    
    # Apply filters
    filtered_videos = all_videos
    
    if args.search:
        search_term = args.search.lower()
        filtered_videos = [v for v in filtered_videos if search_term in v.get('title', '').lower()]
        print(f"🔍 Filtered to {len(filtered_videos)} videos matching '{args.search}'\n")
    
    if args.channel:
        channel_term = args.channel.lower()
        filtered_videos = [v for v in filtered_videos if channel_term in v.get('channel', '').lower()]
        print(f"📺 Filtered to {len(filtered_videos)} videos from channels matching '{args.channel}'\n")
    
    # Select videos to show
    if args.random:
        if len(filtered_videos) > args.random:
            display_videos = random.sample(filtered_videos, args.random)
        else:
            display_videos = filtered_videos
        print(f"🎲 Showing {len(display_videos)} random videos:\n")
    else:
        display_videos = filtered_videos[:args.limit]
        print(f"Showing first {len(display_videos)} videos:\n")
    
    # Display videos
    print("=" * 80)
    for i, video in enumerate(display_videos, 1):
        video_id = video.get('video_id', 'N/A')
        title = video.get('title', 'No title')
        duration = video.get('duration', 0)
        
        # Truncate long titles
        if len(title) > 60:
            title = title[:57] + '...'
        
        print(f"{i:3}. {video_id:15} | {duration:4}s | {title}")
    
    print("=" * 80)
    print(f"\n💡 To score specific videos, use:")
    print(f"   python score_instruction_quality.py --video-ids {display_videos[0]['video_id']}")
    
    if len(display_videos) > 1:
        print(f"   python score_instruction_quality.py --video-ids {display_videos[0]['video_id']} {display_videos[1]['video_id']}")
    
    return 0


if __name__ == '__main__':
    exit(main())
