# Scheduled Caption Extraction Guide

## Overview

The scheduled caption extractor implements conservative bot-detection avoidance strategies to safely extract YouTube captions without triggering IP blocks.

## Key Features

### 🛡️ Bot Detection Avoidance
- **Small Batches**: Processes only 5 videos at a time (configurable)
- **Random Delays**: 8-15 second randomized delays between videos
- **Session Breaks**: 2-5 minute breaks after each batch
- **Random Channel Order**: Channels processed in random order each run
- **IP Block Detection**: Automatically detects and stops on IP blocks

### 📊 State Management
- **Resumable**: Tracks progress across sessions
- **Skip Downloaded**: Automatically excludes already-downloaded videos
- **Statistics**: Maintains extraction history and metrics

### 🔔 Notifications
- **Email Alerts**: Optional email notifications for critical events
- **IP Block Alerts**: Immediate notification when blocked
- **Completion Reports**: Summary at end of each session

## Quick Start

### Basic Usage

Run the default configuration (5 videos per batch):

```bash
python scheduled_extractor.py
```

Or use the batch file:

```bash
run_scheduled_extraction.bat
```

### With Email Notifications

```bash
python scheduled_extractor.py --email your@email.com
```

### Custom Configuration

```bash
python scheduled_extractor.py \
  --batch-size 3 \
  --max-total 15 \
  --max-per-channel 30 \
  --email your@email.com
```

## Configuration Options

### Command Line Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--batch-size` | 5 | Videos to extract before taking a break |
| `--max-total` | None | Maximum total videos this session (None = unlimited) |
| `--max-per-channel` | 50 | Maximum videos per channel |
| `--email` | None | Email address for notifications |
| `--channels-csv` | channels.csv | Path to channels CSV file |
| `--output-dir` | data/captions_output | Output directory for captions |

### Environment Variables

Add these to your `.env` file:

```env
# Required
YOUTUBE_API_KEY=your_youtube_api_key_here

# Optional - Email Notifications
NOTIFICATION_EMAIL=your@email.com
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your@email.com
SMTP_PASSWORD=your_app_password
```

**Note**: For Gmail, use an [App Password](https://support.google.com/accounts/answer/185833), not your regular password.

## How It Works

### 1. Initialization
- Loads channels from `channels.csv`
- Randomizes channel order
- Loads state from previous sessions
- Scans for already-downloaded videos

### 2. Extraction Loop
For each channel (in random order):
- Fetch video list
- Filter out downloaded videos
- For each video:
  - Extract captions
  - Save to disk
  - Record in state
  - Random delay (8-15s)
  - After 5 videos: Take 2-5 minute break

### 3. IP Block Detection
Monitors for signs of blocking:
- "IP blocked" errors
- "Too many requests" errors
- Rate limit responses
- Suspicious traffic warnings

If detected:
- Immediately stops extraction
- Saves current state
- Sends notification
- Provides recovery instructions

### 4. State Persistence
Maintains `extraction_state.json`:
```json
{
  "last_session": "2026-01-27T10:30:00",
  "channels_processed": ["channel1", "channel2"],
  "videos_extracted": {
    "channel1": [
      {"video_id": "abc123", "timestamp": "2026-01-27T10:15:00"}
    ]
  },
  "ip_blocks_detected": [],
  "total_extractions": 42
}
```

## Bot Detection Strategies

### Human-Like Behavior
- **Variable Timing**: Randomized delays prevent pattern detection
- **Session Breaks**: Simulates human taking breaks
- **Random Order**: Channels processed in different order each time
- **Small Batches**: Prevents sustained high-rate requests

### Conservative Defaults
- 5 videos per batch (vs. bulk downloading)
- 8-15 second delays (vs. rapid-fire)
- 2-5 minute breaks (vs. continuous)
- Stops immediately on detection (vs. retrying)

### Timing Examples

**Batch of 5 videos:**
```
Video 1: Extract → 12s delay
Video 2: Extract → 9s delay
Video 3: Extract → 14s delay
Video 4: Extract → 10s delay
Video 5: Extract → 3 minute break
Video 6: Extract → ...
```

**Approximate rates:**
- ~5 videos per 1 minute (during active extraction)
- ~10 videos per 5 minutes (including breaks)
- ~60 videos per 30 minutes (full session)

## Avoiding IP Blocks

### Best Practices

1. **Start Small**: Begin with 5-video batches
2. **Monitor First Run**: Watch for any warnings
3. **Use Residential IP**: Avoid datacenter/VPN IPs (often pre-blocked)
4. **Respect Limits**: Don't force it if blocked
5. **Wait After Blocks**: 2-6 hours minimum before retry

### If You Get Blocked

1. **Stop Immediately**: The scheduler does this automatically
2. **Wait**: Minimum 2 hours, ideally 6+ hours
3. **Change Network**: Try different WiFi/VPN
4. **Reduce Rate**: Use smaller batches (3 videos)
5. **Increase Delays**: Modify `scheduler.py` for longer waits

### IP Block Recovery

The state file preserves your progress, so you can resume later:

```bash
# After 6 hours...
python scheduled_extractor.py --batch-size 3  # More conservative
```

## Email Notifications

### Setup (Gmail Example)

1. Enable 2-factor authentication
2. Generate App Password:
   - Go to Google Account → Security
   - App Passwords → Generate
3. Add to `.env`:
```env
NOTIFICATION_EMAIL=your@gmail.com
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your@gmail.com
SMTP_PASSWORD=your_app_password_here
```

### Notification Types

1. **IP Block Alert**: Immediate notification when blocked
2. **Quota Exceeded**: When API quota is reached
3. **Session Complete**: Summary when finished successfully

## State File

### Location
`extraction_state.json` in project root

### Manual Reset
To start fresh:
```bash
# Windows
del extraction_state.json

# Linux/Mac
rm extraction_state.json
```

### Backup
State file is human-readable JSON. You can backup/restore:
```bash
copy extraction_state.json extraction_state_backup.json
```

## Troubleshooting

### "No videos found"
- Check `channels.csv` has valid channel IDs
- Verify channels have videos
- Check all videos aren't already downloaded

### "IP Blocked immediately"
- You may be on a blacklisted IP (datacenter/cloud)
- Try different network
- Wait longer between sessions

### "Quota exceeded"
- YouTube API has daily quota (10,000 units typically)
- Each video list costs ~3 units
- Each video details costs ~1 unit
- Wait until midnight Pacific Time for reset

### "Email not sending"
- Verify SMTP credentials in `.env`
- For Gmail, use App Password (not regular password)
- Check SMTP server/port settings
- Test with simple email client first

## Advanced Configuration

### Custom Timing

Edit `scheduled_extractor.py`:

```python
self.scheduler = create_default_scheduler(
    channels_csv=channels_csv,
    videos_per_batch=3,  # Even smaller batches
    min_delay_between_videos=15.0,  # Longer delays
    max_delay_between_videos=25.0,
    min_break_duration=300.0,  # 5 minute breaks
    max_break_duration=600.0,  # 10 minute breaks
    notification_email=notification_email
)
```

### Integration with Pipeline

To use in your full pipeline:

```python
from scheduled_extractor import ScheduledCaptionExtractor

# Create extractor
extractor = ScheduledCaptionExtractor(
    api_key=YOUTUBE_API_KEY,
    channels_csv="channels.csv",
    videos_per_batch=5
)

# Run extraction
extractor.run_scheduled_extraction(max_videos_total=25)

# Then continue with chunking, embedding, etc.
```

## Monitoring

### Real-Time Progress

The scheduler shows:
- Current channel being processed
- Videos extracted per channel
- Total videos this session
- Break countdowns
- Delay timers

### Log Output Example

```
================================================================================
CHANNEL 2/3: Khan Academy
================================================================================
  → 15 new videos to process

  [1/15] Introduction to Algebra...
      ✓ Extracted (1 total)
      ⏱ Waiting 11.2s...
  [2/15] Basic Equations...
      ✓ Extracted (2 total)
      ⏱ Waiting 13.7s...
  ...
  [5/15] Quadratic Formulas...
      ✓ Extracted (5 total)

================================================================================
☕ TAKING SESSION BREAK
================================================================================
Duration: 3.5 minutes (210 seconds)
...
```

## Performance

### Typical Session

- **Batch Size**: 5 videos
- **Active Extraction**: ~1 minute
- **Break**: ~3 minutes
- **Per Batch**: ~4 minutes
- **25 videos**: ~20 minutes

### Scaling Up

For large extractions:
- Run multiple small sessions over days
- Don't exceed 50-100 videos per day
- Vary extraction times (morning, afternoon, evening)

## Integration Notes

### With Existing Pipeline

The scheduled extractor can replace the caption extraction step:

**Old way (run_pipeline.py):**
```python
extractor = YouTubeCaptionExtractor(...)
extractor.run_pipeline(...)
```

**New way:**
```python
# Use scheduled extractor instead
from scheduled_extractor import ScheduledCaptionExtractor

extractor = ScheduledCaptionExtractor(...)
extractor.run_scheduled_extraction(...)
```

### State Management

- State file tracks what's been extracted
- Safe to run multiple times
- Automatically skips duplicates
- Can be integrated with your existing workflow

## Security Notes

### API Keys
- Never commit `.env` to git
- Rotate API keys periodically
- Monitor quota usage in Google Cloud Console

### Email Credentials
- Use App Passwords, not regular passwords
- Store in `.env`, never in code
- Consider using environment-specific credentials

## Support

### Common Issues

1. **Script hangs**: Check internet connection
2. **All failures**: Likely IP blocked
3. **Random failures**: Normal, some videos lack captions
4. **Slow**: Intentional - prevents bot detection

### Logs

Check terminal output for detailed status and error messages.

### Getting Help

Include when reporting issues:
- Command line used
- Terminal output
- State file contents (if relevant)
- Error messages
- Whether IP block occurred

## License

Same as main project.
