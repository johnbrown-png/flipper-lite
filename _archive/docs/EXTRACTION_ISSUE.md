# Video Extraction Issue - IP Blocked by YouTube

## Problem
The data pipeline is unable to extract captions from YouTube videos because **YouTube is blocking requests from your IP address**.

## Symptoms
- Pipeline runs successfully but extracts 0 videos
- Error message: `⚠ IP BLOCKED: YouTube is blocking requests from your IP`
- All videos show "✗ No captions" status

## Root Cause
YouTube's transcript API blocks IPs that:
1. Make too many requests in a short period
2. Originate from cloud providers (AWS, Azure, GCP, etc.)
3. Exhibit bot-like behavior patterns
4. Are flagged for suspicious activity

## Solutions (In Order of Ease)

### Solution 1: Wait and Retry (Easiest)
- **Wait 2-6 hours** before trying again
- YouTube's rate limits usually reset within a few hours
- Try extracting just 1-2 videos at a time instead of bulk extraction

### Solution 2: Change Network Connection
- Switch to a different network (e.g., mobile hotspot, different WiFi)
- Use a different internet connection that YouTube hasn't flagged
- Restart your router to potentially get a new IP address

### Solution 3: Use a VPN (Recommended)
- Install a VPN service and connect to a different location
- This gives you a fresh IP address that YouTube hasn't blocked
- Good VPN options: ProtonVPN (free tier), NordVPN, ExpressVPN

### Solution 4: Use Cookies/Proxy (Advanced)
The `youtube-transcript-api` library supports using browser cookies to authenticate:

1. Install cookies from your browser:
   ```bash
   pip install browser_cookie3
   ```

2. Modify [caption_extractor.py](data_pipeline/caption_extractor.py#L294):
   ```python
   # Instead of:
   api = YouTubeTranscriptApi()
   
   # Use cookies:
   import browser_cookie3
   cookies = browser_cookie3.chrome()  # or .firefox(), .edge()
   api = YouTubeTranscriptApi()
   caption_data = api.fetch(video_id, cookies=cookies)
   ```

3. Make sure you're logged into YouTube in your browser

See: [youtube-transcript-api IP ban workarounds](https://github.com/jdepoix/youtube-transcript-api?tab=readme-ov-file#working-around-ip-bans-requestblocked-or-ipblocked-exception)

### Solution 5: Manual Rate Limiting
Add delays between requests in the pipeline:

1. Modify [caption_extractor.py](data_pipeline/caption_extractor.py#L448) in `process_channel`:
   ```python
   import time
   
   for i, video in enumerate(videos, 1):
       # ... existing code ...
       caption_data = self.extract_caption(video['video_id'], verbose=verbose_mode)
       
       # Add delay between requests
       if i < len(videos):
           time.sleep(5)  # Wait 5 seconds between videos
   ```

2. Extract videos in smaller batches (use `--max-videos 1`)

## Testing
To verify if the issue is resolved:

```bash
# Test with a single video
python data_pipeline/run_pipeline.py --extract-only --max-videos 1

# If successful, try more videos
python data_pipeline/run_pipeline.py --extract-only --max-videos 5
```

## Current Status
- ✓ 47 videos already successfully extracted (from earlier runs)
- ✗ Currently unable to extract new videos due to IP block
- ✓ Code updated to show detailed error messages

## Workaround (Immediate)
You can still use the search system with the 47 videos already extracted:

```bash
# Build index from existing captions
python data_pipeline/run_pipeline.py --skip-extract

# Or launch the GUI
python launch_gui.py
```

## Notes
- For **Numberblocks**: 0 new videos available (all cached videos already downloaded)
- For **Khan Academy**: New videos available but blocked by IP restriction
- The API cache is working correctly and preventing redundant YouTube API calls
- This is a YouTube restriction, not a bug in the code

## Updated Code
The caption extractor has been updated to:
- ✓ Show detailed error messages for IP blocks
- ✓ Detect and report geo-blocking issues
- ✓ Provide helpful troubleshooting guidance
- ✓ Warn users immediately when IP is blocked

---
*Last Updated: 2026-01-22*
