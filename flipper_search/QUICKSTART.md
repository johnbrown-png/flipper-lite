"""
Quick-start: How to use flipper_search

This guide covers:
1. Building the embeddings index (one-time)
2. Integrating into flipper_lite
3. Testing the search
"""

# ============================================================================
# STEP 1: Build Embeddings Index (One-Time Setup)
# ============================================================================

# From project root, run:
#   python -m flipper_search.build_index \
#     --curriculum Curriculum/Maths/curriculum_08052026_small_steps.csv \
#     --output data/curriculum_embeddings.npy \
#     --batch-size 50

# This will:
#   - Load all ~2000 curriculum small steps
#   - Embed them using OpenAI (cost: ~$1-2 USD)
#   - Save embeddings to: data/curriculum_embeddings.npy
#   - Save metadata to: data/curriculum_embeddings.json

# Expected output:
#   ✓ Loaded 2000+ small steps
#   ✓ Embeddings shape: (2000, 3072)
#   ✓ Saved embeddings to: data/curriculum_embeddings.npy


# ============================================================================
# STEP 2: Integrate into flipper_lite.py
# ============================================================================

# At the top of flipper_lite.py, add:
#
#   import sys
#   sys.path.insert(0, str(project_root))
#   from flipper_search.streamlit_ui import render_search_ui
#

# In the main() function, after the curriculum assistant block, add:
#
#   # ==========================================
#   # NATURAL LANGUAGE SEARCH (Flipper Search)
#   # ==========================================
#   st.markdown("---")
#   st.markdown("### Or search by topic description:")
#   
#   search_result = render_search_ui(
#       curriculum_csv_path=str(project_root / "Curriculum" / "Maths" / "curriculum_08052026_small_steps.csv"),
#       embeddings_path=str(project_root / "data" / "curriculum_embeddings.npy"),
#       use_semantic=True,
#   )
#   
#   if search_result:
#       action, result_dict = search_result
#       if action == 'small_step_search':
#           # Trigger the same flow as curriculum dropdown selection
#           st.session_state.display_status = 'loading'
#           st.session_state.curriculum_context = result_dict
#           
#           results = lookup_videos_for_step(
#               recommendations_df,
#               result_dict['year'],
#               result_dict['term'],
#               result_dict.get('difficulty', ''),
#               result_dict['topic'],
#               result_dict['small_step_name'],
#               result_dict.get('small_step_id', ''),
#           )
#           st.session_state.display_results = results
#           st.session_state.display_status = 'complete'
#           st.rerun()


# ============================================================================
# STEP 3: Test the Search (Standalone)
# ============================================================================

# python -m flipper_search.test_search --query "adding fractions with different denominators"


# ============================================================================
# Key Files
# ============================================================================

# flipper_search/
#   ├── __init__.py                 # Module exports
#   ├── epoch_definitions.py         # Epoch ranges (Y1-3, Y3-5, etc.)
#   ├── curriculum_index.py          # Load and index curriculum
#   ├── search_engine.py             # Lexical + semantic retrieval
#   ├── build_index.py               # Script to build embeddings
#   ├── streamlit_ui.py              # UI components for flipper_lite
#   ├── test_search.py               # Testing/demo script
#   └── PROJECT_SCOPE.md             # This documentation
#
# data/
#   ├── curriculum_embeddings.npy    # Precomputed embeddings (created by build_index.py)
#   └── curriculum_embeddings.json   # Metadata (created by build_index.py)


# ============================================================================
# API Reference
# ============================================================================

# CurriculumIndex(curriculum_csv_path)
#   - Load and index curriculum data
#   - Methods:
#     - get_searchable_text_all() → Dict[small_step_id, text]
#     - get_curriculum_row(small_step_id) → Dict
#     - get_small_steps_for_display(small_step_ids) → List[Dict]
#     - filter_by_epoch(epoch_name) → DataFrame

# SearchEngine(curriculum_index, embeddings_path, use_semantic=True)
#   - Hybrid search: lexical + semantic rerank
#   - Methods:
#     - search(query, top_k=10) → List[Dict with results]

# render_search_ui(...) → Tuple[action, result_dict] or None
#   - Streamlit UI for epoch filter + search input + results
#   - Returns selected result when user clicks


# ============================================================================
# Troubleshooting
# ============================================================================

# Q: "QueryEmbedder not found" error
# A: Make sure OPENAI_API_KEY is set in .env
#    python -c "from query_embedder import QueryEmbedder; print('OK')"

# Q: Embeddings file not found
# A: Run build_index.py first to create embeddings.npy
#    python -m flipper_search.build_index

# Q: Search is slow
# A: If semantic reranking is slow, can disable with use_semantic=False
#    Lexical-only is ~50ms; hybrid is ~150-200ms

# Q: No results returned
# A: Try simpler queries or different keywords
#    Check that curriculum CSV is loading correctly
