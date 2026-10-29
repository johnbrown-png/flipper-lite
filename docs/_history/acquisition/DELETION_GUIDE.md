# Content Deletion Guide

## Overview

The Content Deletion system allows you to safely remove videos and channels from your Flipper application, ensuring all traces are cleaned up across the entire system.

## What Gets Deleted

When you delete content, the following locations are cleaned:

### For Individual Videos
1. **Metadata Files**
   - `video_inventory.csv` - Row removed
   - `extraction_state.json` - Video entry removed
   - `data/api_cache.json` - Video cache removed

2. **Content Files**
   - `captions_output/{channel}/{title}_{video_id}.json` - Deleted
   - `captions_output/{channel}/{title}_{video_id}.txt` - Deleted
   - `data/captions_output/{channel}/{title}_{video_id}.*` - Deleted (if exists)

3. **Processed Data**
   - `data/chunked_output/{video_id}_chunked.json` - Deleted
   - `data/embeddings_output/{video_id}_embeddings.json` - Deleted

4. **Search Index**
   - FAISS index requires rebuild (automatic or manual)

### For Entire Channels
All of the above for each video, plus:
- `channels.csv` - Channel row removed
- `captions_output/{channel_name}/` - Entire folder deleted

## Usage Methods

### 1. Interactive Mode (Recommended)

```powershell
python delete_content.py
```

This launches an interactive menu where you can:
- Delete single videos
- Delete entire channels
- Preview deletions (dry run)
- Validate deletions
- Get confirmation prompts

### 2. Command-Line Mode

#### Delete a Single Video
```powershell
# With confirmation prompt
python delete_content.py --video VIDEO_ID

# Skip confirmation
python delete_content.py --video VIDEO_ID --yes

# With automatic index rebuild
python delete_content.py --video VIDEO_ID --yes --rebuild-index
```

#### Delete an Entire Channel
```powershell
# With confirmation prompt
python delete_content.py --channel CHANNEL_ID

# Skip confirmation
python delete_content.py --channel CHANNEL_ID --yes

# With automatic index rebuild
python delete_content.py --channel CHANNEL_ID --yes --rebuild-index
```

#### Preview Deletions (Dry Run)
```powershell
# Preview video deletion without executing
python delete_content.py --video VIDEO_ID --dry-run

# Preview channel deletion without executing
python delete_content.py --channel CHANNEL_ID --dry-run
```

#### Rebuild FAISS Index Only
```powershell
python delete_content.py --rebuild-index
```

#### Validate Deletion
```powershell
# Check if video was fully deleted
python delete_content.py --validate VIDEO_ID
```

### 3. Programmatic Usage

```python
from data_pipeline.deletion_manager import DataDeletionManager

# Initialize manager
manager = DataDeletionManager(
    dry_run=False,        # Set True to preview without deleting
    create_backup=True    # Set False to skip backups
)

# Delete a video
results = manager.delete_video("VIDEO_ID")
manager.save_deletion_log()

# Delete a channel
results = manager.delete_channel("CHANNEL_ID")
manager.save_deletion_log()

# Rebuild FAISS index
success = manager.rebuild_faiss_index()

# Validate deletion
validation = manager.validate_deletion("VIDEO_ID")
if validation['fully_deleted']:
    print("Video fully deleted")
else:
    print("Remaining traces:", validation['remaining_traces'])
```

## Safety Features

### 1. Automatic Backups
Before any deletion, metadata files are automatically backed up to:
```
_deletion_backups/
  video_inventory_{timestamp}.csv
  channels_{timestamp}.csv
  extraction_state_{timestamp}.json
  api_cache_{timestamp}.json
  faiss_index_metadata_{timestamp}.json
  faiss_index_{timestamp}.bin
```

### 2. Dry Run Mode
Preview exactly what will be deleted without executing:
```powershell
python delete_content.py --video VIDEO_ID --dry-run
```

### 3. Deletion Logs
Every deletion creates a detailed log in:
```
_deletion_logs/
  deletion_log_{timestamp}.json
```

Log includes:
- Timestamp of each operation
- Files deleted
- Files not found
- Errors encountered

### 4. Validation
Verify complete deletion:
```powershell
python delete_content.py --validate VIDEO_ID
```

### 5. Confirmation Prompts
Interactive mode requires typing 'DELETE' to confirm.

## FAISS Index Rebuilding

**IMPORTANT:** After deleting content, the FAISS search index must be rebuilt.

### When to Rebuild
- After deleting any video(s)
- After deleting any channel(s)
- Before running searches

### How to Rebuild

#### Option 1: Automatic (during deletion)
```powershell
python delete_content.py --video VIDEO_ID --rebuild-index
```

#### Option 2: Manual (later)
```powershell
python delete_content.py --rebuild-index
```

#### Option 3: Programmatic
```python
manager = DataDeletionManager()
manager.rebuild_faiss_index()
```

### Rebuild Process
1. Backs up existing index
2. Collects all remaining embedding files
3. Consolidates embeddings
4. Rebuilds FAISS index from scratch
5. Saves new index and metadata

**Time:** 2-5 minutes for ~5000 videos

## Finding IDs

### Video IDs
From `video_inventory.csv`:
```csv
video_id,channel,title,language,is_song,duration_seconds
F3Qixy-r_rQ,3Blue1Brown,2021 Summer of Math Exposition results,en,False,760
```
Video ID: `F3Qixy-r_rQ`

### Channel IDs
From `channels.csv`:
```csv
channel_id,channel_name
UCPlwvN0w4qFSP1FllALB92w,numberblocks
UC4a-Gbdw7vOaccHmFo40b9g,Khan Academy
```
Channel ID: `UC4a-Gbdw7vOaccHmFo40b9g`

You can also find them in YouTube URLs:
- Video: `https://youtube.com/watch?v=VIDEO_ID`
- Channel: `https://youtube.com/channel/CHANNEL_ID`

## Example Workflows

### Workflow 1: Remove a Single Low-Quality Video

1. **Preview deletion**
   ```powershell
   python delete_content.py --video abc123xyz --dry-run
   ```

2. **Execute deletion**
   ```powershell
   python delete_content.py --video abc123xyz --yes --rebuild-index
   ```

3. **Validate**
   ```powershell
   python delete_content.py --validate abc123xyz
   ```

### Workflow 2: Remove an Ineffective Channel

1. **Check video count**
   ```powershell
   python delete_content.py --channel UCxxxxxxxxxx --dry-run
   ```

2. **Delete channel**
   ```powershell
   python delete_content.py --channel UCxxxxxxxxxx --yes
   ```

3. **Rebuild index later** (if deleting multiple channels)
   ```powershell
   # Delete other channels...
   python delete_content.py --channel UCyyyyyyyyyy --yes
   
   # Then rebuild once
   python delete_content.py --rebuild-index
   ```

### Workflow 3: Batch Delete Multiple Videos

```python
from data_pipeline.deletion_manager import DataDeletionManager

manager = DataDeletionManager(dry_run=False, create_backup=True)

# Delete multiple videos
videos_to_delete = ["video1", "video2", "video3"]

for video_id in videos_to_delete:
    print(f"Deleting {video_id}...")
    manager.delete_video(video_id, skip_index_rebuild=True)

# Save log
manager.save_deletion_log()

# Rebuild index once at the end
print("Rebuilding index...")
manager.rebuild_faiss_index()
```

## Troubleshooting

### Issue: "Video not found in inventory"
- Video may have already been deleted
- Check spelling of video ID
- Verify video exists in `video_inventory.csv`

### Issue: "Files not found" warnings
- Normal if video was partially processed
- Files may have been manually deleted
- Check deletion log for details

### Issue: Index rebuild fails
- Check you have embedding files in `data/embeddings_output/`
- Ensure sufficient disk space
- Check deletion log for specific error

### Issue: Remaining traces after deletion
- Run validation: `python delete_content.py --validate VIDEO_ID`
- Check specific file paths listed
- May need manual cleanup for edge cases

## Restoring from Backup

If you need to undo a deletion:

1. **Find backup** in `_deletion_backups/`
2. **Restore metadata files**:
   ```powershell
   # Example: restore video inventory
   Copy-Item _deletion_backups\video_inventory_20260219_143022.csv video_inventory.csv
   ```
3. **Restore FAISS index**:
   ```powershell
   Copy-Item _deletion_backups\faiss_index_20260219_143022.* data\faiss_index\
   ```

**Note:** Content files (captions, chunks, embeddings) are permanently deleted and cannot be restored from backups. You would need to re-extract those videos.

## Performance

| Operation | Time (approximate) |
|-----------|-------------------|
| Delete single video | < 5 seconds |
| Delete channel (20 videos) | 30-60 seconds |
| FAISS rebuild (5000 videos) | 2-5 minutes |
| Validation check | < 1 second |

## Integration with GUI

To add deletion functionality to your GUI:

```python
import streamlit as st
from data_pipeline.deletion_manager import DataDeletionManager

# In your GUI code
st.header("🗑️ Content Management")

video_id = st.text_input("Video ID to delete")
if st.button("Delete Video"):
    manager = DataDeletionManager(dry_run=False, create_backup=True)
    
    with st.spinner("Deleting video..."):
        results = manager.delete_video(video_id)
        manager.save_deletion_log()
    
    if results['success']:
        st.success("Video deleted successfully")
        
        # Rebuild index
        with st.spinner("Rebuilding search index..."):
            manager.rebuild_faiss_index()
        st.success("Search index updated")
    else:
        st.error("Deletion failed")
        for error in results['errors']:
            st.error(error)
```

## Best Practices

1. **Always preview first** - Use `--dry-run` to see what will be deleted
2. **Batch deletions** - Delete multiple items, then rebuild index once
3. **Keep backups** - Don't disable backup creation unless necessary
4. **Validate after** - Run validation to ensure complete deletion
5. **Rebuild index** - Never skip index rebuild if you run searches
6. **Test on copy** - For large deletions, test on a backup copy first
7. **Log everything** - Review deletion logs for any issues

## Security Notes

- Deletion is **irreversible** for content files (captions, chunks, embeddings)
- Metadata can be restored from backups
- No cloud storage - all operations are local
- Deletion logs contain full file paths

## Support

If you encounter issues:
1. Check deletion log in `_deletion_logs/`
2. Run validation to identify remaining traces
3. Try dry-run mode to diagnose
4. Check backups in `_deletion_backups/`
5. Review error messages in terminal output
