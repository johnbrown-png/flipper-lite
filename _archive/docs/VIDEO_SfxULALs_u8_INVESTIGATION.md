# Investigation Report: Why Video SfxULALs_u8 Is Not Being Extracted

**Video:** https://www.youtube.com/watch?v=SfxULALs_u8  
**Title:** Multiplying: 2 digits times 1 digit (with carrying) | Arithmetic | Khan Academy  
**Date:** 2026-02-13

---

## Root Cause Found

### ✗ IP BLOCKED BY YOUTUBE

The video is not being extracted because **YouTube is blocking your IP address** when the caption extractor tries to fetch transcripts.

---

## Diagnostic Results

### ✓ Video Configuration - PASS
- **Not already downloaded** ✓
- **Duration:** 129 seconds (2m 9s) - well under 1200 second limit ✓
- **Channel:** Khan Academy (UC4a-Gbdw7vOaccHmFo40b9g) ✓
- **Channel in channels.csv:** YES ✓
- **Video status:** Public, processed ✓

### ✗ Caption Extraction - FAIL
```
Error: IpBlocked
Could not retrieve a transcript for the video
```

**All configuration checks passed** - the video SHOULD be extracted, but the extraction fails at runtime due to IP blocking.

---

## Why This Happens

YouTube's anti-bot protection has detected too many transcript requests from your IP and is blocking them. This is NOT a bug in the code - it's YouTube's rate limiting system.

Common triggers:
1. Too many videos extracted in a short time
2. Multiple test runs in quick succession
3. Cloud/VPN IP addresses (YouTube is more aggressive with these)
4. Direct connection without proxy rotation

---

## Evidence from Testing

Earlier today, we ran multiple test scripts:
- `investigate_language_codes.py` - tested 3 videos
- `test_language_fallback.py` - tested 3 more videos (all got IP blocked)
- `diagnose_video.py` - tested this video (IP blocked)

**Result:** YouTube blocked the IP after detecting the pattern of rapid transcript requests.

---

## Why caption_extractor.py Handles This

The caption_extractor already has protection against IP blocking:

1. **Proxy support** (line 390-396):
   ```python
   if self.use_proxy:
       attempts.append(('proxy', YouTubeTranscriptApi(
           proxy_config=WebshareProxyConfig(
               proxy_username="fuyxmmoi",
               proxy_password="8xdrwuvrznki",
               filter_ip_locations=self.proxy_locations,
           )
       )))
   ```

2. **Rate limiting delays** (lines 55-56):
   - Random delays between videos (8-15 seconds)
   - Session breaks after every 5 videos (1-3 minutes)

3. **Proxy location optimization** (lines 143-158):
   - BBC content uses UK proxies
   - Other content uses US/Canada/UK proxies

---

## What's Happening Now

When you run the caption extractor:
1. It tries with Webshare proxy first
2. Falls back to direct connection
3. Both are blocked because YouTube has flagged this activity pattern
4. Video extraction fails with "No captions" error
5. Moves to next video (which also fails)

---

## Solutions

### Immediate (Let it cool down)
Wait 2-4 hours before running the extractor again. YouTube blocks typically expire after a few hours.

### Short-term (Use the built-in protections)
The caption_extractor already has good protections - just run it normally:
```python
python flipper.py  # Or launch_gui.bat
```

Don't run multiple test scripts back-to-back (like we just did).

### Long-term (Already implemented)
The code already uses:
- Webshare proxy rotation ✓
- Random delays ✓
- Session breaks ✓
- IP location filtering ✓

---

## Conclusion

**The video IS NOT being extracted because of IP blocking, NOT because of language codes.**

The earlier hypothesis about language codes ('en' vs 'en-US' vs 'en-GB') was incorrect for this video. When we tested it successfully earlier, it worked fine with just `['en']`.

The real issue is that our testing session triggered YouTube's rate limiting, and now the IP is temporarily blocked from fetching transcripts.

**Action Required:** None - just wait a few hours before running the extractor again.
