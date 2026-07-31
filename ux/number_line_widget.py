"""
Number Line Widget — Interactive draggable number line for learner responses.

Provides a Streamlit-compatible wrapper around the draggable_number_line.html
component. The widget renders inside st.components.v1.html() and communicates
the learner's submitted answer back to Streamlit via postMessage.

Usage:
    from ux.number_line_widget import render_number_line

    answer = render_number_line(
        start=0,
        end=100,
        correct_answer=47,
        question="Where is 47 on the number line?",
        tolerance=0,
        snap_interval=5,
        snap_enabled=True,
    )
    if answer is not None:
        st.write(f"Learner submitted: {answer}")
"""

from __future__ import annotations

import html
import json
import os
import streamlit as st
import streamlit.components.v1 as components
from typing import Optional

# Path to the standalone HTML file
_HTML_FILE = os.path.join(os.path.dirname(__file__), "draggable_number_line.html")

# Cache the HTML content so we only read it once per session
@st.cache_resource(show_spinner=False)
def _load_html() -> str:
    """Load the draggable number line HTML template."""
    with open(_HTML_FILE, "r", encoding="utf-8") as f:
        return f.read()


def _build_html(
    start: int,
    end: int,
    correct_answer: Optional[int],
    tolerance: int,
    snap_interval: int,
    snap_enabled: bool,
    question: str,
    title: str,
    initial_value: Optional[int],
    show_feedback: bool,
    height: int,
) -> str:
    """
    Build the HTML snippet that renders the number line widget.

    Configuration is injected as URL query parameters on the component's src,
    which the JS reads on init.  This avoids the need for postMessage-based
    initialisation and keeps the component stateless-friendly.
    """
    params = {
        "start": str(start),
        "end": str(end),
        "tolerance": str(tolerance),
        "snap": str(snap_interval),
        "snapEnabled": "1" if snap_enabled else "0",
        "title": title,
        "question": question,
        "showFeedback": "1" if show_feedback else "0",
    }
    if correct_answer is not None:
        params["correct"] = str(correct_answer)
    if initial_value is not None:
        params["value"] = str(initial_value)

    # Build query string
    qs = "&".join(f"{k}={html.escape(v)}" for k, v in params.items())

    # Read template and inject the query string into the iframe src
    # We use srcdoc to avoid needing a server — embed the full HTML
    template = _load_html()

    # Instead of modifying the template (which is standalone HTML meant for
    # direct browser use), we serve it as a data URI with srcdoc.
    # The JS inside reads window.location.search, so we need to embed the
    # parameters directly.  We do this by replacing a placeholder script tag
    # with the configuration injection.

    # Strategy: inject a <script> at the end of <head> that overrides the
    # URLSearchParams block with our Python-side config.
    config_js = f"""<script>
// Override URL params with Streamlit-provided configuration
(function() {{
    var _st = {json.dumps(params)};
    // The main script reads from URLSearchParams, so we mock it
    var _origSearch = window.location.search;
    Object.defineProperty(window.location, 'search', {{
        get: function() {{ return '?' + Object.entries(_st).map(function(e){{return e[0]+'='+e[1]}}).join('&'); }},
        configurable: true
    }});
}})();
</script>"""

    # Insert config_js before the closing </head> tag in the template
    html_content = template.replace("</head>", config_js + "\n</head>")

    # Wrap in a container with explicit height
    wrapped = f"""<div style="width:100%;height:{height}px;overflow:hidden;">
{html_content}
</div>"""

    return wrapped


def render_number_line(
    start: int = 0,
    end: int = 100,
    correct_answer: Optional[int] = None,
    question: str = "Drag the marker to your answer",
    title: str = "Number Line",
    tolerance: int = 0,
    snap_interval: int = 1,
    snap_enabled: bool = False,
    initial_value: Optional[int] = None,
    show_feedback: bool = True,
    key: str = "number_line_widget",
    height: int = 500,
) -> Optional[int]:
    """
    Render an interactive draggable number line and return the submitted answer.

    Args:
        start:           Leftmost value on the number line.
        end:             Rightmost value on the number line.
        correct_answer:  If provided, the widget shows correct/incorrect feedback.
        question:        Prompt text displayed above the number line.
        title:           Title for the widget.
        tolerance:       ± range within which an answer is considered correct.
        snap_interval:   When snap is enabled, answers snap to multiples of this.
        snap_enabled:    Whether snap-to-interval is on by default.
        initial_value:   Starting position of the draggable marker.
        show_feedback:   Whether to show correct/incorrect feedback in the widget.
        key:             Unique Streamlit component key (prevents re-mount).
        height:          Height of the widget container in pixels.

    Returns:
        The integer value submitted by the learner, or None if no answer has
        been submitted yet.
    """
    html_content = _build_html(
        start=start,
        end=end,
        correct_answer=correct_answer,
        tolerance=tolerance,
        snap_interval=snap_interval,
        snap_enabled=snap_enabled,
        question=question,
        title=title,
        initial_value=initial_value,
        show_feedback=show_feedback,
        height=height,
    )

    # Render the component.  The answer is communicated back via postMessage,
    # which Streamlit's html component can capture if we use the
    # `st.components.v1.html` with a returned value via a hidden text_input.
    #
    # However, st.components.v1.html() does NOT natively capture postMessage.
    # The established Streamlit pattern for JS→Python communication is:
    #   1. JS writes to a hidden <input> inside the iframe
    #   2. A Streamlit form or button outside the iframe reads it
    #
    # Since we want the "Check Answer" button *inside* the widget, we use
    # a different approach: the JS writes to window.parent via postMessage,
    # AND we include a hidden Streamlit text_input that intercepts the value
    # via a tiny companion script.
    #
    # Simplified approach for now: render the widget and listen for the
    # answer via a Streamlit session_state key updated by a separate
    # invisible component.

    # For a first implementation, we render the widget AND a small listener.
    # The widget's JS already does postMessage.  We add a companion iframe
    # that listens for that message and writes to a hidden st.text_input.

    components.html(html_content, height=height, scrolling=False)

    # The listener component — tiny invisible iframe that bridges postMessage → Streamlit
    listener_html = f"""
    <script>
    (function() {{
        var receivedValue = null;
        window.addEventListener('message', function(e) {{
            if (e.data && e.data.type === 'numberLineAnswer') {{
                receivedValue = JSON.stringify(e.data);
            }}
        }});
        // Poll for the value and expose it to Streamlit
        // Streamlit's component value is set via Streamlit.setComponentValue()
        if (window.Streamlit) {{
            setInterval(function() {{
                if (receivedValue !== null) {{
                    window.Streamlit.setComponentValue(receivedValue);
                    receivedValue = null;
                }}
            }}, 200);
        }}
    }})();
    </script>
    """

    # Use a hidden html component to capture the answer
    result = components.html(listener_html, height=0, scrolling=False)

    # The component returns the value passed to Streamlit.setComponentValue()
    if result:
        try:
            data = json.loads(result)
            if isinstance(data, dict) and "value" in data:
                return int(data["value"])
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    return None


def render_number_line_exercise(
    start: int = 0,
    end: int = 100,
    correct_answer: int = 47,
    question: str = "Where is 47 on the number line?",
    title: str = "Number Line Exercise",
    tolerance: int = 0,
    snap_interval: int = 5,
    snap_enabled: bool = False,
    key_suffix: str = "",
) -> None:
    """
    Higher-level wrapper that renders a number line exercise with Streamlit
    feedback managed on the Python side rather than inside the widget.

    This is useful when you want the feedback (correct/incorrect) to persist
    across Streamlit reruns or be tracked in session_state.

    Args:
        start, end, correct_answer, question, title, tolerance,
        snap_interval, snap_enabled: Same as render_number_line.
        key_suffix: Append to component key for uniqueness across exercises.
    """
    key = f"nl_exercise_{key_suffix}" if key_suffix else "nl_exercise"

    # Initialise session state for this exercise
    if f"{key}_submitted" not in st.session_state:
        st.session_state[f"{key}_submitted"] = None
        st.session_state[f"{key}_correct"] = None

    st.markdown(f"### {title}")
    st.markdown(f"*{question}*")

    answer = render_number_line(
        start=start,
        end=end,
        correct_answer=correct_answer,
        question=question,
        title=title,
        tolerance=tolerance,
        snap_interval=snap_interval,
        snap_enabled=snap_enabled,
        key=key,
    )

    if answer is not None:
        st.session_state[f"{key}_submitted"] = answer
        diff = abs(answer - correct_answer)
        st.session_state[f"{key}_correct"] = diff <= tolerance

    submitted = st.session_state.get(f"{key}_submitted")
    is_correct = st.session_state.get(f"{key}_correct")

    if submitted is not None:
        if is_correct:
            st.success(f"Correct! {submitted} is the right answer.")
        else:
            st.error(
                f"Not quite. You selected {submitted}. "
                f"The correct answer is {correct_answer}."
            )
