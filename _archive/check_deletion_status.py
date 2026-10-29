"""
Check Deletion Status - Verify the state of deleted videos

Use this to check if videos still exist in various parts of the system.

Usage:
    python check_deletion_status.py VIDEO_ID1 VIDEO_ID2 [VIDEO_ID3 ...]
"""

import sys
import json
from pathlib import Path
from data_pipeline.deletion_tracker import DeletionTracker

def check_video_status(video_id: str):
    """Check if video exists in various system components"""
    print(f"\n{'='*60}")
    print(f"Checking status of: {video_id}")
    print(f"{'='*60}")
    
    status = {
        'video_id': video_id,
        'embedding_file': False,
        'chunked_file': False,
        'in_faiss_metadata': False,
        'in_deletion_tracker': False,
        'metadata_entries_count': 0
    }
    
    # Check embedding file
    emb_file = Path(f'data/embeddings_output/{video_id}_embeddings.json')
    status['embedding_file'] = emb_file.exists()
    print(f"Embedding file: {'✓ EXISTS' if status['embedding_file'] else '✗ NOT FOUND'}")
    
    # Check chunked file
    chunk_file = Path(f'data/chunked_output/{video_id}_chunked.json')
    status['chunked_file'] = chunk_file.exists()
    print(f"Chunked file:   {'✓ EXISTS' if status['chunked_file'] else '✗ NOT FOUND'}")
    
    # Check FAISS metadata
    faiss_meta = Path('data/faiss_index/faiss_index_metadata.json')
    if faiss_meta.exists():
        try:
            with open(faiss_meta, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            entries = [e for e in data.get('metadata', []) if e.get('video_id') == video_id]
            status['metadata_entries_count'] = len(entries)
            status['in_faiss_metadata'] = len(entries) > 0
            
            if status['in_faiss_metadata']:
                print(f"FAISS metadata: ✓ FOUND ({len(entries)} entries)")
                print(f"  ⚠️  These entries are 'ghost' embeddings in the index")
            else:
                print(f"FAISS metadata: ✗ NOT FOUND (properly removed)")
        except Exception as e:
            print(f"FAISS metadata: ⚠️  ERROR reading: {e}")
    else:
        print(f"FAISS metadata: ⚠️  File not found")
    
    # Check deletion tracker
    tracker = DeletionTracker()
    status['in_deletion_tracker'] = tracker.is_deleted(video_id)
    print(f"Deletion tracker: {'✓ TRACKED' if status['in_deletion_tracker'] else '✗ NOT TRACKED'}")
    
    # Analysis
    print(f"\n{'='*60}")
    print("ANALYSIS:")
    
    if not status['embedding_file'] and not status['chunked_file']:
        print("✓ Physical files properly deleted")
    else:
        print("⚠️  Physical files still exist (should be deleted)")
    
    if status['in_faiss_metadata'] and not status['in_deletion_tracker']:
        print("⚠️  ACTION NEEDED: Video in FAISS but not tracked for soft-delete")
        print(f"   Run: python fix_old_deletions.py {video_id}")
    elif status['in_faiss_metadata'] and status['in_deletion_tracker']:
        print("✓ Video properly soft-deleted (tracked, will be filtered in search)")
        print("  Note: Will be permanently removed on next index rebuild")
    elif not status['in_faiss_metadata']:
        print("✓ Video properly removed from FAISS metadata")
        if status['in_deletion_tracker']:
            print("  (Deletion tracking can be cleared with next rebuild)")
    
    return status


def main():
    if len(sys.argv) < 2:
        print("Usage: python check_deletion_status.py VIDEO_ID1 VIDEO_ID2 ...")
        print("\nExample: python check_deletion_status.py abc123 xyz789")
        sys.exit(1)
    
    video_ids = sys.argv[1:]
    
    print("="*60)
    print("Video Deletion Status Checker")
    print("="*60)
    
    results = []
    for video_id in video_ids:
        result = check_video_status(video_id)
        results.append(result)
    
    # Summary
    if len(results) > 1:
        print(f"\n{'='*60}")
        print("SUMMARY:")
        print(f"{'='*60}")
        
        needs_tracking = [r['video_id'] for r in results 
                         if r['in_faiss_metadata'] and not r['in_deletion_tracker']]
        
        if needs_tracking:
            print(f"\n⚠️  Videos needing soft-delete tracking: {len(needs_tracking)}")
            print(f"   Run: python fix_old_deletions.py {' '.join(needs_tracking)}")
        else:
            print("\n✓ All videos properly handled!")
    
    # Deletion tracker stats
    print(f"\n{'='*60}")
    tracker = DeletionTracker()
    stats = tracker.get_stats()
    print("Deletion Tracker Stats:")
    print(f"  Currently tracked: {stats['currently_deleted']}")
    print(f"  Since last rebuild: {stats['total_deletions_since_rebuild']}")
    if stats['last_rebuild']:
        print(f"  Last rebuild: {stats['last_rebuild']}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
