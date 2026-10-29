# GUI Integration with Scheduled Extractor

## Summary

✅ **YES**, the new scheduled extractor with bot detection avoidance **is now integrated** into the GUI!

## What Changed

The **"▶ Extract & Chunk"** button in the GUI pipeline (`gui_pipeline.py`) now uses the conservative scheduler.

### Features in GUI

When you click "Extract & Chunk", the system now:

1. ✅ **Small Batches**: Processes 5 videos at a time
2. ✅ **Random Delays**: 8-15 seconds between videos
3. ✅ **Session Breaks**: 2-5 minute breaks after each batch
4. ✅ **IP Block Detection**: Automatically detects and stops if blocked
5. ✅ **Skip Downloaded**: Automatically excludes already-downloaded videos
6. ✅ **State Tracking**: Saves progress to `extraction_state.json`

### Visual Indicators

In the console output you'll see:
```
==============================================================
Starting YouTube Caption Extraction (Conservative Mode)
Channel: numberblocks
Target Videos: 50
Max Duration: 600s
Region Code: GB
==============================================================
Bot Avoidance: 5 videos/batch, 8-15s delays, 2-5min breaks
==============================================================

[1/50] Learn to Count...
  Duration: 245s
  ✓ Extracted and saved
  ⏱ Waiting 11.2s...

[2/50] Number Blocks Song...
  Duration: 180s
  ✓ Extracted and saved
  ⏱ Waiting 13.5s...

...

[5/50] Addition Fun...
  Duration: 195s
  ✓ Extracted and saved

☕ Taking 3.2 minute break to avoid bot detection...
  ✓ Break complete, resuming...
```

### IP Block Detection in GUI

If an IP block is detected, you'll see:
1. Console message: "🚨 IP BLOCK DETECTED - Stopping extraction"
2. Pop-up warning dialog with recovery instructions
3. Extraction stops immediately

## Using the GUI

### Step 1: Launch GUI
```bash
python gui_pipeline.py
# or double-click
launch_gui.bat
```

### Step 2: Configure Settings
- **Number of Videos**: How many to extract (e.g., 50)
- **Max Video Duration**: Filter out long videos (e.g., 600 seconds)
- **Channel Name**: Select from dropdown or enter channel ID
- **Region Code**: GB, US, etc.

### Step 3: Click "▶ Extract & Chunk"
The extraction will:
- Run with bot avoidance strategies automatically
- Show progress in real-time
- Take breaks every 5 videos
- Stop immediately if IP blocked
- Chunk transcripts after extraction

### Step 4: Continue Pipeline
After extraction and chunking:
- Click **"🧠 Generate Embeddings"** (Step 3)
- Click **"📊 Build Search Index"** (Step 4)
- Or run the full pipeline: `python data_pipeline/run_pipeline.py`

## Differences from Command-Line

### GUI Mode
- Visual interface with progress table
- Real-time console output in window
- Pop-up dialogs for critical events
- Single-channel focus per run
- Manual continuation to next steps

### Command-Line Mode (`scheduled_extractor.py`)
- Text-only console output
- Email notifications (optional)
- Multi-channel with random order
- Fully automated pipeline
- More configuration options

Both use the **same underlying scheduler** for bot avoidance!

## State Management

Both GUI and command-line share:
- `extraction_state.json` - Progress tracking
- `data/api_cache.json` - API response caching
- Same output directories

This means you can:
- Start in GUI, continue in command-line (or vice versa)
- State is preserved across both methods
- Downloaded videos are tracked consistently

## Troubleshooting

### "IP Block Detected" dialog appears
1. Click OK to acknowledge
2. Wait 2-6 hours before trying again
3. Or use different network/VPN
4. The extraction state is saved - you can resume later

### Extraction seems slow
This is **intentional**! The conservative timing prevents bot detection:
- 5 videos = ~5 minutes (including delays and breaks)
- 50 videos = ~50 minutes total
- Much safer than fast extraction which gets blocked

### Want faster extraction?
You can modify the scheduler parameters in `gui_pipeline.py` line ~350:
```python
scheduler = ExtractionScheduler(
    channels_csv='channels.csv',
    state_file='extraction_state.json',
    videos_per_batch=10,  # Increase batch size
    min_delay_between_videos=5.0,  # Reduce delays
    max_delay_between_videos=8.0,
    min_break_duration=60.0,  # Shorter breaks
    max_break_duration=120.0,
    notification_email=None
)
```

**Warning**: Faster settings increase risk of IP blocking!

## Comparison Table

| Feature | Old GUI | New GUI | Command-Line |
|---------|---------|---------|--------------|
| Bot Avoidance | ❌ Basic | ✅ Conservative | ✅ Conservative |
| IP Block Detection | ❌ No | ✅ Yes | ✅ Yes |
| Session Breaks | ❌ No | ✅ Yes (2-5 min) | ✅ Yes (2-5 min) |
| Random Delays | ❌ Fixed | ✅ Random (8-15s) | ✅ Random (8-15s) |
| Skip Downloaded | ❌ Manual | ✅ Automatic | ✅ Automatic |
| State Tracking | ❌ No | ✅ Yes | ✅ Yes |
| Multi-Channel | ❌ No | ❌ No | ✅ Yes (random order) |
| Email Notifications | ❌ No | ❌ No (uses dialogs) | ✅ Yes (optional) |
| Visual Progress | ✅ Yes | ✅ Yes | ❌ Console only |

## Recommendations

### For Single-Channel Extraction
✅ **Use the GUI** - Better visual feedback and easier to monitor

### For Multi-Channel Extraction
✅ **Use command-line** - Processes all channels with random order

### For Unattended Extraction
✅ **Use command-line with email** - Get notified of issues

### For Testing
✅ **Use either** - Both are equally safe now!

## Summary

The GUI now has **full bot detection avoidance** integrated! When you click "Extract & Chunk", it:
- ✅ Uses conservative scheduler
- ✅ Takes smart breaks
- ✅ Detects IP blocks
- ✅ Shows visual progress
- ✅ Skips duplicates
- ✅ Saves state

**You're protected against bot detection in both GUI and command-line modes!** 🛡️
