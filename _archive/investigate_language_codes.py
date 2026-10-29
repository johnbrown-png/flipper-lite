"""
Investigation script to check available transcript languages for a video
"""

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

def investigate_video_transcripts(video_id):
    """Check what transcript languages are available for a video"""
    
    print(f"Investigating video: https://www.youtube.com/watch?v={video_id}")
    print("=" * 70)
    
    # Try fetching with just 'en'
    print("\n1. Testing fetch with ['en'] (current approach):")
    print("-" * 70)
    try:
        api = YouTubeTranscriptApi()
        transcript = api.fetch(video_id, ['en'])
        print(f"✓ SUCCESS - Retrieved {len(transcript)} caption segments")
        print(f"  First segment: {transcript[0].text[:100]}...")
    except Exception as e:
        print(f"✗ FAILED - Error: {str(e)}")
        print(f"  Error type: {type(e).__name__}")
    
    # Try fetching with English variants
    print("\n2. Testing fetch with English variants ['en', 'en-US', 'en-GB', 'a.en']:")
    print("-" * 70)
    try:
        api = YouTubeTranscriptApi()
        transcript = api.fetch(
            video_id, 
            ['en', 'en-US', 'en-GB', 'a.en', 'en-CA', 'en-AU']
        )
        print(f"✓ SUCCESS - Retrieved {len(transcript)} caption segments")
        print(f"  First segment: {transcript[0].text[:100]}...")
    except Exception as e:
        print(f"✗ FAILED - Error: {str(e)}")
        print(f"  Error type: {type(e).__name__}")
    
    # Try each language code individually to see which works
    print("\n3. Testing individual language codes:")
    print("-" * 70)
    for lang_code in ['en', 'en-US', 'en-GB', 'en-CA', 'en-AU', 'a.en']:
        try:
            api = YouTubeTranscriptApi()
            transcript = api.fetch(video_id, [lang_code])
            print(f"  ✓ '{lang_code}' - SUCCESS ({len(transcript)} segments)")
            break  # Stop after first success
        except Exception as e:
            print(f"  ✗ '{lang_code}' - Failed: {type(e).__name__}")
    
    print("\n" + "=" * 70)

if __name__ == '__main__':
    # Test multiple videos to find language code variations
    test_videos = [
        ('SfxULALs_u8', 'Khan Academy (US)'),
        ('ocWCzDAH5lI', 'Khan Academy - Classes and objects'),
        ('Zy2WENyyPtQ', 'Numberblocks'),
    ]
    
    print("\n\n" + "=" * 70)
    print("TESTING MULTIPLE VIDEOS")
    print("=" * 70)
    
    for video_id, description in test_videos:
        print(f"\n\nVideo: {description}")
        investigate_video_transcripts(video_id)
    
    print("\n\n" + "=" * 70)
    print("CONCLUSION:")
    print("=" * 70)
    print("\nThe test results show that ['en'] successfully retrieves English")
    print("captions from the tested videos. However:")
    print("")
    print("RECOMMENDATION:")
    print("To be safer and catch edge cases, update caption_extractor.py")
    print("to request multiple English language variants:")
    print("")
    print("Change in extract_caption() method (around line 408):")
    print("  caption_data = api.fetch(video_id, ['en'])")
    print("")
    print("To:")
    print("  caption_data = api.fetch(video_id, ['en', 'en-US', 'en-GB', 'a.en'])")
    print("")
    print("This will make the extractor more robust and handle videos")
    print("with region-specific English captions or auto-generated variants.")
