"""
Clean up deleted videos list after rebuild.
Removes videos from deleted list that are actually present in the rebuilt FAISS index.
"""
import json
from pathlib import Path

# Load FAISS metadata
faiss_meta_path = Path('data/faiss_index/faiss_index_metadata.json')
with open(faiss_meta_path, 'r', encoding='utf-8') as f:
    faiss_data = json.load(f)
    faiss_metadata = faiss_data['metadata']

faiss_video_ids = {item['video_id'] for item in faiss_metadata}
print(f"FAISS index contains: {len(faiss_video_ids)} unique video IDs")

# Load deleted videos
deleted_path = Path('data/deleted_videos.json')
with open(deleted_path, 'r', encoding='utf-8') as f:
    deleted_data = json.load(f)

original_deleted = set(deleted_data['deleted_videos'])
print(f"Deleted list contains: {len(original_deleted)} videos")

# Find videos in both (should be removed from deleted list since they're in index)
videos_in_both = original_deleted & faiss_video_ids
print(f"Videos in both deleted list AND index: {len(videos_in_both)}")

if videos_in_both:
    print(f"\n⚠️  Cleaning up: removing {len(videos_in_both)} videos from deleted list")
    print(f"   (These videos' embeddings still exist and were re-indexed)")
    
    # Remove these from deleted list
    deleted_data['deleted_videos'] = [v for v in deleted_data['deleted_videos'] 
                                      if v not in videos_in_both]
    deleted_data['total_deletions_since_rebuild'] = 0
    
    # Update deletion history to note these were re-indexed
    from datetime import datetime
    for vid_id in list(videos_in_both)[:5]:  # Show sample
        print(f"   - {vid_id}")
    
    deleted_data['last_rebuild'] = datetime.now().isoformat()
    
    # Save updated file
    with open(deleted_path, 'w', encoding='utf-8') as f:
        json.dump(deleted_data, f, indent=2)
    
    print(f"\n✓ Updated deleted_videos.json")
    print(f"  Deleted list now contains: {len(deleted_data['deleted_videos'])} videos")
else:
    print("\n✓ No cleanup needed - deleted list is correct")

print(f"\nFinal state:")
print(f"  FAISS index: {len(faiss_video_ids)} videos")
print(f"  Deleted tracking: {len(deleted_data['deleted_videos'])} videos")
print(f"  Net searchable: {len(faiss_video_ids)} videos (deleted filtered at search time)")
