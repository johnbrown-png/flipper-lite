"""
Flipper Tier 1 - Ultra-Lightweight Curriculum Video Recommendations

No FAISS, no LLM, no runtime AI - just instant CSV lookup of pre-computed recommendations.
Perfect for mobile apps, websites, and low-bandwidth environments.
"""

import streamlit as st
import pandas as pd
from pathlib import Path


# Configure page
st.set_page_config(
    page_title="Flipper - Curriculum Video Guide",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="collapsed"
)


@st.cache_data
def load_precomputed_recommendations():
    """Load pre-computed recommendations CSV"""
    csv_path = Path('precomputed_recommendations.csv')
    if not csv_path.exists():
        return None
    return pd.read_csv(csv_path)


def render_curriculum_selector(df):
    """Render curriculum filter UI and return selected item"""
    
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
    
    # Create column layout
    year_col, term_col, topic_col = st.columns([1, 1, 1])
    
    with year_col:
        years = sorted(df['year'].unique())
        with st.popover(f"📚 {st.session_state.tier1_year}", use_container_width=True):
            st.markdown("**Select Year Group:**")
            for year in years:
                # Convert to string and handle NaN/None
                year_label = str(year) if pd.notna(year) else "Unknown Year"
                if st.button(
                    year_label, 
                    key=f"tier1_year_{year}",
                    use_container_width=True,
                    type="primary" if year == st.session_state.tier1_year else "secondary"
                ):
                    st.session_state.tier1_year = year
                    year_df = df[df['year'] == year]
                    terms = list(year_df['term'].unique())
                    st.session_state.tier1_term = terms[0]
                    term_df = year_df[year_df['term'] == terms[0]]
                    topics = list(term_df['topic'].unique())
                    st.session_state.tier1_topic = topics[0]
                    st.rerun()
    
    year_df = df[df['year'] == st.session_state.tier1_year]
    
    with term_col:
        terms = list(year_df['term'].unique())
        term_display = st.session_state.tier1_term.split('(')[0].strip() if pd.notna(st.session_state.tier1_term) else "Unknown"
        with st.popover(f"📅 {term_display}", use_container_width=True):
            st.markdown("**Select Term:**")
            for term in terms:
                # Convert to string and handle NaN/None
                term_label = str(term) if pd.notna(term) else "Unknown Term"
                if st.button(
                    term_label,
                    key=f"tier1_term_{term}",
                    use_container_width=True,
                    type="primary" if term == st.session_state.tier1_term else "secondary"
                ):
                    st.session_state.tier1_term = term
                    term_df = year_df[year_df['term'] == term]
                    topics = list(term_df['topic'].unique())
                    st.session_state.tier1_topic = topics[0]
                    st.rerun()
    
    term_df = year_df[year_df['term'] == st.session_state.tier1_term]
    
    with topic_col:
        topics = list(term_df['topic'].unique())
        with st.popover(f"📖 {st.session_state.tier1_topic}", use_container_width=True):
            st.markdown("**Select Topic:**")
            for topic in topics:
                # Convert to string and handle NaN/None
                topic_label = str(topic) if pd.notna(topic) else "Unknown Topic"
                if st.button(
                    topic_label,
                    key=f"tier1_topic_{topic}",
                    use_container_width=True,
                    type="primary" if topic == st.session_state.tier1_topic else "secondary"
                ):
                    st.session_state.tier1_topic = topic
                    st.rerun()
    
    # Filter to selected item
    selected_df = df[
        (df['year'] == st.session_state.tier1_year) &
        (df['term'] == st.session_state.tier1_term) &
        (df['topic'] == st.session_state.tier1_topic)
    ]
    
    # Small step selector
    if not selected_df.empty:
        st.markdown("### 📝 Select Learning Objective")
        small_steps = selected_df['small_step'].tolist()
        
        if 'tier1_selected_step_idx' not in st.session_state:
            st.session_state.tier1_selected_step_idx = 0
        
        for idx, step in enumerate(small_steps):
            # Convert to string and handle None/NaN values
            step_label = str(step) if pd.notna(step) and step else f"Step {idx + 1}"
            
            if st.button(
                step_label,
                key=f"tier1_step_{idx}",
                use_container_width=True,
                type="primary" if idx == st.session_state.tier1_selected_step_idx else "secondary"
            ):
                st.session_state.tier1_selected_step_idx = idx
                st.rerun()
        
        return selected_df.iloc[st.session_state.tier1_selected_step_idx]
    
    return None


def parse_pipe_separated(value):
    """Parse pipe-separated string into list"""
    if pd.isna(value) or value == '':
        return []
    return str(value).split('|')


def render_video_card(video_id, title, semantic_score, instruction_score, combined_score):
    """Render a single video recommendation card"""
    
    # YouTube thumbnail and link
    thumbnail_url = f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    with st.container():
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.image(thumbnail_url, use_container_width=True)
        
        with col2:
            st.markdown(f"**[{title}]({video_url})**")
            
            # Score badges
            score_col1, score_col2, score_col3 = st.columns(3)
            with score_col1:
                st.metric("Match", f"{float(semantic_score)*100:.0f}%", help="Semantic similarity to topic")
            with score_col2:
                st.metric("Quality", f"{float(instruction_score):.0f}/100", help="Instruction quality score")
            with score_col3:
                st.metric("Overall", f"{float(combined_score)*100:.0f}%", help="Combined recommendation score")
        
        st.markdown("---")


def main():
    """Main application"""
    
    # Header
    st.title("📚 Flipper - Curriculum Video Guide")
    st.markdown("*Expert-curated video recommendations for every maths learning objective*")
    
    # Load data
    df = load_precomputed_recommendations()
    
    if df is None:
        st.error("⚠️ Precomputed recommendations not found. Please run precompute_curriculum_recommendations.py first.")
        st.info("""
        To generate recommendations:
        ```bash
        python precompute_curriculum_recommendations.py --curriculum "path/to/curriculum.csv"
        ```
        """)
        return
    
    st.success(f"✅ Loaded {len(df)} curriculum items with pre-computed video recommendations")
    
    # Render curriculum selector
    st.markdown("---")
    selected_item = render_curriculum_selector(df)
    
    if selected_item is None:
        st.info("👆 Select a curriculum item above to see video recommendations")
        return
    
    # Display selected curriculum item
    st.markdown("---")
    st.markdown("### 🎯 Selected Learning Objective")
    st.info(f"""
    **Year:** {selected_item['year']}  
    **Term:** {selected_item['term']}  
    **Topic:** {selected_item['topic']}  
    **Small Step:** {selected_item['small_step']}
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
    st.markdown("### 🎬 Recommended Videos")
    st.markdown(f"*{len(video_ids)} expert-selected videos ranked by relevance and quality*")
    st.markdown("")
    
    for video_id, title, sem_score, inst_score, comb_score in zip(
        video_ids, titles, semantic_scores, instruction_scores, combined_scores
    ):
        render_video_card(video_id, title, sem_score, inst_score, comb_score)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: gray; font-size: 0.9em;'>
    <p>Powered by AI-curated content • No runtime AI processing required</p>
    <p>Tier 1: Lightweight Curriculum Guide</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
