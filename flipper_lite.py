"""
Flipper Lite - Lightweight Curriculum Video Browser

A simple web interface for teachers to browse precomputed curriculum-aligned
educational videos without runtime semantic search or LLM operations.
"""

import sys
import re
import hashlib
from pathlib import Path

# Add search_app to path for curriculum assistant import
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from search_app.curriculum_assistant import CurriculumAssistant

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import html
import textwrap

from shared.circular_progress import create_circular_progress_svg
from shared.curriculum_schema import normalize_precomputed_df
from shared.analytics import init_analytics, track_event
from shared.email_sender import send_video_recommendations_email
from shared.step_selection import (
    apply_pending_selector_sync,
    apply_small_step_selection,
    render_selection_debug_panel,
)
from shared.ui_terminology import VIDEO_CARDS_LABEL

# Thought prompt subsystem (page, interactive number line, visuals, educator
# view) lives in thoughtprompt/ and is only rendered when the learner presses
# "Try Thought Prompt" (st.session_state.showing_thought_prompt).
from thoughtprompt.page import (
    THOUGHT_PROMPTS_ENABLED,
    init_thought_prompt_state,
    render_thought_prompt_page,
    should_show_thought_prompt_button,
)

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

# Age dropdown styling (visible 'Learner age' label and 44px height) is
# handled inside CurriculumAssistant.render(), shared with flipper.py.

# Page-wide CSS lives in a static asset (shared/styles/flipper_lite.css) to keep
# this file lean; inject it here at startup.
_css_path = project_root / "shared" / "styles" / "flipper_lite.css"
if _css_path.exists():
    st.markdown(f"<style>{_css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


@st.cache_data(ttl=300)  # Cache for 5 minutes; file changes detected immediately via mtime
def load_precomputed_recommendations_flat():
    """Load precomputed curriculum recommendations CSV.
    
    Cache expires every 5 minutes to pick up updates from precompute_curriculum_recommendations.py runs.
    File modification time is automatically included in Streamlit's cache key.
    """
    qa_csv_path = project_root / 'precomputed_recommendations_flat_qa.csv'
    base_csv_path = project_root / 'precomputed_recommendations_flat.csv'
    load_errors = []

    for csv_path in (qa_csv_path, base_csv_path):
        if not csv_path.exists():
            continue
        try:
            df = pd.read_csv(csv_path)
            if df.empty or len(df.columns) == 0:
                raise pd.errors.EmptyDataError("file contains no recommendation data")
            return normalize_precomputed_df(df)
        except (pd.errors.EmptyDataError, pd.errors.ParserError, OSError) as e:
            load_errors.append(f"{csv_path.name}: {e}")

    detail = "; ".join(load_errors) if load_errors else "no recommendation CSV found"
    st.error(f"Error loading precomputed recommendations: {detail}")
    return None


@st.cache_data(ttl=300)  # Cache for 5 minutes for consistency
def load_video_inventory():
    """
    DEPRECATED: Channel and duration now included in precomputed_recommendations_flat.csv
    This function exists for backward compatibility but is no longer needed.
    """
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


_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _is_valid_email(value):
    return bool(_EMAIL_PATTERN.match(str(value).strip()))


def render_email_recommendations_popover(ctx):
    """Popover letting a visitor email themselves the current top 3 video links.

    The address is used only for this one transactional send; only a
    one-way SHA-256 hash of it is ever passed to analytics (see track_event
    call below), so no plaintext email is stored in Flipper's own systems.
    """
    videos = st.session_state.get('display_results', [])[:3]
    if not videos:
        return

    step_label_parts = []
    if ctx:
        if ctx.get('topic'):
            step_label_parts.append(str(ctx['topic']))
        if ctx.get('small_step'):
            step_label_parts.append(str(ctx['small_step']))
    step_label = " - ".join(step_label_parts) if step_label_parts else "your selected step"
    small_step_desc = str(ctx.get('small_step_desc') or '').strip() if ctx else ""

    feedback_key = "email_recs_feedback"

    with st.popover("✉️ Email me these", use_container_width=True):
        st.markdown("**Get these 3 video links by email**")
        email_value = st.text_input(
            "Your email address",
            key="email_recs_input",
            placeholder="you@example.com",
        )
        consent = st.checkbox(
            "Send me these video links by email. My address is used only to send this one email and is not stored.",
            key="email_recs_consent",
        )
        if st.button("Send email", key="email_recs_send", type="primary"):
            email_clean = email_value.strip()
            if not consent:
                st.session_state[feedback_key] = ("error", "Please tick the consent box to continue.")
            elif not _is_valid_email(email_clean):
                st.session_state[feedback_key] = ("error", "Please enter a valid email address.")
            else:
                success, err = send_video_recommendations_email(email_clean, step_label, small_step_desc, videos)
                email_hash = hashlib.sha256(email_clean.lower().encode("utf-8")).hexdigest()
                track_event(
                    "email_recommendations_requested",
                    {
                        "email_hash": email_hash,
                        "send_status": "sent" if success else "failed",
                        "video_count": len(videos),
                        "small_step": ctx.get("small_step", "") if ctx else "",
                        "small_step_id": ctx.get("small_step_id", "") if ctx else "",
                        "topic": ctx.get("topic", "") if ctx else "",
                        "age": ctx.get("age", "") if ctx else "",
                    },
                )
                if success:
                    st.session_state[feedback_key] = ("success", "Sent! Check your inbox (and spam folder).")
                else:
                    st.session_state[feedback_key] = ("error", f"Could not send email: {err}")

        feedback = st.session_state.get(feedback_key)
        if feedback:
            level, message = feedback
            if level == "success":
                st.success(message)
            else:
                st.error(message)


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
        cards.append(textwrap.dedent(
            f"""
            <article class="landing-demo-card">
                <div class="landing-demo-thumbnail">
                    <img src="https://img.youtube.com/vi/{video_id}/hqdefault.jpg" alt="YouTube video thumbnail: {title}">
                    <span class="landing-demo-play" aria-hidden="true">▶</span>
                </div>
                <div class="landing-demo-card-body">
                    <h3>{title}</h3>
                </div>
            </article>
            """
        ))

    st.markdown(
        textwrap.dedent(f"""
        <section class="landing-demo-frame" aria-label="Three example video suggestions">
            <div class="landing-demo-heading">
                <div>
                    <p class="landing-demo-eyebrow">What you get</p>
                    <h2>Three great videos for every White Rose Small Step</h2>
                </div>
                <p class="landing-demo-context"><strong>Age 5-6</strong> <span aria-hidden="true">·</span> Autumn <span aria-hidden="true">·</span> Place value within 10 <span aria-hidden="true">·</span> Sort objects</p>
            </div>
            <div class="landing-demo-cards">{''.join(cards)}</div>
        </section>
        <style>
            .landing-demo-frame {{
                min-height: clamp(360px, 50vh, 560px);
                margin: 0rem 0 2rem;
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
                gap: 4rem;
                max-width: 900px;
                margin: 0 auto;
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
                filter: grayscale(0.35) saturate(0.65) brightness(1.02);
                transition: filter 0.2s ease;
            }}
            .landing-demo-thumbnail img:hover {{
                filter: none;
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
        """),
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
                    font-size: 2.6rem;
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
                    font-size: 1.2rem;
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
                margin-top: 0rem;
                margin-bottom: 0rem;
                font-weight: 400;
            ">The best Maths videos on YouTube, transcript matched to a world leading curriculum, for each lesson from age 5 to 15
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

    # Initialize thought prompt session state (defined in thoughtprompt/page.py)
    init_thought_prompt_state()
    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = "Learning View"

    # Apply deferred selector-widget key sync before selector widgets instantiate.
    apply_pending_selector_sync()

    # ==========================================
    # Educator view temporarily removed - will be re-added as educator results page
    # (render_educator_view lives in thoughtprompt/page.py)
    # ==========================================
    # render_educator_view()

    # Normal learning view continues below (rest of the function)
    # (the full-screen thought prompt check already ran at the top of main())

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
                        brand_col, email_col, nav_home_col, nav_back_col, nav_next_col = st.columns([6.5, 1.3, 1.3, 1.35, 1.35])
                    else:
                        brand_col, email_col = st.columns([8.5, 1.5])

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

                    with email_col:
                        render_email_recommendations_popover(ctx)

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

                                st.session_state.curr_year = 'Learner\'s Age?'
                                st.session_state.year_select_topic_search = 'Learner\'s Age?'
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

                        st.session_state.curr_year = 'Learner\'s Age?'
                        st.session_state.year_select_topic_search = 'Learner\'s Age?'
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
                    "selection_source": text.get("selection_source", "selector"),
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
