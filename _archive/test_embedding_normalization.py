"""
Test script to verify embedding normalization in FAISS index
"""

import json
import numpy as np
import faiss
from query_embedder import QueryEmbedder

print("=" * 80)
print("EMBEDDING NORMALIZATION TEST")
print("=" * 80)

# Test 1: Check query embeddings
print("\n1. QUERY EMBEDDINGS:")
qe = QueryEmbedder()
test_queries = [
    "test query",
    "Sort objects by color",
    "Graphing quadratic functions"
]

for query in test_queries:
    vec = qe.embed_query(query)
    norm = np.linalg.norm(vec)
    print(f"  Query: '{query[:30]:30s}' | Norm: {norm:.10f}")

# Test 2: Check document embeddings in consolidated file
print("\n2. DOCUMENT EMBEDDINGS (from consolidated file):")
with open('data/embeddings_consolidated.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
    
sample_size = 20
embeddings_sample = [e['embedding'] for e in data['embeddings'][:sample_size]]
norms = [np.linalg.norm(e) for e in embeddings_sample]

print(f"  Sampled {sample_size} embeddings:")
print(f"    Mean norm: {np.mean(norms):.10f}")
print(f"    Min norm:  {np.min(norms):.10f}")
print(f"    Max norm:  {np.max(norms):.10f}")
print(f"    All normalized (~1.0)? {all(0.99 < n < 1.01 for n in norms)}")

# Test 3: Check FAISS index vectors
print("\n3. FAISS INDEX VECTORS:")
index = faiss.read_index("data/faiss_index/faiss_index.bin")
print(f"  Index type: {type(index)}")
print(f"  Total vectors: {index.ntotal}")

# Extract some vectors from the index
sample_indices = list(range(min(20, index.ntotal)))
vectors = np.array([index.reconstruct(i) for i in sample_indices])
index_norms = [np.linalg.norm(v) for v in vectors]

print(f"  Sampled {len(sample_indices)} vectors from index:")
print(f"    Mean norm: {np.mean(index_norms):.10f}")
print(f"    Min norm:  {np.min(index_norms):.10f}")
print(f"    Max norm:  {np.max(index_norms):.10f}")
print(f"    All normalized (~1.0)? {all(0.99 < n < 1.01 for n in index_norms)}")

# Test 4: Perform a test search
print("\n4. TEST SEARCH:")
test_query = "**Sort objects** Example: Children learn to sort object collections into sets by attributes like colour, size, or shape"
print(f"  Query: '{test_query[:80]}...'")

query_vec = qe.embed_query(test_query)
query_norm = np.linalg.norm(query_vec)
print(f"  Query norm: {query_norm:.10f}")

distances, indices = index.search(query_vec, 5)

with open('data/faiss_index/faiss_index_metadata.json', 'r', encoding='utf-8') as f:
    metadata_data = json.load(f)
    metadata = metadata_data['metadata']

print(f"\n  Top 5 results:")
for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
    if idx < len(metadata):
        meta = metadata[idx]
        cosine_sim = 1 - (dist ** 2 / 2)
        print(f"    #{i+1} L2_dist={dist:.4f} | Cosine={cosine_sim:.4f} | {meta['title'][:60]}")
        if i == 0:
            # Check the actual vector in the index
            doc_vec = index.reconstruct(int(idx))
            doc_norm = np.linalg.norm(doc_vec)
            print(f"        Document vector norm: {doc_norm:.10f}")
            
            # Calculate manual dot product
            manual_dot = np.dot(query_vec[0], doc_vec)
            manual_cosine = manual_dot / (query_norm * doc_norm)
            print(f"        Manual cosine similarity: {manual_cosine:.10f}")

print("\n" + "=" * 80)
print("DIAGNOSIS:")
print("=" * 80)

if all(0.99 < n < 1.01 for n in norms) and all(0.99 < n < 1.01 for n in index_norms):
    print("✓ All embeddings are properly normalized")
    print("  The issue may be elsewhere (index corruption, metadata mismatch, etc.)")
else:
    print("✗ EMBEDDINGS ARE NOT NORMALIZED!")
    print("  This explains the incorrect similarity scores.")
    print("  Solution: Rebuild FAISS index with normalized embeddings")
