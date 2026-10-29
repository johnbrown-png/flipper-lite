# Transcript Chunking Documentation

## Overview
The `chunk_transcripts.py` script processes YouTube video transcripts and prepares them for vector embedding and semantic search by chunking them into optimally-sized pieces.

## Tokenization
- **Tokenizer**: `tiktoken` with `cl100k_base` encoding
- **Why**: This is the same tokenizer used by OpenAI's `text-embedding-3-small` and `text-embedding-3-large` models
- **Compatibility**: Works with most modern embedding models including OpenAI, Cohere, and others

## Chunking Strategy

### Hard Constraints
- **Chunk Size**: 250 tokens (target)
- **Overlap**: 40 tokens between consecutive chunks
- **Method**: Sliding window approach

### Soft Constraints
- **Sentence Boundaries**: Used as breakpoints when they fall within ±20 tokens of the target end
- **Logic**: The algorithm looks for the nearest sentence boundary within the margin and breaks there if found
- **Fallback**: If no sentence boundary exists in the margin, breaks at exactly 250 tokens

### Why This Approach?
1. **Token Count Priority**: Ensures chunks fit within embedding model limits
2. **Semantic Coherence**: Soft sentence boundaries preserve meaning when possible
3. **Overlap**: 40-token overlap ensures context continuity across chunks
4. **Deterministic**: Same input always produces same output

## Output Format

Each chunked JSON file contains:

```json
{
  "video_id": "string",
  "title": "string",
  "published_at": "ISO-8601 datetime",
  "total_tokens": integer,
  "total_chunks": integer,
  "chunks": [
    {
      "chunk_index": integer,
      "start_token": integer,
      "end_token": integer,
      "token_count": integer,
      "text": "string"
    }
  ]
}
```

## Usage

### Basic Usage
```bash
python chunk_transcripts.py
```

### Custom Configuration
Edit the `TranscriptChunker` initialization in `main()`:
```python
chunker = TranscriptChunker(
    chunk_size=250,              # Target chunk size
    overlap=40,                  # Token overlap
    sentence_boundary_margin=20, # ±20 tokens for sentence breaks
    model_name="cl100k_base"     # Tokenizer model
)
```

## File Structure
- **Input**: `captions_output/numberblocks/*.json`
- **Output**: `chunked_output/*_chunked.json`

## Statistics from Current Run
- **Total Videos Processed**: 32
- **Typical Chunk Size**: Most videos fit in 1 chunk (under 250 tokens)
- **Multi-chunk Videos**: 2 videos (344 and 341 tokens each → 2 chunks)
- **Token Range**: 3-344 tokens per video

## Integration with Vector Embeddings

The chunked output is ready for:
1. **Vector Embedding**: Feed `chunk['text']` to embedding model
2. **Vector Storage**: Store embeddings with metadata (`video_id`, `chunk_index`, etc.)
3. **Semantic Search**: Query embeddings and retrieve relevant chunks
4. **Result Assembly**: Use `video_id` and `chunk_index` to reconstruct context

## Example Chunk Retrieval Flow

```python
# 1. Load chunked data
with open('chunked_output/7LQQKeVGyFY_chunked.json') as f:
    data = json.load(f)

# 2. Generate embeddings for each chunk
for chunk in data['chunks']:
    embedding = embed_model.encode(chunk['text'])
    store_in_vector_db(
        embedding=embedding,
        metadata={
            'video_id': data['video_id'],
            'title': data['title'],
            'chunk_index': chunk['chunk_index'],
            'token_count': chunk['token_count']
        }
    )

# 3. Query for semantic search
query_embedding = embed_model.encode("Christmas counting")
results = vector_db.search(query_embedding, top_k=5)
```

## Advantages of This Approach

1. **Optimal for Embedding Models**: 250 tokens is well within limits for all major embedding models
2. **Context Preservation**: 40-token overlap ensures no information loss at boundaries
3. **Semantic Integrity**: Soft sentence boundaries keep complete thoughts together
4. **Scalable**: Deterministic chunking allows for incremental updates
5. **Metadata Rich**: Extensive metadata enables precise result filtering and ranking
