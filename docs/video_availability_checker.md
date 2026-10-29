# Video Availability Checker

## Overview

The video availability checker proactively identifies YouTube videos that are no longer accessible due to deletion, privacy changes, or embedding restrictions. This helps maintain Flipper's video quality by detecting broken links before users encounter them.

## Problem Statement

Over time, YouTube content creators:
- Delete videos from their channels
- Change videos from public to private
- Disable embedding on videos
- Region-restrict content

Without proactive checking, these issues are only discovered when users try to watch a video and encounter a broken link or playback error.

## Solution

`check_video_availability.py` uses the YouTube Data API v3 to batch-check video status and detect:

- ❌ **Deleted videos**: Removed from YouTube entirely
- 🔒 **Private videos**: Changed from public to private
- 🚫 **Embedding disabled**: Video exists but can't play in Flipper's embedded player
- ⚠️ **API errors**: Temporary issues or region restrictions

## Usage

### Quick Start (Windows)

Double-click `check_video_availability.bat` to run with default settings.

### Command Line

```bash
# Check qa.csv videos (recommended - these are what users see)
python check_video_availability.py --source qa

# Check all precomputed recommendations
python check_video_availability.py --source precomputed

# Custom output location
python check_video_availability.py --source qa --output reports/availability_check.csv
```

### Options

- `--source {qa|precomputed}`: Choose which dataset to check
  - `qa` (default): Check current_1/2/3 videos from qa.csv (~2,240 unique videos)
  - `precomputed`: Check all recommendations from precomputed_recommendations_flat_qa.csv (~5,039 videos)
  
- `--output PATH`: Specify output file path (default: `video_availability_report.csv`)

- `--no-retry`: Skip automatic retry of failed API calls

## Output Files

The checker creates three reports:

### 1. Full Report (`video_availability_report.csv`)

Complete status for all videos checked:

| Column | Description |
|--------|-------------|
| video_id | YouTube video ID |
| video_title | Title from qa.csv/precomputed |
| channel | Channel name |
| source_step | Small step ID where video is used |
| source_step_name | Human-readable small step name |
| source_position | Position (e.g., current_1, current_2) |
| status | overall status: available, deleted, private, embedding_disabled |
| privacy_status | YouTube privacy setting |
| embeddable | Whether video can be embedded |
| upload_status | YouTube upload status |
| api_title | Current title from YouTube API |

### 2. Unavailable Videos (`unavailable_video_availability_check.csv`)

Only videos with problems - quick reference for action items.

### 3. Deletion Candidates (`deletion_candidates_video_availability_check.csv`)

Videos that should be added to `videos_to_delete.csv`. Includes deleted and private videos, formatted for easy import:

```csv
video_id,video_title,channel
dR0ozGTZkb8,Percentages and Ratios - Solving Percentage Problems,Miacademy
```

## API Quota Usage

- **Batching**: Checks 50 videos per API request (YouTube API limit)
- **Quota cost**: 1 unit per request
- **Daily limit**: 10,000 units (free tier)

Example quota usage:
- 2,240 videos (qa.csv) = ~45 requests = 45 quota units
- 5,039 videos (precomputed) = ~101 requests = 101 quota units

Both well within daily limits.

## Typical Results

From qa.csv check on 2026-07-22:

```
Total videos checked: 2240

Status breakdown:
  ✅ available             2155 ( 96.2%)
  ❌ deleted                 22 (  1.0%)
  🚫 embedding_disabled      63 (  2.8%)

⚠️  ACTION REQUIRED: 85 videos need attention
```

## Recommended Schedule

- **Monthly**: Check qa.csv videos (the ones users actually see)
- **Quarterly**: Full check of all precomputed recommendations
- **After major channel updates**: Ad-hoc checks if a key channel changes content

## Integration with Existing Workflow

### 1. Review Unavailable Videos

```bash
# Open the unavailable report
code reports\unavailable_video_availability_check.csv
```

### 2. Add to Deletion Queue

For deleted/private videos:

```bash
# Append to existing videos_to_delete.csv
Get-Content reports\deletion_candidates_video_availability_check.csv | Select-Object -Skip 1 | Add-Content videos_to_delete\videos_to_delete.csv
```

### 3. Handle Embedding-Disabled Videos

These videos exist but won't play in Flipper. Options:
- Replace with alternative videos using Improve_pick GUI
- Document as known issue
- Contact creator to request embedding permission

### 4. Run Pipeline

After updating videos_to_delete.csv:

```bash
python delete_content.py  # Remove deleted videos from index
```

## Troubleshooting

### "YOUTUBE_API_KEY not found"

Ensure `.env` file contains:
```
YOUTUBE_API_KEY=your_api_key_here
```

### API Quota Exceeded

If you hit the 10,000/day limit:
- Wait until next day (quota resets at midnight Pacific Time)
- Run checks less frequently
- Use `--source qa` instead of `--source precomputed` (fewer videos)

### Many "api_error" Results

Could indicate:
- Network connectivity issues
- API service temporary outage
- Regional blocking

The script automatically retries failed videos once. Use `--no-retry` to skip retry.

## Technical Details

### API Endpoint Used

```python
youtube.videos().list(
    part="status,snippet",
    id="video_id1,video_id2,...",  # Up to 50 IDs
    maxResults=50
)
```

### Status Detection Logic

```python
if upload_status == "deleted":
    status = "deleted"
elif privacy_status == "private":
    status = "private"  
elif not embeddable:
    status = "embedding_disabled"
else:
    status = "available"
```

### Rate Limiting

- 0.5 second delay between batches
- 5 second delay before retry
- Respectful of YouTube API guidelines

## Future Enhancements

Possible additions:
- Email notifications for unavailable videos
- Automatic PR creation with replacement suggestions
- Historical tracking (trend analysis)
- Webhook integration for automated pipeline updates
- Check for region restrictions specific to target audience

## Related Files

- `check_video_availability.py` - Main script
- `check_video_availability.bat` - Windows launcher
- `qa/qa.csv` - Source for current videos
- `precomputed_recommendations_flat_qa.csv` - All recommendations
- `videos_to_delete/videos_to_delete.csv` - Deletion queue
- `delete_content.py` - Removal pipeline
