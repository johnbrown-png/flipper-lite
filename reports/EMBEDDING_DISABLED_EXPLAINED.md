# Understanding "Embedding Disabled" Videos

## What This Means

When the availability checker reports videos as **"embedding_disabled"**, it means:

✅ **The videos ARE available and viewable** on YouTube.com  
❌ **The videos CANNOT be embedded** in other websites (like Flipper)

This is a **creator setting**, not a Flipper bug or YouTube deletion.

## Why This Happens

Video creators can disable embedding for various reasons:
- Monetization strategy (forcing views on YouTube where ads show)
- Copyright protection concerns
- Educational licensing restrictions
- Channel policy decisions

## Current Situation

From your latest check (2026-07-22):

| Channel | Embedding-Disabled Videos |
|---------|---------------------------|
| **JoAnn's_School** | 58 videos |
| Charlton_Primary_School | 1 video |
| Math_Simplified | 1 video |
| Teacher_Ira | 1 video |
| Maths_With_Ease | 1 video |
| susan_dyson | 1 video |
| **TOTAL** | **63 videos** |

**JoAnn's_School** is the primary issue - they've disabled embedding on all their educational videos.

## Impact on Flipper

These videos will:
- ❌ **NOT play** in Flipper's embedded iframe player
- ❌ Show an error or blank player when users try to watch
- ✅ **Work fine** if users click "Watch on YouTube" to open in a new tab

## Your Options

### Option 1: Add "Watch on YouTube" Fallback Button ⭐ RECOMMENDED
Detect when a video can't embed and show a prominent "Watch on YouTube" button instead of the broken embedded player.

**Pros:**
- Keeps the current video selections
- User can still watch the content
- Simple UX addition

**Cons:**
- Slightly degraded user experience (leaves Flipper)
- No in-app video playback

### Option 2: Replace with Embeddable Alternatives
Use the Improve_pick GUI to find replacement videos that allow embedding.

**Pros:**
- Maintains seamless in-app experience
- Better UX for users

**Cons:**
- Requires manual QA for 63 videos
- May not find equivalent quality alternatives

### Option 3: Contact Creators
Reach out to JoAnn's_School to request embedding permission for educational use.

**Pros:**
- Could solve 58 of 63 videos at once
- No content replacement needed

**Cons:**
- No guarantee they'll enable embedding
- Takes time and may not succeed

### Option 4: Do Nothing
Accept that these videos require external viewing.

**Cons:**
- Users will encounter broken players
- Poor user experience

## Recommended Action Plan

1. **Short term**: Document which small steps use embedding-disabled videos
2. **Medium term**: Add detection for embedding-disabled videos and show "Watch on YouTube" button
3. **Long term**: Gradually replace with embeddable alternatives during regular QA cycles

## How to Identify Affected Small Steps

```powershell
# See which curriculum topics are affected
Import-Csv "reports\embedding_disabled_video_availability_check.csv" | 
    Select-Object source_step_name, source_position, video_id, channel | 
    Format-Table -AutoSize
```

## Technical Implementation (Option 1)

In your video player code, check if embedding is disabled:

```python
# When video fails to load, provide fallback
if video.embeddable == False:
    show_youtube_link_button(video_id)
```

You can pre-flag these videos in your database using the `embedding_disabled_video_availability_check.csv` report.

## Files Generated

- **embedding_disabled_video_availability_check.csv** - Full list of 63 videos
  - Includes: video_id, title, channel, small_step, position
  - Status shows "embedding_disabled", privacy_status = "public"
  
- **deletion_candidates_video_availability_check.csv** - Different! These are truly gone
  - Only 22 videos (deleted/private)
  - These MUST be replaced

**Don't confuse the two!** Embedding-disabled videos still exist and work on YouTube.

## Summary

**Embedding-disabled ≠ Unavailable**

These 63 videos are:
- ✅ Viewable on YouTube
- ✅ Public and accessible
- ✅ Valid educational content
- ❌ Not embeddable in Flipper's iframe

**Action**: Decide whether to add fallback UI or replace the videos.
