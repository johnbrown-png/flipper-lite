"""
Test the exact search case: Sort objects -> Graphing Quadratic Functions
"""

import numpy as np
import faiss
import json
from query_embedder import QueryEmbedder

print("="*80)
print("TESTING: Sort objects search")
print("="*80)

# Load index and metadata
index = faiss.read_index("data/faiss_index/faiss_index.bin")
with open('data/faiss_index/faiss_index_metadata.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
    metadata = data['metadata']

print(f"\nLoaded index with {index.ntotal} vectors")
print(f"Loaded metadata with {len(metadata)} entries")
print(f"Index/Metadata alignment: {'✓ MATCH' if index.ntotal == len(metadata) else '✗ MISMATCH!'}")

# Create the exact query from the batch audit
small_step_name = "Sort objects"
small_step_desc = "Children learn to sort object collections into sets by attributes like colour, size, or shape, understanding the same collection can be sorted differently. They're encouraged to create their own sorting criteria. Practical activities and daily tasks, like lining up, reinforce this concept."

query = f"**{small_step_name}** Example: {small_step_desc}"
print(f"\nQuery: {query[:100]}...")

# Embed and search
qe = QueryEmbedder()
query_vec = qe.embed_query(query)

# Search for top 10
distances, indices = index.search(query_vec, 10)

print(f"\nTop 10 results:")
print(f"{'Rank':<6}{'L2 Dist':<12}{'Cosine':<10}{'Video ID':<15}{'Title'}")
print("-" * 120)

for rank, (dist, idx) in enumerate(zip(distances[0], indices[0]), 1):
    if idx == -1 or idx >= len(metadata):
        print(f"  {rank:<6}{'ERROR':<12}{'ERROR':<10}{'N/A':<15}Index out of range!")
        continue
    
    meta = metadata[idx]
    cosine_sim = 1 - (dist ** 2 / 2)
    
    video_id = meta['video_id']
    title = meta['title']
    text_preview = meta['text'][:100].replace('\n', ' ')
    
    print(f"{rank:<6}{dist:<12.6f}{cosine_sim:<10.6f}{video_id:<15}{title[:60]}")
    print(f"       Text: {text_preview}...")
    
    # Special check for the problematic video
    if 'Graphing Quadratic' in title or video_id == 'zGBoz1mebmM':
        print(f"       ⚠️  THIS IS THE PROBLEMATIC VIDEO!")
        print(f"       Chunk index: {meta.get('chunk_index', 'N/A')}")
        print(f"       Start time: {meta.get('start_time', 'N/A')}")
        print(f"       Let's check if this text actually contains relevant content...")
        print(f"       Full text:\n       {meta['text'][:500]}")
    print()

# Now let's check what video ID zGBoz1mebmM actually contains in the index
print("\n" + "="*80)
print("SEARCHING FOR VIDEO: zGBoz1mebmM in metadata")
print("="*80)

matching_chunks = [i for i, m in enumerate(metadata) if m['video_id'] == 'zGBoz1mebmM']
print(f"\nFound {len(matching_chunks)} chunks for video zGBoz1mebmM")

if matching_chunks:
    print(f"\nAll chunks for this video:")
    for i, idx in enumerate(matching_chunks[:5]):  # Show first 5 chunks
        m = metadata[idx]
        print(f"\n  Chunk {i+1} (index {idx}):")
        print(f"    Title: {m['title']}")
        print(f"    Text: {m['text'][:200]}...")
