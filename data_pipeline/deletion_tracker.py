"""
Deletion Tracker

Manages soft-deleted videos tracking and rebuild threshold monitoring.
Videos are marked for deletion in a tracking file, allowing FAISS index
to remain unchanged until a rebuild is explicitly initiated.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Set, Dict, List, Optional
from shared.config import DELETED_VIDEOS_FILE, DELETION_REBUILD_THRESHOLD


class DeletionTracker:
    """Track soft-deleted videos and manage rebuild thresholds"""
    
    def __init__(self):
        self.deleted_videos_path = DELETED_VIDEOS_FILE
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """Create deleted videos file if it doesn't exist"""
        if not self.deleted_videos_path.exists():
            self.deleted_videos_path.parent.mkdir(parents=True, exist_ok=True)
            initial_data = {
                "deleted_videos": [],
                "deletion_history": [],
                "last_rebuild": None,
                "total_deletions_since_rebuild": 0
            }
            with open(self.deleted_videos_path, 'w', encoding='utf-8') as f:
                json.dump(initial_data, f, indent=2)
    
    def load_deleted_videos(self) -> Dict:
        """Load deleted videos data"""
        try:
            with open(self.deleted_videos_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load deleted videos: {e}")
            return {
                "deleted_videos": [],
                "deletion_history": [],
                "last_rebuild": None,
                "total_deletions_since_rebuild": 0
            }
    
    def get_deleted_video_ids(self) -> Set[str]:
        """Get set of currently deleted video IDs"""
        data = self.load_deleted_videos()
        return set(data.get("deleted_videos", []))
    
    def mark_deleted(self, video_id: str, metadata: Optional[Dict] = None) -> None:
        """
        Mark a video as deleted
        
        Args:
            video_id: Video ID to mark as deleted
            metadata: Optional video metadata for logging
        """
        data = self.load_deleted_videos()
        
        # Add to deleted videos if not already there
        if video_id not in data["deleted_videos"]:
            data["deleted_videos"].append(video_id)
            data["total_deletions_since_rebuild"] += 1
            
            # Add to deletion history
            history_entry = {
                "video_id": video_id,
                "deleted_at": datetime.now().isoformat(),
                "title": metadata.get("title") if metadata else None,
                "channel": metadata.get("channel") if metadata else None
            }
            data["deletion_history"].append(history_entry)
            
            # Save updated data
            with open(self.deleted_videos_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
    
    def mark_multiple_deleted(self, video_ids: List[str]) -> None:
        """Mark multiple videos as deleted"""
        data = self.load_deleted_videos()
        
        added_count = 0
        for video_id in video_ids:
            if video_id not in data["deleted_videos"]:
                data["deleted_videos"].append(video_id)
                data["total_deletions_since_rebuild"] += 1
                added_count += 1
                
                history_entry = {
                    "video_id": video_id,
                    "deleted_at": datetime.now().isoformat()
                }
                data["deletion_history"].append(history_entry)
        
        if added_count > 0:
            with open(self.deleted_videos_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
    
    def is_deleted(self, video_id: str) -> bool:
        """Check if a video is marked as deleted"""
        return video_id in self.get_deleted_video_ids()
    
    def clear_deleted_videos(self) -> int:
        """
        Clear all deleted videos after rebuild
        
        Returns:
            Number of videos cleared
        """
        data = self.load_deleted_videos()
        count = len(data["deleted_videos"])
        
        data["deleted_videos"] = []
        data["total_deletions_since_rebuild"] = 0
        data["last_rebuild"] = datetime.now().isoformat()
        
        with open(self.deleted_videos_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        return count
    
    def get_deletion_percentage(self, total_videos: int) -> float:
        """
        Calculate percentage of videos that are soft-deleted
        
        Args:
            total_videos: Total number of videos in the system
            
        Returns:
            Percentage (0.0 to 1.0)
        """
        if total_videos == 0:
            return 0.0
        
        deleted_count = len(self.get_deleted_video_ids())
        return deleted_count / total_videos
    
    def should_warn_rebuild(self, total_videos: int) -> bool:
        """Check if rebuild warning should be shown (>= 5% threshold)"""
        return self.get_deletion_percentage(total_videos) >= DELETION_REBUILD_THRESHOLD
    
    def get_rebuild_warning_message(self, total_videos: int) -> Optional[str]:
        """
        Get rebuild warning message if threshold exceeded
        
        Returns:
            Warning message string or None
        """
        deleted_count = len(self.get_deleted_video_ids())
        percentage = self.get_deletion_percentage(total_videos)
        
        if percentage >= DELETION_REBUILD_THRESHOLD:
            return (
                f"⚠️ REBUILD RECOMMENDED: {deleted_count} videos ({percentage*100:.1f}%) are soft-deleted.\n"
                f"FAISS index contains 'ghost' embeddings taking up space.\n\n"
                f"To rebuild:\n"
                f"1. Close Flipper search app and GUI (free memory)\n"
                f"2. Run: python -m data_pipeline.indexer\n"
                f"3. This will permanently remove deleted videos from index\n\n"
                f"Note: Rebuild requires significant memory. Close other Python processes first."
            )
        
        return None
    
    def get_stats(self) -> Dict:
        """Get deletion statistics"""
        data = self.load_deleted_videos()
        return {
            "currently_deleted": len(data["deleted_videos"]),
            "total_deletions_since_rebuild": data["total_deletions_since_rebuild"],
            "last_rebuild": data.get("last_rebuild"),
            "deletion_history_count": len(data["deletion_history"])
        }
