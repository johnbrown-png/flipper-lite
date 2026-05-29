"""Shared selection and navigation orchestration for Flipper UIs."""

import pandas as pd
import streamlit as st


ENABLE_SELECTION_DEBUG_PANEL = False


def resolve_small_step_context(selection_payload, curriculum_assistant):
    """Build a contract-aligned curriculum context from any step selection payload."""
    source = selection_payload or {}
    selection_source = str(source.get('selection_source', '')).strip() or 'unknown'

    selected_step_name = str(
        source.get('small_step')
        or source.get('small_step_name')
        or source.get('display_text')
        or ''
    ).strip()

    full_ctx = None
    if curriculum_assistant and curriculum_assistant.df is not None:
        df = curriculum_assistant.df
        row_match = pd.DataFrame()
        selected_sid = str(source.get('small_step_id', '')).strip()

        if selected_sid and 'small_step_id' in df.columns:
            row_match = df[df['small_step_id'].astype(str).str.strip() == selected_sid]

        if row_match.empty:
            candidate_step_name = str(source.get('small_step_name') or source.get('small_step') or '').strip()
            fallback_mask = (
                (df['year'].astype(str).str.strip() == str(source.get('year', '')).strip())
                & (df['term'].astype(str).str.strip() == str(source.get('term', '')).strip())
                & (df['topic'].astype(str).str.strip() == str(source.get('topic', '')).strip())
                & (df['small_step_name'].astype(str).str.strip() == candidate_step_name)
            )
            diff_val = str(source.get('difficulty', '')).strip()
            if diff_val:
                fallback_mask &= (df['difficulty'].astype(str).str.strip() == diff_val)
            row_match = df[fallback_mask]

        if not row_match.empty:
            row = row_match.iloc[0]
            full_ctx = {
                'action': 'small_step_search',
                'selection_source': selection_source,
                'year': row.get('year', source.get('year', '')),
                'term': row.get('term', source.get('term', '')),
                'difficulty': row.get('difficulty', source.get('difficulty', '')),
                'topic': row.get('topic', source.get('topic', '')),
                'small_step': row.get('small_step_name', selected_step_name),
                'small_step_desc': row.get('ss_desc', source.get('small_step_desc', source.get('ss_desc', ''))),
                'small_step_full_desc': row.get('ss_wr_desc', source.get('small_step_full_desc', source.get('ss_wr_desc', ''))),
                'small_step_id': row.get('small_step_id', source.get('small_step_id', '')),
                'small_step_num': int(row.get('small_step_num', 0)) if pd.notna(row.get('small_step_num', None)) else 0,
                'small_step_num_in_topic': int(row.get('small_step_num_in_topic', -1)) if pd.notna(row.get('small_step_num_in_topic', None)) else -1,
                'age': row.get('age', source.get('age', '')),
                'display_text': selected_step_name,
            }

    if full_ctx is None:
        full_ctx = {
            'action': 'small_step_search',
            'selection_source': selection_source,
            'age': source.get('age', ''),
            'year': source.get('year', ''),
            'term': source.get('term', ''),
            'difficulty': source.get('difficulty', ''),
            'topic': source.get('topic', ''),
            'small_step': selected_step_name,
            'small_step_desc': source.get('small_step_desc', source.get('ss_desc', '')),
            'small_step_full_desc': source.get('small_step_full_desc', source.get('ss_wr_desc', '')),
            'small_step_id': source.get('small_step_id', ''),
            'display_text': selected_step_name,
        }

    return full_ctx, selected_step_name


def apply_pending_selector_sync():
    """Apply deferred selector-widget key sync before selector widgets render."""
    pending_selector_sync = st.session_state.get('pending_selector_sync')
    if not isinstance(pending_selector_sync, dict):
        return

    sync_age = str(pending_selector_sync.get('age', '')).strip()
    sync_diff = str(pending_selector_sync.get('difficulty', '')).strip()
    sync_topic = str(pending_selector_sync.get('topic', '')).strip() or 'Topic ?'

    if sync_age:
        st.session_state.curr_year = sync_age
        st.session_state.year_select_topic_search = sync_age

    if sync_age in ['14-15', '15-16']:
        if sync_diff not in ['Foundation', 'Higher']:
            sync_diff = 'All'
        st.session_state.curr_difficulty = sync_diff
        st.session_state.difficulty_select_topic_search = sync_diff
    else:
        st.session_state.curr_difficulty = 'All'
        st.session_state.difficulty_select_topic_search = 'All'

    st.session_state.curr_topic = sync_topic
    st.session_state.topic_select_topic_search = sync_topic
    st.session_state.pending_selector_sync = None


def render_selection_debug_panel(curriculum_assistant, enabled=ENABLE_SELECTION_DEBUG_PANEL):
    """Temporary panel to inspect payload shape and nav eligibility conditions."""
    if not enabled:
        return

    raw_ctx = st.session_state.get('curriculum_context')
    ctx = raw_ctx if isinstance(raw_ctx, dict) else {}
    payload_keys = sorted(ctx.keys())

    assistant_ready = bool(curriculum_assistant and curriculum_assistant.df is not None)
    has_context = bool(ctx)
    has_age = bool(str(ctx.get('age', '')).strip())
    has_topic = bool(str(ctx.get('topic', '')).strip())
    has_small_step_id = bool(str(ctx.get('small_step_id', '')).strip())
    has_small_step_num_in_topic = ctx.get('small_step_num_in_topic') is not None
    has_display_results = bool(st.session_state.get('display_results'))
    display_is_complete = st.session_state.get('display_status') == 'complete'

    can_attempt_adjacent = assistant_ready and has_context and has_small_step_num_in_topic
    prev_step = None
    next_step = None
    if can_attempt_adjacent:
        try:
            prev_step, next_step = curriculum_assistant.get_adjacent_steps(ctx)
        except Exception:
            prev_step, next_step = None, None

    adjacent_resolved = bool(prev_step or next_step)
    show_step_nav_now = bool(display_is_complete and has_display_results and adjacent_resolved)

    with st.expander("Temporary Selection Debug", expanded=False):
        st.caption("Live payload keys and step-navigation eligibility")
        st.write(f"selection_source: {ctx.get('selection_source', 'unknown')}")
        st.json(
            {
                'payload_keys': payload_keys,
                'nav_eligibility': {
                    'assistant_ready': assistant_ready,
                    'has_context': has_context,
                    'has_age': has_age,
                    'has_topic': has_topic,
                    'has_small_step_id': has_small_step_id,
                    'has_small_step_num_in_topic': has_small_step_num_in_topic,
                    'display_is_complete': display_is_complete,
                    'has_display_results': has_display_results,
                    'can_attempt_adjacent': can_attempt_adjacent,
                    'adjacent_resolved': adjacent_resolved,
                    'has_prev_step': bool(prev_step),
                    'has_next_step': bool(next_step),
                    'show_step_nav_now': show_step_nav_now,
                },
            }
        )


def apply_small_step_selection(selection_payload, recommendations_df, curriculum_assistant, lookup_videos_for_step):
    """Single selection handler for Selector cards, Match cards, and nav transitions."""
    if not selection_payload:
        return

    st.session_state.display_status = 'loading'
    st.session_state.flipper_lite_scroll_to_video_cards = True

    full_ctx, selected_step_name = resolve_small_step_context(selection_payload, curriculum_assistant)
    st.session_state.curriculum_context = full_ctx
    st.session_state.display_step_name = selected_step_name

    selected_age = str(full_ctx.get('age', '')).strip()
    selected_diff = str(full_ctx.get('difficulty', '')).strip()
    selected_topic = full_ctx.get('topic', st.session_state.get('curr_topic', 'Topic ?'))

    st.session_state.pending_selector_sync = {
        'age': selected_age,
        'difficulty': selected_diff,
        'topic': selected_topic,
    }

    if selected_age:
        st.session_state.curr_year = selected_age

    if selected_age in ['14-15', '15-16']:
        if selected_diff not in ['Foundation', 'Higher']:
            selected_diff = 'All'
        st.session_state.curr_difficulty = selected_diff
    else:
        st.session_state.curr_difficulty = 'All'

    st.session_state.curr_topic = selected_topic
    st.session_state.current_video = None
    st.session_state.current_video_index = 0

    results = lookup_videos_for_step(
        recommendations_df,
        year=full_ctx.get('year', ''),
        term=full_ctx.get('term', ''),
        difficulty=full_ctx.get('difficulty', ''),
        topic=full_ctx.get('topic', ''),
        small_step=full_ctx.get('small_step', ''),
        small_step_id=full_ctx.get('small_step_id', ''),
    )

    st.session_state.display_results = results
    st.session_state.display_status = 'complete'
    st.rerun()
