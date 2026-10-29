# Query Embedding for Front-End Integration

## Overview
Three Python modules to convert user search queries into vector embeddings using the same **text-embedding-3-large** model used for video transcripts.

## Files Created

### 1. `query_embedder.py` - Core Module
Full-featured class for query embedding.

**Usage:**
```python
from query_embedder import QueryEmbedder

# Initialize
embedder = QueryEmbedder(
    model="text-embedding-3-large",
    dimensions=3072
)

# Single query
embedding = embedder.embed_query("How to count to ten")
# Returns: np.ndarray, shape (1, 3072), dtype float32

# Batch queries
embeddings = embedder.embed_batch([
    "count to ten",
    "Christmas songs",
    "multiplication"
])
# Returns: np.ndarray, shape (3, 3072), dtype float32
```

### 2. `query_api.py` - Simple API
Easy-to-use functions for quick integration.

**Usage:**
```python
from query_api import embed_query, embed_queries, embed_for_search

# Single query
embedding = embed_query("How to count to ten")

# Multiple queries
embeddings = embed_queries(["query 1", "query 2"])

# For FAISS search (recommended)
query_vector = embed_for_search("your search here")
```

### 3. `search_demo.py` - Complete Example
Full end-to-end search demonstration.

**Usage:**
```bash
python search_demo.py
```

## Quick Integration Examples

### Example 1: Basic Search
```python
from query_api import embed_for_search
import faiss
import pickle

# Load FAISS index (do this once at startup)
index = faiss.read_index('faiss_index/faiss_index.index')
with open('faiss_index/faiss_index_metadata.pkl', 'rb') as f:
    metadata = pickle.load(f)

# User searches
user_query = "How to count to ten"

# Convert query to embedding (same model as transcripts)
query_vector = embed_for_search(user_query)

# Search FAISS index
k = 5  # Number of results
distances, indices = index.search(query_vector, k)

# Get results with metadata
for i, idx in enumerate(indices[0]):
    result = metadata[idx]
    print(f"{i+1}. {result['title']}")
    print(f"   Similarity: {1 / (1 + distances[0][i]):.4f}")
    print(f"   Text: {result['text'][:100]}...")
```

### Example 2: Flask API
```python
from flask import Flask, request, jsonify
from query_api import embed_for_search
import faiss
import pickle

app = Flask(__name__)

# Load once at startup
index = faiss.read_index('faiss_index/faiss_index.index')
with open('faiss_index/faiss_index_metadata.pkl', 'rb') as f:
    metadata = pickle.load(f)

@app.route('/search', methods=['POST'])
def search():
    data = request.json
    query = data.get('query', '')
    k = data.get('k', 5)
    
    # Generate embedding
    query_vector = embed_for_search(query)
    
    # Search
    distances, indices = index.search(query_vector, k)
    
    # Format results
    results = []
    for i, idx in enumerate(indices[0]):
        if idx == -1:
            continue
        results.append({
            'rank': i + 1,
            'video_id': metadata[idx]['video_id'],
            'title': metadata[idx]['title'],
            'text': metadata[idx]['text'],
            'similarity': float(1 / (1 + distances[0][i]))
        })
    
    return jsonify({
        'query': query,
        'results': results
    })

if __name__ == '__main__':
    app.run(debug=True)
```

### Example 3: Streamlit UI
```python
import streamlit as st
from query_api import embed_for_search
import faiss
import pickle

# Load index (cached)
@st.cache_resource
def load_index():
    index = faiss.read_index('faiss_index/faiss_index.index')
    with open('faiss_index/faiss_index_metadata.pkl', 'rb') as f:
        metadata = pickle.load(f)
    return index, metadata

index, metadata = load_index()

# UI
st.title("🔍 Video Transcript Search")
query = st.text_input("Enter your search query:")

if query:
    # Generate embedding
    query_vector = embed_for_search(query)
    
    # Search
    k = st.slider("Number of results", 1, 10, 5)
    distances, indices = index.search(query_vector, k)
    
    # Display results
    for i, idx in enumerate(indices[0]):
        if idx == -1:
            continue
        
        result = metadata[idx]
        similarity = 1 / (1 + distances[0][i])
        
        with st.expander(f"#{i+1} - {result['title']} (Similarity: {similarity:.4f})"):
            st.write(f"**Video ID:** {result['video_id']}")
            st.write(f"**Chunk:** {result['chunk_index']}")
            st.write(f"**Text:**")
            st.write(result['text'])
```

### Example 4: FastAPI Backend
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from query_api import embed_for_search
import faiss
import pickle

app = FastAPI()

# Load at startup
index = faiss.read_index('faiss_index/faiss_index.index')
with open('faiss_index/faiss_index_metadata.pkl', 'rb') as f:
    metadata = pickle.load(f)

class SearchRequest(BaseModel):
    query: str
    k: int = 5

class SearchResult(BaseModel):
    rank: int
    video_id: str
    title: str
    text: str
    similarity: float

@app.post("/search", response_model=list[SearchResult])
async def search(request: SearchRequest):
    if not request.query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    # Generate embedding
    query_vector = embed_for_search(request.query)
    
    # Search
    distances, indices = index.search(query_vector, request.k)
    
    # Format results
    results = []
    for i, idx in enumerate(indices[0]):
        if idx == -1:
            continue
        result = metadata[idx]
        results.append(SearchResult(
            rank=i + 1,
            video_id=result['video_id'],
            title=result['title'],
            text=result['text'],
            similarity=float(1 / (1 + distances[0][i]))
        ))
    
    return results
```

## Key Features

### ✅ Same Model as Transcripts
- Uses **text-embedding-3-large**
- **3072 dimensions**
- Ensures query and transcript embeddings are in the same vector space

### ✅ Optimized for FAISS
- Returns **float32** NumPy arrays
- Shape: **(1, 3072)** for single queries
- Shape: **(n, 3072)** for batch queries
- Ready for `index.search()`

### ✅ Easy Integration
- Simple function calls
- Works with any Python web framework
- Handles API key management
- Error handling included

## Testing

### Test Single Query
```bash
python -c "from query_api import embed_query; print(embed_query('test').shape)"
# Output: (1, 3072)
```

### Test Batch Queries
```bash
python -c "from query_api import embed_queries; print(embed_queries(['q1', 'q2']).shape)"
# Output: (2, 3072)
```

### Test Complete Search
```bash
python search_demo.py
```

## Performance

- **Single query**: ~100-200ms (OpenAI API call)
- **Batch queries**: ~150-300ms for 10 queries
- **FAISS search**: <1ms for 34 vectors
- **Total search time**: ~100-200ms end-to-end

## Cost

OpenAI API pricing (text-embedding-3-large):
- ~$0.00013 per 1,000 tokens
- Average query: ~10 tokens
- **Cost per search**: ~$0.0000013 (essentially free)

## Front-End Integration Checklist

- [x] Query embedding function ready
- [x] Same model as transcripts (text-embedding-3-large)
- [x] Float32 NumPy arrays for FAISS
- [x] Simple API for easy integration
- [x] Example implementations (Flask, FastAPI, Streamlit)
- [x] Error handling included
- [x] Batch processing supported

## Next Steps

1. Choose your front-end framework (Flask, FastAPI, Streamlit, etc.)
2. Copy the relevant example code above
3. Customize the UI/UX to your needs
4. Deploy your search application

All the embedding infrastructure is ready to go! 🚀
