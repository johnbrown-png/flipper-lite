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
import math
import json
import html
from datetime import datetime

from shared.curriculum_schema import normalize_precomputed_df
from shared.analytics import init_analytics, track_event
from shared.step_selection import (
    apply_pending_selector_sync,
    apply_small_step_selection,
    render_selection_debug_panel,
)
from shared.ui_terminology import VIDEO_CARDS_LABEL

# Import thought prompt visual generator
try:
    from thoughtprompt.visual_generator import MathVisualGenerator
    THOUGHT_PROMPTS_ENABLED = True
except ImportError:
    THOUGHT_PROMPTS_ENABLED = False
    MathVisualGenerator = None

# Master switch to temporarily hide the "Try Thought Prompt" button everywhere.
# Set to False to hide it for all small steps regardless of THOUGHT_PROMPT_SMALL_STEP_RANGE.
SHOW_THOUGHT_PROMPT_BUTTON = True

# Only these small_step_num values currently have authored thought prompt questions
# (e.g. Place value, age 8-9). The button is hidden for any step outside this range.
THOUGHT_PROMPT_SMALL_STEP_RANGE = (373, 389)

# Import interactive number line widget
try:
    from ux.number_line_widget import render_number_line
    INTERACTIVE_NUMBER_LINE_ENABLED = True
except ImportError:
    INTERACTIVE_NUMBER_LINE_ENABLED = False
    render_number_line = None

# Selection payload normalization, routing, deferred widget sync, and debug-panel
# eligibility checks are centralized in shared/step_selection.py.

# Mothballed topic-table search (prefix text box + table): hidden by default.
ENABLE_TOPIC_TABLE_SEARCH = False

# Natural-language Flipper Search (search_engine.py / streamlit_ui.py): disabled, kept for future re-enable.
ENABLE_FLIPPER_SEARCH = False

# Toggle temporary payload/nav diagnostics panel.
ENABLE_SELECTION_DEBUG_PANEL = False

# Configure page
st.set_page_config(
    page_title="Flipper Lite - Video Browser",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Add custom CSS for Age dropdown width (7ch)
st.markdown("""
<style>
div[data-testid="stSelectbox"] label[aria-label="Age"] ~ div:first-child,
div[data-testid="stSelectbox"][aria-label="Age"] > div:first-child {
    width: 7ch !important; min-width: 7ch !important; max-width: 7ch !important;
}
</style>
""", unsafe_allow_html=True)

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
        content: "";
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
    
    /* Style Watch buttons - make them compact and elegant */
    button[key^="play_"] {
        background: linear-gradient(135deg, #2c5f8d 0%, #4a90c8 100%) !important;
        color: white !important;
        border: none !important;
        padding: 0.4rem 0.8rem !important;
        font-size: 0.9rem !important;
        font-weight: 500 !important;
        border-radius: 6px !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1) !important;
        transition: all 0.2s ease !important;
        margin-top: 0.3rem !important;
    }
    
    button[key^="play_"]:hover {
        background: linear-gradient(135deg, #1e3a5f 0%, #2c5f8d 100%) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 3px 6px rgba(0,0,0,0.15) !important;
    }
    
    button[key^="play_"]:active {
        transform: translateY(0) !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important;
    }
    
    /* Thumbnail hover effect */
    .video-thumbnail-container img {
        transition: filter 0.3s ease;
    }
    
    .video-thumbnail-container:hover img {
        filter: brightness(1.05);
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)  # Cache for 5 minutes; file changes detected immediately via mtime
def load_precomputed_recommendations_flat():
    """Load precomputed curriculum recommendations CSV.
    
    Cache expires every 5 minutes to pick up updates from precompute_curriculum_recommendations.py runs.
    File modification time is automatically included in Streamlit's cache key.
    """
    try:
        qa_csv_path = project_root / 'precomputed_recommendations_flat_qa.csv'
        base_csv_path = project_root / 'precomputed_recommendations_flat.csv'
        csv_path = qa_csv_path if qa_csv_path.exists() else base_csv_path
        df = pd.read_csv(csv_path)
        return normalize_precomputed_df(df)
    except Exception as e:
        st.error(f"Error loading precomputed recommendations: {e}")
        return None


@st.cache_data(ttl=300)  # Cache for 5 minutes for consistency
def load_video_inventory():
    """
    DEPRECATED: Channel and duration now included in precomputed_recommendations_flat.csv
    This function exists for backward compatibility but is no longer needed.
    """
    return None


def load_thought_prompts():
    """Load thought prompts from multiple choice CSV"""
    if not THOUGHT_PROMPTS_ENABLED:
        return None
    
    try:
        prompts_path = project_root / 'thoughtprompt' / 'pilot_output' / 'thought_prompts_multiplechoice.csv'
        if not prompts_path.exists():
            return None
        df = pd.read_csv(prompts_path)
        return df
    except Exception as e:
        st.error(f"Error loading thought prompts: {e}")
        return None


def lookup_videos_for_step(df, year, term, difficulty, topic, small_step, small_step_id=""):
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
        year_text = str(year).strip()
        term_text = str(term).strip()
        difficulty_text = str(difficulty).strip()
        topic_text = str(topic).strip()
        step_text = str(small_step).strip()
        step_id_text = str(small_step_id).strip()

        def _norm_col(col_name):
            if col_name not in df.columns:
                return pd.Series(["" for _ in range(len(df))], index=df.index)
            return df[col_name].fillna("").astype(str).str.strip()

        year_col = _norm_col('year')
        term_col = _norm_col('term')
        difficulty_col = _norm_col('difficulty')
        topic_col = _norm_col('topic')
        small_step_col = _norm_col('small_step')
        small_step_name_col = _norm_col('small_step_name')
        base_mask = (year_col == year_text) & (term_col == term_text)

        if difficulty_text:
            base_mask &= (difficulty_col == difficulty_text)
        else:
            base_mask &= (difficulty_col == "")

        step_mask = (small_step_col == step_text) | (small_step_name_col == step_text)

        matches = pd.DataFrame()
        if step_id_text and 'small_step_id' in df.columns:
            step_id_col = _norm_col('small_step_id')
            matches = df[step_id_col == step_id_text].copy()

        if matches.empty:
            # Preferred fallback: same curriculum branch plus exact topic and step text.
            strict_mask = base_mask & (topic_col == topic_text) & step_mask
            matches = df[strict_mask].copy()

        if matches.empty:
            # Compatibility fallback for stale recommendation topic labels after curriculum migrations.
            compat_mask = base_mask & step_mask
            matches = df[compat_mask].copy()

        if matches.empty:
            return []
        # Each row is a single recommendation (not pipe-separated)
        results = []
        for _, row in matches.iterrows():
            result = {
                'rank': row.get('rank', 1),
                'video_id': row.get('video_id', ''),
                'title': row.get('video_title', row.get('title', '')),
                'semantic_score': _to_float(row.get('semantic_score', 0.0)),
                'instruction_score': _to_float(row.get('instruction_score', 0.0)),
                'instruction_justification': row.get('instruction_justification', ''),
                'combined_score': _to_float(row.get('combined_score', 0.0)),
                'channel': row.get('channel', ''),
                'duration': row.get('duration_formatted', row.get('duration', '')),
                'topic': row.get('topic', topic),
                'small_step': row.get('small_step', small_step),
                'small_step_id': row.get('small_step_id', small_step_id),
                'small_step_num': row.get('small_step_num', None),
                'small_step_num_global': row.get('small_step_num_global', None)
            }
            results.append(result)
        return results
    except Exception as e:
        st.error(f"Lookup error: {e}")
        import traceback
        st.error(traceback.format_exc())
        return []


def _to_float(value, default=0.0):
    """Safely parse numeric values that may be blank strings in CSV-backed rows."""
    try:
        if value is None:
            return float(default)
        text = str(value).strip()
        if text == "" or text.lower() == "nan":
            return float(default)
        return float(text)
    except (TypeError, ValueError):
        return float(default)


def _score_to_percent(value):
    """Support both 0..1 normalized scores and 0..100 percentage scores."""
    raw = _to_float(value, default=0.0)
    pct = raw * 100.0 if raw <= 1.0 else raw
    return int(max(0.0, min(100.0, pct)))


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


def create_circular_progress_svg(score_pct, size=80, text_scale=1.0):
    """
    Create an SVG circular progress indicator.
    
    Args:
        score_pct: Score as percentage (0-100)
        size: Diameter of the circle in pixels
        text_scale: Multiplier for score text size in the center
    
    Returns:
        HTML string with SVG element
    """
    # Color based on score (Red -> Yellow -> Green spectrum)
    if score_pct >= 70:
        color = "#22c55e"  # Green
    elif score_pct >= 40:
        color = "#eab308"  # Yellow/Gold
    else:
        color = "#ef4444"  # Red
    
    # Calculate circle parameters
    radius = (size - 10) / 2
    circumference = 2 * math.pi * radius
    
    # Calculate the arc length for the scored portion
    # stroke-dasharray and stroke-dashoffset create the progress effect
    progress = (score_pct / 100) * circumference
    
    svg = f"""
    <svg width="{size}" height="{size}" style="transform: rotate(-90deg);">
        <!-- Background circle (gray) -->
        <circle
            cx="{size/2}"
            cy="{size/2}"
            r="{radius}"
            fill="none"
            stroke="#e5e7eb"
            stroke-width="8"
        />
        <!-- Progress circle (colored) -->
        <circle
            cx="{size/2}"
            cy="{size/2}"
            r="{radius}"
            fill="none"
            stroke="{color}"
            stroke-width="8"
            stroke-dasharray="{circumference}"
            stroke-dashoffset="{circumference - progress}"
            stroke-linecap="round"
        />
        <!-- Score text in center -->
        <text
            x="{size/2}"
            y="{size/2}"
            text-anchor="middle"
            dominant-baseline="middle"
            font-size="{20 * text_scale}"
            font-weight="bold"
            fill="{color}"
            style="transform: rotate(90deg); transform-origin: {size/2}px {size/2}px;"
        >{score_pct}%</text>
    </svg>
    """
    return svg


def get_small_step_num_from_video(video):
    """Extract small_step_num from a video dict, trying multiple fields/formats."""
    if not video:
        return None

    # Method 1: Use global small_step_num (preferred for thought prompts)
    if 'small_step_num_global' in video:
        try:
            return int(float(video['small_step_num_global']))
        except (ValueError, TypeError):
            pass

    # Method 2: Try direct small_step_num field (local topic number)
    if 'small_step_num' in video:
        try:
            return int(float(video['small_step_num']))
        except (ValueError, TypeError):
            pass

    # Method 3: Parse from small_step_id if format is "ss_XXX"
    small_step_id = video.get('small_step_id', '')
    if small_step_id and 'ss_' in small_step_id:
        try:
            return int(small_step_id.replace('ss_', '').split('_')[0])
        except (ValueError, AttributeError):
            pass

    return None


def should_show_thought_prompt_button(video):
    """Whether the 'Try Thought Prompt' button should be shown for this video."""
    if not SHOW_THOUGHT_PROMPT_BUTTON:
        return False
    small_step_num = get_small_step_num_from_video(video)
    if small_step_num is None:
        return False
    lo, hi = THOUGHT_PROMPT_SMALL_STEP_RANGE
    return lo <= small_step_num <= hi


def get_prompts_for_small_step(prompts_df, small_step_num):
    """Get all prompts for a specific small step, sorted by variant"""
    if prompts_df is None or small_step_num is None:
        return []
    
    matches = prompts_df[prompts_df['small_step_num'] == small_step_num]
    if matches.empty:
        return []
    
    # Sort by variant (1, 2, 3)
    return matches.sort_values('variant').to_dict('records')


def _inject_tts(prompt_text):
    """Inject a self-contained JS block that speaks prompt_text via Web Speech API.
    
    Cancels any in-progress speech first (handles Streamlit reruns from
    previous answers).  Height=0 so there is zero UI footprint.
    """
    if not prompt_text:
        return
    
    # Escape for safe embedding inside a JS single-quoted string
    escaped = (
        prompt_text
        .replace("\\", "\\\\")   # backslashes first
        .replace("'", "\\'")     # single quotes
        .replace("\n", " ")      # newlines → spaces
    )
    
    tts_js = f"""<script>
(function() {{
    window.speechSynthesis.cancel();
    
    function speak() {{
        var utterance = new SpeechSynthesisUtterance('{escaped}');
        
        // Prefer a good English voice — try in priority order
        var voices = speechSynthesis.getVoices();
        if (voices.length > 0) {{
            var preferred = null;

            // 1st choice: Google UK English Female
            preferred = voices.find(function(v) {{
                return v.name.indexOf('Google UK English Female') !== -1;
            }});

            // 2nd choice: Samantha
            if (!preferred) {{
                preferred = voices.find(function(v) {{
                    return v.name.indexOf('Samantha') !== -1;
                }});
            }}

            // 3rd choice: any English voice, but skip Microsoft/David
            if (!preferred) {{
                preferred = voices.find(function(v) {{
                    return v.lang.indexOf('en') === 0 &&
                           v.name.indexOf('Microsoft') === -1 &&
                           v.name.indexOf('David') === -1 &&
                           v.name.indexOf('Zira') === -1;
                }});
            }}

            // Last resort: any English voice at all
            if (!preferred) {{
                preferred = voices.find(function(v) {{
                    return v.lang.indexOf('en') === 0;
                }});
            }}

            if (preferred) utterance.voice = preferred;
        }}
        
        utterance.rate = 0.9;    // Slightly slower for young learners
        utterance.pitch = 1.0;
        utterance.volume = 1.0;
        
        speechSynthesis.speak(utterance);
    }}
    
    // Voices may load asynchronously; retry once if not yet loaded
    if (speechSynthesis.getVoices().length === 0) {{
        speechSynthesis.addEventListener('voiceschanged', speak, {{ once: true }});
    }} else {{
        speak();
    }}
}})();
</script>"""
    
    components.html(tts_js, height=0)


def render_thought_prompt(prompt, visual_generator):
    """Render a single thought prompt with its visual"""
    st.markdown(f"### 🎯 {prompt['prompt_text']}")
    
    # --- TTS: speak the prompt text aloud using Web Speech API ---
    _inject_tts(prompt['prompt_text'])
    
    # Generate visual
    try:
        params = json.loads(prompt['visual_params'])
        visual_type = prompt['visual_type']
        small_step_num = None
        try:
            small_step_num = int(float(prompt.get('small_step_num')))
        except (TypeError, ValueError):
            small_step_num = None

        # Legacy compatibility: older step-373 rows stored 1,000-level prompts as tens+ones only.
        # Promote those params so they render through the unified 3D hundreds pipeline.
        if (
            visual_type == 'base10_blocks'
            and small_step_num == 373
            and 'hundreds' not in params
            and 'thousands' not in params
            and 'tens' in params
        ):
            params = {
                'hundreds': int(params.get('tens', 0)),
                'tens': 0,
                'ones': int(params.get('ones', 0)),
                'label': bool(params.get('label', True)),
            }
        
        if visual_type == 'base10_blocks':
            # Route 4-digit base10 prompts to the dedicated generator.
            if 'thousands' in params or 'hundreds' in params:
                img = visual_generator.generate_base10_blocks_4digit(
                    thousands=int(params.get('thousands', 0)),
                    hundreds=int(params.get('hundreds', 0)),
                    tens=int(params.get('tens', 0)),
                    ones=int(params.get('ones', 0)),
                    label=bool(params.get('label', True)),
                )
            elif 'tens' in params and 'ones' in params:
                img = visual_generator.generate_base10_blocks(
                    tens=int(params.get('tens', 0)),
                    ones=int(params.get('ones', 0)),
                    label=bool(params.get('label', True)),
                )
            else:
                st.info("⏭ This base-10 prompt schema is not supported yet")
                return None
        elif visual_type == 'part_whole_model':
            if 'alternative' in params:
                params['alternative_parts'] = params.pop('alternative')
                img = visual_generator.generate_double_part_whole_model(**params)
            else:
                img = visual_generator.generate_part_whole_model(**params)
        elif visual_type == 'number_line':
            # Interactive number line override for "Estimate on a number line to 10,000" (step 382, variant 1)
            if (INTERACTIVE_NUMBER_LINE_ENABLED 
                and small_step_num == 382 
                and int(prompt.get('variant', 0)) == 1):
                # Signal caller to use interactive widget instead of static image
                return {"interactive": True, "params": params}
            img = visual_generator.generate_number_line(**params)
        elif visual_type == 'bar_model':
            img = visual_generator.generate_bar_model(**params)
        elif visual_type == 'none':
            # No visual needed - the prompt text is sufficient
            return True
        else:
            st.error(f"Unknown visual type: {visual_type}")
            return None
        
        # Display visual - further constrained width for learner-friendly layout
        col_img, col_spacer = st.columns([2.2, 1.8])
        with col_img:
            st.image(img, use_container_width=True)
        
        return img
    
    except Exception as e:
        st.error(f"Error generating visual: {e}")
        return None


def _build_interactive_number_line_html(start, end, correct_answer, tolerance, interval, title, question):
    """Build a self-contained HTML page for the interactive number line widget.
    
    This is a lightweight version of draggable_number_line.html that works reliably
    inside Streamlit's components.html iframe. It uses the same CSS/JS logic but is
    embedded directly without URL parameter mocking.
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
        font-family: 'Segoe UI', Arial, sans-serif;
        background: #f8f9fa;
        padding: 12px 16px;
        user-select: none;
    }}
    .widget-container {{
        max-width: 700px;
        margin: 0 auto;
        background: #ffffff;
        border-radius: 12px;
        padding: 20px 24px 16px 24px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }}
    .title {{
        font-size: 1.1rem;
        font-weight: 700;
        color: #1e3a5f;
        margin-bottom: 4px;
    }}
    .subtitle {{
        font-size: 0.85rem;
        color: #6b7280;
        margin-bottom: 16px;
    }}
    .number-line-container {{
        position: relative;
        height: 90px;
        margin: 8px 30px 4px 30px;
    }}
    .number-line {{
        position: absolute;
        top: 50%;
        left: 0;
        right: 0;
        height: 3px;
        background: #2C3E50;
        transform: translateY(-50%);
        border-radius: 2px;
    }}
    .tick {{
        position: absolute;
        top: 50%;
        width: 2px;
        height: 14px;
        background: #2C3E50;
        transform: translate(-50%, -50%);
    }}
    .tick-label {{
        position: absolute;
        top: calc(50% + 12px);
        transform: translateX(-50%);
        font-size: 0.72rem;
        color: #374151;
        font-weight: 500;
        white-space: nowrap;
    }}
    .interval-label {{
        position: absolute;
        bottom: 4px;
        left: 50%;
        transform: translateX(-50%);
        font-size: 0.7rem;
        color: #9ca3af;
        font-style: italic;
    }}
    .handle {{
        position: absolute;
        top: 50%;
        width: 28px;
        height: 28px;
        background: #FF6B6B;
        border: 3px solid #cc4444;
        border-radius: 50%;
        transform: translate(-50%, -50%);
        cursor: grab;
        z-index: 10;
        box-shadow: 0 2px 6px rgba(204,68,68,0.35);
        transition: box-shadow 0.15s;
    }}
    .handle:hover {{ box-shadow: 0 3px 10px rgba(204,68,68,0.5); }}
    .handle:active {{ cursor: grabbing; box-shadow: 0 4px 14px rgba(204,68,68,0.6); }}
    .handle.dragging {{ cursor: grabbing; }}
    .current-value {{
        text-align: center;
        font-size: 1.4rem;
        font-weight: 700;
        color: #1e3a5f;
        margin: 6px 0 12px 0;
    }}
    .current-value .val {{
        color: #FF6B6B;
        font-size: 1.6rem;
    }}
    .controls {{
        display: flex;
        gap: 10px;
        justify-content: center;
        flex-wrap: wrap;
    }}
    .btn {{
        padding: 8px 18px;
        border: none;
        border-radius: 8px;
        font-size: 0.9rem;
        font-weight: 600;
        cursor: pointer;
        transition: background 0.2s, transform 0.1s;
    }}
    .btn:active {{ transform: scale(0.97); }}
    .btn-check {{
        background: #4ECDC4;
        color: #ffffff;
    }}
    .btn-check:hover {{ background: #3dbdb5; }}
    .btn-reset {{
        background: #e5e7eb;
        color: #374151;
    }}
    .btn-reset:hover {{ background: #d1d5db; }}
    .feedback {{
        text-align: center;
        margin-top: 12px;
        padding: 10px 16px;
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.95rem;
        display: none;
    }}
    .feedback.correct {{
        display: block;
        background: #d1fae5;
        color: #065f46;
        border: 1px solid #6ee7b7;
    }}
    .feedback.incorrect {{
        display: block;
        background: #fee2e2;
        color: #991b1b;
        border: 1px solid #fca5a5;
    }}
</style>
</head>
<body>
<div class="widget-container">
    <div class="title">{title}</div>
    <div class="subtitle">{question}</div>
    <div class="current-value">Your guess: <span class="val" id="currentVal">{end}</span></div>
    <div class="number-line-container" id="nlContainer">
        <div class="number-line"></div>
        <div id="ticksLayer"></div>
        <div class="handle" id="handle" style="left:100%;"></div>
    </div>
    <div class="controls">
        <button class="btn btn-check" id="btnCheck">Check Answer</button>
        <button class="btn btn-reset" id="btnReset">&#8634; Reset</button>
    </div>
    <div class="feedback" id="feedback"></div>
</div>
<script>
(function() {{
    var START = {start};
    var END = {end};
    var CORRECT = {correct_answer};
    var TOLERANCE = {tolerance};
    var SNAP = {interval};

    var handle = document.getElementById('handle');
    var container = document.getElementById('nlContainer');
    var currentVal = document.getElementById('currentVal');
    var feedback = document.getElementById('feedback');
    var ticksLayer = document.getElementById('ticksLayer');
    var dragging = false;

    function posToValue(frac) {{
        return Math.round(START + frac * (END - START));
    }}

    function valueToPos(val) {{
        return ((val - START) / (END - START)) * 100;
    }}

    function snapValue(val) {{
        return Math.round(val / SNAP) * SNAP;
    }}

    function clampValue(val) {{
        return Math.max(START, Math.min(END, val));
    }}

    function updateHandle(frac) {{
        var pct = frac * 100;
        pct = Math.max(0, Math.min(100, pct));
        handle.style.left = pct + '%';
        var val = snapValue(posToValue(frac));
        val = clampValue(val);
        currentVal.textContent = val.toLocaleString();
    }}

    function buildTicks() {{
        ticksLayer.innerHTML = '';
        var numTicks = Math.floor((END - START) / SNAP) + 1;
        for (var i = 0; i < numTicks; i++) {{
            var val = START + i * SNAP;
            var pct = valueToPos(val);
            var tick = document.createElement('div');
            tick.className = 'tick';
            tick.style.left = pct + '%';
            ticksLayer.appendChild(tick);
            var label = document.createElement('div');
            label.className = 'tick-label';
            label.style.left = pct + '%';
            label.textContent = val.toLocaleString();
            ticksLayer.appendChild(label);
        }}
    }}

    function getFracFromEvent(e) {{
        var rect = container.getBoundingClientRect();
        var clientX = e.touches ? e.touches[0].clientX : e.clientX;
        return (clientX - rect.left) / rect.width;
    }}

    function onStart(e) {{
        dragging = true;
        handle.classList.add('dragging');
        feedback.classList.remove('correct', 'incorrect');
        feedback.style.display = 'none';
        updateHandle(getFracFromEvent(e));
        e.preventDefault();
    }}

    function onMove(e) {{
        if (!dragging) return;
        updateHandle(getFracFromEvent(e));
        e.preventDefault();
    }}

    function onEnd(e) {{
        dragging = false;
        handle.classList.remove('dragging');
        if (e) e.preventDefault();
    }}

    handle.addEventListener('mousedown', onStart);
    handle.addEventListener('touchstart', onStart, {{passive: false}});
    document.addEventListener('mousemove', onMove);
    document.addEventListener('touchmove', onMove, {{passive: false}});
    document.addEventListener('mouseup', onEnd);
    document.addEventListener('touchend', onEnd);

    container.addEventListener('mousedown', function(e) {{
        if (e.target === handle) return;
        onStart(e);
    }});

    document.getElementById('btnCheck').addEventListener('click', function() {{
        var val = parseInt(currentVal.textContent.replace(/,/g, ''), 10);
        var diff = Math.abs(val - CORRECT);
        feedback.style.display = 'block';
        if (diff <= TOLERANCE) {{
            feedback.textContent = 'Correct! ' + val.toLocaleString() + ' is within ' + TOLERANCE + ' of ' + CORRECT.toLocaleString() + '.';
            feedback.className = 'feedback correct';
        }} else {{
            feedback.textContent = 'Not quite. You selected ' + val.toLocaleString() + '. The correct answer is ' + CORRECT.toLocaleString() + '.';
            feedback.className = 'feedback incorrect';
        }}
        // Pass answer back to Streamlit via setComponentValue
        try {{
            if (window.Streamlit) {{
                window.Streamlit.setComponentValue(JSON.stringify({{
                    value: val,
                    isCorrect: diff <= TOLERANCE
                }}));
            }}
        }} catch(e) {{}}
    }});

    document.getElementById('btnReset').addEventListener('click', function() {{
        updateHandle(1.0);
        feedback.classList.remove('correct', 'incorrect');
        feedback.style.display = 'none';
    }});

    // Initialize
    buildTicks();
    updateHandle(1.0);
}})();
</script>
</body>
</html>"""


def _render_interactive_number_line_prompt(current_prompt, small_step_num, current_variant, current_video, difficulty):
    """Render the interactive draggable number line widget for step 382 variant 1."""
    params = json.loads(current_prompt['visual_params'])
    start = int(params.get('start', 6000))
    end = int(params.get('end', 7000))
    correct_answer = 6500
    tolerance = int(params.get('tolerance', 100))
    interval_value = int(params.get('interval', 100))
    question = current_prompt['prompt_text']
    title = current_prompt['small_step_name']

    widget_key = f"interactive_nl_{current_variant}"

    # Build and render the self-contained widget HTML
    widget_html = _build_interactive_number_line_html(
        start=start, end=end, correct_answer=correct_answer,
        tolerance=tolerance, interval=interval_value,
        title=title, question=question
    )
    result = components.html(widget_html, height=420, scrolling=False)

    # If the learner submitted an answer via the embedded "Check Answer" button,
    # the widget calls window.Streamlit.setComponentValue() which is captured here.
    if result:
        try:
            data = json.loads(result)
            if isinstance(data, dict) and 'value' in data:
                submitted_value = data['value']
                _process_number_line_answer(
                    submitted_value=submitted_value,
                    correct_answer=correct_answer,
                    tolerance=tolerance,
                    small_step_num=small_step_num,
                    current_variant=current_variant,
                    current_video=current_video,
                    difficulty=difficulty,
                    current_prompt=current_prompt
                )
        except (json.JSONDecodeError, TypeError, ValueError):
            pass


def _process_number_line_answer(submitted_value, correct_answer, tolerance, small_step_num, current_variant, current_video, difficulty, current_prompt):
    """Handle the answer for the interactive number line."""
    diff = abs(submitted_value - correct_answer)
    is_correct = diff <= tolerance
    
    response_record = {
        'timestamp': datetime.now().isoformat(),
        'small_step_num': small_step_num,
        'small_step_name': current_prompt['small_step_name'],
        'video_id': current_video['video_id'],
        'variant': current_variant,
        'prompt_text': current_prompt['prompt_text'],
        'user_answer': str(submitted_value),
        'correct_answer': str(correct_answer),
        'is_correct': is_correct,
        'difficulty': difficulty
    }
    st.session_state.tp_responses.append(response_record)
    
    if is_correct:
        st.success(f"✅ Correct! {submitted_value} is within {tolerance} of {correct_answer}")
        st.balloons()
        st.markdown("### Great work! Returning to video...")
        
        track_event("thought_prompt_correct", {
            "small_step_num": small_step_num,
            "variant": current_variant,
            "difficulty": difficulty
        })
        
        import time
        time.sleep(2)
        st.session_state.showing_thought_prompt = False
        st.session_state.tp_current_variant = 1
        st.rerun()
    else:
        st.error(f"❌ Not quite. You selected {submitted_value}. The correct answer is {correct_answer}.")
        
        track_event("thought_prompt_incorrect", {
            "small_step_num": small_step_num,
            "variant": current_variant,
            "difficulty": difficulty,
            "user_answer": str(submitted_value)
        })
        
        if current_variant < 3:
            st.info(f"Moving to attempt {current_variant + 1} of 3...")
            import time
            time.sleep(1.5)
            st.session_state.tp_current_variant += 1
            st.rerun()
        else:
            st.warning("You've tried all variants. Review the material and try again later!")


def render_thought_prompt_page():
    """Render the thought prompt interaction page"""
    # Full-screen immersive CSS - hide Streamlit chrome, maximize viewport
    st.markdown("""<style>
    header[data-testid="stHeader"] { display: none !important; }
    #MainMenu { display: none !important; }
    footer { display: none !important; }
    [data-testid="stSidebar"] { display: none !important; }
    button[kind="header"] { display: none !important; }
    .block-container { padding: 0.5rem 1rem !important; max-width: 100% !important; background: transparent !important; box-shadow: none !important; border-radius: 0 !important; }
    .stApp { min-height: 100vh !important; background: #f0f5f9 !important; }
    .stApp::before { display: none !important; }
    .main { padding: 0 !important; }
    .element-container { margin-bottom: 0.25rem !important; }
    button[kind="secondary"] { font-size: 0.85rem !important; padding: 0.3rem 0.8rem !important; }
    div[data-testid="stVerticalBlock"] { gap: 0.25rem !important; }
    </style>""", unsafe_allow_html=True)
    
    if not THOUGHT_PROMPTS_ENABLED:
        st.warning("Thought prompts not available (visual generator not found)")
        return
    
    # Get current video context
    current_video = st.session_state.get('current_video')
    if not current_video:
        st.warning("No video selected. Please select a video first.")
        return
    
    # Extract small_step_num from current video - try multiple sources
    small_step_num = get_small_step_num_from_video(current_video)
    
    # If we still don't have a small_step_num, show helpful error
    if small_step_num is None:
        st.info("Thought prompts not available for this video (could not determine small step number)")
        with st.expander("Debug Info"):
            st.write("Video data:", current_video)
        return
    
    # Load prompts
    prompts_df = load_thought_prompts()
    if prompts_df is None:
        st.info("No thought prompts available yet")
        return
    
    prompts = get_prompts_for_small_step(prompts_df, small_step_num)
    if not prompts:
        st.info(f"No thought prompts available for small step {small_step_num} yet")
        return
    
    # Initialize thought prompt session state
    if 'tp_current_variant' not in st.session_state:
        st.session_state.tp_current_variant = 1
    if 'tp_responses' not in st.session_state:
        st.session_state.tp_responses = []
    if 'tp_active_small_step' not in st.session_state:
        st.session_state.tp_active_small_step = None
    
    # Check if we're starting a new small step
    if st.session_state.tp_active_small_step != small_step_num:
        st.session_state.tp_active_small_step = small_step_num
        st.session_state.tp_current_variant = 1
    
    # Get current prompt based on variant
    current_variant = st.session_state.tp_current_variant
    if current_variant > len(prompts):
        # All prompts attempted
        st.error("❌ You've tried all three prompts. This topic might need some review!")
        if st.button("Try Again from Start", key="retry_prompts"):
            st.session_state.tp_current_variant = 1
            st.rerun()
        if st.button("← Back to Video", key="back_to_video_bottom", type="primary"):
            st.session_state.showing_thought_prompt = False
            st.rerun()
        return
    
    current_prompt = prompts[current_variant - 1]
    
    # Extract difficulty for tracking purposes
    difficulty = current_prompt['difficulty']
    
    # Initialize visual generator
    visual_generator = MathVisualGenerator()
    
    # Render the prompt
    img = render_thought_prompt(current_prompt, visual_generator)
    
    if img is None:
        # Visual couldn't be generated
        if st.button("Skip to Next Variant", key="skip_variant"):
            st.session_state.tp_current_variant += 1
            st.rerun()
        return
    
    # --- Interactive number line widget path (step 382, variant 1) ---
    if isinstance(img, dict) and img.get('interactive'):
        _render_interactive_number_line_prompt(
            current_prompt, small_step_num, current_variant,
            current_video, difficulty
        )
        return
    
    st.markdown("---")
    
    # Answer input - use large multiple choice buttons from choice1, choice2, choice3 columns
    correct_answer = str(current_prompt['correct_answer']).strip()
    
    # Get the thought_prompt_num to check if this is prompt #25 (which uses draggable number line, not buttons)
    prompt_num = None
    try:
        prompt_num = int(float(current_prompt.get('thought_prompt_num', 0)))
    except (TypeError, ValueError):
        pass
    
    # Check if this prompt has choice columns (exclude prompt #25 which uses draggable number line)
    has_choices = (
        'choice1' in current_prompt and 'choice2' in current_prompt and 'choice3' in current_prompt
        and str(current_prompt.get('choice1', '')).strip() != ''
        and str(current_prompt.get('choice2', '')).strip() != ''
        and str(current_prompt.get('choice3', '')).strip() != ''
        and prompt_num != 25
    )
    
    if has_choices:
        # Use large multiple choice buttons
        choice1 = str(current_prompt.get('choice1', '')).strip()
        choice2 = str(current_prompt.get('choice2', '')).strip()
        choice3 = str(current_prompt.get('choice3', '')).strip()
        
        st.markdown("### Select your answer:")
        
        # Custom CSS for large multiple choice buttons
        st.markdown("""
        <style>
        .mc-button-container button {
            min-height: 80px !important;
            font-size: 1.6rem !important;
            font-weight: 600 !important;
            border-radius: 14px !important;
            padding: 1rem 1.5rem !important;
            margin: 0.4rem 0 !important;
            transition: all 0.2s ease !important;
            border: 3px solid #4a90c8 !important;
            background: linear-gradient(135deg, #ffffff 0%, #e8f1f7 100%) !important;
            color: #1e3a5f !important;
            box-shadow: 0 4px 12px rgba(30, 58, 95, 0.12) !important;
        }
        .mc-button-container button:hover {
            background: linear-gradient(135deg, #e0ecf4 0%, #c8ddf0 100%) !important;
            border-color: #2c5f8d !important;
            transform: translateY(-2px) !important;
            box-shadow: 0 6px 18px rgba(30, 58, 95, 0.2) !important;
        }
        .mc-button-container button:active {
            transform: translateY(0) !important;
            box-shadow: 0 2px 6px rgba(30, 58, 95, 0.1) !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Render three full-width buttons
        submit_clicked = None
        user_answer = None
        
        btn_col1, btn_col2, btn_col3 = st.columns(3)
        
        with btn_col1:
            st.markdown('<div class="mc-button-container">', unsafe_allow_html=True)
            if st.button(f"**A**: {choice1}", key=f"mc_btn_{current_variant}_1", use_container_width=True):
                submit_clicked = True
                user_answer = choice1
            st.markdown('</div>', unsafe_allow_html=True)
        
        with btn_col2:
            st.markdown('<div class="mc-button-container">', unsafe_allow_html=True)
            if st.button(f"**B**: {choice2}", key=f"mc_btn_{current_variant}_2", use_container_width=True):
                submit_clicked = True
                user_answer = choice2
            st.markdown('</div>', unsafe_allow_html=True)
        
        with btn_col3:
            st.markdown('<div class="mc-button-container">', unsafe_allow_html=True)
            if st.button(f"**C**: {choice3}", key=f"mc_btn_{current_variant}_3", use_container_width=True):
                submit_clicked = True
                user_answer = choice3
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        # Fallback: text input for prompts without choices
        user_answer = st.text_input("Your answer:", key=f"answer_text_{current_variant}")
        
        # Submit button
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            submit_clicked = st.button("✓ Check Answer", key=f"submit_{current_variant}", type="primary")
    
    st.markdown("---")
    if st.button("← Back to Video", key="back_to_video_main", type="secondary"):
        st.session_state.showing_thought_prompt = False
        st.rerun()
    
    if submit_clicked:
        if not user_answer:
            st.warning("Please provide an answer first")
            return
        
        # Normalize answers for comparison
        user_answer_norm = str(user_answer).strip().lower()
        correct_answer_norm = correct_answer.lower()
        
        # Check if correct
        is_correct = user_answer_norm == correct_answer_norm
        
        # Record response
        response_record = {
            'timestamp': datetime.now().isoformat(),
            'small_step_num': small_step_num,
            'small_step_name': current_prompt['small_step_name'],
            'video_id': current_video['video_id'],
            'variant': current_variant,
            'prompt_text': current_prompt['prompt_text'],
            'user_answer': user_answer,
            'correct_answer': correct_answer,
            'is_correct': is_correct,
            'difficulty': difficulty
        }
        st.session_state.tp_responses.append(response_record)
        
        if is_correct:
            st.success(f"✅ Correct! The answer is {correct_answer}")
            st.balloons()
            st.markdown("### Great work! Returning to video...")
            
            # Track event
            track_event("thought_prompt_correct", {
                "small_step_num": small_step_num,
                "variant": current_variant,
                "difficulty": difficulty
            })
            
            # Return to video after a moment
            import time
            time.sleep(2)
            st.session_state.showing_thought_prompt = False
            st.session_state.tp_current_variant = 1  # Reset for next time
            st.rerun()
        else:
            st.error(f"❌ Not quite. Try again!")
            
            # Track event
            track_event("thought_prompt_incorrect", {
                "small_step_num": small_step_num,
                "variant": current_variant,
                "difficulty": difficulty,
                "user_answer": user_answer
            })
            
            # Move to next variant
            if current_variant < 3:
                st.info(f"Moving to attempt {current_variant + 1} of 3...")
                import time
                time.sleep(1.5)
                st.session_state.tp_current_variant += 1
                st.rerun()
            else:
                st.warning("You've tried all variants. Review the material and try again later!")


def render_educator_view():
    """Render the educator's view showing all learner responses"""
    st.markdown("## 📊 Educator View - Thought Prompt Responses")
    
    if 'tp_responses' not in st.session_state or not st.session_state.tp_responses:
        st.info("No responses recorded yet. Learners haven't attempted any thought prompts in this session.")
        return
    
    # Group responses by small step
    responses_df = pd.DataFrame(st.session_state.tp_responses)
    
    # Summary stats
    total_attempts = len(responses_df)
    correct_attempts = len(responses_df[responses_df['is_correct']])
    accuracy = (correct_attempts / total_attempts * 100) if total_attempts > 0 else 0
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Attempts", total_attempts)
    with col2:
        st.metric("Correct Answers", correct_attempts)
    with col3:
        st.metric("Accuracy", f"{accuracy:.1f}%")
    
    st.markdown("---")
    
    # Group by small step
    for small_step_num in responses_df['small_step_num'].unique():
        step_responses = responses_df[responses_df['small_step_num'] == small_step_num]
        small_step_name = step_responses.iloc[0]['small_step_name']
        
        # Check if any correct answers
        has_correct = step_responses['is_correct'].any()
        
        st.markdown(f"### {small_step_name}")
        
        if has_correct:
            # Show correct responses with big green tick
            correct_responses = step_responses[step_responses['is_correct']]
            for _, response in correct_responses.iterrows():
                st.markdown(
                    f"""
                    <div style="background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%); 
                                border: 2px solid #28a745; 
                                border-radius: 10px; 
                                padding: 15px; 
                                margin: 10px 0;">
                        <div style="display: flex; align-items: center;">
                            <div style="font-size: 48px; margin-right: 20px;">✓</div>
                            <div>
                                <div style="font-weight: 600; color: #155724; margin-bottom: 5px;">
                                    {response['prompt_text']}
                                </div>
                                <div style="color: #155724;">
                                    <strong>Correct Answer:</strong> {response['correct_answer']}
                                </div>
                                <div style="color: #6c757d; font-size: 0.9em; margin-top: 5px;">
                                    Difficulty: {response['difficulty'].title()} | 
                                    Variant: {response['variant']} | 
                                    {response['timestamp'][:19]}
                                </div>
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        else:
            # No correct answers - show needs help message
            st.markdown(
                f"""
                <div style="background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%); 
                            border: 2px solid #dc3545; 
                            border-radius: 10px; 
                            padding: 20px; 
                            margin: 10px 0;
                            text-align: center;">
                    <div style="font-size: 24px; color: #721c24; font-weight: 600; margin-bottom: 10px;">
                        ⚠️ Needs Some Help or To Go Back a Step
                    </div>
                    <div style="color: #721c24;">
                        No correct answers yet. Consider reviewing earlier material or providing additional support.
                    </div>
                    <div style="margin-top: 15px; color: #856404; background: #fff3cd; padding: 10px; border-radius: 5px;">
                        <strong>Attempts made:</strong> {len(step_responses)} | 
                        <strong>Difficulty range:</strong> {', '.join(step_responses['difficulty'].unique())}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
        
        # Show all attempts in expander
        with st.expander(f"View all {len(step_responses)} attempts"):
            for _, response in step_responses.iterrows():
                status_icon = "✓" if response['is_correct'] else "✗"
                status_color = "#28a745" if response['is_correct'] else "#dc3545"
                st.markdown(
                    f"""
                    <div style="border-left: 4px solid {status_color}; padding-left: 10px; margin: 5px 0;">
                        <strong>{status_icon}</strong> {response['prompt_text']}<br/>
                        <em>User: {response['user_answer']}</em> | Correct: {response['correct_answer']}<br/>
                        <small>Variant {response['variant']} | {response['timestamp'][:19]}</small>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        
        st.markdown("---")


def render_video_player(video_data):
    """Render full-screen video player view with back button"""
    video_id = video_data['video_id']
    title = video_data['title']
    channel = video_data.get('channel', '')
    duration = video_data.get('duration', '')
    
    # Back button above video display for quick navigation
    if st.button("← Back to Search Results", key="back_to_search_top", type="primary"):
        track_event("video_panel_closed", {"video_id": video_id, "location": "top_button"})
        st.session_state.viewing_video = False
        st.session_state.current_video = None
        st.rerun()
    
    # Video player at top using youtube-nocookie (privacy-respecting)
    embed_url = f"https://www.youtube-nocookie.com/embed/{video_id}?rel=0&modestbranding=1"
    
    # Full-width responsive iframe container at very top - edge to edge
    st.markdown(
        f"""
        <style>
        /* Remove all padding for video player page to maximize width */
        .block-container {{
            padding-top: 0rem !important;
            padding-left: 0rem !important;
            padding-right: 0rem !important;
            max-width: 100% !important;
        }}
        </style>
        <div style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; width: 100vw; background: #000; border-radius: 0px; margin: 0; margin-left: calc(-1 * var(--block-padding-x, 0px));">
            <iframe 
                src="{embed_url}" 
                style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: 0;"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                allowfullscreen>
            </iframe>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Back button for navigation - 20px below video
    if st.button("← Back to Search Results", key="back_to_search_bottom", type="primary"):
        track_event("video_panel_closed", {"video_id": video_id, "location": "bottom_button"})
        st.session_state.viewing_video = False
        st.session_state.current_video = None
        st.rerun()
    
    st.markdown("</div>", unsafe_allow_html=True)


def render_result_card(result, compact=False, mobile_viewer_mode=False):
    """Render a single Video card."""
    
    # Get video ID, topic, and small_step for tracking
    video_id = result['video_id']
    topic = result.get('topic', '')
    small_step = result.get('small_step', '')

    # Create a unique DOM id for this context
    dom_id = f"video-card-{video_id}-{topic}-{small_step}".replace(' ', '_').replace('"', '').replace("'", '')

    with st.container():
        show_score_infographic = not mobile_viewer_mode
        if show_score_infographic:
            # Compact mode keeps all three cards visible in one viewport.
            if compact:
                col_thumb, _g_spacer_l, col_gauge, _g_spacer_r, col_content = st.columns([0.95, 0.12, 0.4, 0.12, 3.53])
            else:
                col_thumb, _g_spacer_l, col_gauge, _g_spacer_r, col_content = st.columns([1.2, 0.16, 0.5, 0.16, 3.14])
        else:
            # Mobile viewer mode: thumbnail + content only.
            if compact:
                col_thumb, _card_spacer, col_content = st.columns([1.05, 0.14, 3.81])
            else:
                col_thumb, _card_spacer, col_content = st.columns([1.22, 0.16, 3.62])

        with col_thumb:
            # Clickable thumbnail with visible play button overlay
            unique_key = f"{video_id}_{topic}_{small_step}".replace(' ', '_').replace('"', '').replace("'", '')
            
            # Thumbnail with hover effect and button
            if mobile_viewer_mode:
                # Preserve native YouTube thumbnail aspect ratio on mobile.
                thumb_style = "width: 100%; height: auto; border-radius: 8px; display: block;"
            else:
                thumb_style = "width: 100%; max-height: 120px; object-fit: cover; border-radius: 8px; display: block;" if compact else "width: 100%; border-radius: 8px; display: block;"
            st.markdown(f"""
                <div style='position: relative; width: 100%;' class='video-thumbnail-container'>
                    <img src='https://img.youtube.com/vi/{video_id}/mqdefault.jpg' 
                         style='{thumb_style}'
                         class='video-card' 
                         data-video-id='{video_id}' 
                         data-topic='{topic}' 
                         data-small-step='{small_step}' 
                         id='{dom_id}' />
                </div>
            """, unsafe_allow_html=True)
            
            # Clean watch button
            if st.button(
                "▶ Watch" if not compact else "Watch",
                key=f"play_{unique_key}",
                use_container_width=True,
                type="primary"
            ):
                track_event(
                    "video_opened",
                    {
                        "video_id": video_id,
                        "topic": topic,
                        "small_step": small_step,
                        "compact_results_mode": bool(compact),
                    },
                )
                results_list = st.session_state.get('display_results', [])
                try:
                    idx = next(i for i, r in enumerate(results_list) if r.get('video_id') == result.get('video_id'))
                except StopIteration:
                    idx = 0
                st.session_state.current_video_index = idx
                st.session_state.current_video = result
                st.session_state.flipper_lite_scroll_to_player = True
                st.rerun()
        
        if show_score_infographic:
            with col_gauge:
                # Circular progress indicator for combined score
                combined_pct = _score_to_percent(result.get('combined_score', 0))
                infographic_scale = 1.25
                gauge_size = int(round((56 if compact else 80) * infographic_scale))
                
                # Display circular gauge with label - centered
                st.markdown("<div style='display:flex; flex-direction:column; align-items:center; justify-content:center; padding-top:8px;'>", unsafe_allow_html=True)
                st.markdown(
                    create_circular_progress_svg(combined_pct, size=gauge_size, text_scale=0.75 * infographic_scale),
                    unsafe_allow_html=True,
                )
                st.markdown(
                    "<div style='font-size:0.7rem; color:#6c757d; margin-top:2px; white-space:nowrap;'>Match to curriculum</div>",
                    unsafe_allow_html=True,
                )
                st.markdown("</div>", unsafe_allow_html=True)

        with col_content:
            if not mobile_viewer_mode:
                # Video title at the top (larger font)
                title_style = (
                    "font-size:0.95rem; font-weight:600; margin-bottom:0.18rem; "
                    "line-height:1.2; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;"
                    if compact else
                    "font-size:1.1rem; font-weight:600; margin-bottom:0.3rem"
                )
                st.markdown(f"<div style='{title_style}'>{result['title']}</div>", unsafe_allow_html=True)

            # Channel and duration below title, after a space
            channel = result.get('channel', '')
            duration = result.get('duration', '')
            channel_display = channel.replace('_', ' ') if channel else ''
            duration_display = format_duration(duration) if duration else ''
            if channel_display or duration_display:
                if mobile_viewer_mode:
                    display_line = duration_display or channel_display
                    meta_font = "0.74rem"
                    meta_margin = "0.08rem"
                else:
                    display_line = f"{channel_display} | {duration_display}" if channel_display and duration_display else channel_display or duration_display
                    meta_font = "0.82rem" if compact else "0.95rem"
                    meta_margin = "0.2rem" if compact else "0.5rem"
                st.markdown(f"<div style='font-size:{meta_font}; color:#2c5f8d; margin-bottom:{meta_margin}'>{display_line}</div>", unsafe_allow_html=True)

            # Display instruction justification if available (hidden in mobile viewer mode)
            justification = result.get('instruction_justification', '')
            if (not mobile_viewer_mode) and justification and str(justification).strip():
                if compact:
                    st.markdown(
                        f"""
                        <div style='font-size:0.91rem; color:#4b5f73; margin-top:0.12rem; line-height:1.22; white-space:normal;'>
                            {justification}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(f"<div style='font-size:0.9rem; color:#555; margin-top:0.5rem; font-style:italic; padding:0.5rem; background:#f8f9fa; border-left:3px solid #4a90c8; border-radius:4px;'>💡 {justification}</div>", unsafe_allow_html=True)

        if compact:
            st.markdown("<hr style='margin: 0.35rem 0 0.35rem 0; border:0; border-top:1px solid rgba(44, 95, 141, 0.18);'>", unsafe_allow_html=True)
        else:
            st.markdown("---")


def render_landing_demo_frame(recommendations_df):
    """Show a composed example of the three videos returned for a curriculum step."""
    demo_rows = recommendations_df[
        (recommendations_df['age'].astype(str) == '5-6')
        & (recommendations_df['term'].astype(str) == 'Autumn')
        & (recommendations_df['topic'].astype(str) == 'Place value within 10')
        & (recommendations_df['small_step'].astype(str) == 'Sort objects')
    ].sort_values('rank').head(3)

    if len(demo_rows) != 3:
        return

    cards = []
    for _, row in demo_rows.iterrows():
        video_id = html.escape(str(row.get('video_id', '')).strip(), quote=True)
        title = html.escape(str(row.get('title', '')).strip())
        channel = html.escape(str(row.get('channel', '')).replace('_', ' ').strip())
        duration = html.escape(str(row.get('duration', '')).strip())
        cards.append(
            f"""
            <article class="landing-demo-card">
                <div class="landing-demo-thumbnail">
                    <img src="https://img.youtube.com/vi/{video_id}/hqdefault.jpg" alt="YouTube video thumbnail: {title}">
                    <span class="landing-demo-play" aria-hidden="true">▶</span>
                </div>
                <div class="landing-demo-card-body">
                    <h3>{title}</h3>
                    <p>{channel} <span aria-hidden="true">·</span> {duration}</p>
                </div>
            </article>
            """
        )

    st.markdown(
        f"""
        <section class="landing-demo-frame" aria-label="Three example video suggestions">
            <div class="landing-demo-heading">
                <div>
                    <p class="landing-demo-eyebrow">What you get</p>
                    <h2>Three great videos for one White Rose Small Step</h2>
                </div>
                <p class="landing-demo-context"><strong>Age 5-6</strong> <span aria-hidden="true">·</span> Autumn <span aria-hidden="true">·</span> Place value within 10 <span aria-hidden="true">·</span> Sort objects</p>
            </div>
            <div class="landing-demo-cards">{''.join(cards)}</div>
        </section>
        <style>
            .landing-demo-frame {{
                min-height: clamp(360px, 50vh, 560px);
                margin: 1.5rem 0 2rem;
                padding: clamp(1.25rem, 3vw, 2rem);
                border: 1px solid rgba(44, 95, 141, 0.24);
                border-radius: 12px;
                background: rgba(255, 255, 255, 0.9);
                box-shadow: 0 10px 26px rgba(30, 58, 95, 0.12);
                box-sizing: border-box;
            }}
            .landing-demo-heading {{
                display: flex;
                align-items: end;
                justify-content: space-between;
                gap: 1.5rem;
                margin-bottom: 1.25rem;
            }}
            .landing-demo-eyebrow {{
                margin: 0 0 0.35rem;
                color: #4a90c8;
                font-size: 0.78rem;
                font-weight: 700;
                letter-spacing: 0.08em;
                text-transform: uppercase;
            }}
            .landing-demo-heading h2 {{
                margin: 0;
                color: #1e3a5f;
                font-family: 'Poppins', sans-serif;
                font-size: clamp(1.2rem, 2vw, 1.7rem);
                line-height: 1.2;
            }}
            .landing-demo-context {{
                max-width: 32rem;
                margin: 0;
                color: #2c5f8d;
                font-size: 0.9rem;
                line-height: 1.4;
                text-align: right;
            }}
            .landing-demo-cards {{
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 1rem;
            }}
            .landing-demo-card {{
                min-width: 0;
                overflow: hidden;
                border: 1px solid rgba(44, 95, 141, 0.2);
                border-radius: 8px;
                background: #fff;
            }}
            .landing-demo-thumbnail {{
                position: relative;
                aspect-ratio: 16 / 9;
                overflow: hidden;
                background: #dce8f1;
            }}
            .landing-demo-thumbnail img {{
                display: block;
                width: 100%;
                height: 100%;
                object-fit: cover;
            }}
            .landing-demo-play {{
                position: absolute;
                left: 50%;
                top: 50%;
                display: grid;
                width: 3rem;
                height: 3rem;
                transform: translate(-50%, -50%);
                place-items: center;
                border-radius: 50%;
                color: #fff;
                background: rgba(210, 35, 35, 0.95);
                font-size: 1.15rem;
                box-shadow: 0 3px 10px rgba(0, 0, 0, 0.25);
            }}
            .landing-demo-card-body {{
                padding: 0.85rem 0.9rem 1rem;
            }}
            .landing-demo-card-body h3 {{
                display: -webkit-box;
                min-height: 2.7em;
                margin: 0 0 0.45rem;
                overflow: hidden;
                color: #18324f;
                font-size: 0.98rem;
                line-height: 1.35;
                -webkit-box-orient: vertical;
                -webkit-line-clamp: 2;
            }}
            .landing-demo-card-body p {{
                margin: 0;
                color: #5c7185;
                font-size: 0.78rem;
                line-height: 1.3;
            }}
            @media (max-width: 700px) {{
                .landing-demo-frame {{ min-height: 0; }}
                .landing-demo-heading {{ display: block; }}
                .landing-demo-context {{ margin-top: 0.65rem; text-align: left; }}
                .landing-demo-cards {{ grid-template-columns: 1fr; }}
                .landing-demo-card {{ display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr); }}
                .landing-demo-card-body {{ align-self: center; }}
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def main():
    """Main application"""
    
    # Initialize session state for video viewing mode
    if 'viewing_video' not in st.session_state:
        st.session_state.viewing_video = False
    if 'current_video' not in st.session_state:
        st.session_state.current_video = None

    init_analytics("flipper_lite")
    track_event("page_view", {"page": "home"}, once_key="page_view")

    # ==========================================
    # Thought Prompt Full-Screen Check (must come before all chrome)
    # ==========================================
    if st.session_state.get('showing_thought_prompt', False):
        render_thought_prompt_page()
        st.stop()  # Stop rendering rest of the page — no header, sidebar, footer

    viewer_override = st.query_params.get("viewer", "")
    if isinstance(viewer_override, list):
        viewer_override = viewer_override[0] if viewer_override else ""
    viewer_override = str(viewer_override).strip().lower()

    request_headers = getattr(getattr(st, "context", None), "headers", {}) or {}
    user_agent = str(request_headers.get("user-agent", "")).lower()
    mobile_tokens = ("iphone", "android", "mobile", "windows phone", "opera mini")
    mobile_user_agent = any(token in user_agent for token in mobile_tokens)

    if viewer_override == "mobile":
        mobile_viewer_mode = True
    elif viewer_override in {"web", "desktop"}:
        mobile_viewer_mode = False
    else:
        # Default behavior: automatically simplify UI on phones.
        mobile_viewer_mode = mobile_user_agent

    if mobile_viewer_mode:
        st.markdown(
            """
            <div style="
                margin: 0.2rem 0 0.8rem 0;
                padding: 0.45rem 0.75rem;
                border-radius: 999px;
                display: inline-block;
                font-size: 0.86rem;
                font-weight: 600;
                letter-spacing: 0.02em;
                color: #1e3a5f;
                background: linear-gradient(90deg, rgba(74, 144, 200, 0.24), rgba(44, 95, 141, 0.17));
                border: 1px solid rgba(44, 95, 141, 0.28);
            ">
                Mobile Viewer
            </div>
            """,
            unsafe_allow_html=True,
        )

    results_focus_mode = (
        st.session_state.get('display_status') == 'complete'
        and bool(st.session_state.get('display_results'))
    )
    
    # ========== COLOR SCHEME ==========
    # Professional Blue (Trustworthy, Clean, Modern)
    HEADER_GRADIENT = "linear-gradient(to right, #1e3a5f, #2c5f8d, #4a90c8)"
    MAIN_TEXT_COLOR = "#f0f4f8"
    AI_ACCENT_COLOR = "#FFD700"
    
    results_header_slot = None

    if results_focus_mode:
        st.markdown(
            f"""
            <style>
            .block-container {{
                padding-top: 0 !important;
            }}
            .results-brand-inline {{
                margin: -0.2rem 0 0;
                font-family: 'Poppins', sans-serif;
                font-weight: 600;
                line-height: 1;
                letter-spacing: -0.01em;
                white-space: nowrap;
            }}
            .results-brand-main,
            .results-brand-sub {{
                background: {HEADER_GRADIENT};
                -webkit-background-clip: text;
                background-clip: text;
                color: transparent;
                text-shadow: 0 0 0 rgba(30, 58, 95, 0.02);
            }}
            .results-brand-main {{
                font-size: 1.93rem;
            }}
            .results-brand-sub {{
                font-size: 1.09rem;
                margin-left: 0.1rem;
            }}
            .results-brand-ai {{
                color: {AI_ACCENT_COLOR};
                -webkit-text-fill-color: {AI_ACCENT_COLOR};
                background: none;
            }}
            </style>
            <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
            """,
            unsafe_allow_html=True,
        )
        results_header_slot = st.container()
    else:
        # Custom Styled Header
        col1, col2 = st.columns([0.95, 0.05])

        with col1:
            st.markdown(f"""
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
        <div style="margin-bottom: 0rem;">
            <h1 style="
                font-family: 'Poppins', sans-serif;
                font-weight: 550;
                font-size: 2.5rem;
                margin: 0;
                letter-spacing: -0.5px;
            ">
                <span style="
                    font-size: 3.2rem;
                    font-weight: 600;
                    background: {HEADER_GRADIENT};
                    -webkit-background-clip: text;
                    background-clip: text;
                    color: transparent;
                    text-shadow: 0 0 0 rgba(30, 58, 95, 0.02);
                ">
                    Flipper School
                </span>
                <span style="
                    font-size: 1.8rem;
                    font-weight: 600;
                    background: {HEADER_GRADIENT};
                    -webkit-background-clip: text;
                    background-clip: text;
                    color: transparent;
                    text-shadow: 0 0 0 rgba(30, 58, 95, 0.02);
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
                text-align: centre;
                margin-top: 1rem;
                margin-bottom: 0rem;
                font-weight: 400;
            ">
                High quality Maths videos for each step from age 5 to 15
                <br>
                Curated maths videos from YouTube, matched to your curriculum
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
                back onto the learner. This harnesses evolving use of new mediums for aquiring knowledge and frees up instructional time to be more efficient, allowing it to focus on what its best for,
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
                Registered in Scotland, Edinburgh, EH15 2BG [John.Brown@flipper.school](mailto:John.Brown@flipper.school)
                """)
    
    # Load precomputed recommendations
    recommendations_df = load_precomputed_recommendations_flat()
    
    if recommendations_df is None:
        st.error("❌ Failed to load precomputed recommendations. Please run `precompute_curriculum_recommendations.py` first.")
        st.stop()

    # Note: video_inventory.csv no longer needed - channel & duration now in precomputed_recommendations.csv
    
    # Initialize curriculum assistant (uses same dropdown UI as flipper.py)
    curriculum_path = project_root / "Curriculum" / "Maths" / "curriculum_08052026_small_steps.csv"
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
    if 'current_video_index' not in st.session_state:
        st.session_state.current_video_index = 0
    if 'flipper_lite_scroll_to_video_cards' not in st.session_state:
        st.session_state.flipper_lite_scroll_to_video_cards = False
    if 'flipper_lite_scroll_to_player' not in st.session_state:
        st.session_state.flipper_lite_scroll_to_player = False
    if 'pending_selector_sync' not in st.session_state:
        st.session_state.pending_selector_sync = None
    
    # Initialize thought prompt session state
    if 'showing_thought_prompt' not in st.session_state:
        st.session_state.showing_thought_prompt = False
    if 'tp_current_variant' not in st.session_state:
        st.session_state.tp_current_variant = 1
    if 'tp_responses' not in st.session_state:
        st.session_state.tp_responses = []
    if 'tp_active_small_step' not in st.session_state:
        st.session_state.tp_active_small_step = None
    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = "Learning View"

    # Apply deferred selector-widget key sync before selector widgets instantiate.
    apply_pending_selector_sync()
    
    # ==========================================
    # Educator view temporarily removed - will be re-added as educator results page
    # ==========================================
    # render_educator_view()

    # Check if we should show thought prompt page (full-screen immersive mode)
    if st.session_state.get('showing_thought_prompt', False):
        render_thought_prompt_page()
        st.stop()  # Stop rendering rest of the page

    # Normal learning view continues below (rest of the function)

    # ==========================================
    # INLINE VIDEO PANEL (shown when a video is selected)
    # ==========================================
    if st.session_state.current_video:
        vid = st.session_state.current_video
        video_id = vid['video_id']
        title = vid['title']
        channel = vid.get('channel', '').replace('_', ' ')
        duration = format_duration(vid.get('duration', ''))
        embed_url = f"https://www.youtube-nocookie.com/embed/{video_id}?rel=0&modestbranding=1&autoplay=1"
        meta_parts = [p for p in [channel, duration] if p]
        meta_str = " | ".join(meta_parts)
        meta_html = f'<span style="color:#aac8e4; font-size:0.85rem; font-weight:400; margin-left:1rem;">{meta_str}</span>' if meta_str else ''
        st.markdown(
            f"""
            <div id="flipper-video-player" style="background:#1e3a5f; border-radius:10px; padding:0.75rem 0.75rem 0.5rem 0.75rem; margin-bottom:0.75rem;">
                <div style="color:#f0f4f8; font-size:1rem; font-weight:600; margin-bottom:0.5rem;">
                    &#9654; Now Playing: {title}{meta_html}
                </div>
                <div style="position:relative; padding-bottom:56.25%; height:0; overflow:hidden; border-radius:6px;">
                    <iframe src="{embed_url}"
                        style="position:absolute; top:0; left:0; width:100%; height:100%; border:0;"
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                        allowfullscreen>
                    </iframe>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        # Video controls with thought prompt button
        show_prompt_btn = THOUGHT_PROMPTS_ENABLED and should_show_thought_prompt_button(vid)
        if show_prompt_btn:
            _btn_spacer_l, btn_col_close, btn_col_prompt, btn_col_next, _btn_spacer_r = st.columns([2.5, 1, 1.2, 1, 2.5])
        else:
            _btn_spacer_l, btn_col_close, btn_col_prompt, btn_col_next, _btn_spacer_r = st.columns([3, 1, 0.01, 1, 3])
    
        with btn_col_close:
            if st.button("✕  Close video", key="close_inline_video", type="secondary", use_container_width=True):
                track_event("video_panel_closed", {"video_id": video_id, "location": "inline_close_button"})
                st.session_state.current_video = None
                st.session_state.current_video_index = 0
                st.rerun()
    
        with btn_col_prompt:
            if show_prompt_btn:
                if st.button("🎯 Try Thought Prompt", key="try_thought_prompt", type="primary", use_container_width=True):
                    track_event("thought_prompt_opened", {"video_id": video_id})
                    st.session_state.showing_thought_prompt = True
                    st.rerun()
    
        with btn_col_next:
            results_for_cycling = st.session_state.get('display_results', [])
            if len(results_for_cycling) > 1:
                if st.button("▶▶  Next Video", key="next_video_btn", type="primary", use_container_width=True):
                    next_idx = (st.session_state.current_video_index + 1) % len(results_for_cycling)
                    next_video = results_for_cycling[next_idx]
                    track_event(
                        "video_next_clicked",
                        {
                            "from_video_id": video_id,
                            "to_video_id": next_video.get("video_id"),
                            "results_count": len(results_for_cycling),
                        },
                    )
                    st.session_state.current_video_index = next_idx
                    st.session_state.current_video = next_video
                    st.rerun()
        st.markdown("---")
        if st.session_state.get('flipper_lite_scroll_to_player'):
            components.html(
                """
                <script>
                setTimeout(function() {
                    const target = window.parent.document.getElementById('flipper-video-player');
                    if (target) {
                        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                }, 150);
                </script>
                """,
                height=0,
            )
            st.session_state.flipper_lite_scroll_to_player = False

    st.markdown('<div id="flipper-video-results-top"></div>', unsafe_allow_html=True)

    if st.session_state.display_status == 'idle':
        # Empty state - no message
        pass

    elif st.session_state.display_status == 'loading':
        # Loading state - show spinner
        with st.spinner(""):
            st.empty()

    elif st.session_state.display_status == 'complete':
        # Results state - show Video cards
        if st.session_state.display_results:
            if st.session_state.get('flipper_lite_scroll_to_video_cards'):
                components.html(
                    """
                    <script>
                    const rootWin = window.parent;
                    const target = rootWin.document.getElementById('flipper-video-results-top');
                    if (target && typeof target.scrollIntoView === 'function') {
                        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }
                    </script>
                    """,
                    height=0,
                )
                st.session_state.flipper_lite_scroll_to_video_cards = False
            ctx = st.session_state.get('curriculum_context')
            prev_step = None
            next_step = None
            show_step_nav = False
            compact_small_step_desc = ""

            if curriculum_assistant and curriculum_assistant.df is not None and ctx and ctx.get('small_step_num_in_topic') is not None:
                prev_step, next_step = curriculum_assistant.get_adjacent_steps(ctx)
                show_step_nav = bool(prev_step or next_step)

            if results_focus_mode and results_header_slot is not None:
                with results_header_slot:
                    if show_step_nav:
                        brand_col, nav_home_col, nav_back_col, nav_next_col = st.columns([7.8, 1.3, 1.35, 1.35])
                    else:
                        brand_col = st.columns([1])[0]

                    with brand_col:
                        st.markdown(
                            """
                            <div class='results-brand-inline'>
                                <span class='results-brand-main'>Flipper School</span>
                                <span class='results-brand-sub'> - Cur<span class='results-brand-ai'>AI</span>ted Education Videos</span>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                    if show_step_nav:
                        with nav_home_col:
                            if st.button(
                                "Back to search",
                                key="step_nav_home_top",
                                use_container_width=True,
                                help="Return to search with no filters",
                            ):
                                track_event("results_reset", {"source": "top_nav_home"})
                                st.session_state.display_status = 'idle'
                                st.session_state.display_results = []
                                st.session_state.display_step_name = ""
                                st.session_state.curriculum_context = None
                                st.session_state.current_video = None
                                st.session_state.current_video_index = 0

                                st.session_state.curr_year = 'Age ?'
                                st.session_state.year_select_topic_search = 'Age ?'
                                st.session_state.curr_difficulty = 'All'
                                st.session_state.difficulty_select_topic_search = 'All'
                                st.session_state.curr_topic = 'Topic ?'
                                st.session_state.topic_select_topic_search = 'Topic ?'
                                st.session_state.topic_prefix_search = ''
                                st.session_state.pending_topic_open = None
                                st.session_state.pending_open_difficulty = 'Foundation'
                                st.session_state.clear_topic_prefix_on_open = False
                                st.session_state.pending_step_nav = None
                                st.rerun()
                        with nav_back_col:
                            if prev_step and st.button(
                                "◀  Previous Step",
                                key="step_nav_back_top",
                                use_container_width=True,
                                help=f"Previous: {prev_step['small_step']}",
                            ):
                                track_event(
                                    "step_navigation",
                                    {
                                        "source": "top_nav_previous",
                                        "target_small_step": prev_step.get("small_step", ""),
                                        "target_step_id": prev_step.get("small_step_id", ""),
                                    },
                                )
                                st.session_state.pending_step_nav = prev_step
                                st.rerun()
                        with nav_next_col:
                            if next_step and st.button(
                                "Next Step  ▶",
                                key="step_nav_next_top",
                                use_container_width=True,
                                help=f"Next: {next_step['small_step']}",
                            ):
                                track_event(
                                    "step_navigation",
                                    {
                                        "source": "top_nav_next",
                                        "target_small_step": next_step.get("small_step", ""),
                                        "target_step_id": next_step.get("small_step_id", ""),
                                    },
                                )
                                st.session_state.pending_step_nav = next_step
                                st.rerun()

                    st.markdown(
                        "<hr style='margin: 0.15rem 0 0.3rem 0; border: 0; border-top: 1px solid rgba(44, 95, 141, 0.2);'>",
                        unsafe_allow_html=True,
                    )

            # Display breadcrumb heading if curriculum context is available
            if ctx:
                # Build breadcrumb with labeled sections
                breadcrumb_parts = []
            
                if ctx.get('age'):
                    breadcrumb_parts.append(f"Age: {ctx['age']}")
            
                if ctx.get('term'):
                    breadcrumb_parts.append(f"Term: {ctx['term']}")
            
                # Add difficulty only if it has a value
                difficulty = str(ctx.get('difficulty') or '').strip()
                if difficulty:
                    breadcrumb_parts.append(f"Difficulty: {difficulty}")
            
                if ctx.get('topic'):
                    breadcrumb_parts.append(f"Topic: {ctx['topic']}")

                small_step = str(ctx.get('small_step') or '').strip()
                if small_step:
                    breadcrumb_parts.append(f"Small Step: {small_step}")
            
                # Display breadcrumb with smaller font and separators
                if breadcrumb_parts:
                    breadcrumb_text = " &nbsp;|&nbsp; ".join(breadcrumb_parts)
                    breadcrumb_text_plain = " | ".join(breadcrumb_parts)

                    if results_focus_mode:
                        st.markdown(
                            f"""
                            <div style='font-size:0.84rem; margin:0 0 0.35rem 0; white-space:normal; overflow-wrap:anywhere;' title='{breadcrumb_text_plain}'>
                                {breadcrumb_text}
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    else:
                        breadcrumb_margin = "0.35rem" if results_focus_mode else "1rem"
                        breadcrumb_top_margin = "0" if results_focus_mode else "0.5rem"
                        st.markdown(f"<p style='font-size: 0.84rem; margin-top: {breadcrumb_top_margin}; margin-bottom: {breadcrumb_margin};'>{breadcrumb_text}</p>", unsafe_allow_html=True)

                small_step_desc = str(ctx.get('small_step_desc') or '').strip()
                if small_step_desc:
                    if results_focus_mode:
                        compact_small_step_desc = small_step_desc
                    else:
                        st.markdown(
                            f"""
                            <div style="
                                background: linear-gradient(135deg, rgba(255,255,255,0.96) 0%, rgba(234,242,250,0.96) 100%);
                                border: 1px solid rgba(74, 144, 200, 0.28);
                                border-left: 7px solid #1e3a5f;
                                border-radius: 12px;
                                padding: 0.85rem 1rem 0.9rem 1rem;
                                margin: 0 0 1rem 0;
                                box-shadow: 0 6px 18px rgba(30, 58, 95, 0.12);
                                color: #18324f;
                                font-size: 0.96rem;
                                line-height: 1.45;
                            ">
                                <div style="
                                    display: inline-block;
                                    background: #1e3a5f;
                                    color: #ffffff;
                                    font-size: 0.72rem;
                                    font-weight: 700;
                                    letter-spacing: 0.08em;
                                    text-transform: uppercase;
                                    padding: 0.22rem 0.55rem;
                                    border-radius: 999px;
                                    margin-bottom: 0.45rem;
                                ">
                                    Selected small step
                                </div>
                                <div style="font-weight: 500;">
                                {small_step_desc}
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
        
            # ---- Next Small Step / Back one navigation ----
            if show_step_nav and not results_focus_mode:
                _nav_spacer_l, nav_col_home, nav_col_back, nav_col_next, _nav_spacer_r = st.columns([2, 1, 1, 1, 2])
                with nav_col_home:
                    if st.button(
                        "Back to search",
                        key="step_nav_home",
                        use_container_width=True,
                        help="Return to search with no filters",
                    ):
                        track_event("results_reset", {"source": "bottom_nav_home"})
                        st.session_state.display_status = 'idle'
                        st.session_state.display_results = []
                        st.session_state.display_step_name = ""
                        st.session_state.curriculum_context = None
                        st.session_state.current_video = None
                        st.session_state.current_video_index = 0

                        st.session_state.curr_year = 'Age ?'
                        st.session_state.year_select_topic_search = 'Age ?'
                        st.session_state.curr_difficulty = 'All'
                        st.session_state.difficulty_select_topic_search = 'All'
                        st.session_state.curr_topic = 'Topic ?'
                        st.session_state.topic_select_topic_search = 'Topic ?'
                        st.session_state.topic_prefix_search = ''
                        st.session_state.pending_topic_open = None
                        st.session_state.pending_open_difficulty = 'Foundation'
                        st.session_state.clear_topic_prefix_on_open = False
                        st.session_state.pending_step_nav = None
                        st.rerun()
                with nav_col_back:
                    if prev_step and st.button(
                        "◀  Previous Small Step",
                        key="step_nav_back",
                        use_container_width=True,
                        help=f"Previous: {prev_step['small_step']}",
                    ):
                        track_event(
                            "step_navigation",
                            {
                                "source": "bottom_nav_previous",
                                "target_small_step": prev_step.get("small_step", ""),
                                "target_step_id": prev_step.get("small_step_id", ""),
                            },
                        )
                        st.session_state.pending_step_nav = prev_step
                        st.rerun()
                with nav_col_next:
                    if next_step and st.button(
                        "Next Small Step  ▶",
                        key="step_nav_next",
                        use_container_width=True,
                        help=f"Next: {next_step['small_step']}",
                    ):
                        track_event(
                            "step_navigation",
                            {
                                "source": "bottom_nav_next",
                                "target_small_step": next_step.get("small_step", ""),
                                "target_step_id": next_step.get("small_step_id", ""),
                            },
                        )
                        st.session_state.pending_step_nav = next_step
                        st.rerun()

            for result in st.session_state.display_results:
                render_result_card(
                    result,
                    compact=results_focus_mode,
                    mobile_viewer_mode=mobile_viewer_mode,
                )

            if results_focus_mode and compact_small_step_desc:
                st.markdown(
                    f"""
                    <div style="
                        background: rgba(255,255,255,0.82);
                        border: 1px solid rgba(74, 144, 200, 0.25);
                        border-radius: 9px;
                        padding: 0.35rem 0.6rem;
                        margin: 0.2rem 0 0.45rem 0;
                        color: #18324f;
                        font-size: 0.91rem;
                        line-height: 1.3;
                        white-space: normal;
                        overflow-wrap: anywhere;
                    " title="{compact_small_step_desc}">
                        <strong>Selected small step:</strong> {compact_small_step_desc}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.warning("No videos found for this step. Try a different curriculum step.")

    render_selection_debug_panel(curriculum_assistant, enabled=ENABLE_SELECTION_DEBUG_PANEL)

    # ==========================================
    # STEP NAVIGATION (pending_step_nav from Next/Back buttons)
    # ==========================================
    if st.session_state.get('pending_step_nav'):
        nav = st.session_state.pop('pending_step_nav')
        track_event(
            "step_selection_applied",
            {
                "source": "pending_navigation",
                "small_step": nav.get("small_step", ""),
                "small_step_id": nav.get("small_step_id", ""),
                "topic": nav.get("topic", ""),
                "age": nav.get("age", ""),
            },
        )
        apply_small_step_selection(nav, recommendations_df, curriculum_assistant, lookup_videos_for_step)

    # ==========================================
    # CURRICULUM ASSISTANT (Below results)
    # ==========================================
    if curriculum_assistant:
        # Use the same dropdown UI as flipper.py via CurriculumAssistant.render()
        action, text = curriculum_assistant.render(show_topic_table_search=ENABLE_TOPIC_TABLE_SEARCH)
        if action == 'small_step_search' and text:
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
            apply_small_step_selection(text, recommendations_df, curriculum_assistant, lookup_videos_for_step)

    if not results_focus_mode:
        render_landing_demo_frame(recommendations_df)

    # ==========================================
    # NATURAL LANGUAGE TOPIC SEARCH (Flipper Search)
    # ==========================================
    if ENABLE_FLIPPER_SEARCH and curriculum_path.exists():
        from flipper_search.streamlit_ui import render_search_ui

        st.markdown("---")
        embeddings_path = project_root / "data" / "curriculum_embeddings.npy"
        search_result = render_search_ui(
            curriculum_csv_path=str(curriculum_path),
            embeddings_path=str(embeddings_path),
            use_semantic=True,
        )

        if search_result:
            action, result_dict = search_result
            if action == 'small_step_search' and result_dict:
                track_event(
                    "step_selection_applied",
                    {
                        "source": "flipper_search",
                        "small_step": result_dict.get("small_step", ""),
                        "small_step_id": result_dict.get("small_step_id", ""),
                        "topic": result_dict.get("topic", ""),
                        "age": result_dict.get("age", ""),
                    },
                )
                apply_small_step_selection(result_dict, recommendations_df, curriculum_assistant, lookup_videos_for_step)

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
        """)
        if not mobile_viewer_mode:
            st.markdown("""
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
    
        # Add reload data button
        st.markdown("---")
        if st.button("🔄 Reload Data", use_container_width=True, help="Force refresh precomputed recommendations from CSV (cache updates every 5 mins automatically)"):
            st.cache_data.clear()
            st.rerun()
    
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
                const domId = `video-card-${entry.video_id}-${entry.topic}-${entry.small_step}`.replace(/\\s/g, '_').replace(/"/g, '').replace(/'/g, '');
                const card = parentDoc.getElementById(domId);
                if (card) {
                    card.classList.add('video-card-watched');
                }
            });
        }

        // Reduce only step-navigation button footprint in results mode.
        function applyCompactStepNavButtons() {
            const targets = [
                'Back to search',
                '◀  Previous Step',
                'Next Step  ▶',
                '◀  Previous Small Step',
                'Next Small Step  ▶'
            ];
            const buttons = parentDoc.querySelectorAll('button');
            buttons.forEach(btn => {
                const text = (btn.textContent || '').trim();
                const isTarget = targets.some(t => text.includes(t));
                if (isTarget) {
                    btn.style.fontSize = '0.5em';
                    btn.style.padding = '0.12rem 0.35rem';
                    btn.style.minHeight = '1.05rem';
                    btn.style.lineHeight = '1';
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
                const domId = `video-card-${videoId}-${topic}-${smallStep}`.replace(/\\s/g, '_').replace(/"/g, '').replace(/'/g, '');
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
            applyCompactStepNavButtons();
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
        Registered in Scotland, Edinburgh<br>
        John.Brown@flipper.school
    </div>
    """, unsafe_allow_html=True)


if __name__ == '__main__':
    main()
