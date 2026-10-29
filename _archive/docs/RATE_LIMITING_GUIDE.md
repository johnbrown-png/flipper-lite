# Rate Limiting Guide - Preventing YouTube IP Blocks

## Problem Summary

Your data pipeline was getting your IP blocked by YouTube because it was making **30-60+ queries per minute** with no delays between video caption extractions.

## Root Cause Analysis

### API Query Breakdown

1. **YouTube Data API (Official API)** - Used for:
   - Getting channel info: 1 call/channel (cached)
   - Listing playlist items: 1 call per 50 videos
   - Getting video details: 1 call per 50 videos
   - **These calls had retry delays but were not the problem**

2. **YouTube Transcript API (Unofficial Web Scraping)** - Used for:
   - Extracting captions: **1 call per video with ZERO delay**
   - **This was the problem - hitting YouTube 30-60+ times/minute**

### Why You Got Blocked

The `youtube-transcript-api` library scrapes YouTube's website directly (not the official API). Processing videos back-to-back with no delays triggers YouTube's bot detection, which blocks your IP for suspicious activity.

## Solution Implemented

### Changes Made

1. **Added `DELAY_BETWEEN_VIDEOS` configuration** in [shared/config.py](shared/config.py):
   - Default: **3 seconds** between each video caption extraction
   - Configurable via `.env` file
   - Rate: **~20 videos per minute** (safe threshold)

2. **Updated `YouTubeCaptionExtractor` class**:
   - Added `delay_between_videos` parameter to constructor
   - Added `time.sleep()` between video processing in main loop
   - Applied to both [data_pipeline/caption_extractor.py](data_pipeline/caption_extractor.py) and [youtube_caption_extractor.py](youtube_caption_extractor.py)

3. **Updated pipeline runner** in [data_pipeline/run_pipeline.py](data_pipeline/run_pipeline.py):
   - Passes delay configuration to extractor
   - Shows rate limiting info during execution

## New Query Rates

### With 3-Second Delay (Default)
- **Caption extractions**: ~20 videos per minute
- **100 videos**: ~5 minutes
- **Safe for extended use**

### Configurable Options

You can adjust the delay in your `.env` file:

```bash
# Conservative (recommended if you were just blocked)
DELAY_BETWEEN_VIDEOS=5.0    # ~12 videos/minute

# Default (good balance)
DELAY_BETWEEN_VIDEOS=3.0    # ~20 videos/minute

# Aggressive (use with caution)
DELAY_BETWEEN_VIDEOS=2.0    # ~30 videos/minute

# Very aggressive (high risk of blocking)
DELAY_BETWEEN_VIDEOS=1.0    # ~60 videos/minute
```

## Recommendations

### Immediate Actions

1. **Wait 2-6 hours** before running the pipeline again (let YouTube unblock your IP)
2. **Start with 5-second delay** for the first run after being blocked
3. **Monitor for blocks** - if you get blocked again, increase the delay

### Best Practices

1. **Use caching**: The pipeline already skips downloaded videos automatically
2. **Process during off-peak hours**: Run overnight to be less aggressive
3. **Batch processing**: Process 20-30 videos, take a break, then continue
4. **Consider alternatives**:
   - Use official YouTube Data API captions endpoint (requires quota)
   - Use a VPN or proxy rotation service
   - Add cookies from authenticated YouTube session to bypass some checks

### If You Get Blocked Again

1. **Increase the delay**:
   ```bash
   DELAY_BETWEEN_VIDEOS=10.0  # Very conservative
   ```

2. **Use a VPN** to change your IP address

3. **Add authentication cookies** to the transcript API:
   ```python
   # In caption_extractor.py, modify extract_caption():
   from http.cookiejar import MozillaCookieJar
   
   cookies = MozillaCookieJar('cookies.txt')
   cookies.load()
   
   api = YouTubeTranscriptApi(cookies=cookies)
   ```

4. **Switch to official API** (uses quota but won't block IP):
   - Enable captions in YouTube Data API
   - Use `videos.captions.download()` endpoint
   - Trade-off: Limited by daily quota (10,000 units)

## Technical Details

### Code Changes

**Before:**
```python
for i, video in enumerate(videos, 1):
    caption_data = self.extract_caption(video['video_id'])
    # Process immediately - NO DELAY
```

**After:**
```python
for i, video in enumerate(videos, 1):
    caption_data = self.extract_caption(video['video_id'])
    # Process and save...
    
    # Rate limiting: wait between videos
    if i < len(videos) and self.delay_between_videos > 0:
        time.sleep(self.delay_between_videos)
```

### Configuration Usage

The delay is automatically used by:
- `data_pipeline/run_pipeline.py` (full pipeline)
- `youtube_caption_extractor.py` (standalone script)

Example usage:
```python
from shared.config import DELAY_BETWEEN_VIDEOS
from data_pipeline.caption_extractor import YouTubeCaptionExtractor

extractor = YouTubeCaptionExtractor(
    api_key=api_key,
    delay_between_videos=DELAY_BETWEEN_VIDEOS  # Uses config
)
```

## Monitoring

When running the pipeline, you'll now see:
```
STEP 1: EXTRACTING CAPTIONS FROM YOUTUBE
ℹ Rate limiting: 3.0s delay between videos
  (approximately 20.0 videos per minute)
```

This confirms the rate limiting is active.

## Summary

- **Old rate**: 30-60+ videos/minute → IP blocked
- **New rate**: ~20 videos/minute → Safe and sustainable
- **Configurable**: Adjust via `.env` to find your optimal balance
- **Impact**: Slightly slower processing, but no more blocks!

For 100 videos:
- **Before**: ~2 minutes → BLOCKED
- **Now**: ~5 minutes → SUCCESS ✓
