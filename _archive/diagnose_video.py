"""
Diagnostic script to investigate why a specific video is not being extracted
Video: https://www.youtube.com/watch?v=SfxULALs_u8
"""

import os
import json
from pathlib import Path
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from dotenv import load_dotenv

def check_video_status(video_id, api_key, output_dir='captions_output'):
    """Check all possible reasons why a video might not be extracted"""
    
    print("=" * 70)
    print(f"DIAGNOSTIC REPORT FOR VIDEO: {video_id}")
    print(f"URL: https://www.youtube.com/watch?v={video_id}")
    print("=" * 70)
    
    # 1. Check if video is already downloaded
    print("\n1. CHECKING IF ALREADY DOWNLOADED")
    print("-" * 70)
    output_path = Path(output_dir)
    found_existing = []
    
    if output_path.exists():
        for json_file in output_path.rglob('*.json'):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data.get('video_id') == video_id:
                        found_existing.append(json_file)
                        print(f"✓ FOUND: {json_file}")
                        print(f"  Title: {data.get('title')}")
                        print(f"  Extracted: {data.get('extracted_at')}")
                        print(f"  Duration: {data.get('duration')} seconds")
            except:
                continue
    
    if found_existing:
        print(f"\n⚠ VIDEO ALREADY DOWNLOADED - Would be auto-excluded!")
        print(f"  Found in: {len(found_existing)} file(s)")
    else:
        print("✓ Video NOT yet downloaded - would NOT be excluded")
    
    # 2. Get video details from YouTube API
    print("\n2. CHECKING VIDEO DETAILS")
    print("-" * 70)
    try:
        youtube = build('youtube', 'v3', developerKey=api_key)
        request = youtube.videos().list(
            part='snippet,contentDetails,status',
            id=video_id
        )
        response = request.execute()
        
        if not response.get('items'):
            print("✗ VIDEO NOT FOUND on YouTube!")
            return
        
        video_data = response['items'][0]
        snippet = video_data['snippet']
        content_details = video_data['contentDetails']
        status = video_data['status']
        
        print(f"✓ Video found on YouTube")
        print(f"  Title: {snippet['title']}")
        print(f"  Channel: {snippet['channelTitle']}")
        print(f"  Channel ID: {snippet['channelId']}")
        print(f"  Published: {snippet['publishedAt']}")
        print(f"  Privacy Status: {status.get('privacyStatus')}")
        print(f"  Upload Status: {status.get('uploadStatus')}")
        
        # Parse duration
        duration_str = content_details['duration']
        import re
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
        if match:
            hours = int(match.group(1) or 0)
            minutes = int(match.group(2) or 0)
            seconds = int(match.group(3) or 0)
            total_seconds = hours * 3600 + minutes * 60 + seconds
            print(f"  Duration: {total_seconds} seconds ({minutes}m {seconds}s)")
        
        channel_id = snippet['channelId']
        channel_title = snippet['channelTitle']
        
    except Exception as e:
        print(f"✗ Error getting video details: {e}")
        return
    
    # 3. Check duration filter (default is 1200 seconds = 20 minutes)
    print("\n3. CHECKING DURATION FILTER")
    print("-" * 70)
    max_duration = 1200  # Default from caption_extractor.py
    print(f"  Max duration setting: {max_duration} seconds ({max_duration/60:.1f} minutes)")
    print(f"  Video duration: {total_seconds} seconds ({total_seconds/60:.1f} minutes)")
    
    if total_seconds <= max_duration:
        print(f"  ✓ PASS - Video would be included")
    else:
        print(f"  ✗ FAIL - Video would be EXCLUDED (too long!)")
        print(f"  ⚠ THIS IS WHY THE VIDEO IS NOT EXTRACTED!")
    
    # 4. Check if channel is in channels.csv
    print("\n4. CHECKING IF CHANNEL IS IN channels.csv")
    print("-" * 70)
    csv_path = 'channels.csv'
    
    if not Path(csv_path).exists():
        print(f"✗ channels.csv not found!")
        return
    
    import pandas as pd
    try:
        df = pd.read_csv(csv_path)
        channel_in_csv = channel_id in df['channel_id'].values
        
        if channel_in_csv:
            print(f"✓ Channel IS in channels.csv")
            channel_row = df[df['channel_id'] == channel_id].iloc[0]
            print(f"  Channel Name: {channel_row['channel_name']}")
            print(f"  Channel ID: {channel_row['channel_id']}")
        else:
            print(f"✗ Channel NOT in channels.csv!")
            print(f"  Channel: {channel_title} ({channel_id})")
            print(f"  ⚠ THIS IS WHY THE VIDEO IS NOT EXTRACTED!")
            print(f"\n  To extract this video, add this line to channels.csv:")
            print(f"  {channel_id},{channel_title}")
    except Exception as e:
        print(f"✗ Error reading channels.csv: {e}")
    
    # 5. Check if captions are available
    print("\n5. CHECKING CAPTION AVAILABILITY")
    print("-" * 70)
    try:
        api = YouTubeTranscriptApi()
        
        # Test with just 'en'
        try:
            transcript = api.fetch(video_id, ['en'])
            print(f"✓ Captions available with language=['en']")
            print(f"  Retrieved {len(transcript)} segments")
            print(f"  First segment: {transcript[0].text[:80]}...")
        except Exception as e:
            print(f"✗ Failed with ['en']: {type(e).__name__}")
            
            # Try with language variants
            try:
                transcript = api.fetch(video_id, ['en', 'en-US', 'en-GB', 'a.en'])
                print(f"✓ Captions available with language variants")
                print(f"  Retrieved {len(transcript)} segments")
            except Exception as e2:
                print(f"✗ No captions available: {type(e2).__name__}")
                print(f"  ⚠ THIS IS WHY THE VIDEO IS NOT EXTRACTED!")
    
    except Exception as e:
        print(f"✗ Error checking captions: {e}")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    issues_found = []
    
    if found_existing:
        issues_found.append("Video already downloaded (auto-excluded)")
    
    if total_seconds > max_duration:
        issues_found.append(f"Video too long ({total_seconds}s > {max_duration}s)")
    
    if not channel_in_csv:
        issues_found.append(f"Channel not in channels.csv")
    
    if issues_found:
        print("\n⚠ REASONS WHY VIDEO IS NOT EXTRACTED:")
        for i, issue in enumerate(issues_found, 1):
            print(f"  {i}. {issue}")
    else:
        print("\n✓ No issues found - video SHOULD be extracted")
        print("  If it's still not being extracted, there may be a runtime error.")


if __name__ == '__main__':
    load_dotenv()
    
    video_id = 'SfxULALs_u8'
    api_key = os.getenv('YOUTUBE_API_KEY')
    
    if not api_key or api_key == 'your_api_key_here':
        print("✗ Error: Please set YOUTUBE_API_KEY in .env file")
        exit(1)
    
    check_video_status(video_id, api_key)
