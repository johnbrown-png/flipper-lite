# Instruction Quality Scoring System

This system uses GPT-4o-mini to evaluate the instructional quality of mathematics teaching videos based on their transcripts.

## ⚠️ IMPORTANT: Curriculum-Informed Scoring Only (March 2026)

**All instruction quality scoring is now curriculum-informed** and happens automatically during small step searches in `flipper.py`. The system evaluates videos specifically for how well they teach a particular curriculum objective (small step) to a specific age group.

**Legacy batch scoring system archived:** The original generic batch scoring tools (`score_instruction_quality.py`, `review_instruction_scores.py`) have been moved to `_archive/` as they scored videos without curriculum context. These are preserved for research purposes only.

**Current system:**
- Scores are generated during runtime when searching for small steps
- Each score is specific to: video + age + curriculum small step
- Results cached in: `data/instruction_quality_runtime_cache.json`
- Scoring integrated directly into flipper.py search workflow

---

## Overview (Legacy Batch System - Archived)

The system evaluates videos on:
- Clarity of explanation
- Concrete examples
- Visual/diagrammatic explanations
- Worked examples
- Conceptual explanation
- Student engagement prompts

Videos receive a score from 0-100 with a justification.

## Workflow

### Phase 1: Test Sample (50 videos)

1. **Score 50 random videos:**
   ```bash
   python score_instruction_quality.py --sample
   ```
   
   This will:
   - Randomly select 50 unscored videos
   - Score them using GPT-4o-mini (~$0.06 cost)
   - Save results to `data/video_instruction_quality.json`
   - Display statistics and sample results
   - **STOP automatically for your review**

2. **Review the results:**
   
   View statistics:
   ```bash
   python score_instruction_quality.py --stats
   ```
   
   Review top/bottom scored videos:
   ```bash
   python review_instruction_scores.py --top 10
   python review_instruction_scores.py --bottom 10
   ```
   
   Check random samples:
   ```bash
   python review_instruction_scores.py --random 5
   ```
   
   Look at specific score ranges:
   ```bash
   python review_instruction_scores.py --range 70 89
   ```

3. **Manually verify video quality:**
   - Watch a few highly-scored videos - do they actually teach well?
   - Watch a few low-scored videos - are they genuinely poor quality?
   - Check if the justifications make sense

4. **Decide next step:**
   
   ✅ **If satisfied:** Proceed to Phase 2
   
   🔄 **If prompt needs adjustment:**
   - Edit `EVALUATION_PROMPT` in `data_pipeline/instruction_quality_scorer.py`
   - Delete scored entries or run:
     ```bash
     python score_instruction_quality.py --rescore-sample
     ```

### Alternative: Score Specific Videos

Instead of scoring a random sample, you can score specific videos by their video ID:

```bash
# Score a single video
python score_instruction_quality.py --video-ids VIDEO_ID

# Score multiple videos
python score_instruction_quality.py --video-ids VIDEO_ID1 VIDEO_ID2 VIDEO_ID3
```

**Finding video IDs:**

To see available video IDs from your indexed videos, use:

```bash
# List first 20 videos from inventory
python list_video_ids.py

# List 50 videos
python list_video_ids.py --limit 50

# Search for videos by title
python list_video_ids.py --search "addition"

# Show 10 random videos
python list_video_ids.py --random 10

# Filter by channel
python list_video_ids.py --channel "Khan"

# Use API cache instead of inventory (if needed)
python list_video_ids.py --source api_cache
```

**Note:** The script now uses `video_inventory.csv` by default, which contains all your indexed videos (~4,829 videos). This replaced the previous `data/api_cache.json` which only contained recently downloaded videos.

This is useful for:
- Testing the scoring on videos you've manually selected
- Re-scoring videos after prompt adjustments
- Scoring new videos without processing the entire catalog

The command will:
- Find the requested video(s) in the API cache
- Score them using GPT-4o-mini
- Display the score and justification for each video
- Prompt before re-scoring if videos are already scored


### Phase 2: Score All Videos

Once you're satisfied with the sample scoring:

```bash
python score_instruction_quality.py --continue
```

This will:
- Score all remaining ~4,780 videos
- Cost approximately $1.80
- Take approximately 2.5-3 hours
- Save progress every 10 videos (safe to interrupt)
- Skip non-English, songs, and videos without captions

**Note:** The system now uses `video_inventory.csv` (all indexed videos) instead of `data/api_cache.json`. This means all your downloaded and indexed videos are available for scoring.

### Phase 3: Integration (Future)

After all videos are scored, integrate into the ranking system:
- Add to `run_pipeline.py` to score new downloads
- Modify `flipper.py` ranking formula to incorporate instruction quality
- Add instruction quality display to GUI

## Files Created

- **`data_pipeline/instruction_quality_scorer.py`** - Core scoring class
- **`score_instruction_quality.py`** - Command-line interface for scoring
- **`review_instruction_scores.py`** - Helper to review scored videos
- **`list_video_ids.py`** - Helper to list available video IDs from cache
- **`data/video_instruction_quality.json`** - Scored video data (created on first run)

## Command Reference

### Scoring Commands

```bash
# Score 50 random sample videos (initial test)
python score_instruction_quality.py --sample

# Score specific videos by video ID (single or multiple)
python score_instruction_quality.py --video-ids VIDEO_ID
python score_instruction_quality.py --video-ids VIDEO_ID1 VIDEO_ID2 VIDEO_ID3

# Score all remaining videos (after review)
python score_instruction_quality.py --continue

# Re-score sample (after adjusting prompt)
python score_instruction_quality.py --rescore-sample

# Show statistics
python score_instruction_quality.py --stats

# Custom sample size
python score_instruction_quality.py --sample --sample-size 100
```

### Review Commands

```bash
# Show overall statistics
python review_instruction_scores.py --stats

# Show top 10 highest scored videos
python review_instruction_scores.py --top 10

# Show bottom 10 lowest scored videos
python review_instruction_scores.py --bottom 10

# Show videos in score range
python review_instruction_scores.py --range 70 89

# Show random sample
python review_instruction_scores.py --random 5

# Show specific video
python review_instruction_scores.py --video-id VIDEO_ID

# Compact view (no justifications)
python review_instruction_scores.py --top 20 --no-justification
```

## Score Interpretation

| Score Range | Quality | Description |
|-------------|---------|-------------|
| 90-100 | Excellent | Clear explanations, multiple worked examples, concrete/visual representations |
| 70-89 | Good | Clear explanations and examples, but limited representations or engagement |
| 50-69 | Adequate | Basic explanation but limited examples or conceptual development |
| 30-49 | Weak | Unclear explanation or minimal examples |
| 0-29 | Very Poor | Very poor instructional quality |

## Cost Estimates

Based on GPT-4o-mini pricing ($0.150/$0.600 per 1M tokens):

- **50 video sample:** ~$0.06
- **Full 4,829 videos:** ~$1.88
- **Per video:** ~$0.0004

## Data Format

The output file `data/video_instruction_quality.json` has this structure:

```json
{
  "VIDEO_ID": {
    "video_id": "VIDEO_ID",
    "title": "Video Title",
    "score": 85,
    "justification": "This video provides clear explanations...",
    "model": "gpt-4o-mini",
    "scored_at": "2026-03-06 14:30:00"
  }
}
```

## Skipped Videos

Videos are automatically skipped if:
- Language is not English (`language != 'en'`)
- Video is flagged as a song (`is_song = true`)
- No transcript available or transcript too short (<50 chars)

## Error Handling

- **API failures:** Automatic retry with exponential backoff (3 attempts)
- **Progress saving:** Scores saved every 10 videos (won't lose progress if interrupted)
- **Resume capability:** Re-running after interruption will skip already-scored videos

## Adjusting the Prompt

If you want to adjust what the LLM evaluates:

1. Edit `data_pipeline/instruction_quality_scorer.py`
2. Find the `EVALUATION_PROMPT` constant (around line 29)
3. Modify the scoring criteria
4. Test with: `python score_instruction_quality.py --rescore-sample`

## Future Integration

To automatically score new videos when downloaded:

1. Add to `data_pipeline/run_pipeline.py` (after readability calculation):
   ```python
   from data_pipeline.instruction_quality_scorer import InstructionQualityScorer
   
   scorer = InstructionQualityScorer()
   # Score only newly downloaded videos
   ```

2. Modify `flipper.py` ranking to incorporate instruction quality scores

3. Add instruction quality display to the UI

## Troubleshooting

**"OpenAI API key not found"**
- Ensure `.env` file contains `OPENAI_API_KEY=your_key_here`

**"Video ID not found in cache"**
- The script now uses `video_inventory.csv` by default (contains all indexed videos)
- If you want to use the API cache instead: `python score_instruction_quality.py --video-source api_cache --video-ids VIDEO_ID`
- Use `python list_video_ids.py` to see available video IDs

**"No unscored videos to sample"**
- All videos already scored, or check that video metadata is loaded correctly

**Scores seem inconsistent**
- Review the prompt in `instruction_quality_scorer.py`
- Consider adjusting the temperature parameter (currently 0.3)
- Try scoring a larger sample to see patterns

---

## Note on Documentation

**This document describes the legacy batch scoring system (archived March 2026).** The batch scoring tools referenced throughout this document are now located in `_archive/`:
- `_archive/batch_generic_instruction_scorer.py` (formerly `score_instruction_quality.py`)
- `_archive/batch_generic_review_scores.py` (formerly `review_instruction_scores.py`)

The current production system uses **curriculum-informed scoring** integrated directly into flipper.py's small step search functionality. See the note at the top of this document for details on the current system.
