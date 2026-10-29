# YouTube Caption Extraction GUI

A user-friendly graphical interface for the YouTube caption extraction pipeline.

## Features

- **Easy Configuration**: Simple input fields for extraction parameters
- **Real-time Progress**: Live console output showing extraction progress
- **Results Table**: Visual display of extracted videos with details
- **Async Processing**: Non-blocking UI that remains responsive during extraction
- **Stop Control**: Ability to stop extraction mid-process
- **Refresh Results**: View previously extracted videos

## Usage

### Starting the GUI

Run the GUI application:

```bash
python gui_pipeline.py
```

### Input Parameters

1. **Number of Videos**: How many videos to extract (default: 50)
2. **Max Video Duration (seconds)**: Videos longer than this will be skipped (default: 600)
3. **Channel Name**: Select channel from dropdown (loaded from channels.csv)

### Controls

- **▶ Run Extraction**: Start the extraction process
- **⏹ Stop**: Stop the extraction process (graceful shutdown)
- **🔄 Refresh Results**: Load existing extracted videos into the results table

### Results Table

The results table displays:
- **Video ID**: YouTube video identifier
- **Video Title**: Full title of the video
- **Duration (s)**: Video length in seconds
- **Tags**: Associated video tags (first 3)
- **Status**: Extraction status (✓ Extracted, Skipped, Error, etc.)

### Console Output

The console output section shows:
- Extraction progress
- Video processing status
- Errors and warnings
- Summary statistics

## Requirements

- Python 3.8+
- tkinter (included with Python)
- All dependencies from requirements.txt
- Valid YOUTUBE_API_KEY in .env file
- channels.csv file with channel information

## How It Works

1. **Initialization**: Loads channels from channels.csv
2. **Validation**: Checks user inputs and API key
3. **Fetching**: Retrieves video list from channel
4. **Processing**: 
   - Checks video duration
   - Extracts captions
   - Saves to output directory
   - Updates results table
5. **Completion**: Displays summary and final statistics

## Output

Extracted captions are saved to:
- `captions_output/[channel_name]/[title]_[video_id].json` - Caption data with timestamps
- `captions_output/[channel_name]/[title]_[video_id].txt` - Formatted text with punctuation

## Features in Detail

### Thread Safety
The GUI runs extraction in a separate thread to keep the interface responsive. All UI updates are properly synchronized.

### Rate Limiting
Built-in delays prevent API rate limit issues:
- 1.5s between YouTube API calls
- 2.0s between transcript fetches

### Error Handling
Graceful handling of:
- Missing captions
- API errors
- Duration filtering
- Invalid inputs

### Results Refresh
The "Refresh Results" button scans the chunked_output directory and loads metadata for all previously extracted videos using the YouTube API.

## Tips

- Start with a small number of videos (10-20) to test
- Increase max duration to include longer videos
- Monitor console output for detailed progress
- Use Stop button if you need to halt extraction
- Refresh results to verify previously extracted content

## Troubleshooting

**GUI doesn't start:**
- Ensure tkinter is installed (comes with Python)
- Check Python version (3.8+ required)

**No channels appear:**
- Verify channels.csv exists in project root
- Check CSV format (channel_id, channel_name columns)

**Extraction fails:**
- Verify YOUTUBE_API_KEY in .env file
- Check internet connection
- Ensure API key has proper permissions

**Empty results table:**
- Click "Refresh Results" to load existing data
- Check data/chunked_output directory exists
- Verify YouTube API access

## Architecture

```
gui_pipeline.py
├── PipelineGUI (Main GUI class)
│   ├── setup_ui() - Create interface
│   ├── start_extraction() - Launch extraction thread
│   ├── run_extraction() - Execute extraction logic
│   ├── add_result_row() - Update results table
│   └── refresh_results() - Load existing results
└── Uses EnhancedCaptionExtractor from extract_additional_videos.py
```

## Future Enhancements

Potential additions:
- Export results to CSV
- Video preview thumbnails
- Filter results by status
- Batch channel processing
- Progress bar for extraction
- Dark mode theme
- Save/load extraction configurations
