"""
Streamlit UI components for flipper_search integration with flipper_lite.

Provides:
  - Epoch selector (dropdown)
  - Natural language search input
  - Search results display with ss_desc preview
  - Result selection trigger
"""

import streamlit as st
from pathlib import Path
from typing import Optional, Tuple

from .curriculum_index import CurriculumIndex
from .search_engine import SearchEngine
from .epoch_definitions import EPOCHS, get_epoch_display_name


def initialize_search_engine(
    curriculum_csv_path: str,
    embeddings_path: Optional[str] = None,
    use_semantic: bool = True,
):
    """
    Initialize search engine (cached for session).
    
    Args:
        curriculum_csv_path: Path to curriculum CSV
        embeddings_path: Path to precomputed embeddings
        use_semantic: Whether to use semantic reranking
    
    Returns:
        SearchEngine instance
    """
    @st.cache_resource
    def _init():
        index = CurriculumIndex(curriculum_csv_path)
        engine = SearchEngine(
            index,
            embeddings_path=embeddings_path,
            use_semantic=use_semantic,
        )
        return engine
    
    return _init()


def render_search_ui(
    curriculum_csv_path: str,
    embeddings_path: Optional[str] = None,
    use_semantic: bool = True,
) -> Optional[Tuple[str, dict]]:
    """
    Render the search UI for flipper_lite.
    
    Returns:
        Tuple of (action, result_dict) if user selects a result, else None
        - action: 'small_step_search'
        - result_dict: Full curriculum data for selected small step
    """
    
    # Initialize engine
    engine = initialize_search_engine(
        curriculum_csv_path,
        embeddings_path=embeddings_path,
        use_semantic=use_semantic,
    )
    
    # Session state for search
    if 'flipper_search_query' not in st.session_state:
        st.session_state.flipper_search_query = ''
    if 'flipper_search_results' not in st.session_state:
        st.session_state.flipper_search_results = []
    if 'flipper_search_pending' not in st.session_state:
        st.session_state.flipper_search_pending = None
    
    # Check for pending selection
    if st.session_state.flipper_search_pending:
        result = st.session_state.flipper_search_pending
        st.session_state.flipper_search_pending = None
        return 'small_step_search', result
    
    # UI Header
    st.markdown("### 🔍 Search by Topic")
    
    # Epoch selector
    epoch_names = ['All'] + list(EPOCHS.keys())
    epoch_displays = ['All'] + [get_epoch_display_name(e) for e in EPOCHS.keys()]
    
    col_epoch, col_spacer = st.columns([3, 1])
    with col_epoch:
        selected_epoch_idx = st.selectbox(
            "Schooling Epoch (optional filter):",
            range(len(epoch_displays)),
            format_func=lambda i: epoch_displays[i],
            key='flipper_search_epoch',
            label_visibility='collapsed'
        )
        selected_epoch = epoch_names[selected_epoch_idx] if selected_epoch_idx < len(epoch_names) else 'All'
    
    # Search input
    st.markdown("**Describe what you need help with:**")
    search_query = st.text_input(
        "e.g., 'adding fractions with different denominators', 'gradient of a straight line'",
        key='flipper_search_input',
        label_visibility='collapsed',
        placeholder="Type your question or topic...",
    )
    
    # Search button
    col_btn, col_status = st.columns([1, 3])
    with col_btn:
        search_clicked = st.button("🔍 Search", key='flipper_search_btn', use_container_width=True)
    
    # Execute search
    if search_clicked and search_query.strip():
        with st.spinner("Searching curriculum..."):
            results = engine.search(search_query, top_k=10)
            st.session_state.flipper_search_results = results
            st.session_state.flipper_search_query = search_query
    
    # Display results
    if st.session_state.flipper_search_results:
        st.markdown("---")
        st.markdown(f"**Found {len(st.session_state.flipper_search_results)} results:**")
        
        for idx, result in enumerate(st.session_state.flipper_search_results):
            # Result card
            col_select, col_content = st.columns([0.8, 4])
            
            with col_select:
                # Select button
                if st.button(
                    "→ Select",
                    key=f'flipper_search_select_{idx}',
                    use_container_width=True,
                ):
                    st.session_state.flipper_search_pending = result
                    st.rerun()
            
            with col_content:
                # Result title and metadata
                title = result.get('small_step_name', 'Untitled')
                topic = result.get('topic', '')
                year = result.get('year', '')
                
                title_text = f"**{title}**"
                if topic:
                    title_text += f" — {topic}"
                st.markdown(title_text)
                
                # Metadata
                metadata_parts = []
                if year:
                    metadata_parts.append(year)
                if result.get('age'):
                    metadata_parts.append(f"Age {result['age']}")
                if result.get('difficulty'):
                    metadata_parts.append(f"({result['difficulty']})")
                
                if metadata_parts:
                    st.caption(" | ".join(metadata_parts))
                
                # ss_desc preview
                ss_desc = result.get('ss_desc', '')
                if ss_desc:
                    st.markdown(f"<div style='font-size:0.9rem; color:#555; padding:0.5rem; background:#f0f5f9; border-left:3px solid #4a90c8; border-radius:4px; margin-top:0.3rem;'>{ss_desc}</div>", unsafe_allow_html=True)
                
                # Match scores
                score_parts = []
                if 'lexical_score' in result:
                    score_parts.append(f"Lexical: {result['lexical_score']:.1%}")
                if 'semantic_score' in result:
                    score_parts.append(f"Semantic: {result['semantic_score']:.1%}")
                if 'combined_score' in result:
                    score_parts.append(f"**Match: {result['combined_score']:.1%}**")
                
                if score_parts:
                    st.caption(" | ".join(score_parts))
            
            st.markdown("---")
    
    elif st.session_state.flipper_search_query and not st.session_state.flipper_search_results:
        st.warning("No results found. Try different search terms.")
    
    return None


def render_search_ui_compact(
    curriculum_csv_path: str,
    embeddings_path: Optional[str] = None,
    use_semantic: bool = True,
) -> Optional[Tuple[str, dict]]:
    """
    Compact version of search UI (simpler layout for sidebar or embed).
    
    Returns:
        Same as render_search_ui
    """
    # Initialize engine
    engine = initialize_search_engine(
        curriculum_csv_path,
        embeddings_path=embeddings_path,
        use_semantic=use_semantic,
    )
    
    # Session state
    if 'flipper_search_compact_query' not in st.session_state:
        st.session_state.flipper_search_compact_query = ''
    if 'flipper_search_compact_results' not in st.session_state:
        st.session_state.flipper_search_compact_results = []
    if 'flipper_search_compact_pending' not in st.session_state:
        st.session_state.flipper_search_compact_pending = None
    
    # Check pending
    if st.session_state.flipper_search_compact_pending:
        result = st.session_state.flipper_search_compact_pending
        st.session_state.flipper_search_compact_pending = None
        return 'small_step_search', result
    
    # Simple search input
    search_query = st.text_input(
        "Search topics:",
        key='flipper_search_compact_input',
        placeholder="e.g., adding fractions",
    )
    
    # Search
    if search_query and len(search_query) > 3:
        results = engine.search(search_query, top_k=5)
        st.session_state.flipper_search_compact_results = results
    
    # Display compact results
    if st.session_state.flipper_search_compact_results:
        for result in st.session_state.flipper_search_compact_results:
            if st.button(
                f"{result.get('small_step_name', 'Untitled')} ({result.get('topic', '')})",
                key=f"compact_select_{result.get('small_step_id')}",
                use_container_width=True,
            ):
                st.session_state.flipper_search_compact_pending = result
                st.rerun()
    
    return None
