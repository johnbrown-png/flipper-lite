"""
Test whether the YouTube Transcript API automatically maps 'en' to regional variants
or if we need to explicitly request them
"""

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound

def test_language_fallback(video_id, description):
    """Test different language code combinations"""
    print(f"\nTesting: {description}")
    print(f"Video ID: {video_id}")
    print("-" * 70)
    
    # Test 1: Only 'en'
    try:
        api = YouTubeTranscriptApi()
        transcript = api.fetch(video_id, ['en'])
        print(f"✓ ['en'] worked - {len(transcript)} segments")
    except NoTranscriptFound as e:
        print(f"✗ ['en'] failed: NoTranscriptFound")
        print(f"   Available: {e.transcript_data if hasattr(e, 'transcript_data') else 'unknown'}")
    except Exception as e:
        print(f"✗ ['en'] failed: {type(e).__name__}: {str(e)[:100]}")
    
    # Test 2: Only 'en-GB'
    try:
        api = YouTubeTranscriptApi()
        transcript = api.fetch(video_id, ['en-GB'])
        print(f"✓ ['en-GB'] worked - {len(transcript)} segments")
    except NoTranscriptFound as e:
        print(f"✗ ['en-GB'] failed: NoTranscriptFound")
    except Exception as e:
        print(f"✗ ['en-GB'] failed: {type(e).__name__}")
    
    # Test 3: Only 'en-US'
    try:
        api = YouTubeTranscriptApi()
        transcript = api.fetch(video_id, ['en-US'])
        print(f"✓ ['en-US'] worked - {len(transcript)} segments")
    except NoTranscriptFound as e:
        print(f"✗ ['en-US'] failed: NoTranscriptFound")
    except Exception as e:
        print(f"✗ ['en-US'] failed: {type(e).__name__}")
    
    # Test 4: Multiple fallbacks
    try:
        api = YouTubeTranscriptApi()
        transcript = api.fetch(video_id, ['en', 'en-US', 'en-GB', 'a.en'])
        print(f"✓ Multiple variants worked - {len(transcript)} segments")
    except Exception as e:
        print(f"✗ Multiple variants failed: {type(e).__name__}")


if __name__ == '__main__':
    print("=" * 70)
    print("LANGUAGE FALLBACK TESTING")
    print("=" * 70)
    
    # Test with videos from different sources
    test_videos = [
        ('SfxULALs_u8', 'Khan Academy (US-based)'),
        ('Zy2WENyyPtQ', 'Numberblocks (UK-based)'),
        ('ocWCzDAH5lI', 'Khan Academy Python'),
    ]
    
    for video_id, description in test_videos:
        test_language_fallback(video_id, description)
    
    print("\n" + "=" * 70)
    print("FINDINGS:")
    print("=" * 70)
    print("""
Based on the YouTube Transcript API documentation:
- When you request ['en'], it matches ANY English variant (en, en-US, en-GB, etc.)
- The language codes are hierarchical: 'en' is a base code that matches all variants
- Regional codes like 'en-US' and 'en-GB' are specific variants

HOWEVER, there may be edge cases where:
1. Videos have ONLY a regional code (e.g., only 'en-GB' but not 'en')
2. Auto-generated captions might use different coding (e.g., 'a.en')
3. Some videos might have manual captions in 'en-GB' and auto in 'en'

RECOMMENDATION:
Using ['en', 'en-US', 'en-GB', 'a.en'] provides better coverage and acts as
a fallback chain. The API will try them in order and return the first match.
This is a safety net that costs nothing and could prevent missing videos.
""")
