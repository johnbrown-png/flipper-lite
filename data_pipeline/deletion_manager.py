"""
Data Deletion Manager

Handles safe deletion of videos and channels from the Flipper application.
Removed data includes:
- Metadata files (video_inventory.csv, channels.csv, FAISS metadata)
- Caption files (.json, .txt)
- Chunked transcripts
- Embeddings
- Extraction state
- API cache
- Soft-delete tracking (for FAISS index rebuild optimization)
"""

import os
import json
import shutil
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional
import pickle

from shared.config import (
    PROJECT_ROOT,
    DATA_DIR,
    CAPTIONS_DIR,
    CHUNKED_DIR,
    EMBEDDINGS_DIR,
    FAISS_INDEX_DIR,
    API_CACHE_FILE,
    EMBEDDINGS_CONSOLIDATED_FILE,
    FAISS_METADATA_FILE,
    CHANNELS_CSV
)

from data_pipeline.deletion_tracker import DeletionTracker


class DataDeletionManager:
    """Manage safe deletion of videos and channels"""
    
    def __init__(self, dry_run: bool = False, create_backup: bool = True):
        """
        Initialize deletion manager
        
        Args:
            dry_run: If True, only preview deletions without executing
            create_backup: If True, backup metadata files before deletion
        """
        self.dry_run = dry_run
        self.create_backup = create_backup
        self.video_inventory_path = PROJECT_ROOT / "video_inventory.csv"
        self.channels_csv_path = CHANNELS_CSV
        self.extraction_state_path = PROJECT_ROOT / "extraction_state.json"
        self.api_cache_path = API_CACHE_FILE
        self.captions_root = PROJECT_ROOT / "captions_output"
        self.deletion_log = []
        self.tracker = DeletionTracker()
        
    def _log(self, message: str, level: str = "INFO"):
        """Log deletion operations"""
        timestamp = datetime.now().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message
        }
        self.deletion_log.append(log_entry)
        
        prefix = "[DRY RUN]" if self.dry_run else "+"
        if level == "ERROR":
            prefix = "X"
        elif level == "WARNING":
            prefix = "!"
            
        # Handle encoding for Windows console
        try:
            print(f"{prefix} {message}")
        except UnicodeEncodeError:
            # Fall back to ASCII-safe output
            safe_message = message.encode('ascii', 'ignore').decode('ascii')
            print(f"{prefix} {safe_message}")
    
    def _backup_file(self, file_path: Path):
        """Create backup of a file (keeping only the most recent backup)"""
        if not file_path.exists():
            return
            
        if self.dry_run:
            self._log(f"Would backup: {file_path}", "INFO")
            return
            
        if not self.create_backup:
            return
            
        backup_dir = PROJECT_ROOT / "_deletion_backups"
        backup_dir.mkdir(exist_ok=True)
        
        # Delete old backups of this file
        self._cleanup_old_backups(backup_dir, file_path.stem, file_path.suffix)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
        backup_path = backup_dir / backup_name
        
        shutil.copy2(file_path, backup_path)
        self._log(f"Backed up: {file_path.name} → {backup_path}", "INFO")
    
    def _cleanup_old_backups(self, backup_dir: Path, file_stem: str, file_suffix: str):
        """
        Delete old backups of a file, keeping only the most recent one
        
        Args:
            backup_dir: Directory containing backups
            file_stem: Base name of file (e.g., 'video_inventory')
            file_suffix: File extension (e.g., '.csv')
        """
        # Find all backups matching this file pattern
        pattern = f"{file_stem}_*{file_suffix}"
        old_backups = sorted(backup_dir.glob(pattern))
        
        # Delete all old backups (we're about to create a new one)
        for old_backup in old_backups:
            try:
                old_backup.unlink()
                self._log(f"Removed old backup: {old_backup.name}", "INFO")
            except Exception as e:
                self._log(f"Error removing old backup {old_backup.name}: {e}", "WARNING")
    
    def get_video_info(self, video_id: str) -> Optional[Dict]:
        """
        Get video information from multiple sources
        
        Checks in order:
        1. extraction_state.json (primary source of truth)
        2. Physical files on disk (chunked, embeddings, captions)
        3. video_inventory.csv (optional, may be outdated)
        
        Returns:
            Dict with video info if found, None if video doesn't exist anywhere
        """
        video_info = None
        
        # 1. Check extraction_state.json first (always current)
        if self.extraction_state_path.exists():
            try:
                with open(self.extraction_state_path, 'r', encoding='utf-8') as f:
                    extraction_state = json.load(f)
                    
                # Look through extraction state for this video
                for channel_name, channel_data in extraction_state.items():
                    # Skip if channel_data is not a dict
                    if not isinstance(channel_data, dict):
                        continue
                    if 'extracted_videos' in channel_data:
                        for video_data in channel_data['extracted_videos']:
                            if video_data.get('video_id') == video_id:
                                # Found in extraction state
                                video_info = {
                                    'video_id': video_id,
                                    'channel': channel_name,
                                    'title': video_data.get('title', 'Unknown'),
                                    'language': video_data.get('language', 'Unknown')
                                }
                                self._log(f"Found video {video_id} in extraction_state.json", "INFO")
                                return video_info
            except Exception as e:
                self._log(f"Error reading extraction_state.json: {e}", "WARNING")
        
        # 2. Check if physical files exist (proves video was processed)
        chunked_file = CHUNKED_DIR / f"{video_id}_chunked.json"
        embedding_file = EMBEDDINGS_DIR / f"{video_id}_embeddings.json"
        
        if chunked_file.exists() or embedding_file.exists():
            # Video exists in system, create minimal info
            channel_name = "Unknown"
            
            # Try to extract channel from chunked file
            if chunked_file.exists():
                try:
                    with open(chunked_file, 'r', encoding='utf-8') as f:
                        chunked_data = json.load(f)
                        channel_name = chunked_data.get('channel', 'Unknown')
                except Exception:
                    pass
            
            video_info = {
                'video_id': video_id,
                'channel': channel_name,
                'title': 'Unknown',
                'language': 'Unknown'
            }
            self._log(f"Found video {video_id} files on disk (not in inventory)", "INFO")
            return video_info
        
        # 3. Fall back to video_inventory.csv if available
        if self.video_inventory_path.exists():
            try:
                df = pd.read_csv(self.video_inventory_path)
                video_rows = df[df['video_id'] == video_id]
                
                if len(video_rows) > 0:
                    video_info = video_rows.iloc[0].to_dict()
                    self._log(f"Found video {video_id} in video_inventory.csv", "INFO")
                    return video_info
            except Exception as e:
                self._log(f"Error reading video_inventory.csv: {e}", "WARNING")
        
        # Video not found in any source
        return None
    
    def get_channel_videos(self, channel_id: str) -> List[str]:
        """Get all video IDs for a channel"""
        if not self.video_inventory_path.exists():
            self._log(f"Video inventory not found: {self.video_inventory_path}", "WARNING")
            return []
            
        df = pd.read_csv(self.video_inventory_path)
        
        # Try to match by channel_id first
        if 'channel_id' in df.columns:
            channel_videos = df[df['channel_id'] == channel_id]
        else:
            # Fall back to channel name lookup
            channel_name = self._get_channel_name(channel_id)
            if channel_name:
                # Try exact match first
                channel_videos = df[df['channel'] == channel_name]
                
                # If no match, try with underscores instead of spaces
                if len(channel_videos) == 0:
                    channel_name_underscore = channel_name.replace(' ', '_')
                    channel_videos = df[df['channel'] == channel_name_underscore]
                
                # If still no match, try with spaces instead of underscores
                if len(channel_videos) == 0:
                    channel_name_spaces = channel_name.replace('_', ' ')
                    channel_videos = df[df['channel'] == channel_name_spaces]
            else:
                return []
        
        return channel_videos['video_id'].tolist()
    
    def _get_channel_name(self, channel_id: str) -> Optional[str]:
        """Get channel name from channel ID"""
        if not self.channels_csv_path.exists():
            return None
            
        df = pd.read_csv(self.channels_csv_path)
        channel_rows = df[df['channel_id'] == channel_id]
        
        if len(channel_rows) == 0:
            return None
            
        return channel_rows.iloc[0]['channel_name']
    
    def delete_video(self, video_id: str, skip_index_rebuild: bool = False) -> Dict:
        """
        Delete all data for a single video (soft-delete from FAISS metadata)
        
        Physical files are deleted, but FAISS index embeddings remain until rebuild.
        This avoids memory-intensive rebuilds after each deletion.
        
        Args:
            video_id: YouTube video ID
            skip_index_rebuild: Not used (kept for backward compatibility)
        
        Returns:
            Dict with deletion results
        """
        self._log(f"\n{'='*60}")
        self._log(f"Starting deletion for video: {video_id}")
        self._log(f"{'='*60}")
        
        results = {
            "video_id": video_id,
            "success": True,
            "files_deleted": [],
            "files_not_found": [],
            "errors": []
        }
        
        # Get video info
        video_info = self.get_video_info(video_id)
        if not video_info:
            self._log(f"Video {video_id} not found in system (will attempt to delete any orphaned files)", "WARNING")
        else:
            self._log(f"Video: {video_info.get('title', 'Unknown')}")
            self._log(f"Channel: {video_info.get('channel', 'Unknown')}")
        
        # 1. Remove from video_inventory.csv
        self._delete_from_video_inventory(video_id, results)
        
        # 2. Delete caption files
        self._delete_caption_files(video_id, video_info, results)
        
        # 3. Delete chunked file
        self._delete_chunked_file(video_id, results)
        
        # 4. Delete embedding file
        self._delete_embedding_file(video_id, results)
        
        # 5. Update extraction_state.json
        self._update_extraction_state(video_id, results)
        
        # 6. Update api_cache.json
        self._update_api_cache(video_id, results)
        
        # 7. Soft-delete from FAISS metadata (not the index itself)
        self._soft_delete_from_faiss_metadata(video_id, video_info, results)
        
        # 8. Mark as deleted in tracking file
        if not self.dry_run:
            self.tracker.mark_deleted(video_id, video_info)
            self._log(f"Marked {video_id} as soft-deleted in tracking system")
        
        # 9. Check if rebuild warning needed (5% threshold)
        if not self.dry_run:
            total_videos = self._get_total_video_count()
            warning_msg = self.tracker.get_rebuild_warning_message(total_videos)
            if warning_msg:
                self._log(f"\n{warning_msg}", "WARNING")
        
        self._log(f"\n{'='*60}")
        self._log(f"Deletion summary for {video_id}:")
        self._log(f"  Files deleted: {len(results['files_deleted'])}")
        self._log(f"  Files not found: {len(results['files_not_found'])}")
        self._log(f"  Errors: {len(results['errors'])}")
        self._log(f"{'='*60}\n")
        
        return results
    
    def delete_channel(self, channel_id: str) -> Dict:
        """
        Delete all data for an entire channel
        
        Args:
            channel_id: YouTube channel ID
        
        Returns:
            Dict with deletion results
        """
        self._log(f"\n{'='*60}")
        self._log(f"Starting channel deletion: {channel_id}")
        self._log(f"{'='*60}")
        
        results = {
            "channel_id": channel_id,
            "success": True,
            "videos_deleted": [],
            "errors": []
        }
        
        # Get channel name
        channel_name = self._get_channel_name(channel_id)
        if channel_name:
            self._log(f"Channel name: {channel_name}")
        else:
            self._log(f"Channel name not found for ID: {channel_id}", "WARNING")
        
        # Get all videos for channel
        video_ids = self.get_channel_videos(channel_id)
        self._log(f"Found {len(video_ids)} videos to delete")
        
        if len(video_ids) == 0:
            self._log("No videos found for this channel", "WARNING")
        
        # Delete each video (skip individual index rebuilds)
        for i, video_id in enumerate(video_ids, 1):
            self._log(f"\nDeleting video {i}/{len(video_ids)}: {video_id}")
            video_result = self.delete_video(video_id, skip_index_rebuild=True)
            
            if video_result['success']:
                results['videos_deleted'].append(video_id)
            else:
                results['errors'].extend(video_result['errors'])
        
        # Delete channel caption folder
        if channel_name:
            self._delete_channel_caption_folder(channel_name, results)
        
        # Remove from channels.csv
        self._delete_from_channels_csv(channel_id, results)
        
        # Rebuild FAISS index once for all deletions
        self._log("\nFAISS index rebuild required after channel deletion", "WARNING")
        self._log("Run rebuild_faiss_index() to update search index", "WARNING")
        
        self._log(f"\n{'='*60}")
        self._log(f"Channel deletion summary:")
        self._log(f"  Videos deleted: {len(results['videos_deleted'])}")
        self._log(f"  Errors: {len(results['errors'])}")
        self._log(f"{'='*60}\n")
        
        return results
    
    def _delete_from_video_inventory(self, video_id: str, results: Dict):
        """Remove video from video_inventory.csv"""
        if not self.video_inventory_path.exists():
            results['files_not_found'].append(str(self.video_inventory_path))
            return
        
        self._backup_file(self.video_inventory_path)
        
        if self.dry_run:
            self._log(f"Would remove {video_id} from video_inventory.csv")
            return
        
        try:
            df = pd.read_csv(self.video_inventory_path)
            original_count = len(df)
            df = df[df['video_id'] != video_id]
            new_count = len(df)
            
            if original_count > new_count:
                df.to_csv(self.video_inventory_path, index=False)
                results['files_deleted'].append("video_inventory.csv")
                self._log(f"Removed from video_inventory.csv ({original_count} → {new_count} rows)")
            else:
                self._log(f"Video {video_id} not found in video_inventory.csv", "WARNING")
        except Exception as e:
            error = f"Error updating video_inventory.csv: {e}"
            results['errors'].append(error)
            self._log(error, "ERROR")
    
    def _delete_caption_files(self, video_id: str, video_info: Optional[Dict], results: Dict):
        """Delete caption files (.json and .txt)"""
        # Try both locations: captions_output/ and data/captions_output/
        locations = [
            self.captions_root,
            CAPTIONS_DIR
        ]
        
        deleted = False
        for base_dir in locations:
            if not base_dir.exists():
                continue
            
            # Search through channel folders
            for channel_folder in base_dir.iterdir():
                if not channel_folder.is_dir():
                    continue
                
                # Find files containing the video_id
                for file_path in channel_folder.glob(f"*{video_id}*"):
                    if file_path.suffix in ['.json', '.txt']:
                        if self.dry_run:
                            self._log(f"Would delete: {file_path}")
                        else:
                            try:
                                file_path.unlink()
                                results['files_deleted'].append(str(file_path))
                                self._log(f"Deleted: {file_path}")
                                deleted = True
                            except Exception as e:
                                error = f"Error deleting {file_path}: {e}"
                                results['errors'].append(error)
                                self._log(error, "ERROR")
        
        if not deleted and not self.dry_run:
            self._log(f"Caption files for {video_id} not found", "WARNING")
    
    def _delete_chunked_file(self, video_id: str, results: Dict):
        """Delete chunked transcript file"""
        chunked_file = CHUNKED_DIR / f"{video_id}_chunked.json"
        
        if not chunked_file.exists():
            results['files_not_found'].append(str(chunked_file))
            self._log(f"Chunked file not found: {chunked_file}", "WARNING")
            return
        
        if self.dry_run:
            self._log(f"Would delete: {chunked_file}")
        else:
            try:
                chunked_file.unlink()
                results['files_deleted'].append(str(chunked_file))
                self._log(f"Deleted: {chunked_file}")
            except Exception as e:
                error = f"Error deleting {chunked_file}: {e}"
                results['errors'].append(error)
                self._log(error, "ERROR")
    
    def _delete_embedding_file(self, video_id: str, results: Dict):
        """Delete embedding file"""
        embedding_file = EMBEDDINGS_DIR / f"{video_id}_embeddings.json"
        
        if not embedding_file.exists():
            results['files_not_found'].append(str(embedding_file))
            self._log(f"Embedding file not found: {embedding_file}", "WARNING")
            return
        
        if self.dry_run:
            self._log(f"Would delete: {embedding_file}")
        else:
            try:
                embedding_file.unlink()
                results['files_deleted'].append(str(embedding_file))
                self._log(f"Deleted: {embedding_file}")
            except Exception as e:
                error = f"Error deleting {embedding_file}: {e}"
                results['errors'].append(error)
                self._log(error, "ERROR")
    
    def _soft_delete_from_faiss_metadata(self, video_id: str, video_info: Optional[Dict], results: Dict):
        """
        Soft-delete video from FAISS metadata (remove entries, keep index intact)
        
        This removes metadata entries for the video, but leaves embeddings in the
        FAISS index file. Search will skip these "ghost" embeddings by checking
        against deleted_videos.json.
        """
        if not FAISS_METADATA_FILE.exists():
            results['files_not_found'].append(str(FAISS_METADATA_FILE))
            self._log(f"FAISS metadata file not found: {FAISS_METADATA_FILE}", "WARNING")
            return
        
        self._backup_file(FAISS_METADATA_FILE)
        
        if self.dry_run:
            self._log(f"Would remove {video_id} from FAISS metadata")
            return
        
        try:
            # Load metadata
            with open(FAISS_METADATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            original_count = len(data.get('metadata', []))
            
            # Filter out entries for this video
            data['metadata'] = [
                entry for entry in data.get('metadata', [])
                if entry.get('video_id') != video_id
            ]
            
            removed_count = original_count - len(data['metadata'])
            
            if removed_count > 0:
                # Update total count
                data['total_embeddings'] = len(data['metadata'])
                
                # Save updated metadata
                with open(FAISS_METADATA_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
                
                results['files_deleted'].append(f"FAISS metadata ({removed_count} entries removed)")
                self._log(f"Removed {removed_count} metadata entries for {video_id}")
                self._log(f"FAISS index still contains {removed_count} 'ghost' embeddings (will be skipped in search)")
            else:
                self._log(f"Video {video_id} not found in FAISS metadata", "WARNING")
                
        except Exception as e:
            error = f"Error updating FAISS metadata: {e}"
            results['errors'].append(error)
            self._log(error, "ERROR")
    
    def _get_total_video_count(self) -> int:
        """Get total count of videos currently in system (for deletion percentage calc)"""
        try:
            if FAISS_METADATA_FILE.exists():
                with open(FAISS_METADATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # Count unique video IDs in metadata
                video_ids = set(entry.get('video_id') for entry in data.get('metadata', []))
                return len(video_ids)
        except Exception as e:
            self._log(f"Error counting videos: {e}", "WARNING")
        
        # Fallback: count embedding files
        try:
            return len(list(EMBEDDINGS_DIR.glob("*_embeddings.json")))
        except Exception:
            return 0
    
    def _update_extraction_state(self, video_id: str, results: Dict):
        """Remove video from extraction_state.json"""
        if not self.extraction_state_path.exists():
            results['files_not_found'].append(str(self.extraction_state_path))
            return
        
        self._backup_file(self.extraction_state_path)
        
        if self.dry_run:
            self._log(f"Would remove {video_id} from extraction_state.json")
            return
        
        try:
            with open(self.extraction_state_path, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            removed = False
            for channel_id, videos in state.get('videos_extracted', {}).items():
                original_count = len(videos)
                videos[:] = [v for v in videos if v.get('video_id') != video_id]
                if len(videos) < original_count:
                    removed = True
            
            if removed:
                with open(self.extraction_state_path, 'w', encoding='utf-8') as f:
                    json.dump(state, f, indent=2)
                results['files_deleted'].append("extraction_state.json (updated)")
                self._log(f"Removed from extraction_state.json")
            else:
                self._log(f"Video {video_id} not found in extraction_state.json", "WARNING")
        except Exception as e:
            error = f"Error updating extraction_state.json: {e}"
            results['errors'].append(error)
            self._log(error, "ERROR")
    
    def _update_api_cache(self, video_id: str, results: Dict):
        """Remove video from api_cache.json"""
        if not self.api_cache_path.exists():
            results['files_not_found'].append(str(self.api_cache_path))
            return
        
        self._backup_file(self.api_cache_path)
        
        if self.dry_run:
            self._log(f"Would remove {video_id} from api_cache.json")
            return
        
        try:
            with open(self.api_cache_path, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            
            removed = False
            for cache_key, videos in cache.get('videos', {}).items():
                if isinstance(videos, list):
                    original_count = len(videos)
                    videos[:] = [v for v in videos if v.get('video_id') != video_id]
                    if len(videos) < original_count:
                        removed = True
            
            if removed:
                with open(self.api_cache_path, 'w', encoding='utf-8') as f:
                    json.dump(cache, f, indent=2)
                results['files_deleted'].append("api_cache.json (updated)")
                self._log(f"Removed from api_cache.json")
            else:
                self._log(f"Video {video_id} not found in api_cache.json", "WARNING")
        except Exception as e:
            error = f"Error updating api_cache.json: {e}"
            results['errors'].append(error)
            self._log(error, "ERROR")
    
    def _delete_channel_caption_folder(self, channel_name: str, results: Dict):
        """Delete entire channel caption folder"""
        locations = [
            self.captions_root / channel_name,
            CAPTIONS_DIR / channel_name
        ]
        
        for folder_path in locations:
            if not folder_path.exists():
                continue
            
            if self.dry_run:
                self._log(f"Would delete folder: {folder_path}")
            else:
                try:
                    shutil.rmtree(folder_path)
                    results['files_deleted'].append(str(folder_path))
                    self._log(f"Deleted folder: {folder_path}")
                except Exception as e:
                    error = f"Error deleting folder {folder_path}: {e}"
                    results['errors'].append(error)
                    self._log(error, "ERROR")
    
    def _delete_from_channels_csv(self, channel_id: str, results: Dict):
        """Remove channel from channels.csv"""
        if not self.channels_csv_path.exists():
            results['files_not_found'].append(str(self.channels_csv_path))
            return
        
        self._backup_file(self.channels_csv_path)
        
        if self.dry_run:
            self._log(f"Would remove {channel_id} from channels.csv")
            return
        
        try:
            df = pd.read_csv(self.channels_csv_path)
            original_count = len(df)
            df = df[df['channel_id'] != channel_id]
            new_count = len(df)
            
            if original_count > new_count:
                df.to_csv(self.channels_csv_path, index=False)
                results['files_deleted'].append("channels.csv")
                self._log(f"Removed from channels.csv ({original_count} → {new_count} rows)")
            else:
                self._log(f"Channel {channel_id} not found in channels.csv", "WARNING")
        except Exception as e:
            error = f"Error updating channels.csv: {e}"
            results['errors'].append(error)
            self._log(error, "ERROR")
    
    def rebuild_faiss_index(self) -> bool:
        """
        Rebuild FAISS index from remaining embeddings
        
        Returns:
            True if successful, False otherwise
        """
        self._log(f"\n{'='*60}")
        self._log("Starting FAISS index rebuild")
        self._log(f"{'='*60}")
        
        if self.dry_run:
            self._log("Cannot rebuild index in dry-run mode", "WARNING")
            return False
        
        try:
            from data_pipeline.indexer import FAISSIndexBuilder
            
            # Backup existing index (keeping only the most recent backup)
            if FAISS_INDEX_DIR.exists():
                backup_dir = PROJECT_ROOT / "_deletion_backups"
                backup_dir.mkdir(exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                for file in FAISS_INDEX_DIR.glob("faiss_index*"):
                    # Delete old backups of this FAISS file
                    self._cleanup_old_backups(backup_dir, file.stem, file.suffix)
                    
                    backup_path = backup_dir / f"{file.stem}_{timestamp}{file.suffix}"
                    shutil.copy2(file, backup_path)
                    self._log(f"Backed up: {file.name}")
            
            # Collect all remaining embedding files
            self._log("\nCollecting remaining embedding files...")
            embedding_files = list(EMBEDDINGS_DIR.glob("*_embeddings.json"))
            self._log(f"Found {len(embedding_files)} embedding files")
            
            if len(embedding_files) == 0:
                self._log("No embedding files found - cannot build index", "ERROR")
                return False
            
            # Build consolidated embeddings
            self._log("\nConsolidating embeddings...")
            all_embeddings = []
            
            for emb_file in embedding_files:
                try:
                    with open(emb_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    for item in data.get('embeddings', []):
                        all_embeddings.append(item)
                except Exception as e:
                    self._log(f"Error reading {emb_file.name}: {e}", "WARNING")
            
            self._log(f"Total embeddings collected: {len(all_embeddings)}")
            
            # Save consolidated file
            consolidated_data = {
                "total_embeddings": len(all_embeddings),
                "rebuild_timestamp": datetime.now().isoformat(),
                "embeddings": all_embeddings
            }
            
            self._log(f"\nSaving consolidated embeddings...")
            with open(EMBEDDINGS_CONSOLIDATED_FILE, 'w', encoding='utf-8') as f:
                json.dump(consolidated_data, f)
            self._log(f"Saved: {EMBEDDINGS_CONSOLIDATED_FILE}")
            
            # Build FAISS index
            self._log("\nBuilding FAISS index...")
            builder = FAISSIndexBuilder(
                embeddings_dir=str(EMBEDDINGS_DIR),
                output_dir=str(FAISS_INDEX_DIR),
                dimension=3072
            )
            
            index, metadata = builder.build_from_file(
                EMBEDDINGS_CONSOLIDATED_FILE,
                index_type="Flat"
            )
            
            # Save index
            builder.save_index(index, metadata, FAISS_INDEX_DIR, "faiss_index")
            
            self._log(f"\n{'='*60}")
            self._log("✓ FAISS index rebuild completed successfully")
            self._log(f"  Total vectors in index: {index.ntotal}")
            self._log(f"{'='*60}\n")
            
            # Clear deletion tracker after successful rebuild
            deleted_count = self.tracker.clear_deleted_videos()
            if deleted_count > 0:
                self._log(f"✓ Cleared {deleted_count} soft-deleted videos from tracking")
            
            return True
            
        except Exception as e:
            error = f"Error rebuilding FAISS index: {e}"
            self._log(error, "ERROR")
            import traceback
            self._log(traceback.format_exc(), "ERROR")
            return False
    
    def save_deletion_log(self):
        """Save deletion log to file"""
        if len(self.deletion_log) == 0:
            return
        
        log_dir = PROJECT_ROOT / "_deletion_logs"
        log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"deletion_log_{timestamp}.json"
        
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(self.deletion_log, f, indent=2)
        
        print(f"\n💾 Deletion log saved: {log_file}")
    
    def validate_deletion(self, video_id: str) -> Dict:
        """
        Validate that a video has been completely deleted
        
        Args:
            video_id: YouTube video ID
        
        Returns:
            Dict with validation results
        """
        results = {
            "video_id": video_id,
            "fully_deleted": True,
            "remaining_traces": []
        }
        
        # Check video_inventory.csv
        if self.video_inventory_path.exists():
            df = pd.read_csv(self.video_inventory_path)
            if video_id in df['video_id'].values:
                results['fully_deleted'] = False
                results['remaining_traces'].append("video_inventory.csv")
        
        # Check caption files
        for base_dir in [self.captions_root, CAPTIONS_DIR]:
            if base_dir.exists():
                for file_path in base_dir.rglob(f"*{video_id}*"):
                    results['fully_deleted'] = False
                    results['remaining_traces'].append(str(file_path))
        
        # Check chunked file
        chunked_file = CHUNKED_DIR / f"{video_id}_chunked.json"
        if chunked_file.exists():
            results['fully_deleted'] = False
            results['remaining_traces'].append(str(chunked_file))
        
        # Check embedding file
        embedding_file = EMBEDDINGS_DIR / f"{video_id}_embeddings.json"
        if embedding_file.exists():
            results['fully_deleted'] = False
            results['remaining_traces'].append(str(embedding_file))
        
        return results


def main():
    """Command-line interface for deletion manager"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Delete videos or channels from Flipper")
    parser.add_argument('--video', '-v', help='Video ID to delete')
    parser.add_argument('--channel', '-c', help='Channel ID to delete')
    parser.add_argument('--dry-run', action='store_true', help='Preview deletions without executing')
    parser.add_argument('--no-backup', action='store_true', help='Skip backup creation')
    parser.add_argument('--rebuild-index', action='store_true', help='Rebuild FAISS index')
    parser.add_argument('--validate', help='Validate deletion of video ID')
    
    args = parser.parse_args()
    
    manager = DataDeletionManager(
        dry_run=args.dry_run,
        create_backup=not args.no_backup
    )
    
    if args.validate:
        results = manager.validate_deletion(args.validate)
        if results['fully_deleted']:
            print(f"✓ Video {args.validate} is fully deleted")
        else:
            print(f"✗ Video {args.validate} still has traces:")
            for trace in results['remaining_traces']:
                print(f"  - {trace}")
    
    elif args.video:
        results = manager.delete_video(args.video)
        manager.save_deletion_log()
        
        if args.rebuild_index and not args.dry_run:
            manager.rebuild_faiss_index()
    
    elif args.channel:
        results = manager.delete_channel(args.channel)
        manager.save_deletion_log()
        
        if args.rebuild_index and not args.dry_run:
            manager.rebuild_faiss_index()
    
    elif args.rebuild_index:
        manager.rebuild_faiss_index()
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
