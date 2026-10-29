"""
Test script to check caption availability for a single video
"""

from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from youtube_transcript_api.proxies import WebshareProxyConfig

def test_video_captions(video_id):
    """Test caption extraction for a specific video"""
    print(f"Testing video ID: {video_id}")
    print(f"Video URL: https://www.youtube.com/watch?v={video_id}")
    print("-" * 70)
    
    try:
        # Fetch transcript directly
        print("\n" + "=" * 70)
        print("Attempting to fetch transcript...")
        print("=" * 70)
        
        # Create API instance and fetch transcript
        api = YouTubeTranscriptApi(
            proxy_config=WebshareProxyConfig(
                proxy_username="fuyxmmoi",
                proxy_password="8xdrwuvrznki",
            )
        )
        caption_data = api.fetch(video_id)
        
        print("✓ Found transcript!")
        
        print(f"\nTranscript details:")
        print(f"  Total segments: {len(caption_data)}")
        
        # Show first few lines
        print(f"\nFirst 5 caption segments:")
        print("-" * 70)
        for i, segment in enumerate(caption_data[:5], 1):
            print(f"{i}. [{segment.start:.2f}s] {segment.text}")
        
        # Show full text preview
        full_text = " ".join([item.text for item in caption_data[:20]])
        print(f"\nText preview (first 20 segments):")
        print("-" * 70)
        print(full_text[:500] + "..." if len(full_text) > 500 else full_text)
        
        print("\n" + "=" * 70)
        print("✓ SUCCESS - Captions extracted successfully!")
        print("=" * 70)
        
    except TranscriptsDisabled:
        print("\n✗ ERROR: Transcripts are disabled for this video")
    except NoTranscriptFound:
        print("\n✗ ERROR: No transcript found for this video")
    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {e}")

if __name__ == '__main__':
    # Test the specific video
    video_id = "bT7282PUKnY"
    test_video_captions(video_id)
