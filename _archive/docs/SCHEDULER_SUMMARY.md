# Conservative Scheduled Caption Extraction - Summary

## What Was Created

A complete scheduled extraction system with bot detection avoidance for safely extracting YouTube captions.

## New Files

### Core System
1. **`data_pipeline/scheduler.py`** - Conservative scheduler with bot avoidance
   - Small batch processing (5 videos default)
   - Randomized delays (8-15 seconds)
   - Session breaks (2-5 minutes)
   - IP block detection
   - State management
   - Email notifications

2. **`scheduled_extractor.py`** - Main extraction script with scheduler integration
   - Randomizes channel order
   - Skips downloaded videos
   - Stops on IP blocks
   - Resumable sessions
   - Comprehensive logging

3. **`test_scheduler.py`** - Test script to verify configuration
   - Checks API keys
   - Validates channels.csv
   - Tests scheduler functions
   - Verifies IP block detection

### Helper Files
4. **`run_scheduled_extraction.bat`** - Windows batch file for easy launching
   - Pre-configured for 25 videos (5 batches of 5)
   - Simple double-click execution

5. **`.env.example`** - Example environment configuration
   - Shows all available settings
   - Includes SMTP setup for notifications

### Documentation
6. **`SCHEDULED_EXTRACTION_GUIDE.md`** - Comprehensive guide
   - Detailed feature documentation
   - Configuration options
   - Bot avoidance strategies
   - Troubleshooting guide
   - Email notification setup

7. **`QUICKSTART_SCHEDULED.md`** - Quick start guide
   - Simple setup instructions
   - Common usage examples
   - Command-line reference
   - Quick troubleshooting

## Key Features Implemented

### 🛡️ Bot Detection Avoidance
- **Small Batches**: Only 5 videos at a time (configurable)
- **Random Delays**: 8-15 seconds between videos (variable)
- **Session Breaks**: 2-5 minute breaks after each batch
- **Random Order**: Channels processed in different order each run
- **Immediate Stop**: Detects IP blocks and stops immediately

### 📊 Smart State Management
- **Progress Tracking**: `extraction_state.json` tracks all extractions
- **Resumable**: Can stop/restart without losing progress
- **Skip Duplicates**: Automatically excludes downloaded videos
- **History**: Maintains extraction history and statistics

### 🔔 Notification System
- **Email Alerts**: Optional email notifications
- **IP Block Alerts**: Immediate notification when blocked
- **Completion Reports**: Summary at end of session
- **Quota Warnings**: Alerts when API quota exceeded

### ⚙️ Flexible Configuration
- **Command-line args**: Easy customization without code changes
- **Environment variables**: Sensitive data in .env
- **Conservative defaults**: Safe settings out of the box
- **Extensible**: Easy to modify timing/behavior

## Usage Examples

### Basic Usage
```bash
# Default (5 videos per batch, unlimited total)
python scheduled_extractor.py

# With total limit
python scheduled_extractor.py --max-total 25

# With email notifications
python scheduled_extractor.py --email your@email.com
```

### Conservative Settings (After Being Blocked)
```bash
python scheduled_extractor.py --batch-size 3 --max-total 15
```

### Aggressive Settings (Residential IP, Never Blocked)
```bash
python scheduled_extractor.py --batch-size 10 --max-total 100
```

### Windows Batch File
```bash
# Double-click or run:
run_scheduled_extraction.bat
```

## How It Works

### Extraction Flow
```
1. Load channels.csv → Randomize order
2. For each channel:
   a. Fetch video list
   b. Filter out downloaded videos
   c. For each video:
      - Extract caption
      - Save to disk
      - Record in state
      - Random delay (8-15s)
   d. After 5 videos:
      - Take 2-5 minute break
3. Save final state
4. Send completion notification
```

### IP Block Detection
```
Monitor for:
  • "IP blocked" errors
  • "Too many requests"
  • Rate limit responses (429)
  • Suspicious traffic warnings

On detection:
  1. Immediately stop extraction
  2. Save current state
  3. Send email notification
  4. Display recovery instructions
  5. Exit gracefully
```

### State Persistence
```json
{
  "last_session": "2026-01-27T10:30:00",
  "channels_processed": ["UC..."],
  "videos_extracted": {
    "channel_id": [
      {"video_id": "abc123", "timestamp": "..."}
    ]
  },
  "ip_blocks_detected": [
    {"timestamp": "...", "message": "..."}
  ],
  "total_extractions": 42
}
```

## Bot Avoidance Strategies

### Human-Like Behavior
✅ **Variable timing** - Not predictable patterns
✅ **Session breaks** - Simulates human taking breaks
✅ **Random channel order** - Different pattern each run
✅ **Small batches** - Not bulk downloading
✅ **Immediate stop on block** - Doesn't retry aggressively

### Conservative Defaults
- 5 videos per batch (vs. 50-100 bulk)
- 8-15 second delays (vs. 1-2 seconds)
- 2-5 minute breaks (vs. continuous)
- Random channel order (vs. alphabetical)
- Stop on detection (vs. retry loop)

### Timing Analysis
```
Single Batch (5 videos):
  Video 1: Extract → 12s delay
  Video 2: Extract → 9s delay
  Video 3: Extract → 14s delay
  Video 4: Extract → 10s delay
  Video 5: Extract
  Total: ~45-75 seconds + 2-5 minute break

Session (25 videos):
  5 batches × ~5 minutes = ~25 minutes
  Much safer than: 25 videos × 2s = 50 seconds (BLOCKED!)
```

## Configuration Reference

### Command-Line Arguments
| Argument | Default | Description |
|----------|---------|-------------|
| `--batch-size N` | 5 | Videos per batch before break |
| `--max-total N` | None | Max videos this session |
| `--max-per-channel N` | 50 | Max videos per channel |
| `--email addr` | None | Email for notifications |
| `--channels-csv path` | channels.csv | Channels file |
| `--output-dir path` | data/captions_output | Output location |

### Environment Variables (.env)
```env
# Required
YOUTUBE_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here

# Optional - Notifications
NOTIFICATION_EMAIL=your@email.com
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your@email.com
SMTP_PASSWORD=app_password_here

# Optional - Timing (has safe defaults)
VIDEOS_PER_BATCH=5
RANDOM_DELAY_MIN=8.0
RANDOM_DELAY_MAX=15.0
BREAK_DURATION_MIN=120.0
BREAK_DURATION_MAX=300.0
```

## Testing

Run the test script to verify setup:
```bash
python test_scheduler.py
```

Expected output:
```
================================================================================
TESTING SCHEDULED EXTRACTION SYSTEM
================================================================================

✓ YouTube API key found
✓ Found channels.csv with 3 channels

Scheduler Configuration:
  • Videos per batch: 5
  • Delay range: 8.0-15.0 seconds
  • Break range: 2.0-5.0 minutes
  • Notifications: your@email.com

Testing channel loading:
  ✓ Loaded 3 channels in random order:
    1. Khan Academy
    2. numberblocks
    3. BBC Teach

✓ ALL TESTS PASSED
================================================================================
```

## Troubleshooting

### Common Issues

**"No videos found"**
- Check channels.csv format: `channel_id,channel_name`
- Verify channel IDs are valid
- Check if all videos already downloaded

**"IP blocked immediately"**
- Datacenter/cloud IP (often pre-blocked)
- Previous block still active (wait 6+ hours)
- Solution: Residential internet or VPN

**"Quota exceeded"**
- YouTube API daily limit (10,000 units)
- Resets midnight Pacific Time
- Solution: Wait or reduce extraction volume

**"Email not sending"**
- Gmail requires App Password (not regular password)
- Check SMTP_SERVER, SMTP_PORT in .env
- Verify SMTP_USERNAME and SMTP_PASSWORD
- Test with another email client first

### Recovery After IP Block

1. **Wait**: 2-6 hours minimum
2. **Verify**: Try single video with test script
3. **Resume**: Run with smaller batches
   ```bash
   python scheduled_extractor.py --batch-size 3 --max-total 15
   ```
4. **Monitor**: Watch for any warnings

## Performance Estimates

### Conservative (Default)
- Batch: 5 videos in ~5 minutes (including break)
- Hour: ~60 videos
- Day: ~500 videos (spread across multiple sessions)

### Very Conservative (After Block)
- Batch: 3 videos in ~5 minutes
- Hour: ~35 videos
- Day: ~300 videos

### Aggressive (Residential, Never Blocked)
- Batch: 10 videos in ~5 minutes
- Hour: ~120 videos
- Day: ~1000 videos

## Integration with Existing Pipeline

### Option 1: Replace Extraction Step
```python
# In run_pipeline.py, replace:
# extractor = YouTubeCaptionExtractor(...)
# extractor.run_pipeline(...)

# With:
from scheduled_extractor import ScheduledCaptionExtractor

extractor = ScheduledCaptionExtractor(
    api_key=YOUTUBE_API_KEY,
    channels_csv="channels.csv",
    videos_per_batch=5
)
extractor.run_scheduled_extraction(max_videos_total=25)
```

### Option 2: Separate Process
```bash
# Step 1: Extract with scheduler
python scheduled_extractor.py --max-total 50

# Step 2: Process with existing pipeline
python data_pipeline/run_pipeline.py --skip-extraction
```

## Best Practices

### Daily Workflow
1. **Morning**: Run small session (25 videos)
2. **Afternoon**: Run another session (25 videos)
3. **Evening**: Run final session (25 videos)
4. **Monitor**: Check for any IP warnings

### Weekly Workflow
1. **Monday**: Extract new videos (50-100)
2. **Tuesday-Thursday**: Continue extraction if needed
3. **Friday**: Process everything (chunk, embed, index)
4. **Review**: Check extraction stats

### Recovery Workflow
1. **Detect block**: Automatic (script stops)
2. **Wait**: 6+ hours
3. **Change network**: Different WiFi/VPN
4. **Test**: Small batch (3-5 videos)
5. **Resume**: Gradually increase if successful

## Security & Privacy

### API Keys
- ✅ Store in .env (not in code)
- ✅ Add .env to .gitignore
- ✅ Rotate keys periodically
- ✅ Monitor usage in Google Cloud Console

### Email Credentials
- ✅ Use App Passwords (not regular passwords)
- ✅ Store in .env only
- ✅ Use dedicated email if possible
- ✅ Enable 2FA on account

### State File
- Contains video IDs (public data)
- No sensitive information
- Safe to commit to private repos
- Can be deleted to reset

## Support & Maintenance

### Logs
All output goes to terminal:
- Real-time progress updates
- Error messages with context
- Session summaries
- Recovery instructions

### State File Location
`extraction_state.json` in project root:
- Human-readable JSON
- Can be manually edited if needed
- Delete to start fresh
- Backup before major changes

### Updates
To modify timing/behavior:
1. Edit `data_pipeline/scheduler.py`
2. Adjust min/max delay values
3. Change batch sizes
4. Modify break durations

### Getting Help
When reporting issues, include:
- Command used
- Terminal output
- extraction_state.json (if relevant)
- Error messages
- Network type (residential/datacenter/VPN)

## Success Metrics

### Healthy Session
- ✅ All batches complete
- ✅ No IP block warnings
- ✅ ~5 minutes per 5 videos
- ✅ State file updated
- ✅ Completion notification received

### Warning Signs
- ⚠️ Multiple "No captions" in a row
- ⚠️ Unusually slow responses
- ⚠️ Connection timeouts
- ⚠️ Rate limit messages

### Critical Issues
- 🚨 IP block detected
- 🚨 All videos failing
- 🚨 Quota exceeded
- 🚨 Authentication errors

## Next Steps

After successful extraction:

1. **Verify Output**
   ```bash
   # Check caption files
   dir data\captions_output\*\*.txt
   ```

2. **Continue Pipeline**
   ```bash
   # Chunk transcripts
   python data_pipeline/chunker.py
   
   # Generate embeddings
   python data_pipeline/embedder.py
   
   # Build FAISS index
   python data_pipeline/indexer.py
   ```

3. **Or Run Full Pipeline**
   ```bash
   python data_pipeline/run_pipeline.py --skip-extraction
   ```

4. **Launch Search GUI**
   ```bash
   python launch_gui.py
   ```

## Conclusion

The conservative scheduled extraction system provides:
- ✅ Safe, bot-detection-aware extraction
- ✅ Automatic IP block detection and stopping
- ✅ Resumable sessions with state management
- ✅ Email notifications for critical events
- ✅ Easy configuration and usage
- ✅ Comprehensive documentation

**Ready to use!** Just run:
```bash
python scheduled_extractor.py --email your@email.com
```

Or use the Windows batch file:
```bash
run_scheduled_extraction.bat
```

Happy extracting! 🎬
