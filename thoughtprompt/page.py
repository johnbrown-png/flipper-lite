"""Thought prompt full-screen page for Flipper Lite.

Invoked from flipper_lite.py only when the learner presses
"Try Thought Prompt" (``st.session_state.showing_thought_prompt``).
All thought prompt session state, prompt loading, TTS, visuals routing and
the educator view live here so the main app file stays lean.
"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from shared.analytics import track_event
from thoughtprompt.number_line import (
    INTERACTIVE_NUMBER_LINE_ENABLED,
    render_interactive_number_line_prompt,
)

project_root = Path(__file__).parent.parent

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


def init_thought_prompt_state():
    """Initialize thought prompt session-state keys (idempotent)."""
    if 'showing_thought_prompt' not in st.session_state:
        st.session_state.showing_thought_prompt = False
    if 'tp_current_variant' not in st.session_state:
        st.session_state.tp_current_variant = 1
    if 'tp_responses' not in st.session_state:
        st.session_state.tp_responses = []
    if 'tp_active_small_step' not in st.session_state:
        st.session_state.tp_active_small_step = None


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
    init_thought_prompt_state()

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
        render_interactive_number_line_prompt(
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
