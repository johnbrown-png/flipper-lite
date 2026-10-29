# Readability Scoring for Video Transcripts

This feature calculates Flesch Reading Ease and Flesch-Kincaid Grade Level scores for all video transcripts to help rank videos by educational appropriateness.

## Setup

Install the required package:
```bash
pip install textstat
```

Or install all requirements:
```bash
pip install -r requirements.txt
```

## Usage

### For Existing Videos (One-Time Backfill)

Run the backfill script to calculate readability scores for all existing videos:

```bash
python backfill_readability.py
```

This will:
- Process all caption files in `data/captions_output/`
- Calculate Flesch Reading Ease and Flesch-Kincaid Grade Level
- Save scores to `data/video_readability.json`
- Skip videos that already have scores (unless you use `--force`)

Options:
```bash
python backfill_readability.py --help
python backfill_readability.py --force  # Recalculate all scores
python backfill_readability.py --captions-dir custom/path  # Custom captions directory
```

### For New Videos (Automatic)

Readability scores are **automatically calculated** in both the GUI and command-line pipeline:

#### GUI Extraction (gui_main.py)
When extracting videos through any of the GUI tabs:
- 📺 **Channel Extraction Tab**: Calculates readability after each video extraction
- 🎯 **Video IDs Tab**: Calculates readability after each video extraction  
- 🔍 **Topic Search Tab**: Calculates readability when extracting selected videos

Readability is calculated immediately after caption extraction and logged in the console output.

#### Command-Line Pipeline
```bash
python data_pipeline/run_pipeline.py
```

The pipeline flow is:
1. Extract captions ✅
2. **Calculate readability** ⭐ (automatic)
3. Chunk transcripts ✅
4. Generate embeddings ✅
5. Build FAISS index ✅

To skip readability calculation:
```bash
python data_pipeline/run_pipeline.py --skip-readability
```

## Output Format

Scores are saved to `data/video_readability.json`:

```json
{
  "video_id_123": {
    "video_id": "video_id_123",
    "title": "Counting to 10",
    "flesch_reading_ease": 72.5,
    "flesch_kincaid_grade": 6.8,
    "word_count": 850
  },
  ...
}
```

## Understanding the Scores

### Flesch Reading Ease (0-100, higher = easier)
- **90-100**: Very Easy (5th grade)
- **80-90**: Easy (6th grade)
- **70-80**: Fairly Easy (7th grade)
- **60-70**: Standard (8th-9th grade)
- **50-60**: Fairly Difficult (10th-12th grade)
- **30-50**: Difficult (College)
- **0-30**: Very Difficult (College graduate)

### Flesch-Kincaid Grade Level
- Direct grade level estimate (e.g., 7.2 = 7th grade level)
- Lower = easier to read
- Typical range for educational videos: 5-9

## Using Scores in flipper.py

Readability scores are now **integrated into the flipper.py search interface**:

### Viewing Readability Stats

1. Run flipper: `streamlit run flipper.py`
2. Enable the **🔬 Diagnostics** checkbox
3. Perform a search
4. Expand the "🔬 Diagnostic Data" section for any video result

The diagnostics panel shows:
- **Reading Ease**: Flesch Reading Ease score (0-100 scale, higher = easier)
- **Grade Level**: Flesch-Kincaid Grade Level (e.g., 7.2 = 7th grade)
- **Word Count**: Total words in the transcript

### Interpreting the Scores

Use these scores to:
- **Identify appropriate difficulty levels** for your target audience
- **Compare video complexity** at a glance
- **Filter content** by reading level (future enhancement)
- **Detect outliers** (very difficult or very easy content)

### Technical Implementation

The readability scores are:
- Loaded once at startup for fast performance
- Matched by video ID using caption filename format
- Displayed alongside similarity metrics in diagnostics

## Technical Notes

### How It Works

1. **Text Extraction**: Extracts full transcript from caption JSON files
2. **Sentence Boundary Detection**: Uses multiple heuristics to infer sentence breaks (YouTube captions lack punctuation):
   - Timing gaps > 0.8 seconds between segments
   - Word counting (period every ~18 words as fallback)
   - Natural ending patterns (e.g., "right", "okay", "done")
3. **Readability Calculation**: Uses `textstat` library to calculate Flesch scores
4. **Storage**: Saves to persistent JSON file for fast lookup during search

**Note**: The improved sentence detection algorithm (March 2026) fixes issues with overlapping timestamps in auto-generated captions, ensuring accurate readability scores for all videos.

### Performance

- Processing ~6,500 videos takes approximately 5-10 minutes
- Zero OpenAI API cost (local calculation only)
- No re-embedding required
- Incremental updates are automatic with pipeline

### Maintenance

Readability scores are calculated once per video and stored. They don't need to be recalculated unless:
- Caption files are updated
- You want to use different calculation parameters
- The backfill script failed for some videos

## Troubleshooting

**Import error for textstat:**
```bash
pip install textstat
```

**"Insufficient text" error:**
- Videos with very short transcripts (<100 characters) cannot be scored
- These are marked with `"error": "Insufficient text"` in the JSON

**Scores seem incorrect:**
- YouTube auto-captions may have inaccuracies affecting scores
- Scores are estimates based on transcript text quality
- Consider the scores as relative rankings rather than absolute measures
