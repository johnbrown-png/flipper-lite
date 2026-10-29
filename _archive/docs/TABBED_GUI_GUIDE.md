# Tabbed GUI Guide - Three Ways to Extract Captions

## Overview

The new tabbed GUI provides **three extraction methods** in one interface:

1. **📺 Channel Extraction** - Extract from entire channels (original functionality)
2. **🎯 Video IDs** - Extract specific videos by ID (new - for curriculum gaps)
3. **🔍 Topic Search** - Discover and extract videos by keywords (new - for gap discovery)

---

## Tab 1: 📺 Channel Extraction

**Use when:** You want to extract videos from entire channels listed in `channels.csv`

### How to Use:
1. Select channel from dropdown
2. Set number of videos to extract
3. Set max video duration filter
4. Click **▶ Start Extraction**

### Features:
- Bulk extraction from curated channels
- Auto-excludes already downloaded videos
- Respects duration filters
- Shows real-time progress

**Example:** Extract 50 videos under 20 minutes from Khan Academy

---

## Tab 2: 🎯 Video ID Extraction

**Use when:** You know specific video IDs you want (filling curriculum gaps)

### Input Methods:

#### Method 1: Load from File
1. Click **📁 Load from File**
2. Select `.txt` or `.csv` file
3. Click **▶ Extract Captions**

**File Formats Supported:**

**Simple text file (video_ids.txt):**
```
SfxULALs_u8
ocWCzDAH5lI
JrVd-czHl_g
```

**CSV with metadata (curriculum_gaps.csv):**
```csv
video_id,topic,year_group,curriculum_code
SfxULALs_u8,Multiplication with Carrying,Year 3,3MA02
ocWCzDAH5lI,Python Classes,Year 9,9CS01
JrVd-czHl_g,Conservation of Energy,Year 10,10PH03
```

#### Method 2: Paste Directly
1. Paste video IDs into text box (one per line)
2. Accepts full URLs or just IDs
3. Click **▶ Extract Captions**

**Accepted formats:**
- Video IDs: `SfxULALs_u8`
- Full URLs: `https://www.youtube.com/watch?v=SfxULALs_u8`
- Short URLs: `https://youtu.be/SfxULALs_u8`
- Comments: Lines starting with `#` are ignored

### Features:
- Batch extraction (multiple videos at once)
- Auto-fetches video metadata
- Shows extraction progress
- Organizes by topic (if CSV has 'topic' column)

### Output Location:
```
captions_output/
  Video_IDs/ (or organized by topic)
    video_title_SfxULALs_u8.json
    video_title_SfxULALs_u8.txt
```

**Example Use Case:**
```
You identified gaps in Year 4 fractions coverage.
You found 3 perfect videos manually.
→ Paste their IDs here and extract!
```

---

## Tab 3: 🔍 Topic Search

**Use when:** You need to discover videos covering specific topics

### How to Use:

#### Step 1: Search for Videos
1. Enter search keywords (e.g., "long division")
2. Set max duration filter (e.g., 300 seconds = 5 minutes)
3. Set max results (e.g., 20 videos)
4. Optional: Filter by specific channel
5. Click **🔍 Search Videos**

#### Step 2: Review Results
- Browse search results in table
- Shows: Video ID, Title, Channel, Duration
- Click checkboxes to select videos

#### Step 3: Extract or Save
- **▶ Extract Selected** - Extract captions immediately
- **💾 Save IDs to File** - Save selected IDs for later
- **✓ Select All** / **✗ Deselect All** - Quick selection

### Search Tips:

**For introductory content:**
```
Search: "introduction to fractions"
Filter: Max duration 300s (5 min)
Channel: Khan Academy
```

**For specific skills:**
```
Search: "multiplying fractions word problems"
Filter: Max duration 600s (10 min)
Channel: All channels
```

**For age-appropriate content:**
```
Search: "photosynthesis for kids"
Filter: Max duration 240s (4 min)
Channel: BBC Bitesize
```

### Features:
- Searches across YouTube using official API
- Filters by duration, channel, date
- Checkbox selection for batch extraction
- Save search results for review
- Excludes already-downloaded videos

### API Quota Cost:
- **100 units per search** (you have 10,000 daily)
- Can do ~100 searches per day
- Be strategic with searches

**Example Workflow:**
```
1. Search: "division remainders"
2. Found 15 videos
3. Select 5 most relevant
4. Extract captions
5. Fill curriculum gap! ✓
```

---

## Complete Curriculum Gap-Filling Workflow

### Scenario: Year 4 Fractions Division - No Coverage

**Step 1: Discover Content (Tab 3: Topic Search)**
```
Search query: "dividing fractions visual"
Max duration: 360s (6 minutes)
Max results: 15
→ Found 12 relevant videos
```

**Step 2: Save for Review (Still in Tab 3)**
```
Select 5 best videos
Click "💾 Save IDs to File"
Save as: curriculum_gaps_fractions.csv
```

**Step 3: Extract (Tab 2: Video IDs)**
```
Load file: curriculum_gaps_fractions.csv
Check "Organize by topic"
Click "▶ Extract Captions"
→ 5 videos extracted to Video_IDs/Fractions_Division/
```

**Step 4: Process for Search**
```
Run chunking and embedding pipeline
Build FAISS index
→ Students can now search for "dividing fractions"!
```

---

## Tips & Best Practices

### For Channel Extraction (Tab 1):
- Use for initial bulk extraction
- Run overnight for large channels
- Set appropriate duration filters

### For Video ID Extraction (Tab 2):
- Perfect for targeted gap-filling
- Use CSV format to track curriculum codes
- Can process 100+ videos in one batch

### For Topic Search (Tab 3):
- Use specific, descriptive keywords
- Filter by duration for age-appropriate content
- Save results before extracting (for record-keeping)
- Be mindful of API quota (100 units/search)

---

## File Organization

The tabbed GUI organizes extracted captions:

```
captions_output/
  
  Khan_Academy/          ← From Tab 1 (Channel Extraction)
    video1.json
    video2.json
  
  Video_IDs/             ← From Tab 2 (Video ID Extraction)
    Custom_Videos/       ← Default subfolder
      video3.json
    Year_3_Multiplication/ ← If organized by topic
      video4.json
  
  Curriculum_Gaps/       ← From Tab 3 (Topic Search → Extract)
    video5.json
```

---

## Keyboard Shortcuts

- **Tab**: Switch between text fields
- **Enter**: Submit form (in search box)
- **Ctrl+A**: Select all text
- **Ctrl+V**: Paste video IDs

---

## Common Workflows

### Workflow 1: Regular Bulk Extraction
```
Tab 1 → Select channel → Set filters → Extract
```

### Workflow 2: Fill Specific Gap
```
Tab 2 → Paste video IDs → Extract
```

### Workflow 3: Discover Then Extract
```
Tab 3 → Search → Select videos → Extract
or
Tab 3 → Search → Save IDs → Tab 2 → Load file → Extract
```

### Workflow 4: Curriculum Coverage Audit
```
1. Identify missing topics (external analysis)
2. Tab 3 → Search each topic → Save results
3. Tab 2 → Load all saved IDs → Batch extract
4. Process and index
5. Re-audit coverage → Repeat if needed
```

---

## Troubleshooting

### "No videos selected" in Topic Search
- Click checkboxes in first column of results
- Or use "✓ Select All" button

### "Failed to load file" in Video IDs
- Check file format (see examples above)
- Ensure UTF-8 encoding
- Check for empty lines or special characters

### Search returns no results
- Broaden search terms
- Remove duration filter
- Try "All channels" instead of specific channel
- Check API quota hasn't been exceeded

### Extraction fails
- Check YouTube API key in `.env` file
- Check internet connection
- Videos may have no captions (common)
- May be geo-blocked or private

---

## Status Messages

| Message | Meaning |
|---------|---------|
| "Ready" | System idle, ready for input |
| "Searching..." | Performing YouTube search |
| "Extracting..." | Downloading captions |
| "Completed" | Extraction finished successfully |
| "Failed - ..." | Error occurred, see console |

---

## Advanced: Combining All Three Methods

For comprehensive curriculum coverage:

1. **Initial extraction** (Tab 1)
   - Extract from all curated channels
   - Builds foundation library

2. **Gap analysis** (External)
   - Identify missing curriculum topics
   - List topics needing coverage

3. **Content discovery** (Tab 3)
   - Search for each missing topic
   - Review and select best videos
   - Save selected IDs

4. **Targeted extraction** (Tab 2)
   - Load saved IDs
   - Batch extract all gap-filling content

5. **Process and verify** (External)
   - Run embedding and indexing
   - Test search with curriculum queries
   - Confirm gaps are filled

This workflow ensures **complete curriculum coverage** across all topics!

---

## Summary: When to Use Each Tab

| Tab | Best For | Key Benefit |
|-----|----------|-------------|
| 📺 Channels | Bulk extraction from known channels | Automated, hands-off |
| 🎯 Video IDs | Specific videos you've identified | Precise, targeted |
| 🔍 Topic Search | Discovering content for topics | Exploration, discovery |

**All three work together** to give you complete control over your educational video library!
