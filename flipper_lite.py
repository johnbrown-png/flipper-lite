"""
Flipper Lite - Lightweight Curriculum Video Browser

A simple web interface for teachers to browse precomputed curriculum-aligned
educational videos without runtime semantic search or LLM operations.
"""

import sys
from pathlib import Path

# Add search_app to path for curriculum assistant import
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from search_app.curriculum_assistant import CurriculumAssistant

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

# Configure page
st.set_page_config(
    page_title="Flipper Lite - Video Browser",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Add custom CSS for more compact layout
st.markdown("""
<style>
    /* Hide Streamlit header */
    header[data-testid="stHeader"] {
        display: none;
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


@st.cache_data
def load_precomputed_recommendations():
    """Load precomputed curriculum recommendations CSV"""
    try:
        csv_path = project_root / 'precomputed_recommendations.csv'
        df = pd.read_csv(csv_path)
        return df
    except Exception as e:
        st.error(f"Error loading precomputed recommendations: {e}")
        return None


@st.cache_data
def load_video_inventory():
    """
    DEPRECATED: Channel and duration now included in precomputed_recommendations.csv
    This function exists for backward compatibility but is no longer needed.
    """
    return None


def lookup_videos_for_step(df, year, term, difficulty, topic, small_step):
    """
    Lookup videos from precomputed recommendations
    
    Args:
        df: Precomputed recommendations DataFrame
        year: Year value
        term: Term value
        difficulty: Difficulty level (Foundation/Higher, or empty)
        topic: Topic value
        small_step: Small step value
    
    Returns:
        List of video dictionaries
    """
    try:
        # Normalize difficulty for comparison (handle empty strings and NaN)
        # Convert empty strings to NaN for proper pandas comparison
        lookup_difficulty = difficulty if difficulty else None
        
        # Filter DataFrame for exact match (including difficulty)
        # Handle both empty strings and NaN in difficulty column
        if not difficulty:
            # If difficulty is empty/None, match rows where difficulty is NaN or empty
            mask = (
                (df['year'] == year) & 
                (df['term'] == term) & 
                (df['difficulty'].isna() | (df['difficulty'] == '')) &
                (df['topic'] == topic) & 
                (df['small_step'] == small_step)
            )
        else:
            # If difficulty has a value, match exactly
            mask = (
                (df['year'] == year) & 
                (df['term'] == term) & 
                (df['difficulty'] == difficulty) & 
                (df['topic'] == topic) & 
                (df['small_step'] == small_step)
            )
        matches = df[mask]
        
        if matches.empty:
            return []
        
        # Get first match (should only be one per curriculum item)
        row = matches.iloc[0]
        
        # Parse pipe-separated values
        video_ids = str(row['video_id']).split('|') if pd.notna(row['video_id']) else []
        video_titles = str(row['video_title']).split('|') if pd.notna(row['video_title']) else []
        semantic_scores = str(row['semantic_scores']).split('|') if pd.notna(row['semantic_scores']) else []
        instruction_scores = str(row['instruction_quality_scores']).split('|') if pd.notna(row['instruction_quality_scores']) else []
        combined_scores = str(row['combined_scores']).split('|') if pd.notna(row['combined_scores']) else []
        
        # Parse channel and duration (new columns)
        channels = str(row.get('channel', '')).split('|') if pd.notna(row.get('channel')) else []
        durations = str(row.get('duration_formatted', '')).split('|') if pd.notna(row.get('duration_formatted')) else []
        
        # Build result list (top 3)
        results = []
        for i in range(min(3, len(video_ids))):
            if i < len(video_ids):
                result = {
                    'rank': i + 1,
                    'video_id': video_ids[i],
                    'title': video_titles[i] if i < len(video_titles) else 'Unknown Title',
                    'semantic_score': float(semantic_scores[i]) if i < len(semantic_scores) else 0.0,
                    'instruction_score': float(instruction_scores[i]) if i < len(instruction_scores) else 0.0,
                    'combined_score': float(combined_scores[i]) if i < len(combined_scores) else 0.0,
                    'channel': channels[i] if i < len(channels) else '',
                    'duration': durations[i] if i < len(durations) else ''
                }
                results.append(result)
        
        return results
    
    except Exception as e:
        st.error(f"Lookup error: {e}")
        import traceback
        st.error(traceback.format_exc())
        return []


def format_duration(duration_str):
    """Convert duration to MM:SS format (e.g., 06:45)"""
    try:
        # Handle if already in MM:SS or HH:MM:SS format
        if ':' in str(duration_str):
            parts = str(duration_str).split(':')
            if len(parts) == 2:  # Already MM:SS
                mins, secs = int(parts[0]), int(parts[1])
                return f"{mins:02d}:{secs:02d}"
            elif len(parts) == 3:  # HH:MM:SS format
                hours, mins, secs = int(parts[0]), int(parts[1]), int(parts[2])
                total_mins = hours * 60 + mins
                return f"{total_mins:02d}:{secs:02d}"
        # Handle if in seconds
        total_seconds = int(float(duration_str))
        mins = total_seconds // 60
        secs = total_seconds % 60
        return f"{mins:02d}:{secs:02d}"
    except:
        return str(duration_str)


def render_result_card(result):
    """Render a single video result card"""
    
    # Get video ID, topic, and small_step for tracking
    video_id = result['video_id']
    topic = result.get('topic', '')
    small_step = result.get('small_step', '')

    # Create a unique DOM id for this context
    dom_id = f"video-card-{video_id}-{topic}-{small_step}".replace(' ', '_').replace('"', '').replace("'", '')

    with st.container():
        # Layout: thumbnail on left, content on right
        col_thumb, col_content = st.columns([1, 3])

        with col_thumb:
            # YouTube thumbnail with play link (yout-ube redirects without ads)
            video_url = f"https://www.yout-ube.com/watch?v={video_id}"
            thumbnail_url = f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
            st.markdown(
                f"<div class='video-card' data-video-id='{video_id}' data-topic='{topic}' data-small-step='{small_step}' id='{dom_id}'>"
                f"<a href='{video_url}' target='_blank' class='video-link' data-video-id='{video_id}' data-topic='{topic}' data-small-step='{small_step}'>"
                f"<img src='{thumbnail_url}' style='width:100%; border-radius:8px; cursor:pointer;' />"
                f"</a></div>",
                unsafe_allow_html=True
            )

        with col_content:
            # Video title at the top (larger font)
            st.markdown(f"<div style='font-size:1.1rem; font-weight:600; margin-bottom:0.3rem'>{result['title']}</div>", unsafe_allow_html=True)

            # Channel and duration below title, after a space
            channel = result.get('channel', '')
            duration = result.get('duration', '')
            channel_display = channel.replace('_', ' ') if channel else 'Unknown'
            duration_display = format_duration(duration) if duration else 'N/A'
            st.markdown(f"<div style='font-size:0.95rem; color:#2c5f8d; margin-bottom:0.5rem'>{channel_display} | {duration_display}</div>", unsafe_allow_html=True)

            # Display scores as badges (as before)
            semantic_pct = int(result.get('semantic_score', 0) * 100)
            instruction_pct = int(result.get('instruction_score', 0))
            combined_pct = int(result.get('combined_score', 0) * 100)

            st.caption(f"🔍 Semantic: {semantic_pct}% | 📚 Instruction: {instruction_pct}% | ⭐ Combined: {combined_pct}%")

        st.markdown("---")


def main():
    """Main application"""
    
    # ========== COLOR SCHEME ==========
    # Professional Blue (Trustworthy, Clean, Modern)
    HEADER_GRADIENT = "linear-gradient(to right, #1e3a5f, #2c5f8d, #4a90c8)"
    MAIN_TEXT_COLOR = "#f0f4f8"
    AI_ACCENT_COLOR = "#FFD700"
    
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
            Select the learners age, pick term and topic to play AI curated education videos for each Small Step in the White Rose Maths curriculum
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
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Load precomputed recommendations
    recommendations_df = load_precomputed_recommendations()
    
    if recommendations_df is None:
        st.error("❌ Failed to load precomputed recommendations. Please run `precompute_curriculum_recommendations.py` first.")
        st.stop()
    
    # Note: video_inventory.csv no longer needed - channel & duration now in precomputed_recommendations.csv
    
    # Initialize curriculum assistant
    curriculum_path = project_root / "Curriculum" / "Maths" / "curriculum_22032026.csv"
    curriculum_assistant = None
    if curriculum_path.exists():
        curriculum_assistant = CurriculumAssistant(str(curriculum_path))
    
    # Initialize curriculum assistant expanded state
    if 'curriculum_expanded' not in st.session_state:
        st.session_state.curriculum_expanded = True
    
    # Initialize display status tracking
    if 'display_status' not in st.session_state:
        st.session_state.display_status = 'idle'  # 'idle', 'loading', 'complete'
    if 'display_results' not in st.session_state:
        st.session_state.display_results = []
    if 'display_step_name' not in st.session_state:
        st.session_state.display_step_name = ""
    if 'curriculum_context' not in st.session_state:
        st.session_state.curriculum_context = None
    
    # ==========================================
    # RESULTS SECTION (Always visible above the fold)
    # ==========================================
    st.markdown("---")
    
    if st.session_state.display_status == 'idle':
        # Empty state - no message
        pass
    
    elif st.session_state.display_status == 'loading':
        # Loading state - show spinner
        with st.spinner(""):
            st.empty()
    
    elif st.session_state.display_status == 'complete':
        # Results state - show video cards
        if st.session_state.display_results:
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
                
                if ctx.get('small_step'):
                    breadcrumb_parts.append(f"Small Step: {ctx['small_step']}")
                
                # Display breadcrumb with smaller font and separators
                if breadcrumb_parts:
                    breadcrumb_text = " &nbsp;|&nbsp; ".join(breadcrumb_parts)
                    st.markdown(f"<p style='font-size: 0.9rem; margin-bottom: 1rem;'>{breadcrumb_text}</p>", unsafe_allow_html=True)
            
            for result in st.session_state.display_results:
                render_result_card(result)
        else:
            st.warning("No videos found for this step. Try a different curriculum step.")
    
    # ==========================================
    # CURRICULUM ASSISTANT (Below results)
    # ==========================================
    if curriculum_assistant:
        action, text = curriculum_assistant.render()
        
        if action == 'small_step_search' and text:
            # Handle small step selection with CSV lookup
            st.session_state.display_status = 'loading'
            st.session_state.display_step_name = text.get('small_step', text['display_text'])
            
            # Store curriculum context for breadcrumb display
            st.session_state.curriculum_context = text
            
            # Extract curriculum context
            year = text.get('year')
            term = text.get('term')
            difficulty = text.get('difficulty', '')
            topic = text.get('topic')
            small_step = text.get('small_step')
            
            # Lookup videos from precomputed CSV (includes channel & duration)
            results = lookup_videos_for_step(recommendations_df, year, term, difficulty, topic, small_step)
            
            # Store results and update status
            st.session_state.display_results = results
            st.session_state.display_status = 'complete'
            st.rerun()
    
    # Sidebar with info
    with st.sidebar:
        st.markdown("### 📖 About Flipper Lite")
        st.markdown("""
        Flipper Lite is a lightweight curriculum video browser that helps teachers 
        find relevant educational content aligned to the White Rose Mathematics curriculum.
        
        **How it works:**
        1. Navigate the dropdowns to select your curriculum step
        2. The system instantly displays precomputed video recommendations
        3. Videos are ranked by relevance and instructional quality
        
        **Understanding Scores:**
        - 🔍 **Semantic**: How well video content matches the curriculum step
        - 📚 **Instruction**: Quality of teaching and explanation
        - ⭐ **Combined**: Overall ranking score
        
        **Score Ranges:**
        - 🟢 80-100%: Excellent match
        - 🟡 60-80%: Good match
        - 🟠 40-60%: Fair match
        - 🔴 0-40%: Weak match
        """)
        
        st.markdown("---")
        st.markdown("### ⚙️ Technical Details")
        st.markdown(f"""
        - **Mode:** Precomputed CSV Lookup
        - **Scoring:** Offline (no runtime LLM calls)
        - **Video Count:** {len(recommendations_df)} curriculum items
        - **Top Videos per Step:** 3
        """)
        
        st.markdown("---")
        st.markdown("### 💡 About This Version")
        st.markdown("""
        **Flipper Lite** is optimized for:
        - 🚀 Fast loading (no FAISS index)
        - 📱 Mobile-friendly browsing
        - 💰 Cost-effective (no runtime API calls)
        - 🌐 Low-bandwidth environments
        
        All video recommendations are precomputed offline using semantic search 
        and AI-powered instruction quality scoring.
        """)

    # Watch tracking JavaScript - unique per (video_id, topic, small_step)
    components.html("""
    <script>
    (function() {
        const parentWindow = window.parent;
        const parentDoc = parentWindow.document;

        // Get watched videos from localStorage (array of objects)
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

        // Mark a video as watched for a specific context
        function markVideoWatched(videoId, topic, smallStep) {
            const watched = getWatchedVideos();
            // Check if already present
            const exists = watched.some(v => v.video_id === videoId && v.topic === topic && v.small_step === smallStep);
            if (!exists) {
                watched.push({video_id: videoId, topic: topic, small_step: smallStep});
                saveWatchedVideos(watched);
                console.log('Marked as watched:', videoId, topic, smallStep);
            }
        }

        // Apply watched styling to videos in parent document
        function applyWatchedStyling() {
            const watched = getWatchedVideos();
            // Remove watched class from all video cards first
            const allCards = parentDoc.querySelectorAll('.video-card');
            allCards.forEach(card => card.classList.remove('video-card-watched'));
            // Add watched class only to matching cards
            watched.forEach(entry => {
                const domId = `video-card-${entry.video_id}-${entry.topic}-${entry.small_step}`.replace(/\s/g, '_').replace(/"/g, '').replace(/'/g, '');
                const card = parentDoc.getElementById(domId);
                if (card) {
                    card.classList.add('video-card-watched');
                }
            });
        }

        // Attach click handlers to video links
        function attachClickHandlers() {
            const videoLinks = parentDoc.querySelectorAll('a.video-link[data-video-id]');
            videoLinks.forEach(link => {
                link.removeEventListener('click', handleVideoClick);
                link.addEventListener('click', handleVideoClick);
            });
        }

        function handleVideoClick(event) {
            const videoId = this.getAttribute('data-video-id');
            const topic = this.getAttribute('data-topic') || '';
            const smallStep = this.getAttribute('data-small-step') || '';
            if (videoId) {
                markVideoWatched(videoId, topic, smallStep);
                // Apply styling immediately
                const domId = `video-card-${videoId}-${topic}-${smallStep}`.replace(/\s/g, '_').replace(/"/g, '').replace(/'/g, '');
                const card = parentDoc.getElementById(domId);
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

        console.log('Video watch tracker initialized (context-aware)');
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
