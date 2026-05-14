# Flipper Search – Project Scope

## Purpose

Enable flipper_lite users to find relevant curriculum topics using natural-language descriptions of what they need help with, rather than navigating structured dropdowns. Complement (not replace) the existing Age → Term → Topic → Small Step hierarchical navigation.

**User problem**: "How do I add fractions with different denominators?" → should find the right small step without knowing it's formally called "Fractions: addition with different denominators" or whether it's in Year 4 or 5.

## Approach

**Two-stage retrieval (Pass 1 MVP):**

1. **Stage A – Lexical Retrieval**
   - User enters: "how do I add fractions"
   - Build searchable text per small step: `topic + small_step_name + ss_desc + ss_wr_desc`
   - TF-IDF or BM25 ranking
   - Return top 30–50 candidates

2. **Stage B – Semantic Rerank** (optional but recommended)
   - Embed user query once (OpenAI embedding API; ~$0.000001 per query)
   - Cosine similarity against precomputed curriculum embeddings
   - Rerank lexical results by semantic similarity
   - Return top 5–10 results to user

**Why this works**:
- Lexical catches obvious keyword matches (very fast, zero cost)
- Semantic rerank handles paraphrasing ("gradient of a line" → "Gradients from equations")
- Hybrid avoids expensive full-corpus semantic search

## Scope – Pass 1 (MVP)

### In scope
- Epoch-based filtering (Early Primary Y1–3, Middle Primary Y3–5, Late Primary Y5–6, Early Secondary Y6–9, Middle Secondary Y8–10, Late Secondary Y9–11)
- Lexical retrieval with TF-IDF or BM25
- Optional semantic rerank (if cost acceptable to user)
- Display top 5–10 results with:
  - small_step_name
  - topic
  - age / year range
  - ss_desc (curriculum-provided short description, shown inline)
  - Match score (lexical or hybrid)
- Result selection → trigger existing flipper_lite small_step_search flow
- Streamlit UI integration into flipper_lite

### Out of scope
- Confidence thresholding (deferred to Pass 2)
- Query rewriting suggestions ("Did you mean...") – Pass 2
- Hover tooltips on results – Pass 2 (complexity trade-off)
- Video transcript search – remains curriculum-first only

## Technical Stack

- **Lexical indexing**: scikit-learn TfidfVectorizer or rank-bm25
- **Embeddings** (optional): OpenAI text-embedding-3-large (precomputed offline, single query embedding at runtime)
- **Corpus**: ~2000 small steps from curriculum_08052026_small_steps.csv
- **Storage**: Precomputed embeddings stored as `.npy` or pickle (loaded at startup, cached)
- **UI**: Streamlit (text_input, selectbox for epoch, results as clickable cards)

## Files to Create (Pass 1)

```
flipper_search/
├── __init__.py
├── epoch_definitions.py       # Epoch ranges and filtering
├── curriculum_index.py         # Load curriculum, build text corpus
├── search_engine.py            # Lexical + semantic retrieval
├── build_index.py              # Offline script to precompute embeddings
├── streamlit_ui.py             # Epoch filter + search box UI for flipper_lite
└── PROJECT_SCOPE.md            # This file
```

## Cost Implications

- **Offline (one-time)**: ~0.1–1.0 USD to embed ~2000 curriculum steps
- **Per search**: ~$0.000001–0.000005 (negligible; ~$0.003 per 1000 searches)
- **Alternative**: Use pure lexical (zero cost) if cost is a blocker

## Next Steps

1. Clarify: Lexical-only vs. Hybrid (lexical + semantic)?
2. Create `epoch_definitions.py` and `curriculum_index.py`
3. Implement lexical search in `search_engine.py`
4. Add Streamlit UI to flipper_lite
5. (Pass 2) Add semantic rerank, hover tooltips, confidence thresholding
