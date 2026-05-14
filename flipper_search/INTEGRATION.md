"""
Integration Guide: Adding flipper_search to flipper_lite

This document shows the exact code changes needed to integrate natural-language
topic search into flipper_lite.
"""

# ============================================================================
# PREREQUISITE: Build the embeddings index
# ============================================================================

# From project root (one-time only):
#   python -m flipper_search.build_index \
#     --curriculum Curriculum/Maths/curriculum_08052026_small_steps.csv \
#     --output data/curriculum_embeddings.npy

# This creates:
#   - data/curriculum_embeddings.npy (embeddings matrix)
#   - data/curriculum_embeddings.json (metadata)


# ============================================================================
# STEP 1: Update flipper_lite.py imports
# ============================================================================

# At the top of flipper_lite.py, after existing imports, add:
#
# From flipper_search import the UI renderer
# from flipper_search.streamlit_ui import render_search_ui

# (Already have these, no change needed:)
# from search_app.curriculum_assistant import CurriculumAssistant
# import streamlit as st
# from pathlib import Path


# ============================================================================
# STEP 2: Add search UI section in main()
# ============================================================================

# In flipper_lite.py main() function, AFTER the curriculum assistant section
# (after the line: "action, text = curriculum_assistant.render()")
# 
# Add this new section:

CODE_SNIPPET = '''
    # ==========================================
    # NATURAL LANGUAGE TOPIC SEARCH (Flipper Search)
    # ==========================================
    st.markdown("---")
    
    with st.expander("🔍 Search by Topic Description", expanded=False):
        st.markdown("""
        Don't know the official curriculum term? Describe what you need help with:
        - "adding fractions with different denominators"
        - "how do I work out the gradient of a straight line"
        - "multiplying decimals by 10, 100, 1000"
        """)
        
        # Render search UI
        embeddings_path = project_root / "data" / "curriculum_embeddings.npy"
        search_result = render_search_ui(
            curriculum_csv_path=str(curriculum_path),
            embeddings_path=str(embeddings_path),
            use_semantic=True,  # Hybrid lexical + semantic
        )
        
        # Handle search result selection
        if search_result:
            action, result_dict = search_result
            if action == 'small_step_search':
                # Trigger same flow as dropdown selection
                st.session_state.display_status = 'loading'
                st.session_state.curriculum_context = result_dict
                
                # Lookup videos for this small step
                results = lookup_videos_for_step(
                    recommendations_df,
                    year=result_dict.get('year'),
                    term=result_dict.get('term'),
                    difficulty=result_dict.get('difficulty', ''),
                    topic=result_dict.get('topic'),
                    small_step=result_dict.get('small_step_name'),
                    small_step_id=result_dict.get('small_step_id', ''),
                )
                
                st.session_state.display_results = results
                st.session_state.display_status = 'complete'
                st.rerun()
'''

print(CODE_SNIPPET)


# ============================================================================
# STEP 3: Requirements (no additional packages needed)
# ============================================================================

# The flipper_search module uses:
#   - scikit-learn (TfidfVectorizer) - already in requirements.txt
#   - numpy - already in requirements.txt
#   - streamlit - already in requirements.txt
#   - pandas - already in requirements.txt
#   - openai - already in requirements.txt (for QueryEmbedder)
#
# No additional dependencies required!


# ============================================================================
# STEP 4: Test the integration
# ============================================================================

# 1. Ensure embeddings are built:
#    ls data/curriculum_embeddings.npy
#
# 2. Start flipper_lite:
#    streamlit run flipper_lite.py
#
# 3. Look for the "Search by Topic Description" expander above the dropdown
#
# 4. Try searching:
#    - "adding fractions"
#    - "gradient"
#    - "collecting like terms"
#
# 5. Click a result to see videos


# ============================================================================
# OPTIONAL: Fine-tuning
# ============================================================================

# A. Lexical-only (no API cost, slightly lower quality):
#    search_result = render_search_ui(
#        curriculum_csv_path=str(curriculum_path),
#        use_semantic=False,  # Disable semantic reranking
#    )

# B. Show more results:
#    In search_engine.py, change top_k in the search() call:
#    results = engine.search(query, top_k=15)  # Default is 10

# C. Faster hybrid (trade semantic quality for speed):
#    In streamlit_ui.py, reduce lexical_candidates_k:
#    results = engine.search(query, top_k=top_k, lexical_candidates_k=20)


# ============================================================================
# TROUBLESHOOTING
# ============================================================================

# "ModuleNotFoundError: No module named 'flipper_search'"
#   → Make sure flipper_search/ folder is in project root with __init__.py

# "OpenAI API key not found"
#   → Check .env file has OPENAI_API_KEY set
#   → Or use use_semantic=False for lexical-only search

# "Embeddings file not found"
#   → Run: python -m flipper_search.build_index
#   → Or use use_semantic=False

# Search is slow (>1 second)
#   → Normal for hybrid mode (1-2 seconds for embedding API call)
#   → Use use_semantic=False for ~50ms latency

# No results found
#   → Try different keywords or simpler queries
#   → Check curriculum CSV is loading (test_search.py can help debug)


# ============================================================================
# File Structure After Integration
# ============================================================================

"""
flipper16012026/
├── flipper_lite.py                           (modified: add search UI)
├── Curriculum/
│   └── Maths/
│       └── curriculum_08052026_small_steps.csv
├── data/
│   ├── curriculum_embeddings.npy             (created by build_index.py)
│   └── curriculum_embeddings.json            (created by build_index.py)
├── flipper_search/                           (NEW)
│   ├── __init__.py
│   ├── curriculum_index.py
│   ├── epoch_definitions.py
│   ├── search_engine.py
│   ├── build_index.py
│   ├── streamlit_ui.py
│   ├── test_search.py
│   ├── PROJECT_SCOPE.md
│   ├── QUICKSTART.md
│   └── INTEGRATION.md                        (this file)
├── requirements.txt                          (no changes needed)
└── ...
"""
