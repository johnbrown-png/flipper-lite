# Bot Detection Prevention Guide

## What Was Changed

Your data pipeline has been updated with **aggressive anti-bot detection measures** to prevent YouTube IP blocking.

## Key Improvements

### 1. **Randomized Delays** 🎲
- **Before**: Fixed 3-second delay between videos (predictable bot pattern)
- **After**: Random 8-15 second delays (mimics human behavior)
- Makes request timing unpredictable and less detectable

### 2. **Session Breaks** ☕
- **New Feature**: Automatic breaks every 5 videos
- Pauses for 1-3 minutes between batches
- Prevents sustained high-velocity requests that trigger bot detection

### 3. **Smaller Processing Batches** 📦
- **Before**: 100 videos per channel
- **After**: 20 videos per channel (default)
- Process in smaller chunks to reduce risk

### 4. **API Call Rate Limiting** ⏱️
- Added 1-3 second random delays between pagination requests
- Prevents burst traffic patterns to YouTube Data API

## New Configuration Settings

In [shared/config.py](shared/config.py):

```python
# Conservative defaults to prevent IP blocking
MAX_VIDEOS_PER_CHANNEL = 20  # Reduced from 100

# Randomized delays (8-15 seconds) instead of fixed delays
RANDOM_DELAY_MIN = 8.0   # Minimum delay in seconds
RANDOM_DELAY_MAX = 15.0  # Maximum delay in seconds

# Session breaks
VIDEOS_PER_BATCH = 5          # Process this many videos before break
BREAK_DURATION_MIN = 60.0     # Minimum 1-minute break
BREAK_DURATION_MAX = 180.0    # Maximum 3-minute break
```

## How It Works Now

When you run the pipeline:

1. **Process video 1-5**: Random 8-15s delay between each
2. **Session break**: Pause 1-3 minutes
3. **Process video 6-10**: Random 8-15s delay between each
4. **Session break**: Pause 1-3 minutes
5. Continue until reaching 20 videos (or your configured limit)

## Customizing for Your Needs

### More Aggressive (Even Safer)
```python
# In .env file or config.py
RANDOM_DELAY_MIN=15.0
RANDOM_DELAY_MAX=30.0
VIDEOS_PER_BATCH=3
MAX_VIDEOS_PER_CHANNEL=10
```

### Less Conservative (Riskier, but faster)
```python
# Only if you have good IP reputation
RANDOM_DELAY_MIN=5.0
RANDOM_DELAY_MAX=10.0
VIDEOS_PER_BATCH=10
MAX_VIDEOS_PER_CHANNEL=30
```

## What Triggers Bot Detection

Based on your case and YouTube's behavior:

### High Risk Factors 🔴
1. **Burst traffic**: Processing many videos in rapid succession
2. **Predictable timing**: Same delay between every request
3. **Same channel repeatedly**: Scraping entire playlists at once
4. **No breaks**: Continuous activity without pauses
5. **Datacenter IPs**: Cloud provider IPs are heavily monitored

### Medium Risk Factors 🟡
1. **Using unofficial transcript API**: `youtube_transcript_api` is monitored
2. **No user agent variety**: Default headers look automated
3. **High volume in short time**: >20 videos per session

### Low Risk Factors 🟢
1. **Official YouTube Data API**: Using API key (you're doing this ✓)
2. **Caching**: Reducing redundant requests (you have this ✓)
3. **Error handling**: Backing off on rate limits (you have this ✓)

## Running After IP Block

If your IP was blocked:

1. **Wait 6-24 hours** before trying again
2. **Use VPN/different network** if you need immediate access
3. **Start with smallest batch**:
   ```python
   MAX_VIDEOS_PER_CHANNEL=5
   VIDEOS_PER_BATCH=2
   ```
4. **Monitor console output** for "IP blocked" warnings

## Performance Impact

- **Before**: ~20 videos/minute (risky)
- **After**: ~3-4 videos/minute (safe)

Example timeline for 20 videos:
- Video processing: 20 videos
- Delays: ~230 seconds (8-15s × 20)
- Breaks: ~360 seconds (3 breaks × 1-3 min)
- **Total time**: ~10-15 minutes for 20 videos

## Console Output Changes

You'll now see:
```
[1/20] Video title... ✓
  ⏱ Waiting 12.3s...
[2/20] Video title... ✓
  ⏱ Waiting 9.7s...
...
[5/20] Video title... ✓
  ☕ Taking session break (2.1 minutes) to avoid bot detection...
  ✓ Resuming extraction...
[6/20] Video title... ✓
```

## Additional Recommendations

### 1. Spread Processing Over Time
Instead of processing 100 videos at once:
- Day 1: Process 20 videos
- Day 2: Process 20 more videos
- Etc.

### 2. Use Multiple API Keys
Rotate between different Google Cloud projects (each has its own quota)

### 3. Proxy/VPN Rotation
For large-scale extraction, consider rotating IPs between batches

### 4. Process Different Channels
Avoid processing the same channel repeatedly in one session

## Troubleshooting

### Still Getting Blocked?
1. Increase `RANDOM_DELAY_MIN` to 20 seconds
2. Reduce `VIDEOS_PER_BATCH` to 2-3
3. Reduce `MAX_VIDEOS_PER_CHANNEL` to 10
4. Switch networks/use VPN

### Too Slow?
Current settings are conservative. Only increase speed if:
- You haven't been blocked in multiple sessions
- You're using residential IP (not cloud/VPN)
- You're processing <50 videos total per day

### Error Messages
- `"IP BLOCKED"`: Wait 12-24 hours, use VPN
- `"quotaExceeded"`: YouTube API quota limit (resets midnight PT)
- `"rateLimitExceeded"`: Automatic retry with exponential backoff

## Best Practices Going Forward

✅ **DO**:
- Process 10-20 videos per session
- Take breaks every 5 videos
- Use randomized delays
- Process different channels on different days
- Monitor for IP block warnings

❌ **DON'T**:
- Process 50+ videos in one session
- Use fixed, predictable delays
- Scrape same channel repeatedly
- Ignore IP block warnings
- Rush through extraction

---

**Remember**: Slower is safer. The new defaults prioritize avoiding IP blocks over speed.
