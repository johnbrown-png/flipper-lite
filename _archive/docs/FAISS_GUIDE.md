# FAISS Vector Index Documentation

## Overview
Your embeddings have been successfully converted to a FAISS vector search index with **float32 precision** NumPy arrays, optimized for fast similarity search.

## What Was Done

### 1. NumPy Conversion
- ✅ All embeddings converted to NumPy arrays
- ✅ Precision set to **float32** using `np.array(embeddings).astype('float32')`
- ✅ Array shape: **(34, 3072)**
- ✅ Memory optimized: 0.40 MB

### 2. FAISS Index Created
- **Type**: IndexFlatL2 (exact L2 distance search)
- **Vectors**: 34 embeddings
- **Dimension**: 3072
- **Memory**: ~0.4 MB

### 3. Files Generated
```
faiss_index/
  ├── faiss_index.index           # FAISS index (binary)
  ├── faiss_index_metadata.pkl    # Metadata (pickle format)
  └── faiss_index_metadata.json   # Metadata (human-readable)
```

## Scripts

### `build_faiss_index.py`
Converts embeddings to FAISS index with float32 precision.

**Features:**
- Loads embeddings from JSON
- Converts to NumPy arrays (float32)
- Creates FAISS index (Flat, IVF, or HNSW)
- Saves index and metadata

**Usage:**
```bash
python build_faiss_index.py
```

### `search_faiss.py`
Search engine for querying the FAISS index.

**Features:**
- Loads FAISS index and metadata
- Generates query embeddings via OpenAI API
- Performs similarity search
- Returns ranked results with metadata

**Usage:**
```bash
python search_faiss.py
```

## Technical Details

### Array Specifications
```python
embeddings_array = np.array(embeddings_list).astype('float32')
# Shape: (34, 3072)
# Dtype: float32
# Memory: 34 * 3072 * 4 bytes = 417,792 bytes (~0.4 MB)
```

### FAISS Index Types

#### IndexFlatL2 (Current - Default)
- **Pros**: Exact search, 100% accuracy
- **Cons**: Linear search time O(n)
- **Best for**: Small to medium datasets (<1M vectors)

#### IndexIVFFlat (Optional)
- **Pros**: Faster search with minimal quality loss
- **Setup**: Requires training, uses clustering
- **Best for**: Large datasets (>100K vectors)

#### IndexHNSW (Optional)
- **Pros**: Very fast approximate search
- **Cons**: Uses more memory
- **Best for**: Real-time search applications

### Change Index Type
Edit `build_faiss_index.py`:
```python
index_type = "Flat"   # Current
index_type = "IVF"    # Faster, needs training
index_type = "HNSW"   # Fastest, uses more memory
```

## Search Example

```python
from build_faiss_index import load_index
import numpy as np

# Load index
index, metadata = load_index(
    Path('faiss_index/faiss_index.index'),
    Path('faiss_index/faiss_index_metadata.pkl')
)

# Query vector (from OpenAI embedding API)
query_vector = np.array([embedding]).astype('float32')

# Search for top 5 similar vectors
k = 5
distances, indices = index.search(query_vector, k)

# Get results
for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
    print(f"Rank {i+1}: {metadata[idx]['title']}")
    print(f"Distance: {dist:.4f}")
    print(f"Text: {metadata[idx]['text'][:100]}...")
```

## Performance

### Current Dataset
- **34 vectors** × **3072 dimensions**
- **Search time**: ~0.1ms per query
- **Memory**: 0.4 MB

### Scalability
| Vectors | Search Time (Flat) | Memory |
|---------|-------------------|---------|
| 1K | ~0.5ms | 12 MB |
| 10K | ~5ms | 120 MB |
| 100K | ~50ms | 1.2 GB |
| 1M+ | Switch to IVF/HNSW | — |

## Integration Examples

### Python Integration
```python
from search_faiss import FAISSSearchEngine

engine = FAISSSearchEngine(
    index_path=Path('faiss_index/faiss_index.index'),
    metadata_path=Path('faiss_index/faiss_index_metadata.pkl'),
    openai_api_key='your_key'
)

results = engine.search("How to count to ten", k=5)
```

### REST API (Flask Example)
```python
from flask import Flask, request, jsonify

app = Flask(__name__)
engine = FAISSSearchEngine(...)

@app.route('/search', methods=['POST'])
def search():
    query = request.json['query']
    k = request.json.get('k', 5)
    results = engine.search(query, k)
    return jsonify(results)
```

### Gradio UI (Interactive Demo)
```python
import gradio as gr

def search_ui(query, k=5):
    results = engine.search(query, k)
    return "\n\n".join([
        f"**{r['title']}**\n{r['text'][:200]}..."
        for r in results
    ])

gr.Interface(
    fn=search_ui,
    inputs=[gr.Textbox(label="Query"), gr.Slider(1, 10, 5, label="Results")],
    outputs=gr.Textbox(label="Results")
).launch()
```

## Advantages of FAISS

1. **Speed**: Optimized C++ implementation
2. **Memory Efficient**: float32 reduces size by 50% vs float64
3. **Scalable**: Handles millions of vectors
4. **Production Ready**: Used by Facebook, Google, etc.
5. **GPU Support**: Optional GPU acceleration available

## Next Steps

1. **Test Search**: Run `python search_faiss.py`
2. **Add More Data**: Rerun pipeline when you have more videos
3. **Optimize Index**: Switch to IVF/HNSW for larger datasets
4. **Build UI**: Create web interface for end users
5. **Deploy**: Integrate into your application

## Troubleshooting

### "Index not found"
Run `python build_faiss_index.py` first.

### "Dimension mismatch"
Ensure query vectors are 3072 dimensions (same as index).

### "Out of memory"
Use IVF index type or reduce dimensions during embedding generation.

### Slow search
Switch from Flat to IVF or HNSW for faster approximate search.
