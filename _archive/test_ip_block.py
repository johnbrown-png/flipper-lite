"""
Quick test to check if YouTube is blocking your IP address
"""

import os
from dotenv import load_dotenv
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import WebshareProxyConfig

# Load environment
load_dotenv()
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')

# Test video ID (a popular numberblocks video that definitely has captions)
TEST_VIDEO_ID = 'syzTUYdx9ss'  # Christmas Eve Excitment

def test_youtube_data_api():
    """Test if YouTube Data API is accessible"""
    print("\n" + "="*60)
    print("TEST 1: YouTube Data API (Official)")
    print("="*60)
    
    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        
        # Try to get video details
        request = youtube.videos().list(
            part='snippet',
            id=TEST_VIDEO_ID
        )
        response = request.execute()
        
        if response.get('items'):
            video_title = response['items'][0]['snippet']['title']
            print(f"✓ SUCCESS: API is working")
            print(f"  Retrieved: {video_title}")
            return True
        else:
            print(f"✗ FAILED: No data returned")
            return False
            
    except Exception as e:
        error_msg = str(e).lower()
        if 'quota' in error_msg:
            print(f"✗ FAILED: API quota exceeded")
            print(f"  (Not an IP block - just out of daily API quota)")
        else:
            print(f"✗ FAILED: {str(e)[:200]}")
        return False


def test_transcript_api():
    """Test if YouTube Transcript API (web scraping) is accessible"""
    print("\n" + "="*60)
    print("TEST 2: YouTube Transcript API (Web Scraping)")
    print("="*60)
    print("This is the API that gets blocked when you make too many requests")
    
    try:
        # Try to fetch transcript using the same method as your pipeline
        api = YouTubeTranscriptApi(
            proxy_config=WebshareProxyConfig(
                proxy_username="fuyxmmoi",
                proxy_password="8xdrwuvrznki",
            )
        )
        caption_data = api.fetch(TEST_VIDEO_ID)
        
        # Convert generator to list
        transcript = [{'text': seg.text, 'start': seg.start, 'duration': seg.duration} for seg in caption_data]
        
        if transcript and len(transcript) > 0:
            first_line = transcript[0]['text'][:50]
            print(f"✓ SUCCESS: Transcript API is working")
            print(f"  Retrieved {len(transcript)} caption segments")
            print(f"  First segment: {first_line}...")
            return True
        else:
            print(f"✗ FAILED: No transcript returned")
            return False
            
    except Exception as e:
        error_msg = str(e).lower()
        
        # Check for specific error types
        if 'too many requests' in error_msg or '429' in error_msg:
            print(f"✗ BLOCKED: Too many requests (Rate limited)")
            print(f"  → Wait a few hours before trying again")
            
        elif 'ip' in error_msg and 'block' in error_msg:
            print(f"✗ BLOCKED: IP address blocked")
            print(f"  → Your IP is blocked by YouTube")
            print(f"  → Solutions:")
            print(f"     1. Wait 2-6 hours")
            print(f"     2. Use a VPN")
            print(f"     3. Try from a different network")
            
        elif 'forbidden' in error_msg or '403' in error_msg:
            print(f"✗ BLOCKED: Access forbidden (likely IP block)")
            print(f"  → YouTube is blocking access from your IP")
            
        elif 'disabled' in error_msg or 'not available' in error_msg:
            print(f"⚠ WARNING: Test video has no captions (unusual)")
            print(f"  → This might not be an IP block")
            
        else:
            print(f"✗ FAILED: {str(e)[:200]}")
            
        print(f"\n  Full error: {str(e)}")
        return False


def main():
    print("\n" + "="*60)
    print("YouTube IP Block Test")
    print("="*60)
    print("Testing if YouTube is blocking requests from your IP...")
    
    # Check API key
    if not YOUTUBE_API_KEY:
        print("\n✗ ERROR: YOUTUBE_API_KEY not found in .env file")
        return
    
    # Run tests
    api_ok = test_youtube_data_api()
    transcript_ok = test_transcript_api()
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    if api_ok and transcript_ok:
        print("✓ All tests passed - Your IP is NOT blocked!")
        print("  You can safely run the caption extraction pipeline")
        
    elif api_ok and not transcript_ok:
        print("⚠ PARTIAL BLOCK: Transcript scraping is blocked")
        print("  → The official YouTube Data API works fine")
        print("  → But the transcript scraping API is blocked")
        print("  → This is the most common type of block")
        print("\n  RECOMMENDATION:")
        print("  1. Wait 2-6 hours before running caption extraction")
        print("  2. When you resume, use DELAY_BETWEEN_VIDEOS=5.0")
        print("  3. Consider using a VPN if blocking persists")
        
    elif not api_ok and transcript_ok:
        print("⚠ API QUOTA ISSUE")
        print("  → The official API is out of quota (not a block)")
        print("  → Transcript scraping still works")
        print("  → You can still extract captions (they use scraping)")
        
    else:
        print("✗ BOTH TESTS FAILED")
        print("  → This is unusual - check your internet connection")
        print("  → Or YouTube might be having issues")
    
    print("="*60 + "\n")


if __name__ == '__main__':
    main()
