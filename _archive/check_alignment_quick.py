"""Quick diagnostic to check FAISS/metadata/embeddings alignment"""
import json
from pathlib import Path

# Check FAISS metadata
faiss_meta_path = Path('data/faiss_index/faiss_index_metadata.json')
with open(faiss_meta_path, 'r', encoding='utf-8') as f:
    faiss_metadata = json.load(f)

print(f"✓ FAISS metadata type: {type(faiss_metadata)}")
print(f"✓ FAISS metadata entries: {len(faiss_metadata)}")
if isinstance(faiss_metadata, dict):
    print(f"  Keys: {list(faiss_metadata.keys())}")
    if 'metadata' in faiss_metadata:
        faiss_list = faiss_metadata['metadata']
        print(f"  Metadata array length: {len(faiss_list)}")
        print(f"  Total vectors (from file): {faiss_metadata.get('total_vectors', 'N/A')}")
        
        if faiss_list and len(faiss_list) > 0:
            first_item = faiss_list[0]
            print(f"  Sample video_id: {first_item.get('video_id', 'N/A')}")
            print(f"  Sample keys: {list(first_item.keys())}")
    else:
        faiss_list = []
elif isinstance(faiss_metadata, list):
    faiss_list = faiss_metadata
    if faiss_list:
        print(f"  Sample video_id: {faiss_list[0].get('video_id', 'N/A')}")
        print(f"  Sample keys: {list(faiss_list[0].keys())}")
else:
    faiss_list = []

# Check deleted videos
deleted_path = Path('data/deleted_videos.json')
with open(deleted_path, 'r', encoding='utf-8') as f:
    deleted_data = json.load(f)

deleted_ids = set(deleted_data.get('deleted_videos', []))
print(f"\n✓ Deleted videos: {len(deleted_ids)}")

# Check embeddings consolidated (SIZE CHECK ONLY)
emb_path = Path('data/embeddings_consolidated.json')
# Skip loading for now - file is too large
embeddings_count = 0
print(f"⏸️  Embeddings consolidated: SKIPPED (file too large, {emb_path.stat().st_size / (1024**2):.1f}MB)")

# Check for misalignment
print(f"\n=== ALIGNMENT CHECK ===")
print(f"FAISS metadata count:    {len(faiss_list)}")
print(f"Deleted videos count:    {len(deleted_ids)}")
print(f"Expected (if all deleted removed): {len(faiss_list) - len(deleted_ids)}")

# Check if deleted videos are in FAISS metadata
faiss_video_ids = {item.get('video_id') for item in faiss_list if isinstance(item, dict)}
deleted_in_faiss = faiss_video_ids & deleted_ids

if deleted_in_faiss:
    print(f"\n⚠️  WARNING: {len(deleted_in_faiss)} deleted videos still in FAISS metadata!")
    print(f"   Sample deleted IDs in FAISS: {list(deleted_in_faiss)[:10]}")
    
    # Show some details about these deleted videos
    for vid_id in list(deleted_in_faiss)[:3]:
        for item in faiss_list:
            if item.get('video_id') == vid_id:
                print(f"   - {vid_id}: {item.get('title', 'N/A')[:60]}")
                break
else:
    print(f"\n✓ No deleted videos found in FAISS metadata")
