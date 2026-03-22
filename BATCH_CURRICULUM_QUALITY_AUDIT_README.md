# Batch Curriculum Quality Audit

## Overview

`batch_curriculum_quality_audit.py` is a batch processing tool that systematically audits all curriculum small steps to identify which have sufficient high-quality video coverage. It replicates the Flipper search workflow (semantic search + instruction quality scoring) for every small step in your curriculum CSV.

## Purpose

**Problem**: Manually clicking through Flipper for hundreds of small steps to check video quality is time-consuming.

**Solution**: This script automates the entire process:
1. Reads curriculum CSV (all rows and small steps 1-7)
2. For each small step: performs semantic search using FAISS index
3. Scores top 5 videos with LLM-based instruction quality evaluation
4. Outputs detailed results showing which small steps lack good video coverage

## Key Benefits

✅ **Automated QA** - Batch process all curriculum small steps without manual clicking  
✅ **Cache Population** - Pre-scores videos so future Flipper searches are instant and free  
✅ **Cost Efficient** - Caching means LLM calls are only made once per video+curriculum combination  
✅ **Actionable Report** - Identifies exactly which small steps need more/better videos  
✅ **Same Logic as Flipper** - Uses identical search and scoring algorithms

## Requirements

- Python environment with all dependencies installed (`.venv` activated)
- FAISS index built (`data/faiss_index/`)
- OpenAI API key configured (`.env` file)
- Curriculum CSV file with proper format

## Usage

### Basic Command

```powershell
python batch_curriculum_quality_audit.py --curriculum "Curriculum/Maths/mat_curr_short_import - 08032026.csv"
```

### Test with Sample (Recommended First Run)

Process only first 5 rows to test before full run:

```powershell
python batch_curriculum_quality_audit.py --curriculum "Curriculum/Maths/mat_curr_short_import - 08032026.csv" --sample 5
```

### Custom Output Location

```powershell
python batch_curriculum_quality_audit.py --curriculum "Curriculum/Maths/mat_curr_short_import - 08032026.csv" --output "results/audit_march_2026.csv"
```

### Advanced Options

```powershell
python batch_curriculum_quality_audit.py --curriculum "Curriculum/Maths/mat_curr_short_import - 08032026.csv" --top-k 15 --top-n 7
```

**Options:**
- `--curriculum` (required) - Path to curriculum CSV file
- `--output` (default: `curriculum_quality_audit.csv`) - Output CSV file path
- `--sample` (optional) - Process only first N rows (for testing)
- `--top-k` (default: 10) - Number of semantic search results to retrieve
- `--top-n` (default: 5) - Number of top results to score with LLM

## How It Works

### Step-by-Step Process

For each small step in the curriculum:

1. **Semantic Search**
   - Uses `SS{i}_desc_short` column as search query
   - Generates embedding via OpenAI API
   - Searches FAISS index for top K video chunks
   - Calculates cosine similarity scores
   - Deduplicates by video_id (keeps highest scoring chunk)

2. **Instruction Quality Scoring**
   - Takes top N unique videos from semantic search
   - Scores each video with LLM using curriculum context:
     - Learner age
     - Topic
     - Small step name and description
   - Returns score (0-100) and justification
   - **Uses cache** - checks if video+curriculum combo already scored

3. **Results Aggregation**
   - Combines semantic match score + instruction quality score
   - Identifies small steps with <3 "good" videos
   - Good video = ≥60% semantic match AND ≥60/100 instruction quality

## Output Files

### 1. Main Results CSV

**File**: `curriculum_quality_audit.csv` (or custom `--output` name)

**Columns**:
- `unique_row` - Curriculum row identifier (e.g., "Year 1AutumnPlace value within 10 A")
- `year` - Year level (e.g., "Year 1")
- `age` - Learner age range (e.g., "5-6")
- `topic` - Curriculum topic (e.g., "Place value within 10 A")
- `small_step_num` - Small step number (1-7)
- `small_step_name` - Small step title (e.g., "Sort objects")
- `small_step_desc_short` - Short description used for search
- `video_id` - YouTube video ID
- `video_title` - Video title
- `video_channel` - Channel name
- `video_duration` - Duration in seconds
- `video_language` - Language code (e.g., "en")
- `video_is_song` - Boolean flag for song videos
- `semantic_match` - Cosine similarity score (0-1, higher is better)
- `instruction_quality` - LLM score (0-100, higher is better)
- `instruction_justification` - LLM explanation of score
- `instruction_from_cache` - True if result was cached (no new API call)
- `instruction_error` - Error message if scoring failed
- `rank` - Rank within this small step's results (1-5)
- `chunk_index` - Which chunk of the video matched

**Example Row**:
```csv
Year 1AutumnPlace value,Year 1,5-6,Place value within 10 A,1,Sort objects,"Children learn to sort...",abc123,"Sorting Colors Video",MathChannel,310,en,False,0.82,67,"Clear visual examples...",True,"",1,0
```

### 2. Summary Report

**File**: `curriculum_quality_audit.summary.txt`

**Contents**:
- Overall statistics (rows, steps, videos scored)
- Cache hit rate (shows cost savings)
- **List of small steps with insufficient videos** (<3 good videos)
  - This is the key actionable output!

**Example Summary**:
```
================================================================================
CURRICULUM QUALITY AUDIT SUMMARY
================================================================================
Generated: 2026-03-10 14:30:00
Curriculum: Curriculum/Maths/mat_curr_short_import - 08032026.csv

OVERALL STATISTICS
--------------------------------------------------------------------------------
Total curriculum rows processed: 45
Total small steps audited: 285
Total videos scored: 1425
LLM cache hits: 1120 (78.6%)
LLM cache misses (new API calls): 305

SMALL STEPS WITH INSUFFICIENT GOOD VIDEOS
--------------------------------------------------------------------------------
Criteria: <3 videos with ≥60% semantic match AND ≥60/100 instruction quality
Count: 12

  • Year 1AutumnPlace value within 10 A
    Topic: Place value within 10 A
    Small Step 3: Count objects from a larger group
    Good videos: 2/5

  • Year 2SpringMeasurement - Length
    Topic: Length and Height
    Small Step 5: Compare lengths using standard units
    Good videos: 1/5

  [... more entries ...]
```

## Console Output

During execution, you'll see real-time progress:

```
================================================================================
ROW 1/45: Year 1AutumnPlace value within 10 A
Topic: Place value within 10 A
================================================================================

[Row 1/45] [Step 1/7]
  Small Step 1: Sort objects
  🔍 Semantic search...
  ✓ Found 8 unique videos
  🤖 Scoring top 5 videos with LLM...
    #1 Sorting Colors and Shapes                        | Sem:  82.3% | Inst:  67% 💾
    #2 How to Sort Objects                              | Sem:  78.1% | Inst:  72% 💾
    #3 Sorting Game for Kids                            | Sem:  75.4% | Inst:  58% 🆕
    #4 Learn to Sort                                    | Sem:  71.2% | Inst:  63% 🆕
    #5 Sorting Activity                                 | Sem:  68.9% | Inst:  55% 💾

[Row 1/45] [Step 2/7]
  Small Step 2: Count objects
  ...
```

**Icons**:
- 💾 = Cache hit (free - result already computed)
- 🆕 = Cache miss (new LLM API call - costs money)

## Cost Estimation

### First Run (No Cache)

Assuming:
- 50 curriculum rows × average 6 small steps = 300 small steps
- 5 videos scored per small step = 1,500 LLM calls
- Average 2,000 tokens per call (1,500 input + 500 output)
- Using `gpt-4o-mini` at $0.15/$0.60 per 1M tokens (input/output)

**Estimated cost**: $0.68 for first full run

### Subsequent Runs

- Cache hit rate: 80-95% (depending on video overlap)
- Cost: $0.07-$0.14 per run

### Flipper Benefit

After batch run completes:
- All teacher searches in Flipper = **$0.00** for cached results
- 100 teacher searches × 10 small steps each = 1,000 searches = **FREE** (vs ~$50 without cache)

## Curriculum CSV Format Requirements

The script expects these columns:

**Required Columns**:
- `UniqueRow` - Unique identifier for the curriculum row
- `Year` - Year level (e.g., "Year 1")
- `Age` - Age range (e.g., "5-6")
- `Topic` - Topic name

**Small Step Columns (for each i from 1-7)**:
- `Small Step {i}` - Small step name/title
- `SS{i}_desc_short` - Short description (THIS IS USED FOR SEARCH)
- `SS{i}_desc` - Full description (optional, not used for search)

**Example**:
```csv
UniqueRow,Year,Age,Topic,Small Step 1,SS1_desc_short,SS1_desc,...
Year 1AutumnPlace value,Year 1,5-6,Place value within 10 A,Sort objects,"Children learn to sort object collections...","Detailed description...",...
```

## Cache Management

### How Caching Works

The script uses `data/instruction_quality_runtime_cache.json` to store LLM scores.

**Cache Key Format**: `{video_id}|{age}|{small_step_name}`

**Example**: `abc123xyz|5-6|Sort objects`

### When Cache is Used

✅ Same video + same age + same small step = **Cache hit** (instant, free)  
❌ Different combination = **Cache miss** (new LLM call, costs money)

### Viewing Cache

```powershell
# View cache file
Get-Content data/instruction_quality_runtime_cache.json | jq
```

### Clearing Cache (if needed)

```powershell
# Clear cache via Flipper UI
# Click "Clear Instruction Quality Cache" button in Flipper sidebar

# Or manually delete cache file
Remove-Item data/instruction_quality_runtime_cache.json
```

## Interpreting Results

### What is a "Good" Video?

By default, the script considers a video "good" if:
- **Semantic Match ≥ 60%** (0.6 cosine similarity)
- **Instruction Quality ≥ 60/100** (LLM score)

### Why <3 Good Videos is the Threshold

- Teachers need multiple video options for differentiation
- Some videos may not work in certain contexts (blocked, songs, language)
- Having 3+ options ensures robust curriculum coverage

### Action Items from Results

**Review the summary report** and for each small step with insufficient videos:

1. **<1 good video**: High priority - Search or create new videos
2. **1-2 good videos**: Medium priority - Find 1-2 more options
3. **3+ good videos**: Well covered - no action needed

**Consider**:
- Are the semantic matches too low? (May need better video tagging/descriptions)
- Are the instruction quality scores low? (May need better explainer videos)
- Are videos available but marked as songs? (Filter songs if not appropriate)

## Troubleshooting

### Error: "Curriculum file not found"

**Solution**: Check file path is correct and uses forward slashes or escaped backslashes:
```powershell
# Good
--curriculum "Curriculum/Maths/mat_curr_short_import - 08032026.csv"

# Also good (Windows)
--curriculum "Curriculum\Maths\mat_curr_short_import - 08032026.csv"
```

### Error: "FAISS index not found"

**Solution**: Build the FAISS index first:
```powershell
python data_pipeline/build_faiss_index.py
```

### Error: "OpenAI API key not found"

**Solution**: Ensure `.env` file exists with:
```
OPENAI_API_KEY=sk-...your-key...
```

### Script Runs Very Slowly

**Possible causes**:
- Low cache hit rate (first run is slower)
- Network latency to OpenAI API
- Large curriculum (many small steps)

**Solutions**:
- Use `--sample 5` to test first
- Check internet connection
- Consider running during off-peak hours

### High Cost / Many Cache Misses

**Possible causes**:
- Cache was cleared recently
- Small step names changed in curriculum
- First run through curriculum

**Solutions**:
- Don't clear cache unnecessarily
- Keep small step names consistent
- Cache builds up over time - subsequent runs cheaper

### No Results for Some Small Steps

**Possible causes**:
- Empty `SS{i}_desc_short` column
- Very niche topic with no matching videos
- All matching videos were deleted (soft-delete filtering)

**Solutions**:
- Check CSV has short descriptions populated
- Consider adding more videos to your collection
- Review deletion log if unexpected

## Best Practices

### Before First Run

1. ✅ Test with `--sample 5` flag first
2. ✅ Check OpenAI API quota/limits
3. ✅ Verify curriculum CSV format
4. ✅ Ensure FAISS index is up-to-date

### During Run

1. ✅ Monitor console output for errors
2. ✅ Watch cache hit rate (should increase over time)
3. ✅ Don't interrupt - progress is saved periodically

### After Run

1. ✅ Review summary report first (high-level overview)
2. ✅ Open CSV in Excel/spreadsheet for detailed analysis
3. ✅ Sort by `instruction_quality` to find poorest videos
4. ✅ Filter for small steps with <3 good videos
5. ✅ Share results with content team

### Maintenance

1. ✅ Re-run monthly to check new videos
2. ✅ Keep cache file backed up
3. ✅ Update curriculum CSV as content changes
4. ✅ Monitor OpenAI API costs

## Integration with Flipper

This script and Flipper share the same cache, so:

**Batch Run Benefits Flipper**:
- Videos scored in batch → cached for Flipper searches
- Teachers get instant results (no waiting for LLM)
- Zero API costs for cached results

**Flipper Benefits Batch Run**:
- Teachers' searches populate cache
- Next batch run finds more cache hits
- Reduced cost over time

**Workflow Recommendation**:
1. Run batch audit weekly/monthly
2. Teachers use Flipper for daily searches
3. Both systems benefit from shared cache
4. Costs decrease over time as cache grows

## Related Files

- `flipper.py` - Main Flipper search interface (web UI)
- `query_embedder.py` - Generates embeddings for search queries
- `data_pipeline/instruction_quality_scorer.py` - LLM-based video scoring
- `data/instruction_quality_runtime_cache.json` - Shared cache file
- `data/faiss_index/` - Semantic search index

## Support

For issues or questions:
1. Check this README
2. Review console error messages
3. Verify all requirements are met
4. Test with `--sample 5` flag to isolate issues

---

**Last Updated**: March 10, 2026  
**Script Version**: 1.0  
**Maintainer**: Flipper Project
