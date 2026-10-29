"""
Fix Old Deletions - Add previously deleted videos to soft-delete tracker

Use this script to properly track videos that were deleted before the 
soft-delete system was implemented. This ensures they won't appear in 
Flipper search results.

Usage:
    python fix_old_deletions.py VIDEO_ID1 VIDEO_ID2 [VIDEO_ID3 ...]
"""

import sys
import json
from pathlib import Path
from data_pipeline.deletion_tracker import DeletionTracker

def main():
    if len(sys.argv) < 2:
        print("Usage: python fix_old_deletions.py VIDEO_ID1 VIDEO_ID2 ...")
        print("\nExample: python fix_old_deletions.py abc123 xyz789")
        sys.exit(1)
    
    video_ids = sys.argv[1:]
    
    print("="*60)
    print("Fix Old Deletions - Adding to Soft-Delete Tracker")
    print("="*60)
    print(f"\nVideo IDs to track: {', '.join(video_ids)}")
    
    # Confirm
    response = input("\nAdd these videos to deletion tracker? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("Cancelled.")
        sys.exit(0)
    
    # Load tracker
    tracker = DeletionTracker()
    
    # Check which are already tracked
    already_deleted = tracker.get_deleted_video_ids()
    new_videos = [vid for vid in video_ids if vid not in already_deleted]
    already_tracked = [vid for vid in video_ids if vid in already_deleted]
    
    if already_tracked:
        print(f"\n✓ Already tracked: {', '.join(already_tracked)}")
    
    if not new_videos:
        print("\n✓ All videos already in deletion tracker. Nothing to do.")
        sys.exit(0)
    
    # Add to tracker
    print(f"\n📝 Adding {len(new_videos)} video(s) to deletion tracker...")
    tracker.mark_multiple_deleted(new_videos)
    
    print(f"✓ Added: {', '.join(new_videos)}")
    
    # Get stats
    stats = tracker.get_stats()
    print(f"\n{'='*60}")
    print("Deletion Tracker Stats:")
    print(f"  Total soft-deleted videos: {stats['currently_deleted']}")
    print(f"  Deletions since last rebuild: {stats['total_deletions_since_rebuild']}")
    print(f"{'='*60}")
    
    # Check rebuild threshold
    faiss_metadata = Path('data/faiss_index/faiss_index_metadata.json')
    if faiss_metadata.exists():
        try:
            with open(faiss_metadata, 'r', encoding='utf-8') as f:
                data = json.load(f)
            total_videos = len(set(e.get('video_id') for e in data.get('metadata', [])))
            
            warning_msg = tracker.get_rebuild_warning_message(total_videos)
            if warning_msg:
                print(f"\n{warning_msg}")
            else:
                deleted_pct = (stats['currently_deleted'] / total_videos) * 100 if total_videos > 0 else 0
                print(f"\n💡 Deletion percentage: {deleted_pct:.2f}% (rebuild recommended at 5%)")
        except Exception as e:
            print(f"\nNote: Could not check rebuild threshold: {e}")
    
    print("\n✅ Done! These videos will now be filtered from Flipper search results.")

if __name__ == "__main__":
    main()
