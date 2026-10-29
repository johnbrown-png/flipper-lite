import json
import faiss

idx = faiss.read_index('data/faiss_index/faiss_index.bin')
with open('data/faiss_index/faiss_index_metadata.json', 'r', encoding='utf-8') as f:
    meta = json.load(f)

index_count = idx.ntotal
meta_count = len(meta["metadata"])
aligned = index_count == meta_count

print(f"Index vectors: {index_count}")
print(f"Metadata entries: {meta_count}")
print(f"Aligned: {aligned}")

if aligned:
    print("✓ Index and metadata are now synchronized!")
else:
    print(f"✗ Still misaligned by {abs(index_count - meta_count)} entries")
