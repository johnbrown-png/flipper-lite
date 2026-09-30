"""
Curriculum Assistant for White Rose Maths
Provides cascading filters for searching curriculum content
"""


import html

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path

from shared.curriculum_schema import curriculum_to_long_df
from shared.ui_terminology import SELECTOR_CARDS_LABEL
from shared.analytics import track_event

# 'Pick by Small Step' subheading: hidden by default, kept for future re-enable.
ENABLE_PICK_BY_SMALL_STEP_HEADING = False

# Small-step description preview: number of leading words shown before '...more'.
SMALL_STEP_DESC_PREVIEW_WORDS = 10

# Free-text skill search: how many small-step rows to show.
SMALL_STEP_SEARCH_LIMIT = 15


def _render_truncated_description(text, title=''):
    """Render a small-step title and description with a clickable '...more' disclosure."""
    title_html = f'<div class="ss-desc-title"><strong>{html.escape(title)}</strong></div>' if title else ''
    words = text.split()
    if len(words) <= SMALL_STEP_DESC_PREVIEW_WORDS:
        st.markdown(
            f'<div class="ss-desc-block">{title_html}<div class="ss-desc-caption">{html.escape(text)}</div></div>',
            unsafe_allow_html=True,
        )
        return

    preview = html.escape(' '.join(words[:SMALL_STEP_DESC_PREVIEW_WORDS]))
    remainder = html.escape(' '.join(words[SMALL_STEP_DESC_PREVIEW_WORDS:]))
    st.markdown(
        f'''
        <div class="ss-desc-block">
            {title_html}
            <div class="ss-desc-caption">
                {preview} <details class="ss-desc-details"><span>{remainder}</span><summary></summary></details>
            </div>
        </div>
        ''',
        unsafe_allow_html=True,
    )


class CurriculumAssistant:
    """Helper for navigating the White Rose Maths curriculum"""
    
    def __init__(self, csv_path):
        """Initialize with path to curriculum CSV"""
        self.csv_path = Path(csv_path)
        self.df = self._load_curriculum()
        self._recommendations_csv_path = self._resolve_recommendations_csv_path()
        self.duplicate_step_ids = set()
        self._refresh_duplicate_flags()

    @staticmethod
    def _resolve_recommendations_csv_path():
        """Prefer the QA recommendations CSV when available, else fall back to base CSV."""
        project_root = Path(__file__).resolve().parent.parent
        qa_csv_path = project_root / 'precomputed_recommendations_flat_qa.csv'
        base_csv_path = project_root / 'precomputed_recommendations_flat.csv'
        return qa_csv_path if qa_csv_path.exists() else base_csv_path

    @st.cache_data(ttl=300)
    def _load_duplicate_step_ids(_self, recommendations_csv_path: str, recommendations_mtime: float = 0.0):
        """Load small_step_ids flagged duplicate=1 in the recommendations CSV."""
        path = Path(recommendations_csv_path)
        if not path.exists():
            return []
        try:
            df = pd.read_csv(path)
            if 'small_step_id' not in df.columns or 'duplicate' not in df.columns:
                return []
            step_ids = df['small_step_id'].astype(str).str.strip()
            duplicate_numeric = pd.to_numeric(df['duplicate'], errors='coerce').fillna(0)
            duplicate_text = df['duplicate'].astype(str).str.strip().str.lower()
            is_duplicate = (duplicate_numeric > 0) | duplicate_text.isin({'1', 'true', 'yes', 'y'})
            valid_ids = is_duplicate & step_ids.ne('') & step_ids.ne('nan')
            return sorted(set(step_ids[valid_ids].tolist()))
        except Exception:
            return []

    def _refresh_duplicate_flags(self):
        """Refresh duplicate flags from recommendations CSV (cached)."""
        self._recommendations_csv_path = self._resolve_recommendations_csv_path()

        rec_mtime = self._recommendations_csv_path.stat().st_mtime if self._recommendations_csv_path.exists() else 0.0

        self.duplicate_step_ids = set(self._load_duplicate_step_ids(str(self._recommendations_csv_path), rec_mtime))

    def _get_topic_steps(self, age, topic, difficulty=''):
        """Return topic steps in curriculum order, excluding duplicate-flagged rows."""
        if self.df is None:
            self.df = self._load_curriculum()
        if self.df is None:
            return pd.DataFrame()

        mask = (self.df['age'] == age) & (self.df['topic'] == topic)
        if difficulty:
            mask &= (self.df['difficulty'] == difficulty)

        topic_steps = self.df[mask].sort_values('small_step_num_in_topic', kind='stable').copy()
        if topic_steps.empty:
            return topic_steps

        self._refresh_duplicate_flags()
        if self.duplicate_step_ids:
            topic_steps = topic_steps[~topic_steps['small_step_id'].isin(self.duplicate_step_ids)].copy()

        return topic_steps.reset_index(drop=True)

    @staticmethod
    def _age_sort_key(age_value):
        """Sort age bands numerically by their first number (e.g., 5-6, 10-11)."""
        try:
            age_text = str(age_value).strip()
            return int(age_text.split('-')[0])
        except Exception:
            return 999

    @staticmethod
    def _search_tokens(text):
        """Split text into lowercase word tokens."""
        cleaned = ''.join(ch if ch.isalnum() else ' ' for ch in str(text).lower())
        return [tok for tok in cleaned.split() if tok]

    @staticmethod
    def _token_in_haystack(query_tok, haystack):
        """Match a query word exactly, or by a shared stem of at least 3 letters."""
        if query_tok in haystack:
            return True
        if len(query_tok) < 3:
            return False
        for hay_tok in haystack:
            if len(hay_tok) < 3:
                continue
            if hay_tok.startswith(query_tok) or query_tok.startswith(hay_tok):
                return True
        return False

    @classmethod
    def _tokens_covered(cls, query_tokens, haystack):
        return all(cls._token_in_haystack(tok, haystack) for tok in query_tokens)

    def _search_small_steps(self, query):
        """Rank small steps whose name, or name plus topic, contains every query word.

        Phrase matches in the step name rank above loose word matches in the name,
        which rank above words split across the step name and topic.
        """
        columns = ['small_step_id', 'small_step', 'topic', 'age', 'difficulty']
        if self.df is None:
            self.df = self._load_curriculum()
        if self.df is None:
            return pd.DataFrame(columns=columns)

        query_tokens = self._search_tokens(query)
        if not query_tokens:
            return pd.DataFrame(columns=columns)
        phrase = ' '.join(query_tokens)

        self._refresh_duplicate_flags()

        matches = []
        for _, row in self.df.iterrows():
            step_id = str(row.get('small_step_id', '')).strip()
            if not step_id or step_id in self.duplicate_step_ids:
                continue
            step = str(row.get('small_step_name', '')).strip()
            topic = str(row.get('topic', '')).strip()
            age = str(row.get('age', '')).strip()
            if not step or step.lower() == 'nan' or not age or age.lower() == 'nan':
                continue
            if topic.lower() == 'nan':
                topic = ''

            step_tokens = self._search_tokens(step)
            topic_tokens = self._search_tokens(topic)
            step_text = ' '.join(step_tokens)
            if phrase in step_text:
                rank = 0
            elif self._tokens_covered(query_tokens, step_tokens):
                rank = 1
            elif self._tokens_covered(query_tokens, step_tokens + topic_tokens):
                rank = 2
            else:
                continue

            difficulty = str(row.get('difficulty', '')).strip()
            if difficulty.lower() == 'nan':
                difficulty = ''
            matches.append({
                'small_step_id': step_id,
                'small_step': step,
                'topic': topic,
                'age': age,
                'difficulty': difficulty,
                'rank': rank,
                'name_len': len(step),
                'age_sort': self._age_sort_key(age),
            })

        if not matches:
            return pd.DataFrame(columns=columns)

        ranked = pd.DataFrame(matches)
        ranked = ranked.sort_values(
            ['rank', 'name_len', 'age_sort', 'topic', 'small_step'],
            kind='stable',
        )
        ranked = ranked.drop_duplicates(subset=['small_step_id'])
        return ranked[columns].reset_index(drop=True)

    def _get_step_row(self, small_step_id):
        """Return the curriculum row for a small_step_id, or None."""
        if self.df is None:
            return None
        rows = self.df[self.df['small_step_id'] == small_step_id]
        if rows.empty:
            return None
        return rows.iloc[0]

    @staticmethod
    def _step_payload(row, selection_source, display_step_num=None):
        """Build a small_step_search payload (docs/SMALL_STEP_PAYLOAD_CONTRACT.md) from a curriculum row."""
        step_text = str(row['small_step_name']).strip()
        full_desc = str(row.get('ss_wr_desc', '')).strip()
        example_text = str(row.get('ss_desc', '')).strip()
        diff_val = row.get('difficulty', '')
        if pd.isna(diff_val):
            diff_val = ''
        payload = {
            'action': 'small_step_search',
            'selection_source': selection_source,
            'year': row['year'],
            'term': row['term'],
            'difficulty': diff_val,
            'topic': row['topic'],
            'small_step': step_text,
            'small_step_desc': example_text if example_text else full_desc,
            'small_step_full_desc': full_desc,
            'small_step_id': row['small_step_id'],
            'small_step_num': int(row['small_step_num']),
            'small_step_num_in_topic': int(row['small_step_num_in_topic']),
            'age': row['age'],
            'display_text': step_text if not example_text else f"{step_text} - {example_text}",
        }
        if display_step_num is not None:
            payload['display_small_step_num_in_topic'] = display_step_num
        return payload
    
    @st.cache_data(ttl=300)  # Cache for 5 minutes to allow for curriculum updates
    def _load_curriculum(_self):
        """Load and cache the curriculum data"""
        try:
            df = pd.read_csv(_self.csv_path)
            return curriculum_to_long_df(df)
        except FileNotFoundError:
            st.error(f"Curriculum file not found: {_self.csv_path}")
            return None
        except Exception as e:
            st.error(f"Error loading curriculum: {e}")
            return None

    @staticmethod
    def _clear_parent_results_state():
        """Clear previously displayed results when navigation context changes."""
        st.session_state.display_status = 'idle'
        st.session_state.display_results = []
        st.session_state.display_step_name = ""
        st.session_state.curriculum_context = None
        if 'current_video' in st.session_state:
            st.session_state.current_video = None
        if 'viewing_video' in st.session_state:
            st.session_state.viewing_video = False

    @staticmethod
    def _reset_curriculum_selection():
        """Return the curriculum selector and parent page to the landing state."""
        st.session_state.curr_year = 'Learner\'s Age?'
        st.session_state.year_select_topic_search = 'Learner\'s Age?'
        st.session_state.curr_difficulty = 'All'
        st.session_state.difficulty_select_topic_search = 'All'
        st.session_state.curr_topic = 'Topic ?'
        st.session_state.topic_select_topic_search = 'Topic ?'
        st.session_state.topic_prefix_search = ''
        st.session_state.clear_topic_prefix_on_open = False
        st.session_state.pending_step_nav = None
        CurriculumAssistant._clear_parent_results_state()

    def get_adjacent_steps(self, ctx):
        """Return (prev_step_dict, next_step_dict) for the step described in ctx.

        Both dicts are ready to be written into st.session_state.pending_insertion.
        Contract: docs/SMALL_STEP_PAYLOAD_CONTRACT.md
        Returns (None, None) if the curriculum is not loaded or context is missing.
        Wraps cyclically: next of last step is first; prev of first is last.
        """
        if self.df is None:
            self.df = self._load_curriculum()
        if self.df is None or not ctx:
            return None, None
        try:
            topic = ctx.get('topic')
            age = ctx.get('age')
            difficulty = ctx.get('difficulty') or ''
            current_sid = str(ctx.get('small_step_id', '')).strip()
            current_num = int(ctx.get('small_step_num_in_topic', -1))
            if not topic or not age:
                return None, None

            steps = self._get_topic_steps(age=age, topic=topic, difficulty=difficulty)
            if steps.empty:
                return None, None

            if current_sid:
                sid_matches = steps.index[steps['small_step_id'] == current_sid].tolist()
                if not sid_matches:
                    return None, None
                pos = sid_matches[0]
            else:
                nums = steps['small_step_num_in_topic'].tolist()
                try:
                    pos = nums.index(current_num)
                except ValueError:
                    return None, None

            n = len(steps)
            prev_row = steps.iloc[(pos - 1) % n]
            next_row = steps.iloc[(pos + 1) % n]
            return self._step_payload(prev_row, 'nav'), self._step_payload(next_row, 'nav')
        except Exception:
            return None, None
    
    def render(self, show_topic_table_search=True):
        """Render the curriculum assistant UI and return selected text.

        Args:
            show_topic_table_search: Whether to show the prefix topic-table search UI.
                The Age -> Topic -> Small Steps flow remains visible regardless.
        """
        # --- Custom CSS: Make Search buttons red (curriculum navigation only) ---
        st.markdown('''
        <div class="curriculum-assistant-chrome" hidden></div>
        <style>
        /* Blue buttons for curriculum navigation Watch buttons, matching video-card Watch buttons */
        button[key^="find_step_topic_"] {
            background: linear-gradient(135deg, #2c5f8d 0%, #4a90c8 100%) !important;
            color: #fff !important;
            border: none !important;
        }
        button[key^="find_step_topic_"]:hover {
            background: linear-gradient(135deg, #1e3a5f 0%, #2c5f8d 100%) !important;
            color: #fff !important;
        }
        /* Skill search results table: compact rows (about half the default row height). */
        .st-key-flipper_step_search_table,
        .st-key-flipper_step_search_table [data-testid="stVerticalBlock"] {
            gap: 0.15rem !important;
        }
        .st-key-flipper_step_search_table [data-testid="stMarkdownContainer"] p {
            margin: 0 !important;
            line-height: 1.25 !important;
        }
        .st-key-flipper_step_search_table button {
            min-height: 1.6rem !important;
            padding-top: 0.05rem !important;
            padding-bottom: 0.05rem !important;
        }
        /* Keep Watch buttons (skill search results and topic step list) on one line.
           The search header's empty action column carries a marker so it gets the same width as the rows. */
        div[data-testid="stColumn"]:has(.flipper-watch-col-marker),
        div[data-testid="stColumn"]:has([class*="st-key-open_step_match_"]),
        div[data-testid="stColumn"]:has([class*="st-key-find_step_topic_"]) {
            min-width: 6.5rem !important;
            flex-shrink: 0 !important;
        }
        [class*="st-key-open_step_match_"] button,
        [class*="st-key-find_step_topic_"] button {
            white-space: nowrap !important;
            min-width: 6rem !important;
        }
        [class*="st-key-open_step_match_"] button p,
        [class*="st-key-find_step_topic_"] button p {
            white-space: nowrap !important;
        }
        /* Small-step description preview with clickable '...more' disclosure */
        .ss-desc-caption {
            font-size: 0.875rem;
            color: rgb(108, 117, 125);
            line-height: 1.4;
        }
        .ss-desc-block {
            margin: 0;
        }
        .ss-desc-title {
            line-height: 1.4;
        }
        .ss-desc-details {
            display: inline;
        }
        .ss-desc-details summary {
            display: inline;
            list-style: none;
            cursor: pointer;
            color: #2c5f8d;
            text-decoration: underline;
        }
        .ss-desc-details summary::before {
            content: "...more";
        }
        .ss-desc-details[open] summary::before {
            content: "...less";
        }
        .ss-desc-details summary::-webkit-details-marker {
            display: none;
        }
        /* Dropdown menus (Age / Difficulty / Topic): white background + dark border for attention */
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
            background-color: #ffffff !important;
            border: 2px solid #1e3a5f !important;
            border-radius: 8px !important;
        }
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover,
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:focus-within {
            border-color: #2c5f8d !important;
            box-shadow: 0 0 0 3px rgba(44, 95, 141, 0.25) !important;
        }
        div[data-baseweb="popover"] ul[data-baseweb="menu"],
        ul[data-baseweb="menu"] {
            background-color: #ffffff !important;
            border: 2px solid #1e3a5f !important;
            border-radius: 8px !important;
        }
        ul[data-baseweb="menu"] li {
            background-color: #ffffff !important;
        }
        /* Topic free-text search: same white field and 2px dark outline as Age / Topic dropdowns.
           Scoped to the widget immediately after the search marker so other text fields stay untouched. */
        div[data-testid="stElementContainer"]:has(.flipper-topic-search-marker) {
            display: none !important;
            height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
            min-height: 0 !important;
            overflow: hidden !important;
        }
        div[data-testid="stElementContainer"]:has(.flipper-topic-search-marker) + div[data-testid="stElementContainer"] {
            margin-top: 0.75rem;
        }
        div[data-testid="stElementContainer"]:has(.flipper-topic-search-marker) + div[data-testid="stElementContainer"] [data-testid="stTextInput"] div[data-baseweb="input"] {
            background-color: #ffffff !important;
            border: 2px solid #1e3a5f !important;
            border-radius: 8px !important;
            min-height: 44px !important;
            box-shadow: none !important;
        }
        div[data-testid="stElementContainer"]:has(.flipper-topic-search-marker) + div[data-testid="stElementContainer"] [data-testid="stTextInput"] div[data-baseweb="input"]:hover,
        div[data-testid="stElementContainer"]:has(.flipper-topic-search-marker) + div[data-testid="stElementContainer"] [data-testid="stTextInput"] div[data-baseweb="input"]:focus-within {
            border-color: #2c5f8d !important;
            box-shadow: 0 0 0 3px rgba(44, 95, 141, 0.25) !important;
        }
        div[data-testid="stElementContainer"]:has(.flipper-topic-search-marker) + div[data-testid="stElementContainer"] [data-testid="stTextInput"] div[data-baseweb="input"] > div {
            background-color: #ffffff !important;
            border: none !important;
            box-shadow: none !important;
        }
        div[data-testid="stElementContainer"]:has(.flipper-topic-search-marker) + div[data-testid="stElementContainer"] [data-testid="stTextInput"] input {
            background-color: #ffffff !important;
            min-height: 40px !important;
        }
        div[data-testid="stElementContainer"]:has(.flipper-topic-search-marker) + div[data-testid="stElementContainer"] [data-testid="stTextInput"] input::placeholder {
            color: #31333F !important;
            opacity: 1 !important;
        }
        </style>
        ''', unsafe_allow_html=True)

        self.df = self._load_curriculum()
        if self.df is None:
            st.warning("Curriculum data not available")
            return None, None

        # Check if there's a pending search from previous interaction
        if 'pending_insertion' in st.session_state and st.session_state.pending_insertion:
            insertion_data = st.session_state.pending_insertion
            st.session_state.pending_insertion = None
            if insertion_data['action'] == 'small_step_search':
                return insertion_data['action'], insertion_data
            else:
                return None, None

        # Clear the skill search box after a search result was opened.
        if st.session_state.get('clear_topic_prefix_on_open'):
            st.session_state.topic_prefix_search = ''
            st.session_state.clear_topic_prefix_on_open = False

        if ENABLE_PICK_BY_SMALL_STEP_HEADING:
            st.markdown(
                """
                <p style="
                    font-family: 'Poppins', sans-serif;
                    font-size: 1.2rem;
                    color: #2c5f8d;
                    text-align: left;
                    margin-top: 0.25rem;
                    margin-bottom: 0.15rem;
                    padding: 0;
                    line-height: 1;
                    font-weight: 400;
                ">
                    Pick by Small Step
                </p>
                """,
                unsafe_allow_html=True,
            )

        # --- Final: Age -> Topic -> Small Steps UI ---
        # Age dropdown: render the Step 1 heading flush against the age control
        # (no extra vertical gap) and keep the control at a consistent 44px height.
        st.markdown(
            """
            <style>
            /* 1rem space below Step 1 / Step 2 headings. */
            div[data-testid="stElementContainer"]:has(.step-one-heading),
            div[data-testid="stElementContainer"]:has(.step-two-heading) {
                margin-bottom: 0 !important;
                padding-bottom: 0 !important;
            }
            .step-one-heading,
            .step-two-heading {
                font-size: 1.2rem !important;
                font-weight: 600;
                line-height: 1.15;
                letter-spacing: -0.005em;
                color: inherit;
                margin: 0;
                padding: 0.6rem 0 1rem 0;
            }
            div[data-testid="stSelectbox"]:has(label[data-testid="stWidgetLabel"]) div[data-baseweb="select"] > div {
                min-height: 44px;
            }
            </style>
            <h3 class="step-one-heading">Step 1 of 2: Pick the learner's age to get great teaching videos</h3>
            """,
            unsafe_allow_html=True,
        )
        ages = sorted(self.df['age'].dropna().unique(), key=lambda x: int(str(x).split('-')[0]) if '-' in str(x) else 0)
        age_options = ['Learner\'s Age?'] + ages
        if 'curr_year' not in st.session_state or st.session_state.curr_year not in age_options:
            st.session_state.curr_year = 'Learner\'s Age?'
        if 'year_select_topic_search' not in st.session_state or st.session_state.year_select_topic_search not in age_options:
            st.session_state.year_select_topic_search = st.session_state.curr_year
        age_col, reset_col, _age_spacer_col = st.columns([1, 1, 5])
        with age_col:
            st.markdown(
                '<div id="flipper-age-select-marker" class="flipper-age-select-marker"></div>',
                unsafe_allow_html=True,
            )
            selected_year = st.selectbox(
                "",
                age_options,
                key="year_select_topic_search",
                label_visibility="collapsed",
            )
        with reset_col:
            st.button(
                "Reset",
                key="reset_curriculum_selection",
                on_click=self._reset_curriculum_selection,
            )
        if selected_year != st.session_state.curr_year:
            st.session_state.curr_year = selected_year
            st.session_state.curr_difficulty = 'All'
            st.session_state.curr_topic = 'Topic ?'
            # Reset dependent widget states immediately so dropdown text refreshes on age change.
            st.session_state.difficulty_select_topic_search = 'All'
            st.session_state.topic_select_topic_search = 'Topic ?'
            self._clear_parent_results_state()
            if selected_year != 'Learner\'s Age?':
                track_event("age_selected", {"age": selected_year})
            st.rerun()

        # Difficulty dropdown for ages 14-15 and 15-16
        show_difficulty = st.session_state.curr_year in ['14-15', '15-16']
        difficulty_options = ['All', 'Foundation', 'Higher']
        if show_difficulty:
            if 'curr_difficulty' not in st.session_state or st.session_state.curr_difficulty not in difficulty_options:
                st.session_state.curr_difficulty = 'All'
            if 'difficulty_select_topic_search' not in st.session_state or st.session_state.difficulty_select_topic_search not in difficulty_options:
                st.session_state.difficulty_select_topic_search = st.session_state.curr_difficulty
            selected_difficulty = st.selectbox(
                "Difficulty",
                difficulty_options,
                key="difficulty_select_topic_search",
                label_visibility="collapsed"
            )
            if selected_difficulty != st.session_state.curr_difficulty:
                st.session_state.curr_difficulty = selected_difficulty
                st.session_state.curr_topic = 'Topic ?'
                st.session_state.topic_select_topic_search = 'Topic ?'
                self._clear_parent_results_state()
                st.rerun()

        # Topic dropdown stays visible on the landing page; options fill after age
        # (and Foundation/Higher for GCSE) is chosen so lists are not mixed.
        topics_ready = (
            st.session_state.curr_year != 'Learner\'s Age?'
            and (not show_difficulty or st.session_state.curr_difficulty != 'All')
        )
        if topics_ready:
            filtered_df = self.df[self.df['age'] == st.session_state.curr_year]
            if show_difficulty:
                filtered_df = filtered_df[filtered_df['difficulty'] == st.session_state.curr_difficulty]
            # Preserve CSV order instead of sorting alphabetically
            topics = filtered_df['topic'].dropna().unique().tolist()
            topic_options = ['Topic ?'] + topics
        else:
            topic_options = ['Topic ?']
        if 'curr_topic' not in st.session_state or st.session_state.curr_topic not in topic_options:
            st.session_state.curr_topic = 'Topic ?'
        if 'topic_select_topic_search' not in st.session_state or st.session_state.topic_select_topic_search not in topic_options:
            st.session_state.topic_select_topic_search = st.session_state.curr_topic
        st.markdown(
            """
            <h3 class="step-two-heading">Step 2 of 2: Pick a topic they have not mastered yet</h3>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div id="flipper-topic-select-marker" class="flipper-topic-select-marker"></div>',
            unsafe_allow_html=True,
        )
        selected_topic = st.selectbox(
            "Topic",
            topic_options,
            key="topic_select_topic_search",
            label_visibility="collapsed"
        )
        components.html(
            """
            <script>
            (function() {
                const doc = window.parent.document;
                const TOOLTIP_TEXT = "Topics are in the order of learning. Try higher and lower on the list to find learners level";

                function findTopicSelectbox() {
                    const marker = doc.getElementById('flipper-topic-select-marker');
                    if (!marker) return null;
                    const container = marker.closest('[data-testid="stElementContainer"]');
                    let node = container ? container.nextElementSibling : null;
                    while (node) {
                        const box = (node.matches && node.matches('[data-testid="stSelectbox"]'))
                            ? node
                            : node.querySelector('[data-testid="stSelectbox"]');
                        if (box) return box;
                        node = node.nextElementSibling;
                    }
                    return null;
                }

                function ensureTooltip() {
                    let tip = doc.getElementById('flipper-topic-tooltip');
                    if (tip) return tip;
                    tip = doc.createElement('div');
                    tip.id = 'flipper-topic-tooltip';
                    tip.className = 'flipper-topic-tooltip';
                    tip.setAttribute('role', 'tooltip');
                    tip.textContent = TOOLTIP_TEXT;
                    doc.body.appendChild(tip);
                    return tip;
                }

                function placeTooltip(box) {
                    const tip = ensureTooltip();
                    const rect = box.getBoundingClientRect();
                    tip.classList.add('is-visible');
                    const width = tip.offsetWidth || 280;
                    const maxLeft = Math.max(12, (window.parent.innerWidth || 0) - width - 12);
                    const search = doc.querySelector('.flipper-topic-search-marker');
                    let top = rect.bottom + 8;
                    if (search) {
                        const searchInput = search.closest('[data-testid="stElementContainer"]');
                        const next = searchInput ? searchInput.nextElementSibling : null;
                        const field = next ? next.querySelector('[data-testid="stTextInput"]') : null;
                        if (field) {
                            top = field.getBoundingClientRect().bottom + 8;
                        }
                    }
                    tip.style.top = top + 'px';
                    tip.style.left = Math.max(12, Math.min(rect.left, maxLeft)) + 'px';
                }

                function hideTooltip() {
                    const tip = doc.getElementById('flipper-topic-tooltip');
                    if (tip) tip.classList.remove('is-visible');
                }

                function findAgeSelectbox() {
                    const marker = doc.getElementById('flipper-age-select-marker');
                    if (marker) {
                        const col = marker.closest('[data-testid="stColumn"]')
                            || marker.closest('[data-testid="column"]')
                            || marker.closest('[data-testid="stHorizontalBlock"]');
                        if (col) {
                            const box = col.querySelector('[data-testid="stSelectbox"]');
                            if (box) return box;
                        }
                    }
                    return doc.querySelector('[data-testid="stSelectbox"]');
                }

                function ageIsPlaceholder() {
                    const box = findAgeSelectbox();
                    const text = ((box && box.innerText) || '').replace(/\\s+/g, ' ').trim();
                    return text.indexOf("Learner's Age?") !== -1;
                }

                function closeTopicMenu() {
                    const esc = new KeyboardEvent('keydown', {
                        key: 'Escape',
                        code: 'Escape',
                        keyCode: 27,
                        which: 27,
                        bubbles: true,
                        cancelable: true,
                    });
                    doc.dispatchEvent(esc);
                }

                function pulseAgeFromTopic(event) {
                    const box = findTopicSelectbox();
                    if (!box || !box.contains(event.target)) return false;
                    if (!ageIsPlaceholder()) return false;
                    event.preventDefault();
                    event.stopPropagation();
                    if (typeof event.stopImmediatePropagation === 'function') {
                        event.stopImmediatePropagation();
                    }
                    hideTooltip();
                    if (typeof window.parent.__flipperPulseAgeSelect === 'function') {
                        window.parent.__flipperPulseAgeSelect();
                    }
                    closeTopicMenu();
                    setTimeout(closeTopicMenu, 0);
                    return true;
                }

                if (window.parent.__flipperTopicTooltipBound) return;
                window.parent.__flipperTopicTooltipBound = true;

                doc.addEventListener('mouseover', function(event) {
                    const box = findTopicSelectbox();
                    if (!box) return;
                    if (box.contains(event.target)) {
                        placeTooltip(box);
                    }
                }, true);

                doc.addEventListener('mouseout', function(event) {
                    const box = findTopicSelectbox();
                    if (!box) return;
                    const leftFor = event.relatedTarget;
                    if (box.contains(event.target) && !box.contains(leftFor)) {
                        hideTooltip();
                    }
                }, true);

                doc.addEventListener('mousedown', function(event) {
                    pulseAgeFromTopic(event);
                }, true);

                doc.addEventListener('click', function(event) {
                    pulseAgeFromTopic(event);
                }, true);

                doc.addEventListener('keydown', function(event) {
                    if (event.key !== 'Enter' && event.key !== ' ') return;
                    pulseAgeFromTopic(event);
                }, true);
            })();
            </script>
            """,
            height=0,
        )
        if selected_topic != st.session_state.curr_topic:
            st.session_state.curr_topic = selected_topic
            self._clear_parent_results_state()
            if selected_topic != 'Topic ?':
                st.session_state.flipper_lite_scroll_to_topic_steps = True
                track_event(
                    "topic_selected",
                    {
                        "age": st.session_state.curr_year,
                        "topic": selected_topic,
                        "difficulty": st.session_state.curr_difficulty if show_difficulty else "",
                    },
                )
            st.rerun()

        if show_topic_table_search:
            st.markdown(
                '<div id="flipper-topic-search-marker" class="flipper-topic-search-marker"></div>',
                unsafe_allow_html=True,
            )
            topic_prefix = st.text_input(
                "Or type a skill",
                placeholder="Or type a skill e.g. adding fractions",
                key="topic_prefix_search",
                label_visibility="collapsed",
            )

            topic_prefix = (topic_prefix or '').strip()
            if topic_prefix:
                matches = self._search_small_steps(topic_prefix)

                if matches.empty:
                    st.caption(f"No small steps match '{topic_prefix}'.")
                else:
                    shown = matches.head(SMALL_STEP_SEARCH_LIMIT)
                    if len(matches) > len(shown):
                        st.caption(f"Showing {len(shown)} of {len(matches)} small steps")
                    else:
                        st.caption(f"{len(shown)} small step matches")
                    longest_step_len = max(len(str(v)) for v in shown['small_step'])
                    longest_topic_len = max(len(str(v)) for v in shown['topic'])
                    longest_age_len = max(
                        len(f"{a} ({d})" if d else str(a)) for a, d in zip(shown['age'], shown['difficulty'])
                    )

                    # Keep columns compact and left-justified based on visible search results.
                    step_col_chars = max(len('Small step'), longest_step_len + 2)
                    topic_col_chars = max(len('Topic'), longest_topic_len + 2)
                    age_col_chars = max(len('Age'), 5, longest_age_len)
                    action_col_chars = max(14, len('Watch') + 9)
                    compact_total = step_col_chars + topic_col_chars + age_col_chars + action_col_chars
                    spacer_chars = max(16, compact_total)
                    col_spec = [step_col_chars, topic_col_chars, age_col_chars, action_col_chars, spacer_chars]

                    results_table = st.container(key="flipper_step_search_table")
                    h1, h2, h3, h4, _hs = results_table.columns(col_spec, vertical_alignment="center")
                    with h1:
                        st.markdown("**Small step**")
                    with h2:
                        st.markdown("**Topic**")
                    with h3:
                        st.markdown("**Age**")
                    with h4:
                        st.markdown('<span class="flipper-watch-col-marker"></span>', unsafe_allow_html=True)
                    for idx, row in shown.iterrows():
                        step_id = row['small_step_id']
                        step_val = row['small_step']
                        topic_val = row['topic']
                        age_val = row['age']
                        difficulty_val = row['difficulty']
                        age_label = f"{age_val} ({difficulty_val})" if difficulty_val else age_val

                        c1, c2, c3, c4, _cs = results_table.columns(col_spec, vertical_alignment="center")
                        with c1:
                            st.write(step_val)
                        with c2:
                            st.write(topic_val)
                        with c3:
                            st.write(age_label)
                        with c4:
                            safe_key = ''.join(ch if ch.isalnum() else '_' for ch in f"{idx}_{step_id}")
                            btn_key = f"open_step_match_{safe_key}"
                            if st.button("Watch", key=btn_key, help="Find videos for this step"):
                                step_row = self._get_step_row(step_id)
                                if step_row is not None:
                                    st.session_state.pending_insertion = self._step_payload(step_row, 'search')
                                    st.session_state.clear_topic_prefix_on_open = True
                                    track_event(
                                        "step_search_watch_clicked",
                                        {
                                            "query": topic_prefix,
                                            "small_step": step_val,
                                            "small_step_id": step_id,
                                            "topic": topic_val,
                                            "age": age_val,
                                            "difficulty": difficulty_val,
                                        },
                                    )
                                    st.rerun()

        # Show small steps if topic selected
        if topics_ready and st.session_state.curr_topic != 'Topic ?':
            st.markdown(
                '<div id="flipper-topic-steps-top" class="flipper-topic-steps-top"></div>',
                unsafe_allow_html=True,
            )
            topic_steps = self._get_topic_steps(
                age=st.session_state.curr_year,
                topic=st.session_state.curr_topic,
                difficulty=st.session_state.curr_difficulty if show_difficulty else '',
            )
            if not topic_steps.empty:
                if len(topic_steps) > 0:
                    for display_step_num, (_, row) in enumerate(topic_steps.iterrows(), start=1):
                        step_text = str(row['small_step_name']).strip()
                        full_desc = str(row.get('ss_wr_desc', '')).strip()
                        example_text = str(row.get('ss_desc', '')).strip()
                        col_button, col_content = st.columns([1, 9])
                        with col_button:
                            step_id = str(row.get('small_step_id', '')).strip()
                            button_key = f"find_step_topic_{display_step_num}_{step_id}" if step_id else f"find_step_topic_{display_step_num}"
                            if st.button("Watch", key=button_key, help="Find videos for this step"):
                                difficulty_val = row.get('difficulty', '')
                                if pd.isna(difficulty_val):
                                    difficulty_val = ''
                                st.session_state.pending_insertion = self._step_payload(
                                    row, 'selector', display_step_num=display_step_num
                                )
                                track_event(
                                    "step_watch_clicked",
                                    {
                                        "small_step": step_text,
                                        "small_step_id": row['small_step_id'],
                                        "topic": row['topic'],
                                        "age": row['age'],
                                        "difficulty": difficulty_val,
                                        "term": row['term'],
                                    },
                                )
                                st.rerun()
                        with col_content:
                            if example_text:
                                _render_truncated_description(
                                    example_text,
                                    title=f"{display_step_num}. {step_text}",
                                )
                            else:
                                st.markdown(f"**{display_step_num}.** {step_text}")
                else:
                    st.caption("No small steps available for this topic.")
            else:
                st.caption("No non-duplicate small steps available for this topic.")
            if st.session_state.get('flipper_lite_scroll_to_topic_steps'):
                components.html(
                    """
                    <script>
                    setTimeout(function() {
                        const doc = window.parent.document;
                        const target = doc.getElementById('flipper-topic-steps-top');
                        if (!target) return;
                        const candidates = [
                            doc.querySelector('section.stMain'),
                            doc.querySelector('[data-testid="stMain"]'),
                            doc.querySelector('section.main'),
                            doc.querySelector('[data-testid="stAppViewContainer"]'),
                            doc.scrollingElement,
                            doc.documentElement
                        ];
                        let root = doc.querySelector('section.stMain')
                            || doc.scrollingElement
                            || doc.documentElement;
                        for (const node of candidates) {
                            if (node && node.scrollHeight > node.clientHeight + 24) {
                                root = node;
                                break;
                            }
                        }
                        const header = doc.querySelector('.flipper-sticky-header');
                        const wrap = header && (
                            header.closest('[data-testid="stElementContainer"]')
                            || header.parentElement
                        );
                        const headerOffset = ((wrap && wrap.getBoundingClientRect().height) || 110) + 10;
                        const rootTop = root.getBoundingClientRect ? root.getBoundingClientRect().top : 0;
                        const y = target.getBoundingClientRect().top - rootTop + (root.scrollTop || 0) - headerOffset;
                        if (typeof root.scrollTo === 'function') {
                            root.scrollTo({ top: Math.max(0, y), behavior: 'smooth' });
                        }
                    }, 150);
                    </script>
                    """,
                    height=0,
                )
                st.session_state.flipper_lite_scroll_to_topic_steps = False
        return None, None
    
    def get_stats(self):
        """Get curriculum statistics"""
        if self.df is None:
            return {}
        
        return {
            'total_entries': len(self.df),
            'year_groups': len(self.df['year'].unique()),
            'topics': len(self.df['topic'].unique())
        }
