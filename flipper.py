"""
Flipper - Video Search Frontend for Teachers

A simple web interface for teachers to search educational video transcripts
using semantic search powered by FAISS and OpenAI embeddings.
"""

import sys
from pathlib import Path

# Add search_app to path for curriculum assistant import
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from search_app.curriculum_assistant import CurriculumAssistant

import streamlit as st
import streamlit.components.v1 as components
import numpy as np
import faiss
import json
from query_embedder import QueryEmbedder
from data_pipeline.deletion_tracker import DeletionTracker
from shared.analytics import (
    get_analytics_webhook_token,
    get_analytics_webhook_url,
    init_analytics,
    track_event,
)

# Initialize query embedder
_embedder = None
_deletion_tracker = None
FAISS_PRE_AGGREGATION_CHUNKS = 40

def embed_for_search(query: str):
    """Generate embedding for search query"""
    global _embedder
    if _embedder is None:
        _embedder = QueryEmbedder()
    embedding = _embedder.embed_query(query)
    return embedding.reshape(1, -1)


def get_deleted_videos():
    """Get set of deleted video IDs"""
    global _deletion_tracker
    if _deletion_tracker is None:
        _deletion_tracker = DeletionTracker()
    return _deletion_tracker.get_deleted_video_ids()


# Configure page
st.set_page_config(
    page_title="Flipper - Video Search",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Add custom CSS for Age dropdown width (15ch)
st.markdown("""
<style>
div[data-testid="stSelectbox"] label[aria-label="Age"] ~ div:first-child,
div[data-testid="stSelectbox"][aria-label="Age"] > div:first-child {
    width: 15ch !important; min-width: 15ch !important; max-width: 15ch !important;
}
</style>
""", unsafe_allow_html=True)

 # Add custom CSS for more compact layout and Age dropdown width
st.markdown("""
<style>
    /* Hide Streamlit header */
    header[data-testid="stHeader"] {
        display: none;
    }
    /* Set Age dropdown width to 15ch for all selectboxes labeled Age */
    div[data-testid="stSelectbox"] label[aria-label="Age"] ~ div:first-child,
    div[data-testid="stSelectbox"][aria-label="Age"] > div:first-child {
        width: 15ch !important; min-width: 15ch !important; max-width: 15ch !important;
    }
    
    /* Page-wide background - Balanced blue tone */
    .stApp {
        background: 
            linear-gradient(135deg, rgba(30, 58, 95, 0.08) 0%, rgba(74, 144, 200, 0.12) 100%),
            linear-gradient(to bottom, #f0f5f9 0%, #e0ecf4 100%);
        background-attachment: fixed;
    }
    
    /* Top accent bar */
    .stApp::before {
        content: '';
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(to right, #1e3a5f, #2c5f8d, #4a90c8);
        z-index: 9999;
    }
    
    /* Reduce padding around main content */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        background: rgba(255, 255, 255, 0.7);
        border-radius: 12px;
        box-shadow: 0 3px 10px rgba(30, 58, 95, 0.12);
        backdrop-filter: blur(10px);
    }
    
    /* Reduce spacing between elements */
    .element-container {
        margin-bottom: 0.5rem;
    }
    
    /* Make headers more compact */
    h1, h2, h3 {
        margin-top: 0;
        margin-bottom: 0.5rem;
    }
    
    /* Reduce expander padding */
    .streamlit-expanderHeader {
        font-size: 14px;
    }
    
    /* Compact metrics */
    [data-testid="stMetric"] {
        padding: 0;
    }
    
    /* Enhanced loading spinner styling - Blue theme */
    div[data-testid="stSpinner"] > div {
        border: 4px solid #e8f1f7;
        border-top: 4px solid #2c5f8d;
        border-radius: 50%;
        width: 50px;
        height: 50px;
        animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    /* Spinner container styling */
    div[data-testid="stSpinner"] {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 2rem;
        background: rgba(255, 255, 255, 0.95);
        border-radius: 10px;
        box-shadow: 0 4px 12px rgba(30, 58, 95, 0.1);
        margin: 1rem 0;
    }
    
    /* Watch tracking - subtle opacity for watched videos */
    .video-card-watched {
        opacity: 0.65;
        filter: saturate(0.7);
        transition: opacity 0.3s ease, filter 0.3s ease;
    }
    
    .video-card-watched:hover {
        opacity: 0.85;
        filter: saturate(0.85);
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def load_search_index():
    """Load FAISS index and metadata (cached for performance)"""
    try:
        index_path = Path('data/faiss_index/faiss_index.bin')
        metadata_path = Path('data/faiss_index/faiss_index_metadata.json')
        
        index = faiss.read_index(str(index_path))
        with open(metadata_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            metadata = data['metadata']
        
        return index, metadata
    except Exception as e:
        st.error(f"Error loading search index: {e}")
        return None, None





def calculate_cosine_similarity(l2_distance):
    """
    Convert L2 distance to cosine similarity
    
    For normalized vectors (which OpenAI embeddings are):
    cosine_similarity = 1 - (L2_distance^2 / 2)
    
    Args:
        l2_distance: L2 distance from FAISS
    
    Returns:
        Cosine similarity score (0 to 1, where 1 is identical)
    """
    return 1 - (l2_distance ** 2 / 2)


def search_videos(query, index, metadata, k=3):
    """
    Search for videos matching the query
    
    Args:
        query: Search query string
        index: FAISS index
        metadata: Video metadata
        k: Number of results to return
    
    Returns:
        List of result dictionaries
    """
    try:
        # Get deleted video IDs to filter out
        deleted_videos = get_deleted_videos()
        
        # Generate query embedding
        query_vector = embed_for_search(query)
        
        # Search FAISS index
        distances, indices = index.search(query_vector, k)
        
        # Format results with cosine similarity
        results = []
        for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
            if idx == -1:
                continue
            
            # Bounds check - ensure index is within metadata range
            if idx >= len(metadata):
                st.warning(f"Index {idx} out of range (metadata has {len(metadata)} entries). Index may be corrupted. Please rebuild.")
                continue
            
            meta = metadata[idx]
            
            # Skip deleted videos (soft-delete filtering)
            if meta['video_id'] in deleted_videos:
                continue
            
            cosine_sim = calculate_cosine_similarity(dist)
            
            result = {
                'rank': i + 1,
                'cosine_similarity': float(cosine_sim),
                'l2_distance': float(dist),
                'video_id': meta['video_id'],
                'title': meta['title'],
                'channel': meta.get('channel', 'Unknown'),
                'published_at': meta['published_at'],
                'language': meta.get('language', 'en'),
                'duration': meta.get('duration', 0),
                'is_song': meta.get('is_song', False),
                'chunk_index': meta['chunk_index'],
                'token_count': meta['token_count'],
                'start_time': meta.get('start_time', 0),
                'end_time': meta.get('end_time', 0),
                'text': meta['text']
            }
            results.append(result)
        
        return results
    
    except Exception as e:
        st.error(f"Search error: {e}")
        import traceback
        st.error(traceback.format_exc())
        return []


def render_result_card(result):
    """Render a single search result card"""
    # Format duration
    def format_duration(seconds):
        if not seconds:
            return "Unknown"
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"
    
    # Format timestamp
    def format_timestamp(seconds):
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"
    
    # Get video ID for tracking
    video_id = result['video_id']
    
    # Create compact result card with watch tracking
    with st.container():
        # Compact title with badges
        badges = []
        if result.get('is_song'):
            badges.append("🎵")
        if result.get('language', 'en') != 'en':
            badges.append(f"🌍 {result['language'].upper()}")
        
        badge_str = " ".join(badges)
        
        # Layout: thumbnail on left, title and info on right
        col_thumb, col_content = st.columns([1, 3])
        
        with col_thumb:
            # YouTube thumbnail with play link (yout-ube redirects without ads)
            video_url = f"https://www.yout-ube.com/watch?v={video_id}"
            thumbnail_url = f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
            st.markdown(
                f"<div class='video-card' data-video-id='{video_id}' id='video-card-{video_id}'>" 
                f"<a href='{video_url}' target='_blank' class='video-link' data-video-id='{video_id}'>" 
                f"<img src='{thumbnail_url}' style='width:100%; border-radius:8px; cursor:pointer;' />" 
                f"</a></div>",
                unsafe_allow_html=True
            )
        
        with col_content:
            st.markdown(f"**{result['title']}** {badge_str}")
            channel_name = result.get('channel', 'Unknown').replace('_', ' ')
            duration_str = format_duration(result.get('duration', 0))
            st.caption(f"{channel_name} | {duration_str} | Ch.{result['chunk_index']}")
        
        st.markdown("---")


def main():
    """Main application"""

    init_analytics("flipper")
    track_event("page_view", {"page": "home"}, once_key="page_view")
    
    # ========== COLOR SCHEME OPTIONS ==========
    # 
    # SCHEME 1 - Forest Green (Original - Natural, Educational)
    # Background gradient: #1a4d2e, #2d6a4f, #52b788
    # Main text: #e0e0e0 (light gray)
    # AI accent: #FF9533 (orange)
    # 
    # SCHEME 2 - Professional Blue (Current - Trustworthy, Clean, Modern)
    # Background gradient: #1e3a5f, #2c5f8d, #4a90c8
    # Main text: #f0f4f8 (soft white)
    # AI accent: #ffa726 (warm amber)
    #
    # SCHEME 3 - Sophisticated Slate (Alternative - Professional, Elegant)
    # Background gradient: #2c3e50, #34495e, #546e7a
    # Main text: #ecf0f1 (light gray)
    # AI accent: #3498db (bright blue)
    #
    # SCHEME 4 - Deep Teal (Alternative - Modern, Balanced)
    # Background gradient: #0d5c63, #1a7f8e, #2ba3b4
    # Main text: #f5f5f5 (off-white)
    # AI accent: #ff6b6b (coral)
    # ==========================================
    
    # Current Active Scheme: Professional Blue
    HEADER_GRADIENT = "linear-gradient(to right, #1e3a5f, #2c5f8d, #4a90c8)"
    MAIN_TEXT_COLOR = "#f0f4f8"
    AI_ACCENT_COLOR = "#FFD700"

    # --- Sun Rays SVG Overlay for Cheerful Background ---
    # --- Sun Rays SVG Overlay ATTEMPT (commented out due to Streamlit layout limitations) ---
    # st.markdown(
    #     '''<div style="position:fixed;z-index:0;top:0;left:0;width:100vw;height:200vh;pointer-events:none;overflow:hidden;">
    #     <svg width="100%" height="200%" viewBox="0 0 3000 2200" fill="none" xmlns="http://www.w3.org/2000/svg" style="position:absolute;top:0;left:0;">
    #         <defs>
    #             <radialGradient id="sunGradient" cx="-0.3" cy="-0.35" r="0.8">
    #                 <stop offset="0%" stop-color="#fffde7" stop-opacity="0.92"/>
    #                 <stop offset="80%" stop-color="#fffde7" stop-opacity="0.13"/>
    #                 <stop offset="100%" stop-color="#fffde7" stop-opacity="0"/>
    #             </radialGradient>
    #             <linearGradient id="rayGradient" x1="0" y1="0" x2="0" y2="1">
    #                 <stop offset="0%" stop-color="#fff9c4" stop-opacity="0.32"/>
    #                 <stop offset="100%" stop-color="#fff9c4" stop-opacity="0"/>
    #             </linearGradient>
    #         </defs>
    #         <!-- Sun center, even further above and left -->
    #         <circle cx="-800" cy="-700" r="420" fill="url(#sunGradient)"/>
    #         <!-- Rays: more, longer, fanned out -->
    #         <g style="mix-blend-mode:screen;">
    #             <polygon points="-800,-700 3000,0 3000,200" fill="url(#rayGradient)"/>
    #             <polygon points="-800,-700 3000,400 3000,600" fill="url(#rayGradient)"/>
    #             <polygon points="-800,-700 3000,800 3000,1000" fill="url(#rayGradient)"/>
    #             <polygon points="-800,-700 3000,1200 3000,1400" fill="url(#rayGradient)"/>
    #             <polygon points="-800,-700 3000,1600 3000,1800" fill="url(#rayGradient)"/>
    #             <polygon points="-800,-700 3000,2000 3000,2200" fill="url(#rayGradient)"/>
    #             <!-- More rays, including downward and near-vertical -->
    #             <polygon points="-800,-700 1200,2200 1400,2200" fill="url(#rayGradient)"/>
    #             <polygon points="-800,-700 2000,2200 2200,2200" fill="url(#rayGradient)"/>
    #             <polygon points="-800,-700 2800,2200 3000,2200" fill="url(#rayGradient)"/>
    #             <polygon points="-800,-700 0,2200 200,2200" fill="url(#rayGradient)"/>
    #             <polygon points="-800,-700 600,2200 800,2200" fill="url(#rayGradient)"/>
    #             <polygon points="-800,-700 2600,0 2600,2200" fill="url(#rayGradient)"/>
    #             <polygon points="-800,-700 0,1800 0,2200" fill="url(#rayGradient)"/>
    #         </g>
    #     </svg>
    #     </div>''', unsafe_allow_html=True)

    # Custom Styled Header
    col1, col2 = st.columns([0.95, 0.05])
    
    with col1:
        st.markdown(f"""
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
        <div style="
            background: {HEADER_GRADIENT};
            padding: 1.5rem 2rem;
            border-radius: 10px;
            margin-bottom: 0rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            position: relative;
            z-index: 1;
        ">
            <h1 style="
                font-family: 'Poppins', sans-serif;
                font-weight: 550;
                font-size: 2.5rem;
                margin: 0;
                color: #ffffff;
                letter-spacing: -0.5px;
            ">
                <span style="
                    font-size: 3.2rem;
                    font-weight: 600;
                    color: {MAIN_TEXT_COLOR};
                ">
                    Flipper School
                </span>
                <span style="
                    font-size: 1.8rem;
                    font-weight: 600;
                    color: {MAIN_TEXT_COLOR};
                ">
                     - Cur<span style="color: {AI_ACCENT_COLOR};">AI</span>ted Education Videos
                </span>
            </h1>
        </div>
        """, unsafe_allow_html=True)
        
        # Subheading below banner
        st.markdown("""
        <p style="
            font-family: 'Poppins', sans-serif;
            font-size: 1.2rem;
            color: #2c5f8d;
            text-align: center;
            margin-top: 1rem;
            margin-bottom: 0.5rem;
            font-weight: 400;
        ">
            Select the learners age and topic to play AI curated education videos for each Small Step in the White Rose Maths curriculum
        </p>
        """, unsafe_allow_html=True)
    
    with col2:
        with st.popover("ℹ️", use_container_width=True):
            st.markdown("### Flipper School - Cur*AI*ted Education Videos")
            
            st.markdown("#### Our goal:")
            st.markdown("""
            Flipper School aims to support maths learning by making it easier for educators 
            everywhere to find the best instructional videos linked to highly regarded curriculum White Rose 
            based on the UK National Curriculum and Singapore Mastery learning (depth before speed) 
            Concrete → Pictorial → Abstract (CPA) progression. Via videos we aim to provide some context 
            and quick/light introductions to topics to complement other forms of learning.
            """)

            st.markdown("#### Why flipped/ flipped classroom:")
            st.markdown("""
            Flipper School was named after flipped classrooms the idea of reversing the learning of introductory concepts 
            back onto the learner. This frees up instructional time to be more efficient, allowing it to focus on what its best for,
            embedding, exploration, elaboration and mastery.                                  .
            """)
            
            st.markdown("#### How our service works:")
            st.markdown("""
            At Flipper School, experienced education researchers find the best education videos on youtube, 
            selecting those that are safe, most relevant to learning maths and provide the highest 
            instructional quality. We use advanced language processing to match video content to the 
            White Rose Mathematics curriculum. The most relevant videos are shortlisted and then scored 
            for instructional quality using AI, the top three videos are presented.
            """)
            
            st.markdown("#### How it might be used:")
            st.markdown("""
            As the White Rose curriculum is sequential and later topics require mastery of earlier topics 
            we recommend users find the latest topic the learner has mastered then view following videos 
            in order, at the pace that suits other teaching.
            """)
            
            st.markdown("#### Feedback:")
            st.markdown("""
            We are keen to hear any views you have on Flipper Schools to help us improve our contribution 
            to learning. Please contact [John.Brown@flipper.school](mailto:John.Brown@flipper.school)
            """)
            
            st.markdown("#### Contact:")
            st.markdown("""
            FLIPPER EDUCATION LTD Company number: SC882978
            Registered in Scotland, 36-1 Marlborough Street, Midlothian, Edinburgh, EH15 2BG [John.Brown@flipper.school](mailto:John.Brown@flipper.school)
            """)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Load index
    index, metadata = load_search_index()
    
    if index is None or metadata is None:
        st.error("❌ Failed to load search index. Please run `build_faiss_index.py` first.")
        st.stop()
    
    # Initialize curriculum assistant
    curriculum_path = project_root / "Curriculum" / "Maths" / "curriculum_08052026_small_steps.csv"
    curriculum_assistant = None
    if curriculum_path.exists():
        curriculum_assistant = CurriculumAssistant(str(curriculum_path))
    
    # Initialize session state for search query
    if 'search_query' not in st.session_state:
        st.session_state.search_query = ""
    
    # Initialize curriculum assistant expanded state
    if 'curriculum_expanded' not in st.session_state:
        st.session_state.curriculum_expanded = True
    
    # Initialize search status tracking
    if 'search_status' not in st.session_state:
        st.session_state.search_status = 'idle'  # 'idle', 'searching', 'complete'
    if 'search_results' not in st.session_state:
        st.session_state.search_results = []
    if 'search_step_name' not in st.session_state:
        st.session_state.search_step_name = ""
    
    # ==========================================
    # RESULTS SECTION (Always visible above the fold)
    # ==========================================
    st.markdown("---")
    
    if st.session_state.search_status == 'idle':
        # Empty state - no message
        pass
    
    elif st.session_state.search_status == 'searching':
        # Loading state - show spinner with no message
        with st.spinner(""):
            st.empty()  # Placeholder to keep spinner visible
    
    elif st.session_state.search_status == 'complete':
        # Results state - show video cards
        if st.session_state.search_results:
            # Display breadcrumb heading if curriculum context is available
            if 'curriculum_context' in st.session_state and st.session_state.curriculum_context:
                ctx = st.session_state.curriculum_context
                
                # Build breadcrumb with labeled sections
                breadcrumb_parts = []
                
                if ctx.get('age'):
                    breadcrumb_parts.append(f"Age: {ctx['age']}")
                
                if ctx.get('term'):
                    breadcrumb_parts.append(f"Term: {ctx['term']}")
                
                # Add difficulty only if it has a value
                difficulty = ctx.get('difficulty', '').strip()
                if difficulty:
                    breadcrumb_parts.append(f"Difficulty: {difficulty}")
                
                if ctx.get('topic'):
                    breadcrumb_parts.append(f"Topic: {ctx['topic']}")
                
                # Display breadcrumb with smaller font and separators
                if breadcrumb_parts:
                    breadcrumb_text = " &nbsp;|&nbsp; ".join(breadcrumb_parts)
                    st.markdown(f"<p style='font-size: 0.9rem; margin-bottom: 1rem;'>{breadcrumb_text}</p>", unsafe_allow_html=True)
            
            for result in st.session_state.search_results:
                render_result_card(result)
        else:
            st.warning("No videos found for this step. Try a different curriculum step.")
    
    st.markdown("---")
    
    # ==========================================
    # CURRICULUM ASSISTANT (Below results)
    # ==========================================
    if curriculum_assistant:
        action, text = curriculum_assistant.render()
        
        if action == 'small_step_search' and text:
            # Handle small step search with instruction quality scoring
            track_event(
                "step_selection_applied",
                {
                    "source": "curriculum_assistant",
                    "small_step": text.get("small_step", ""),
                    "small_step_id": text.get("small_step_id", ""),
                    "topic": text.get("topic", ""),
                    "age": text.get("age", ""),
                },
            )
            st.session_state.search_mode = 'small_step'
            st.session_state.curriculum_context = text
            st.session_state.search_query = text['display_text']
            st.session_state.search_step_name = text.get('small_step', text['display_text'])
            st.session_state.auto_search = True  # Auto-trigger search
            st.session_state.search_status = 'searching'  # Set searching status
            st.rerun()
    
    # Search interface
    # Compact Search box
    st.text_area(
        "Search Query",
        placeholder="Type freely or use Curriculum Assistant above to search for videos...",
        help="Enter your search query in natural language",
        height=90,
        key="search_query",
        label_visibility="collapsed"
    )
    
    # Read query from session state
    query = st.session_state.search_query
    
    # Clear button callback function (retained for functionality)
    def clear_search():
        st.session_state.search_query = ""
        st.session_state.curriculum_context = None
        st.session_state.search_results = []
        st.session_state.search_status = 'idle'
    
    # Cache refresh callback (retained for functionality)
    def refresh_index_cache():
        st.cache_resource.clear()
        st.toast("🔄 Index cache cleared - reloading...", icon="✅")
    
    # Search and Clear buttons
    col_btn1, col_btn2, col_btn3, col_spacer = st.columns([1, 1, 1, 3])
    with col_btn1:
        search_button = st.button("🔍 Search", type="primary", use_container_width=True)
    with col_btn2:
        st.button("🗑️ Clear", use_container_width=True, on_click=clear_search)
    with col_btn3:
        st.button("🔄 Refresh Index", use_container_width=True, on_click=refresh_index_cache, 
                  help="Reload search index after deletions")
    
    # Perform search (triggered by auto-search flag from Curriculum Assistant)
    auto_search = st.session_state.get('auto_search', False)
    if auto_search:
        st.session_state.auto_search = False  # Reset flag after use
    
    if (search_button or auto_search) and query:
        # If manual search (not auto_search from curriculum), clear old curriculum context
        if search_button and not auto_search:
            st.session_state.curriculum_context = None

        track_event(
            "search_submitted",
            {
                "source": "manual" if search_button and not auto_search else "auto",
                "query_length": len(str(query)),
                "has_curriculum_context": bool(st.session_state.get("curriculum_context")),
                "is_small_step_search": bool(st.session_state.get('search_mode') == 'small_step'),
            },
        )
        
        # Check if this is a small step search requiring instruction quality scoring
        is_small_step_search = st.session_state.get('search_mode') == 'small_step'
        curriculum_context = st.session_state.get('curriculum_context', {})
        
        # Enhanced loading spinner with dynamic message
        spinner_msg = ""
        with st.spinner(spinner_msg):
            # PHASE 1: Semantic search
            # Retrieve chunk hits before grouping/deduplicating to unique videos.
            k_results = FAISS_PRE_AGGREGATION_CHUNKS
            results = search_videos(query, index, metadata, k=k_results)
            
            # Collect chunks per video for ranking calculation
            video_chunks = {}  # {video_id: [list of chunk results]}
            for result in results:
                video_id = result['video_id']
                if video_id not in video_chunks:
                    video_chunks[video_id] = []
                video_chunks[video_id].append(result)
            
            # Calculate ranking score for each video: Median + (chunks >60% × 2%)
            video_stats = {}
            for video_id, chunks in video_chunks.items():
                sims = [c['cosine_similarity'] for c in chunks]
                # Count chunks above quality threshold (0.6 = 60%)
                good_chunks = [c for c in chunks if c['cosine_similarity'] >= 0.6]
                median_sim = sorted(sims)[len(sims)//2]
                ranking_score = median_sim + (len(good_chunks) * 0.02)  # Median + bonus for good chunks
                video_stats[video_id] = {
                    'ranking_score': ranking_score,
                    'median_similarity': median_sim,
                    'good_chunks_count': len(good_chunks)
                }
            
            # Deduplicate by video_id, keeping highest cosine similarity chunk
            seen_videos = {}
            for result in results:
                video_id = result['video_id']
                if video_id not in seen_videos:
                    seen_videos[video_id] = result
                elif result['cosine_similarity'] > seen_videos[video_id]['cosine_similarity']:
                    seen_videos[video_id] = result
            
            # Add ranking_score to each result for ranking
            for video_id, result in seen_videos.items():
                result['ranking_score'] = video_stats[video_id]['ranking_score']
                result['median_similarity'] = video_stats[video_id]['median_similarity']
                result['good_chunks_count'] = video_stats[video_id]['good_chunks_count']
            
            # Convert back to list and sort by ranking_score
            results = sorted(seen_videos.values(), 
                           key=lambda x: x['ranking_score'], 
                           reverse=True)
            
            # PHASE 2: Instruction Quality Scoring (if small step search)
            if is_small_step_search and curriculum_context and len(results) > 0:
                from data_pipeline.instruction_quality_scorer import InstructionQualityScorer
                
                # Initialize scorer
                try:
                    # Show progress for instruction quality scoring
                    progress_placeholder = st.empty()
                    progress_placeholder.info("")
                    
                    scorer = InstructionQualityScorer()
                    
                    # Get top 5 for instruction scoring
                    top_5_results = results[:5]
                    video_ids_to_score = [r['video_id'] for r in top_5_results]
                    
                    # Extract curriculum context
                    age = curriculum_context.get('age', '')
                    topic = curriculum_context.get('topic', '')
                    small_step = curriculum_context.get('small_step', '')
                    small_step_desc = curriculum_context.get('small_step_desc', '')
                    
                    # Run async scoring with parallel execution
                    import asyncio
                    
                    async def score_all_parallel():
                        # Create all tasks at once for parallel execution
                        tasks = [
                            scorer.score_for_curriculum_context_async(
                                video_id=video_id,
                                age=age,
                                topic=topic,
                                small_step=small_step,
                                small_step_desc=small_step_desc,
                                use_cache=True
                            )
                            for video_id in video_ids_to_score
                        ]
                        
                        # Run all tasks in parallel
                        scored = await asyncio.gather(*tasks)
                        return scored
                    
                    # Run async scoring (all 5 calls run simultaneously)
                    instruction_scores = asyncio.run(score_all_parallel())
                    
                    # Map instruction scores to results
                    score_map = {s['video_id']: s for s in instruction_scores if s}
                    
                    # Combine scores (60% semantic, 40% instruction)
                    SEMANTIC_WEIGHT = 0.6
                    INSTRUCTION_WEIGHT = 0.4
                    
                    for result in top_5_results:
                        video_id = result['video_id']
                        if video_id in score_map:
                            inst_data = score_map[video_id]
                            
                            # Store instruction quality data
                            result['instruction_score'] = inst_data.get('score')
                            result['instruction_justification'] = inst_data.get('justification', '')
                            result['instruction_from_cache'] = inst_data.get('from_cache', False)
                            result['instruction_error'] = inst_data.get('error')
                            
                            # Calculate combined score only if instruction score succeeded
                            if result['instruction_score'] is not None:
                                semantic_score = result['cosine_similarity']
                                instruction_score_normalized = result['instruction_score'] / 100.0
                                result['combined_score'] = (semantic_score * SEMANTIC_WEIGHT) + (instruction_score_normalized * INSTRUCTION_WEIGHT)
                            else:
                                # Fallback to semantic only if instruction scoring failed
                                result['combined_score'] = result['cosine_similarity']
                    
                    # Re-sort ONLY the scored videos by combined score
                    # CRITICAL: Don't mix scored videos with unscored videos 6-10
                    # If instruction scores are low, videos 6-10 would rank higher (by semantic alone)
                    scored_videos = [r for r in top_5_results if 'combined_score' in r]
                    results = sorted(scored_videos, key=lambda x: x['combined_score'], reverse=True)
                    
                    # Clear progress message
                    progress_placeholder.empty()
                    
                except Exception as e:
                    st.warning(f"⚠️ Instruction quality scoring failed: {str(e)}\nShowing semantic search results only.")
                    if 'progress_placeholder' in locals():
                        progress_placeholder.empty()
                
                # Clear search mode after one use
                st.session_state.search_mode = None
                # Keep curriculum_context so breadcrumb can be displayed
            
            # Limit to top 3 unique videos (from scored set when using instruction quality)
            results = results[:3]
        
        # Store results in session state and update status
        st.session_state.search_results = results
        st.session_state.search_status = 'complete'
        track_event(
            "search_results_rendered",
            {
                "results_count": len(results),
                "top_video_ids": [r.get("video_id", "") for r in results[:3]],
            },
        )
        st.rerun()  # Rerun to display results in the top section
    
    elif (search_button or auto_search) and not query:
        # No query - keep idle state
        st.session_state.search_status = 'idle'
    
    # Sidebar with info
    with st.sidebar:
        st.markdown("### 📖 About Flipper")
        st.markdown("""
        Flipper helps teachers find relevant educational video content by searching 
        through video transcripts using semantic search.
        
        **How it works:**
        1. Enter your search in natural language
        2. The system converts your query to a vector embedding
        3. FAISS finds the most similar video content
        4. Results show cosine similarity scores
        
        **Understanding Similarity Scores:**
        - 🟢 80-100%: Excellent match
        - 🟡 60-80%: Good match
        - 🟠 40-60%: Fair match
        - 🔴 0-40%: Weak match
        
        **Example Searches:**
        - "How to count to ten"
        - "Christmas songs and celebrations"
        - "Learning multiplication tables"
        - "Counting with friends"
        """)
        
        st.markdown("---")
        st.markdown("### ⚙️ Technical Details")
        st.markdown(f"""
        - **Model:** text-embedding-3-large
        - **Dimensions:** 3072
        - **Index Type:** FAISS L2
        - **Metric:** Cosine Similarity
        """)
        
        st.markdown("---")
        st.markdown("### 🗑️ Cache Management")
        
        if st.button("Clear Instruction Quality Cache", use_container_width=True):
            try:
                from data_pipeline.instruction_quality_scorer import InstructionQualityScorer
                scorer = InstructionQualityScorer()
                scorer.clear_runtime_cache()
                st.success("✅ Instruction quality cache cleared!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Failed to clear cache: {str(e)}")

    # Watch tracking JavaScript - using components.html for reliable execution
    client_webhook_url = get_analytics_webhook_url()
    if get_analytics_webhook_token():
        # Avoid exposing or requiring secret tokens in browser-side events.
        client_webhook_url = ""
    analytics_session_id = st.session_state.get("analytics_session", {}).get("session_id", "")
    components.html(f"""
    <script>
    (function() {
        const parentWindow = window.parent;
        const parentDoc = parentWindow.document;
        const webhookUrl = {json.dumps(client_webhook_url)};
        const sessionId = {json.dumps(analytics_session_id)};

        function trackClientEvent(eventName, properties) {{
            if (!webhookUrl) return;
            const payload = {{
                timestamp_utc: new Date().toISOString(),
                app: 'flipper',
                session_id: sessionId,
                event_name: eventName,
                query: {{}},
                referrer: document.referrer || '',
                user_agent: navigator.userAgent || '',
                properties: properties || {{}}
            }};
            try {{
                const body = JSON.stringify(payload);
                if (navigator.sendBeacon) {{
                    const blob = new Blob([body], {{ type: 'application/json' }});
                    navigator.sendBeacon(webhookUrl, blob);
                }} else {{
                    fetch(webhookUrl, {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body,
                        keepalive: true
                    }});
                }}
            }} catch (e) {{
                console.error('Client analytics failed:', e);
            }}
        }}
        
        // Get watched videos from localStorage
        function getWatchedVideos() {
            try {
                const watched = localStorage.getItem('flipper_watched_videos');
                return watched ? JSON.parse(watched) : [];
            } catch (e) {
                console.error('Error reading watched videos:', e);
                return [];
            }
        }
        
        // Save watched videos to localStorage
        function saveWatchedVideos(videos) {
            try {
                localStorage.setItem('flipper_watched_videos', JSON.stringify(videos));
            } catch (e) {
                console.error('Error saving watched videos:', e);
            }
        }
        
        // Mark a video as watched
        function markVideoWatched(videoId) {
            const watched = getWatchedVideos();
            if (!watched.includes(videoId)) {
                watched.push(videoId);
                saveWatchedVideos(watched);
                console.log('Marked as watched:', videoId);
            }
        }
        
        // Apply watched styling to videos in parent document
        function applyWatchedStyling() {
            const watched = getWatchedVideos();
            console.log('Applying styling to', watched.length, 'watched videos');
            watched.forEach(videoId => {
                const card = parentDoc.getElementById('video-card-' + videoId);
                if (card) {
                    card.classList.add('video-card-watched');
                }
            });
        }
        
        // Attach click handlers to video links
        function attachClickHandlers() {
            const videoLinks = parentDoc.querySelectorAll('a.video-link[data-video-id]');
            videoLinks.forEach(link => {
                // Remove existing listener if any
                link.removeEventListener('click', handleVideoClick);
                // Add new listener
                link.addEventListener('click', handleVideoClick);
            });
        }
        
        function handleVideoClick(event) {
            const videoId = this.getAttribute('data-video-id');
            if (videoId) {
                markVideoWatched(videoId);
                trackClientEvent('video_link_clicked', {{ video_id: videoId, source: 'thumbnail_link' }});
                // Apply styling immediately
                const card = parentDoc.getElementById('video-card-' + videoId);
                if (card) {
                    card.classList.add('video-card-watched');
                }
            }
        }
        
        // Initialize
        function initialize() {
            applyWatchedStyling();
            attachClickHandlers();
        }
        
        // Run initialization
        initialize();
        
        // Re-run periodically to catch Streamlit updates
        setInterval(function() {
            applyWatchedStyling();
            attachClickHandlers();
        }, 500);
        
        // Watch for DOM changes
        const observer = new MutationObserver(function(mutations) {
            let needsUpdate = false;
            mutations.forEach(mutation => {
                mutation.addedNodes.forEach(node => {
                    if (node.nodeType === 1 && 
                        (node.classList?.contains('video-card') || 
                         node.querySelector?.('.video-card'))) {
                        needsUpdate = true;
                    }
                });
            });
            
            if (needsUpdate) {
                setTimeout(initialize, 100);
            }
        });
        
        observer.observe(parentDoc.body, {
            childList: true,
            subtree: true
        });
        
        console.log('Video watch tracker initialized');
    })();
    </script>
    """, height=0)

    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; padding: 1rem; font-size: 0.75rem; color: #666;">
        FLIPPER EDUCATION LTD Company number: SC882978<br>
        Registered in Scotland, 36-1 Marlborough Street, Midlothian, Edinburgh, EH15 2BG<br>
        John.Brown@flipper.school
    </div>
    """, unsafe_allow_html=True)


if __name__ == '__main__':
    main()
