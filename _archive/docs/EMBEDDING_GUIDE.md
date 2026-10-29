# Embedding Generation Module

## Overview
The `generate_embeddings.py` script converts text chunks into vector embeddings using OpenAI's API, specifically the `text-embedding-3-large` model.

## Features
- ✅ Modular and reusable design
- ✅ Batch processing for efficiency (up to 100 texts per API call)
- ✅ Rate limiting to avoid API throttling
- ✅ Rich metadata preservation
- ✅ Individual and consolidated output files
- ✅ Error handling and retry logic
- ✅ Configurable via environment variables

## Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure API Key
Add your OpenAI API key to `.env`:
```env
OPENAI_API_KEY=sk-your-actual-key-here
EMBEDDING_MODEL=text-embedding-3-large
```

## Usage

### Basic Usage
```bash
python generate_embeddings.py
```

### Output Structure

#### Individual Files
Each video gets its own embedding file:
```
embeddings_output/
  ├── 7LQQKeVGyFY_embeddings.json
  ├── gUWYzub1ZyA_embeddings.json
  └── ...
```

#### Consolidated File
All embeddings combined:
```
embeddings_consolidated.json
```

## Output Format

### Individual Embedding File
```json
{
  "video_id": "string",
  "title": "string",
  "published_at": "ISO-8601 datetime",
  "embedding_model": "text-embedding-3-large",
  "embedding_dimension": 3072,
  "total_chunks": integer,
  "embeddings": [
    {
      "metadata": {
        "video_id": "string",
        "title": "string",
        "published_at": "string",
        "chunk_index": integer,
        "start_token": integer,
        "end_token": integer,
        "token_count": integer,
        "text": "string",
        "embedding_model": "text-embedding-3-large",
        "embedding_dimension": 3072
      },
      "embedding": [float, float, ...] // 3072 dimensions
    }
  ]
}
```

### Consolidated File
```json
{
  "embedding_model": "text-embedding-3-large",
  "embedding_dimension": 3072,
  "total_videos": integer,
  "total_embeddings": integer,
  "embeddings": [
    // All embeddings from all videos with full metadata
  ]
}
```

## Module Architecture

### Class: `EmbeddingGenerator`

#### Initialization
```python
generator = EmbeddingGenerator(
    api_key="your-openai-api-key",
    model="text-embedding-3-large",  # or "text-embedding-3-small"
    dimensions=3072,                 # Optional: reduce dimensions
    batch_size=100,                  # Texts per API call
    rate_limit_delay=0.1            # Seconds between calls
)
```

#### Key Methods

##### `generate_embedding(text: str) -> List[float]`
Generate embedding for a single text.

##### `generate_embeddings_batch(texts: List[str]) -> List[List[float]]`
Generate embeddings for multiple texts in one API call (more efficient).

##### `process_chunked_file(json_path: Path) -> List[Dict]`
Process a single chunked JSON file and return embeddings with metadata.

##### `process_directory(input_dir: Path, output_dir: Path) -> Dict`
Process all chunked files in a directory.

##### `save_consolidated_embeddings(embeddings_dir: Path, output_file: Path)`
Merge all individual embedding files into one consolidated file.

## Configuration Options

### Environment Variables
```env
# Required
OPENAI_API_KEY=your_key_here

# Optional
EMBEDDING_MODEL=text-embedding-3-large  # or text-embedding-3-small
EMBEDDING_DIMENSIONS=3072               # Reduce for smaller storage
```

### Model Options

| Model | Default Dimensions | Max Dimensions |
|-------|-------------------|----------------|
| text-embedding-3-large | 3072 | 3072 |
| text-embedding-3-small | 1536 | 1536 |

### Dimension Reduction
You can reduce dimensions for smaller storage while maintaining quality:
```python
# Instead of 3072 dimensions, use 1536
generator = EmbeddingGenerator(
    api_key=api_key,
    model="text-embedding-3-large",
    dimensions=1536  # Reduced from 3072
)
```

## Performance

### Batch Processing
- Uses OpenAI's batch API endpoint
- Processes up to 100 chunks per API call
- Significantly faster than individual calls

### Rate Limiting
- Default: 0.1 second delay between batches
- Adjust via `rate_limit_delay` parameter
- Prevents API throttling

### Expected Timing
- ~100ms per batch of 100 texts
- For 32 videos (~34 chunks): ~1-2 seconds total
- Scales linearly with number of chunks

## Integration Examples

### Use with Vector Database
```python
from generate_embeddings import EmbeddingGenerator
import json

# Initialize
generator = EmbeddingGenerator(api_key="your_key")

# Load consolidated embeddings
with open('embeddings_consolidated.json') as f:
    data = json.load(f)

# Store in vector database (example: Pinecone, Weaviate, etc.)
for item in data['embeddings']:
    vector_db.upsert(
        id=f"{item['metadata']['video_id']}_{item['metadata']['chunk_index']}",
        vector=item['embedding'],
        metadata=item['metadata']
    )
```

### Semantic Search Example
```python
# Generate query embedding
query = "How to count to ten"
query_embedding = generator.generate_embedding(query)

# Search vector database
results = vector_db.search(
    vector=query_embedding,
    top_k=5,
    filter={"video_id": {"$exists": True}}
)

# Display results
for result in results:
    print(f"Video: {result.metadata['title']}")
    print(f"Chunk: {result.metadata['chunk_index']}")
    print(f"Text: {result.metadata['text'][:100]}...")
    print(f"Score: {result.score}")
    print()
```

## Error Handling

The module handles common errors:
- ✅ API key validation
- ✅ Rate limit errors (automatic retry)
- ✅ Network timeouts
- ✅ Invalid JSON files
- ✅ Empty chunks

## Cost Estimation

### OpenAI Pricing (as of Jan 2026)
- text-embedding-3-large: ~$0.13 per 1M tokens
- text-embedding-3-small: ~$0.02 per 1M tokens

### Your Dataset
- 32 videos
- ~34 total chunks
- ~4,000 total tokens
- **Estimated cost**: < $0.01

## Next Steps

After generating embeddings:
1. **Store in Vector Database**: Use Pinecone, Weaviate, ChromaDB, or FAISS
2. **Build Search Interface**: Create query endpoint
3. **Implement RAG**: Use for retrieval-augmented generation
4. **Analytics**: Cluster similar content, find patterns

## Troubleshooting

### "No API key found"
Add `OPENAI_API_KEY` to your `.env` file.

### "Rate limit exceeded"
Increase `rate_limit_delay` parameter.

### "Invalid dimensions"
Ensure dimensions ≤ max for model (3072 for large, 1536 for small).

### Memory Issues
Process files individually instead of batch mode, or reduce dimensions.
