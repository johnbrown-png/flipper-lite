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
    if 'flipper_search_submitted' not in st.session_state:
        st.session_state.flipper_search_submitted = False
    
    # Check for pending selection
    if st.session_state.flipper_search_pending:
        result = st.session_state.flipper_search_pending
        st.session_state.flipper_search_pending = None
        return 'small_step_search', result
    
    # UI Header
    st.markdown(
        """
        <p style="
            font-family: 'Poppins', sans-serif;
            font-size: 1.2rem;
            color: #2c5f8d;
            text-align: left;
            margin-top: 0.5rem;
            margin-bottom: 0.5rem;
            font-weight: 400;
        ">
            or...search for a maths topic
        </p>
        """,
        unsafe_allow_html=True,
    )
    
    # --- Epoch selector mothballed: keep for future re-enable ---
    # ENABLE_EPOCH_FILTER = False  # set True to restore epoch dropdown
    # epoch_names = ['All'] + list(EPOCHS.keys())
    # epoch_displays = ['All'] + [get_epoch_display_name(e) for e in EPOCHS.keys()]
    # col_epoch, col_spacer = st.columns([3, 1])
    # with col_epoch:
    #     selected_epoch_idx = st.selectbox(
    #         "Schooling Epoch (optional filter):",
    #         range(len(epoch_displays)),
    #         format_func=lambda i: epoch_displays[i],
    #         key='flipper_search_epoch',
    #         label_visibility='collapsed'
    #     )
    #     selected_epoch = epoch_names[selected_epoch_idx] if selected_epoch_idx < len(epoch_names) else 'All'
    selected_epoch = 'All'  # epoch filter disabled; always search all epochs
    
    # Search input
    def _submit_search() -> None:
        st.session_state.flipper_search_submitted = True

    search_query = st.text_input(
        "Search",
        key='flipper_search_input',
        label_visibility='collapsed',
        placeholder="e.g. 'adding fractions', 'gradient of a straight line'...",
        on_change=_submit_search,
    )

    # Execute search when the user presses Enter in the text box.
    if st.session_state.get('flipper_search_submitted') and search_query.strip():
        with st.spinner("Searching curriculum..."):
            results = engine.search(search_query, top_k=5)
            st.session_state.flipper_search_results = results
            st.session_state.flipper_search_query = search_query
    
    if st.session_state.get('flipper_search_submitted'):
        st.session_state.flipper_search_submitted = False
    
    # Display results
    if st.session_state.flipper_search_results:
        st.markdown("---")
        st.markdown(
            """
            <style>
            div[data-testid="stButton"] > button {
                min-height: 1.5rem;
                height: 1.5rem;
                padding: 0.05rem 0.5rem;
                font-size: 0.74rem;
                line-height: 1.0;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        display_results = st.session_state.flipper_search_results[:5]
        
        for idx, result in enumerate(display_results):
            # Result card
            col_select, col_content = st.columns([0.28, 4.72])
            
            with col_select:
                # Select button
                if st.button(
                    "Go!",
                    key=f'flipper_search_select_{idx}',
                    use_container_width=False,
                ):
                    st.session_state.flipper_search_pending = result
                    st.rerun()
            
            with col_content:
                # Result title and metadata
                title = result.get('small_step_name', 'Untitled')
                topic = result.get('topic', '')
                year = result.get('year', '')
                
                title_text = f"<strong>{title}</strong>"
                if topic:
                    title_text += f" — {topic}"
                st.markdown(
                    f"<div style='margin:0 0 0.04rem 0; padding:0; line-height:1.1; font-size:0.94rem;'>{title_text}</div>",
                    unsafe_allow_html=True,
                )
                
                # Metadata
                metadata_parts = []
                if year:
                    metadata_parts.append(year)
                if result.get('age'):
                    metadata_parts.append(f"Age {result['age']}")
                if result.get('difficulty'):
                    metadata_parts.append(f"({result['difficulty']})")
                
                if metadata_parts:
                    st.markdown(
                        f"<div style='margin:0 0 0.06rem 0; padding:0; font-size:0.76rem; color:#627486; line-height:1.06;'>{' | '.join(metadata_parts)}</div>",
                        unsafe_allow_html=True,
                    )
                
                # ss_desc preview
                ss_desc = result.get('ss_desc', '')
                if ss_desc:
                    st.markdown(
                        f"<div style='font-size:0.84rem; color:#4f5f6f; padding:0.22rem 0.34rem; background:#f0f5f9; border-left:3px solid #4a90c8; border-radius:4px; margin:0.05rem 0 0.06rem 0; line-height:1.16;'>{ss_desc}</div>",
                        unsafe_allow_html=True,
                    )
                
                # Match scores
                score_parts = []
                if 'semantic_score' in result:
                    score_parts.append(f"Semantic: {result['semantic_score']:.1%}")
                if 'combined_score' in result:
                    score_parts.append(f"**Match: {result['combined_score']:.1%}**")
                
                if score_parts:
                    st.markdown(
                        f"<div style='margin:0; padding:0; font-size:0.74rem; color:#5f7082; line-height:1.06;'>{' | '.join(score_parts)}</div>",
                        unsafe_allow_html=True,
                    )
            
            st.markdown("<hr style='margin:0.14rem 0 0.16rem 0; border:0; border-top:1px solid rgba(44,95,141,0.16);'>", unsafe_allow_html=True)
    
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
