"""Interactive draggable number line for thought prompts.

Single live implementation: a self-contained HTML/JS widget rendered via
``streamlit.components.v1.html``. (The earlier ``ux/number_line_widget.py``
wrapper around ``draggable_number_line.html`` was never called by
flipper_lite.py — it was imported only as a feature flag — so this module is
now the one parsimonious implementation used by the thought prompt page.)
"""

import json
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

from shared.analytics import track_event

# The widget below has no optional dependencies, so it is always available.
INTERACTIVE_NUMBER_LINE_ENABLED = True


def build_interactive_number_line_html(start, end, correct_answer, tolerance, interval, title, question):
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


def render_interactive_number_line_prompt(current_prompt, small_step_num, current_variant, current_video, difficulty):
    """Render the interactive draggable number line widget for step 382 variant 1."""
    params = json.loads(current_prompt['visual_params'])
    start = int(params.get('start', 6000))
    end = int(params.get('end', 7000))
    correct_answer = 6500
    tolerance = int(params.get('tolerance', 100))
    interval_value = int(params.get('interval', 100))
    question = current_prompt['prompt_text']
    title = current_prompt['small_step_name']

    # Build and render the self-contained widget HTML
    widget_html = build_interactive_number_line_html(
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
                process_number_line_answer(
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


def process_number_line_answer(submitted_value, correct_answer, tolerance, small_step_num, current_variant, current_video, difficulty, current_prompt):
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
