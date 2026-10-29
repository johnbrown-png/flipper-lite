"""
Flipper Tier 1 - Mobile-Optimized Version

Key mobile UX improvements:
- Single column layout on mobile
- Selectboxes instead of popovers
- Larger touch targets
- Simplified video cards
- Responsive design
"""

import streamlit as st
import pandas as pd
from pathlib import Path


# Configure page for mobile
st.set_page_config(
    page_title="Flipper Curriculum Guide",
    page_icon="📚",
    layout="wide",  # Will be constrained by CSS for mobile
    initial_sidebar_state="collapsed"
)

# Mobile-optimized CSS
st.markdown("""
<style>
    /* Increase touch target sizes for mobile */
    .stButton > button {
        min-height: 50px;
        font-size: 16px;
        padding: 12px 24px;
        margin: 8px 0;
    }
    
    /* Make selectboxes mobile-friendly */
    .stSelectbox > div > div {
        min-height: 50px;
        font-size: 16px;
    }
    
    /* Ensure video cards stack nicely */
    .video-card {
        margin-bottom: 20px;
        padding: 15px;
        border-radius: 10px;
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
    }
    
    /* Responsive images */
    img {
        max-width: 100%;
        height: auto;
    }
    
    /* Larger metric cards for touch */
    .metric-card {
        padding: 10px;
        text-align: center;
    }
    
    /* Prevent horizontal scroll on mobile */
    .main .block-container {
        max-width: 100%;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    
    /* Responsive columns - stack on mobile */
    @media (max-width: 768px) {
        .stColumns {
            flex-direction: column;
        }
        .stColumn {
            width: 100% !important;
        }
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_precomputed_recommendations():
    """Load pre-computed recommendations CSV"""
    csv_path = Path('precomputed_recommendations.csv')
    if not csv_path.exists():
        return None
    return pd.read_csv(csv_path)


def render_mobile_curriculum_selector(df):
    """
    Mobile-optimized curriculum selector using native dropdowns
    instead of popovers for better mobile UX
    """
    
    # Initialize session state
    if 'tier1_year' not in st.session_state:
        years = sorted(df['year'].unique())
        st.session_state.tier1_year = years[0]
    if 'tier1_term' not in st.session_state:
        year_df = df[df['year'] == st.session_state.tier1_year]
        terms = list(year_df['term'].unique())
        st.session_state.tier1_term = terms[0]
    if 'tier1_topic' not in st.session_state:
        year_df = df[df['year'] == st.session_state.tier1_year]
        term_df = year_df[year_df['term'] == st.session_state.tier1_term]
        topics = list(term_df['topic'].unique())
        st.session_state.tier1_topic = topics[0]
    
    st.markdown("### 🎯 Find Learning Resources")
    
    # Use SELECTBOX instead of popovers - much better for mobile
    # These are native HTML elements that work great on all devices
    
    # Filter 1: Year Group
    years = sorted(df['year'].unique())
    year_index = years.index(st.session_state.tier1_year) if st.session_state.tier1_year in years else 0
    
    selected_year = st.selectbox(
        "📚 Year Group",
        options=years,
        index=year_index,
        key="year_selector"
    )
    
    # Update if changed
    if selected_year != st.session_state.tier1_year:
        st.session_state.tier1_year = selected_year
        year_df = df[df['year'] == selected_year]
        terms = list(year_df['term'].unique())
        st.session_state.tier1_term = terms[0]
        term_df = year_df[year_df['term'] == terms[0]]
        topics = list(term_df['topic'].unique())
        st.session_state.tier1_topic = topics[0]
        st.rerun()
    
    # Filter 2: Term
    year_df = df[df['year'] == st.session_state.tier1_year]
    terms = list(year_df['term'].unique())
    term_index = terms.index(st.session_state.tier1_term) if st.session_state.tier1_term in terms else 0
    
    selected_term = st.selectbox(
        "📅 Term",
        options=terms,
        index=term_index,
        key="term_selector"
    )
    
    if selected_term != st.session_state.tier1_term:
        st.session_state.tier1_term = selected_term
        term_df = year_df[year_df['term'] == selected_term]
        topics = list(term_df['topic'].unique())
        st.session_state.tier1_topic = topics[0]
        st.rerun()
    
    # Filter 3: Topic
    term_df = year_df[year_df['term'] == st.session_state.tier1_term]
    topics = list(term_df['topic'].unique())
    topic_index = topics.index(st.session_state.tier1_topic) if st.session_state.tier1_topic in topics else 0
    
    selected_topic = st.selectbox(
        "📖 Topic",
        options=topics,
        index=topic_index,
        key="topic_selector"
    )
    
    if selected_topic != st.session_state.tier1_topic:
        st.session_state.tier1_topic = selected_topic
        st.rerun()
    
    # Filter to selected items
    selected_df = df[
        (df['year'] == st.session_state.tier1_year) &
        (df['term'] == st.session_state.tier1_term) &
        (df['topic'] == st.session_state.tier1_topic)
    ]
    
    # Small step selector - use radio buttons for better mobile UX
    if not selected_df.empty:
        st.markdown("---")
        st.markdown("#### 📝 Choose Learning Objective")
        
        small_steps = selected_df['small_step'].tolist()
        
        if 'tier1_selected_step_idx' not in st.session_state:
            st.session_state.tier1_selected_step_idx = 0
        
        # Use radio buttons - native, mobile-friendly
        selected_step = st.radio(
            "Select a small step:",
            options=small_steps,
            index=st.session_state.tier1_selected_step_idx,
            key="step_selector",
            label_visibility="collapsed"
        )
        
        new_idx = small_steps.index(selected_step)
        if new_idx != st.session_state.tier1_selected_step_idx:
            st.session_state.tier1_selected_step_idx = new_idx
            st.rerun()
        
        return selected_df.iloc[st.session_state.tier1_selected_step_idx]
    
    return None


def parse_pipe_separated(value):
    """Parse pipe-separated string into list"""
    if pd.isna(value) or value == '':
        return []
    return str(value).split('|')


def render_mobile_video_card(video_id, title, semantic_score, instruction_score, combined_score):
    """
    Mobile-optimized video card - single column layout
    """
    
    # YouTube links
    thumbnail_url = f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    # Use custom HTML for better mobile control
    st.markdown(f"""
    <div class="video-card">
        <a href="{video_url}" target="_blank" style="text-decoration: none; color: inherit;">
            <img src="{thumbnail_url}" style="width: 100%; border-radius: 8px; margin-bottom: 10px;">
            <h4 style="margin: 10px 0; color: #1f77b4;">{title}</h4>
        </a>
    </div>
    """, unsafe_allow_html=True)
    
    # Score metrics in a row
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Match", 
            f"{float(semantic_score)*100:.0f}%",
            help="Semantic similarity"
        )
    with col2:
        st.metric(
            "Quality", 
            f"{float(instruction_score):.0f}",
            help="Instruction quality (0-100)"
        )
    with col3:
        st.metric(
            "Overall", 
            f"{float(combined_score)*100:.0f}%",
            help="Combined score"
        )
    
    # Large "Watch Video" button
    if st.button(
        "▶️ Watch on YouTube",
        key=f"watch_{video_id}",
        use_container_width=True,
        type="primary"
    ):
        st.markdown(f'<meta http-equiv="refresh" content="0;url={video_url}">', unsafe_allow_html=True)
    
    st.markdown("---")


def main():
    """Main application"""
    
    # Compact header for mobile
    st.title("📚 Flipper")
    st.caption("Curriculum-aligned video recommendations for maths teaching")
    
    # Load data
    df = load_precomputed_recommendations()
    
    if df is None:
        st.error("⚠️ Precomputed recommendations not found.")
        st.info("""
        Run this first:
        ```bash
        python precompute_curriculum_recommendations.py
        ```
        """)
        return
    
    # Show data stats
    with st.expander("ℹ️ About this tool"):
        st.markdown(f"""
        **Loaded:** {len(df)} curriculum items with expert-curated video recommendations.
        
        **How it works:**
        1. Select your year group, term, and topic
        2. Choose a specific learning objective
        3. View top-rated videos matched to that objective
        
        All videos have been pre-filtered using AI for relevance and instructional quality.
        """)
    
    st.markdown("---")
    
    # Render mobile-optimized curriculum selector
    selected_item = render_mobile_curriculum_selector(df)
    
    if selected_item is None:
        st.info("👆 Select curriculum filters above to see video recommendations")
        return
    
    # Display selected curriculum item in a compact format
    st.markdown("---")
    st.success(f"""
**Selected:** {selected_item['year']} → {selected_item['term'].split('(')[0].strip()} → {selected_item['topic']}  
**Learning Objective:** {selected_item['small_step']}
    """)
    
    # Parse recommendations
    video_ids = parse_pipe_separated(selected_item['video_ids'])
    titles = parse_pipe_separated(selected_item['video_titles'])
    semantic_scores = parse_pipe_separated(selected_item['semantic_scores'])
    instruction_scores = parse_pipe_separated(selected_item['instruction_quality_scores'])
    combined_scores = parse_pipe_separated(selected_item['combined_scores'])
    
    if not video_ids:
        st.warning("No video recommendations available for this curriculum item.")
        return
    
    # Display recommendations
    st.markdown("---")
    st.markdown(f"### 🎬 Top {len(video_ids)} Videos")
    st.caption("Tap any video to watch on YouTube")
    st.markdown("")
    
    for i, (video_id, title, sem_score, inst_score, comb_score) in enumerate(zip(
        video_ids, titles, semantic_scores, instruction_scores, combined_scores
    ), 1):
        st.markdown(f"**#{i}**")
        render_mobile_video_card(video_id, title, sem_score, inst_score, comb_score)
    
    # Footer
    st.markdown("---")
    st.caption("Powered by AI-curated content • Tier 1: Lightweight Guide")


if __name__ == "__main__":
    main()
