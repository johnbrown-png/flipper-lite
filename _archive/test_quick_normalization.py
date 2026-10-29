"""
Quick test to check FAISS index normalization
"""

import numpy as np
import faiss
from query_embedder import QueryEmbedder
import json

print("Testing FAISS index normalization...")

# Load FAISS index
index = faiss.read_index("data/faiss_index/faiss_index.bin")
print(f"\nFAISS Index: {index.ntotal} vectors")

# Sample some vectors from the index
sample_indices = list(range(min(100, index.ntotal)))
vectors = np.array([index.reconstruct(i) for i in sample_indices])
norms = [np.linalg.norm(v) for v in vectors]

print(f"\nDocument vectors (sample of {len(sample_indices)}):")
print(f"  Mean norm: {np.mean(norms):.6f}")
print(f"  Min:  {np.min(norms):.6f}")
print(f"  Max:  {np.max(norms):.6f}")
print(f"  Std:  {np.std(norms):.6f}")

# Check query vector
qe = QueryEmbedder()
query_vec = qe.embed_query("test")
query_norm = np.linalg.norm(query_vec)
print(f"\nQuery vector norm: {query_norm:.6f}")

# Diagnosis
print("\n" + "="*60)
if 0.99 < np.mean(norms) < 1.01:
    print("✓ Document embeddings appear normalized (~1.0)")
else:
    print(f"✗ Document embeddings NOT normalized! (mean={np.mean(norms):.6f})")
    print("  This causes incorrect similarity scores!")
    print("  -> Need to rebuild FAISS index with normalized vectors")

if 0.99 < query_norm < 1.01:
    print("✓ Query embeddings are normalized (~1.0)")
else:
    print(f"✗ Query embeddings NOT normalized! (norm={query_norm:.6f})")
