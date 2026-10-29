# Quick Start: Conservative Scheduled Extraction

## What This Does

Extracts YouTube captions safely without triggering bot detection:
- ✅ Processes 5 videos at a time
- ✅ Takes 2-5 minute breaks between batches
- ✅ Randomizes channel order
- ✅ Auto-detects IP blocks and stops
- ✅ Sends email notifications (optional)
- ✅ Resumes where it left off

## Setup (One-Time)

1. **Install dependencies** (if not already done):
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure .env file**:
   ```bash
   # Copy example and edit
   copy .env.example .env
   # Edit .env and add your YOUTUBE_API_KEY
   ```

3. **Verify channels.csv**:
   - Make sure `channels.csv` has the channels you want
   - Format: `channel_id,channel_name`

## Usage

### Option 1: Run with Batch File (Windows)

Double-click:
```
run_scheduled_extraction.bat
```

This will extract 25 videos total (5 at a time with breaks).

### Option 2: Run with Python

**Basic (extracts until done or blocked):**
```bash
python scheduled_extractor.py
```

**With email notifications:**
```bash
python scheduled_extractor.py --email your@email.com
```

**Custom configuration:**
```bash
python scheduled_extractor.py --batch-size 3 --max-total 15
```

## What to Expect

### Normal Run
```
================================================================================
SCHEDULED YOUTUBE CAPTION EXTRACTION
================================================================================
Configuration:
  • Videos per batch: 5
  • Delay between videos: 8.0-15.0s
  • Break duration: 2.0-5.0 min
  ...

CHANNEL 1/3: numberblocks
================================================================================
  → 12 new videos to process

  [1/12] Learn to Count...
      ✓ Extracted (1 total)
      ⏱ Waiting 11.2s...
  [2/12] Number Blocks Song...
      ✓ Extracted (2 total)
      ⏱ Waiting 9.5s...
  ...
  [5/12] Addition Fun...
      ✓ Extracted (5 total)

☕ TAKING SESSION BREAK
Duration: 3.2 minutes
  ⏱ Break time remaining: 3.2 minutes...
  ✓ Break complete! Resuming extraction...
```

### If IP Blocked
```
🚨 IP BLOCK DETECTED!
================================================================================
Error: YouTube has blocked your IP address

Extraction stopped to avoid further blocking.
Total videos extracted this session: 3

⏰ Wait 2-6 hours before retrying or use a different network/VPN
================================================================================
```

## Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--batch-size 5` | 5 | Videos per batch |
| `--max-total 25` | None | Total videos this session |
| `--max-per-channel 50` | 50 | Videos per channel |
| `--email you@email.com` | None | Email for notifications |

## Tips

### ✅ Best Practices
- Start with default settings (5 videos per batch)
- Run during normal hours (9am-5pm)
- Use residential internet (not datacenter/VPN)
- Let breaks complete fully
- Don't force it if blocked

### ⚠️ If You Get Blocked
1. **Stop immediately** (scheduler does this automatically)
2. **Wait 2-6 hours** before trying again
3. **Try different network** or VPN
4. **Reduce batch size** to 3 videos
5. **Check your IP** - datacenter IPs often pre-blocked

### 📊 Monitoring
- Script shows progress in real-time
- State saved to `extraction_state.json`
- Can stop/resume anytime (Ctrl+C)
- Automatically skips downloaded videos

## After Extraction

Continue with the rest of your pipeline:

```bash
# Run the full pipeline (chunks, embeds, indexes)
python data_pipeline/run_pipeline.py

# Or launch the search GUI
python launch_gui.py
```

## Troubleshooting

**"No videos found"**
- Check channels.csv has valid channel IDs
- Verify channels have videos

**"IP blocked immediately"**
- You may be on a datacenter/cloud IP
- Try residential internet or different VPN

**"Quota exceeded"**
- YouTube API daily limit reached
- Resets at midnight Pacific Time
- Reduce `--max-total` to stay under limit

**"Email not sending"**
- Check SMTP settings in .env
- Gmail requires App Password (not regular password)
- See SCHEDULED_EXTRACTION_GUIDE.md for details

## State File

Progress saved to `extraction_state.json`:
- Tracks what's been extracted
- Safe to run multiple times
- Skips duplicates automatically
- Delete to start fresh:
  ```bash
  del extraction_state.json
  ```

## More Information

See [SCHEDULED_EXTRACTION_GUIDE.md](SCHEDULED_EXTRACTION_GUIDE.md) for:
- Detailed configuration
- Email notification setup
- Advanced customization
- Integration with existing pipeline
- Troubleshooting guide

## Quick Reference

```bash
# Default run (5 per batch, no limit)
python scheduled_extractor.py

# Small test run
python scheduled_extractor.py --batch-size 3 --max-total 9

# Full day's extraction (conservative)
python scheduled_extractor.py --batch-size 5 --max-total 50

# With notifications
python scheduled_extractor.py --email you@email.com --max-total 25

# Very conservative (if previously blocked)
python scheduled_extractor.py --batch-size 2 --max-total 10
```

## Safety Features

The scheduler automatically:
- ✅ Randomizes delays (8-15 seconds)
- ✅ Takes breaks (2-5 minutes)
- ✅ Randomizes channel order
- ✅ Detects IP blocks
- ✅ Stops on detection
- ✅ Sends notifications
- ✅ Saves progress
- ✅ Skips duplicates

You don't have to do anything - just run it and let it work safely!
