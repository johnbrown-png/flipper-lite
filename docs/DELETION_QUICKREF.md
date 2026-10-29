# Content Deletion - Quick Reference

## Quick Commands

### Delete Single Video
```powershell
# Preview (recommended first)
python delete_content.py --video VIDEO_ID --dry-run

# Execute
python delete_content.py --video VIDEO_ID --yes --rebuild-index
```

### Delete Channel
```powershell
# Preview
python delete_content.py --channel CHANNEL_ID --dry-run

# Execute
python delete_content.py --channel CHANNEL_ID --yes --rebuild-index
```

### Interactive Mode
```powershell
python delete_content.py
```

### Validate Deletion
```powershell
python delete_content.py --validate VIDEO_ID
```

### Rebuild Index Only
```powershell
python delete_content.py --rebuild-index
```

## Finding IDs

### Video ID
- From `video_inventory.csv` (first column)
- From YouTube URL: `https://youtube.com/watch?v=VIDEO_ID`

### Channel ID  
- From `channels.csv` (first column)
- From YouTube URL: `https://youtube.com/channel/CHANNEL_ID`

## Example: Remove Ineffective Content

1. Open `video_inventory.csv` or `channels.csv`
2. Copy the ID to delete
3. Preview deletion:
   ```powershell
   python delete_content.py --video abc123xyz --dry-run
   ```
4. Execute deletion:
   ```powershell
   python delete_content.py --video abc123xyz --yes --rebuild-index
   ```
5. Validate:
   ```powershell
   python delete_content.py --validate abc123xyz
   ```

## Safety Features

✅ **Automatic backups** → `_deletion_backups/`  
✅ **Deletion logs** → `_deletion_logs/`  
✅ **Dry-run mode** → `--dry-run`  
✅ **Validation** → `--validate VIDEO_ID`  
✅ **Confirmation prompts** (unless `--yes`)

## What Gets Deleted

- ✓ Video metadata records
- ✓ Caption files (.json, .txt)
- ✓ Chunked transcripts
- ✓ Embeddings
- ✓ Search index entries (via rebuild)
- ✓ Extraction history
- ✓ API cache

## Important Notes

⚠️ **ALWAYS rebuild index after deletion**  
⚠️ **Content files cannot be restored** (need re-extraction)  
⚠️ **Metadata can be restored** from backups  
⚠️ **Test with --dry-run first**

## Programmatic Usage

```python
from data_pipeline.deletion_manager import DataDeletionManager

# Initialize
manager = DataDeletionManager(dry_run=False, create_backup=True)

# Delete video
results = manager.delete_video("VIDEO_ID")
manager.save_deletion_log()

# Rebuild index
manager.rebuild_faiss_index()
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Video not found" | Check video_inventory.csv for correct ID |
| Files not found | Normal for partial processing |
| Index rebuild fails | Check embeddings_output folder |
| Remaining traces | Run validation, manual cleanup if needed |

## Need More Help?

See [DELETION_GUIDE.md](DELETION_GUIDE.md) for complete documentation.
