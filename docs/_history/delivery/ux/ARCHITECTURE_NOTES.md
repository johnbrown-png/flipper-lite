# Flipper Lite — UX Architecture Notes

**Version:** 0.1  
**Date:** May 2026  
**Audience:** Developer implementing UX changes to `flipper_lite.py`

---

## 1. Technology Constraints

`flipper_lite.py` is a **Streamlit** app. Key architectural facts that govern all UX decisions:

- **No persistent server state.** Every user interaction triggers a Python re-run from the top of the script. All state must be in `st.session_state`.
- **No WebSockets / bidirectional JS.** The only bridge between JavaScript and Python is through Streamlit's component API (`streamlit.components.v1`). Reading from `localStorage` into Python requires a workaround (see §4).
- **Single-page app.** There is no routing. Different "views" are achieved by conditional rendering based on `st.session_state` flags.
- **Streamlit rerun model.** Calling `st.rerun()` restarts execution from line 1. All intermediate state that has not been written to `session_state` before the rerun is lost.

---

## 2. Session State Design

All navigation state lives in `st.session_state`. Keys are initialized in `main()` before any rendering.

### 2.1 Existing Keys (do not rename)

| Key | Type | Purpose |
|-----|------|---------|
| `viewing_video` | bool | Legacy flag (now superseded by `current_video`) |
| `current_video` | dict\|None | Video currently shown in inline player |
| `curriculum_expanded` | bool | Whether curriculum assistant is expanded |
| `display_status` | str | `'idle'`, `'loading'`, `'complete'` |
| `display_results` | list[dict] | Video cards to render |
| `display_step_name` | str | Name of currently selected small step |
| `curriculum_context` | dict\|None | Full context dict from CurriculumAssistant |

### 2.2 New Keys to Add (UX subproject)

| Key | Type | Initial Value | Purpose |
|-----|------|---------------|---------|
| `nav_mode` | str | `'expert'` | `'expert'` or `'sequential'` |
| `seq_all_steps` | list[str] | `[]` | Ordered `small_step_id` list (built once) |
| `seq_step_index` | int | `0` | Current position in `seq_all_steps` |
| `seq_video_index` | int | `0` | Current video index (0-based) within step |
| `seq_videos_current` | list[dict] | `[]` | Videos for current sequential step |
| `watched_videos` | set[str] | `set()` | Set of `"video_id::small_step_id"` strings |
| `exercises_complete` | set[str] | `set()` | Set of completed `small_step_id` strings |

> **Note on `watched_videos` key format:** Use `"video_id::small_step_id"` (double colon separator) to ensure uniqueness across contexts. This matches the existing localStorage format's intent but uses a stable composite key.

---

## 3. Curriculum Ordering

### 3.1 Building `seq_all_steps`

Load `precomputed_recommendations_flat.csv` once. Deduplicate by `small_step_id`, then sort by:

```python
df_steps = df.drop_duplicates(subset=['small_step_id']).copy()

# Map term to sort order
term_order = {"autumn": 1, "spring": 2, "summer": 3}
df_steps['_term_order'] = df_steps['term'].str.lower().map(term_order).fillna(99)

# Map difficulty (blank/Foundation=1, Higher=2)
def difficulty_order(d):
    d = str(d).strip().lower()
    if d == 'higher': return 2
    return 1
df_steps['_diff_order'] = df_steps['difficulty'].apply(difficulty_order)

# Year as numeric (extract first number from e.g. "Year 3")
import re
def year_num(y):
    m = re.search(r'\d+', str(y))
    return int(m.group()) if m else 99
df_steps['_year_num'] = df_steps['year'].apply(year_num)

# small_step_num_in_topic as numeric (if present)
df_steps['_step_num'] = pd.to_numeric(
    df_steps.get('small_step_num_in_topic', pd.Series(dtype=str)),
    errors='coerce'
).fillna(0)

df_steps = df_steps.sort_values([
    '_year_num', '_term_order', '_diff_order', 'topic', '_step_num', 'small_step'
])

seq_all_steps = df_steps['small_step_id'].tolist()
```

Cache this in `st.session_state['seq_all_steps']` after first build (it is derived from the cached DataFrame).

### 3.2 Looking Up Videos for a Step Index

```python
step_id = st.session_state.seq_all_steps[st.session_state.seq_step_index]
videos = df[df['small_step_id'] == step_id].sort_values('rank').to_dict('records')
st.session_state.seq_videos_current = videos
```

---

## 4. localStorage ↔ Streamlit Bridge

### 4.1 Writing to localStorage (already working)
The existing `components.html(...)` block writes watched video data to localStorage.
The pattern: inject JS that runs in the iframe context, accesses `window.parent.document` to
find elements or posts messages.

### 4.2 Reading from localStorage into session_state

**Recommended pattern — URL query parameter trick (simplest for Streamlit):**

On first load, inject JS that reads localStorage and sets a query parameter, triggering a rerun.
However, this can cause reload loops. A safer approach:

**Recommended pattern — hidden `st.text_input` + JS setValue:**

1. Render a hidden `st.text_input` (label hidden via CSS, `label_visibility='collapsed'`)
2. JS reads localStorage and sets the input value via DOM manipulation
3. On `st.session_state` the value is available after the next user interaction or rerun

**Simplest safe approach for watched videos:**

Because Streamlit re-runs on every interaction, initialise `watched_videos` in `session_state`
as empty on fresh session start, then sync from localStorage only once per session using a
one-shot JS component:

```python
if 'watched_synced' not in st.session_state:
    st.session_state.watched_synced = False
    st.session_state.watched_videos = set()

if not st.session_state.watched_synced:
    # Render a one-shot JS component that posts watched IDs via query params
    # This is the only reliable sync point
    pass  # Implementation detail: see Streamlit community patterns
```

For the initial implementation, accept that watched state is **write-only cross-session**
(localStorage stores it) and **read-only within session** (displayed from session_state).
Full bidirectional sync is a v2 concern.

---

## 5. Mode Toggle UI

Place the mode toggle **above** the results area, below the header:

```python
nav_mode = st.radio(
    "Navigation mode",
    options=["Expert", "Sequential"],
    horizontal=True,
    key="nav_mode_radio",
    label_visibility="collapsed"
)
st.session_state.nav_mode = nav_mode.lower()
```

Or use `st.tabs(["🔍 Expert", "▶ Sequential"])` for a more prominent visual treatment.

---

## 6. Sequential Mode Rendering

The sequential navigation block replaces the CurriculumAssistant dropdown block when `nav_mode == 'sequential'`.

**Structure:**

```python
if st.session_state.nav_mode == 'sequential':
    render_sequential_navigator(recommendations_df)
else:
    # existing CurriculumAssistant.render() block
    ...
```

**`render_sequential_navigator(df)` responsibilities:**
1. Ensure `seq_all_steps` is populated (build if not)
2. Display compact position indicator (Step N of M, breadcrumb)
3. Render Prev Step / Next Step buttons (cols layout)
4. Render Prev Video / Next Video buttons (cols layout)  
5. Render current video card (`render_result_card(current_video)`)

---

## 7. Watched Video Badge

In `render_result_card(result)`, check if the video is watched:

```python
composite_key = f"{result['video_id']}::{result.get('small_step_id', result.get('small_step', ''))}"
is_watched = composite_key in st.session_state.get('watched_videos', set())
```

If watched, overlay the ✓ badge via HTML in the thumbnail `<div>`:

```html
<div style="position:absolute; top:6px; right:6px; 
     background:#22c55e; color:white; border-radius:50%;
     width:24px; height:24px; display:flex; align-items:center;
     justify-content:center; font-size:14px; font-weight:bold;
     box-shadow:0 1px 3px rgba(0,0,0,0.3);">✓</div>
```

And add the `video-card-watched` CSS class to the container (already defined in the stylesheet).

---

## 8. Exercise Panel

In `render_result_card` or in a dedicated section below all cards:

```python
exercise = load_exercise(small_step_id)  # returns dict or None
if exercise:
    with st.expander("📝 Try the exercise"):
        render_exercise(exercise, small_step_id)
```

`load_exercise` reads from `ux/exercises/<small_step_id>.json` (sanitise the filename).
If file not found, returns `None` and the expander is not shown.

---

## 9. File Structure for New Code

Prefer keeping changes in `flipper_lite.py` directly for small additions.
For larger additions (exercise rendering, sequential navigator), create helper modules:

```
ux/
  navigator.py          ← render_sequential_navigator(), build_step_order()
  exercise_panel.py     ← load_exercise(), render_exercise()
  watched_tracker.py    ← watched state helpers
  exercises/
    <small_step_id>.json
```

Import from `flipper_lite.py`:
```python
from ux.navigator import render_sequential_navigator, build_step_order
from ux.exercise_panel import load_exercise, render_exercise
```

---

## 10. Testing Approach

Since this is a Streamlit app, automated testing is limited. Recommended approach:
- Manual walkthrough with a checklist (see `ux/UX_SPEC.md §8 Acceptance Criteria`)
- Test at curriculum boundaries: first small step (Year 1, Autumn, Step 1) and last step
- Test mode switching mid-session to confirm state is preserved
- Test with `localStorage` cleared to confirm graceful first-run behaviour
- Test on mobile viewport (Chrome DevTools) to confirm layout
