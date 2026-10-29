# Flipper Lite — UX Specification

**Version:** 0.1 (pre-implementation)  
**Date:** May 2026

---

## 1. Overview

This spec covers all planned UX changes to `flipper_lite.py`. Changes are grouped into
three tracks that can be implemented independently or in sequence:

| Track | Description | Priority |
|-------|-------------|----------|
| A | Mode toggle (Expert vs Sequential) | High |
| B | Sequential navigation controls | High |
| C | Watched-video visual indicators | Medium |
| D | Exercise placeholder and gating design | Low (design only) |

---

## 2. Mode A — Laissez-Faire / Expert Navigation (current behaviour, polished)

### 2.1 Behaviour
- User selects curriculum position via dropdowns: **Year → Term → [Difficulty] → Topic → Small Step**
- On small step selection, up to 3 video cards are displayed instantly (precomputed lookup)
- Video player opens inline on "▶ Watch" click
- No change to core logic required

### 2.2 Potential Polish (optional, low risk)
- Add keyboard shortcut hints to dropdowns for power users
- Persist last-selected small step across page reloads (localStorage)
- "Jump to…" free-text search over small step names (filtered dropdown)

### 2.3 Unchanged elements
- Dropdown hierarchy and CurriculumAssistant render() interface
- Video card layout (thumbnail, gauge, title, channel, duration, scores, justification)
- Inline video player

---

## 3. Mode B — Linear / Sequential Navigation

### 3.1 Concept
The user picks a **starting small step** (using the existing dropdowns) then switches into
a sequential browsing flow. The curriculum becomes a linear tape:

```
← Prev Small Step  |  [Current Small Step]  |  Next Small Step →
                        ← Prev Video  |  Video N of M  |  Next Video →
```

### 3.2 Entry Point
- A **mode toggle** (tab or radio button) appears at the top of the page:
  ```
  [ Expert Mode ]  |  [ Sequential Mode ]
  ```
- In Sequential Mode, the dropdown panel is replaced by a compact position indicator + nav buttons
- The user can still change their starting position by temporarily switching back to Expert Mode,
  then re-entering Sequential Mode from that position

### 3.3 Navigation State (session_state keys)

| Key | Type | Description |
|-----|------|-------------|
| `nav_mode` | str | `'expert'` or `'sequential'` |
| `seq_step_index` | int | Index into the ordered list of all small_step_ids |
| `seq_video_index` | int | 0-based index of current video within the current step (0–2) |
| `seq_all_steps` | list[str] | Ordered list of all `small_step_id` values (curriculum order) |
| `seq_videos_current` | list[dict] | Videos for the current step (rank-ordered) |

### 3.4 Curriculum Order
Small steps are ordered by: Year (numeric) → Term (Autumn < Spring < Summer) → [Difficulty (Foundation < Higher)] → Topic → small_step_num_in_topic.

`seq_all_steps` is built once at load time from `precomputed_recommendations_flat.csv` and cached.

### 3.5 Navigation Controls UI

```
┌─────────────────────────────────────────────────────────────────┐
│  ← Prev Step          [Step N of 847]          Next Step →      │
│  Year 3 · Autumn · Place Value · Partition 3-digit numbers      │
├─────────────────────────────────────────────────────────────────┤
│  ← Prev Video                                   Next Video →    │
│                    Video 1 of 3                                  │
└─────────────────────────────────────────────────────────────────┘
```

- **"Prev Step"** / **"Next Step"** buttons decrement/increment `seq_step_index`, reset `seq_video_index` to 0, reload `seq_videos_current`
- **"Prev Video"** / **"Next Video"** buttons decrement/increment `seq_video_index` within `seq_videos_current`
- Buttons are disabled (greyed) at the curriculum boundaries (first/last step, first/last video)
- The position counter ("Step N of 847") updates on every navigation

### 3.6 Compact Position Indicator
Replaces the full breadcrumb. Displays:
- Step N of total
- Year, Term, Topic, Small Step name (one line, truncated if needed)

### 3.7 Returning to Expert Mode
Switching back to Expert Mode pre-fills the dropdowns with the current sequential position,
so the user can see all videos for that step or jump to a different one.

---

## 4. Watched Video Tracking

### 4.1 Current State
`flipper_lite.py` already writes to `localStorage['flipper_watched_videos']` as an array of
`{video_id, topic, small_step}` objects when a video is played. But this state is not yet
surfaced visually.

### 4.2 Visual Indicators

**On the video card:**
- A green ✓ badge overlaid on the thumbnail (top-right corner, 24×24px circle)
- Subtitle text changes to "Watched · Channel | Duration" (green-tinted channel name)
- Card overall slightly desaturated (already scaffolded via `.video-card-watched` CSS class)

**In Sequential Mode position bar:**
- A small dot or icon alongside each step indicator (if all videos in that step have been watched)
- "Step N of 847 · ✓ Completed" when all videos watched

### 4.3 Persistence
- Cross-session: `localStorage['flipper_watched_videos']` (already implemented)
- In-session: mirror into `st.session_state['watched_videos']` on page load (via JS → component)
- On "▶ Watch" click: immediately add to both session state and localStorage

### 4.4 Reading localStorage Back into Streamlit
Use `streamlit.components.v1.html()` to emit a JS snippet that posts the localStorage value
to `st.session_state` via a hidden `st.text_input` trick or Streamlit's custom component
bidirectional communication pattern.

---

## 5. Exercise Architecture (Design Only — no implementation yet)

### 5.1 Purpose
Optional exercises linked to each small step. In the simplest form: a multiple-choice question.
In future: worked examples, drag-and-drop, etc.

### 5.2 Data Model

**File:** `ux/exercises/<small_step_id>.json`  
**Fallback:** `ux/exercises/default_placeholder.json`

```json
{
  "small_step_id": "Year 3_7-8_Autumn__Place Value_1_Partition a 3-digit number",
  "question": "What is 347 partitioned into hundreds, tens and ones?",
  "type": "multiple_choice",
  "options": [
    {"label": "300 + 40 + 7", "correct": true},
    {"label": "30 + 4 + 7", "correct": false},
    {"label": "347 + 0", "correct": false},
    {"label": "3 + 4 + 7", "correct": false}
  ],
  "hint": "Think about the value of each digit.",
  "explanation": "347 = 3 hundreds + 4 tens + 7 ones = 300 + 40 + 7"
}
```

### 5.3 UI Placement
- Exercise panel appears **below** the video cards within a small step
- Initially collapsed with "📝 Try the exercise" expander
- On correct answer: expander header turns green, "✓ Exercise complete" shown
- State stored: `st.session_state['exercises_complete']` = set of `small_step_id` strings

### 5.4 Gating (configurable)
A global config flag `EXERCISE_GATING_ENABLED` (default `False`).
When `True`: the "Next Small Step" button in Sequential Mode is disabled until the exercise
for the current step is marked complete.

### 5.5 Dependencies
- Exercises are authored separately and placed in `ux/exercises/`
- If no exercise file exists for a step, the exercise panel is hidden (no placeholder shown)
- The system degrades gracefully: gating is skipped if no exercise exists

---

## 6. Open Questions

| # | Question | Decision needed |
|---|----------|----------------|
| 1 | Should mode preference persist across sessions (localStorage)? | Recommend yes |
| 2 | Should sequential position persist across browser sessions? | Recommend yes (localStorage) |
| 3 | Is "Next Step" blocked by exercise gating on first use, or only once exercises exist? | Recommend: only when exercise file exists |
| 4 | Should the expert dropdown remain visible in sequential mode as a "jump to" control? | Recommend: hidden by default, expandable |
| 5 | Maximum videos per small step currently 3 — is this always sufficient? | Recommend: keep 3, revisit if content grows |
| 6 | Watched tracking: track per (video_id, small_step_id) or per video_id globally? | Recommend: per (video_id, small_step_id) for accuracy |

---

## 7. Interaction Flow Diagrams

### Expert Mode (Mode A)
```
Load page
  └─ Select Year
       └─ Select Term
            └─ [Select Difficulty if secondary]
                 └─ Select Topic
                      └─ Select Small Step
                           └─ Video cards displayed
                                └─ Click ▶ Watch → inline player
                                     └─ Close player → back to cards
```

### Sequential Mode (Mode B)
```
Load page
  └─ Toggle to Sequential Mode
       └─ (First time) Prompt: "Choose your starting point" → Expert dropdowns
            └─ Select small step → Enter sequential mode at that position
                 └─ Video 1 of N displayed
                      ├─ Click ▶ Watch → inline player → marked as watched
                      ├─ Click Next Video → Video 2 of N
                      └─ Click Next Step → advance to next small_step_id
                           └─ (if gating ON and exercise not complete) → blocked
```

---

## 8. Acceptance Criteria (per track)

### Track A (Mode toggle)
- [ ] Mode toggle visible at top of page
- [ ] Switching mode does not clear currently displayed videos
- [ ] Mode preference saved to localStorage

### Track B (Sequential navigation)
- [ ] "Next Step" / "Prev Step" advance curriculum position correctly
- [ ] "Next Video" / "Prev Video" cycle within step's ranked videos
- [ ] Boundary conditions: buttons disabled at start/end of curriculum
- [ ] Position indicator shows "Step N of total" and breadcrumb

### Track C (Watched indicators)
- [ ] ✓ badge appears on thumbnail of watched videos
- [ ] Badge persists on page reload (from localStorage)
- [ ] Watched state updates immediately on "▶ Watch" click

### Track D (Exercise design)
- [ ] Exercise data model documented and validated by example JSON
- [ ] Exercise panel renders without error when JSON file present
- [ ] Gating flag documented and toggleable
