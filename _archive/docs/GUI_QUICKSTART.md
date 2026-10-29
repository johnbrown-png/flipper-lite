# YouTube Caption Extraction GUI - Quick Start Guide

## Overview

The GUI provides an easy-to-use interface for extracting YouTube video captions with the following features:

✅ Configure extraction parameters (number of videos, duration filter, channel)  
✅ Real-time progress monitoring with console output  
✅ Visual results table showing extracted videos  
✅ Stop extraction at any time  
✅ Refresh to view previously extracted content  

---

## Quick Start

### Option 1: Using Python Launcher (Recommended)

```bash
python launch_gui.py
```

This launcher will:
- Check all requirements
- Display any warnings
- Launch the GUI automatically

### Option 2: Using Batch File (Windows)

```bash
launch_gui.bat
```

Double-click the file or run from command prompt.

### Option 3: Direct Launch

```bash
python gui_pipeline.py
```

---

## GUI Layout

```
┌─────────────────────────────────────────────────────────────┐
│         YouTube Caption Extraction Pipeline                 │
├─────────────────────────────────────────────────────────────┤
│ Extraction Parameters                                        │
│   Number of Videos:              [50        ]                │
│   Max Video Duration (seconds):  [600       ]                │
│   Channel Name:                  [numberblocks ▼]            │
│                                                              │
│   [▶ Run Extraction]  [⏹ Stop]  [🔄 Refresh Results]       │
│                                                              │
│   Status: Ready                                              │
├─────────────────────────────────────────────────────────────┤
│ Extraction Results                                           │
│ ┌───────────────────────────────────────────────────────┐   │
│ │Video ID│Video Title        │Duration│Tags   │Status  │   │
│ │────────│──────────────────│────────│───────│────────│   │
│ │abc123  │Example Video     │  145   │math   │✓Extract│   │
│ └───────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│ Console Output                                               │
│ ┌───────────────────────────────────────────────────────┐   │
│ │[12:34:56] Starting extraction...                       │   │
│ │[12:34:57] Fetching videos from channel...              │   │
│ └───────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Usage

### 1. Configure Parameters

**Number of Videos**
- How many videos you want to extract
- Default: 50
- Example: Enter 20 for a quick test run

**Max Video Duration (seconds)**
- Maximum length of videos to extract
- Videos longer than this are skipped
- Default: 600 (10 minutes)
- Example: Enter 300 for 5-minute max

**Channel Name**
- Select from dropdown
- Loaded from `channels.csv`
- Default: numberblocks

### 2. Start Extraction

Click **▶ Run Extraction** button to start.

The GUI will:
1. Validate your inputs
2. Fetch video list from YouTube
3. Filter by duration
4. Extract captions from each video
5. Save to output directory
6. Update results table

### 3. Monitor Progress

**Console Output** shows:
- Current video being processed
- Duration checks
- Caption extraction status
- Save confirmations
- Error messages (if any)

**Results Table** displays:
- Each processed video
- Real-time status updates
- Final extraction results

### 4. Stop If Needed

Click **⏹ Stop** button to gracefully halt extraction.

- Current video will complete
- Progress is saved
- Summary is displayed

### 5. View Results

Click **🔄 Refresh Results** to load previously extracted videos.

This queries the YouTube API to get:
- Video titles
- Durations
- Tags
- Current status

---

## Understanding Results

### Status Values

| Status | Meaning |
|--------|---------|
| ✓ Extracted | Successfully extracted and saved |
| Skipped (duration) | Video too long |
| Skipped (No captions available) | Captions not found |
| Skipped (TranscriptsDisabled) | Captions disabled |
| Error loading | Error fetching video details |
| ✓ Existing | Previously extracted (from refresh) |

### Console Messages

**Success Indicators:**
```
✓ Duration: 145s
💾 Saved: Example_Video_abc123.json
✓ Extraction Complete!
```

**Skip Indicators:**
```
⏭️  Skipped: Duration 850s > 600s
⏭️  Skipped: No captions available
```

**Error Indicators:**
```
❌ Error: API quota exceeded
Warning: Error getting duration
```

---

## Output Files

Extracted captions are saved to:

```
captions_output/
└── numberblocks/
    ├── Video_Title_abc123.json  (Caption data with timestamps)
    └── Video_Title_abc123.txt   (Formatted text with punctuation)
```

**JSON Format:**
```json
{
  "video_id": "abc123",
  "title": "Example Video",
  "captions": [
    {"text": "Hello", "start": 0.0, "duration": 1.5},
    {"text": "world", "start": 1.5, "duration": 1.2}
  ]
}
```

**TXT Format:**
```
Hello world. This is an example video about numbers.
```

---

## Tips & Best Practices

### Starting Out
1. **Test with small numbers** - Try 10 videos first
2. **Use shorter durations** - Set 300s for quick tests
3. **Monitor console** - Watch for errors

### Optimization
1. **Batch processing** - Run overnight for large extractions
2. **Duration filtering** - Adjust based on your needs
3. **Stop and resume** - Videos already extracted are skipped automatically

### Troubleshooting
1. **Check .env file** - Ensure YOUTUBE_API_KEY is set
2. **Verify channels.csv** - Confirm channel exists
3. **API limits** - YouTube API has daily quotas
4. **Rate limiting** - Built-in delays prevent throttling

---

## Common Scenarios

### Scenario 1: Extract Recent Videos
```
Number of Videos: 20
Max Duration: 600
Channel: numberblocks
```
Extracts 20 recent videos under 10 minutes.

### Scenario 2: Get Short Form Content
```
Number of Videos: 100
Max Duration: 180
Channel: numberblocks
```
Extracts 100 videos under 3 minutes (shorts).

### Scenario 3: Long Form Content
```
Number of Videos: 10
Max Duration: 3600
Channel: numberblocks
```
Extracts 10 videos under 1 hour.

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Alt+R | Run Extraction |
| Alt+S | Stop |
| Alt+F | Refresh Results |
| Ctrl+C | Copy selected result |

---

## Error Recovery

### If GUI Freezes
- Wait a moment - extraction runs in background thread
- UI remains responsive during extraction
- Check console for progress

### If Extraction Fails
1. Check error message in console
2. Verify API key in .env
3. Check internet connection
4. Try with fewer videos
5. Check API quota limits

### If Results Don't Appear
1. Click "Refresh Results"
2. Check `data/chunked_output/` directory
3. Verify videos were actually extracted
4. Check console for save confirmations

---

## Advanced Features

### Skipping Already Extracted Videos
The system automatically:
- Checks `chunked_output/` directory
- Skips videos already processed
- Only fetches new videos

### Rate Limiting
Built-in delays:
- 1.5s between YouTube API calls
- 2.0s between transcript fetches
- Prevents API throttling

### Thread Safety
- Extraction runs in separate thread
- UI remains responsive
- Progress updates in real-time

---

## Integration with Pipeline

The GUI integrates with:

1. **extract_additional_videos.py** - Core extraction logic
2. **channels.csv** - Channel configuration
3. **.env** - API credentials
4. **captions_output/** - Output directory
5. **chunked_output/** - Processed video tracking

Next pipeline steps:
```
GUI Extraction → captions_output/
                ↓
         chunk_transcripts.py
                ↓
         generate_embeddings.py
                ↓
         build_faiss_index.py
```

---

## Support & Documentation

- **GUI README**: `GUI_README.md`
- **Project README**: `PROJECT_README.md`
- **Extraction Guide**: See `extract_additional_videos.py` header
- **Chunking Guide**: `CHUNKING_GUIDE.md`
- **Embedding Guide**: `EMBEDDING_GUIDE.md`

---

## Version History

**v1.0.0** - Initial Release
- Basic extraction interface
- Results table
- Console output
- Stop control
- Refresh functionality

---

Enjoy using the YouTube Caption Extraction GUI! 🎉
