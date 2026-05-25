"""
Curriculum Assistant for White Rose Maths
Provides cascading filters for searching curriculum content
"""


import pandas as pd
import streamlit as st
from pathlib import Path

from shared.curriculum_schema import curriculum_to_long_df


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

    def get_adjacent_steps(self, ctx):
        """Return (prev_step_dict, next_step_dict) for the step described in ctx.

        Both dicts are ready to be written into st.session_state.pending_insertion.
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

            def _row_to_dict(row):
                step_text = str(row['small_step_name']).strip()
                full_desc = str(row.get('ss_wr_desc', '')).strip()
                example_text = str(row.get('ss_desc', '')).strip()
                diff_val = row.get('difficulty', '')
                if pd.isna(diff_val):
                    diff_val = ''
                return {
                    'action': 'small_step_search',
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

            return _row_to_dict(prev_row), _row_to_dict(next_row)
        except Exception:
            return None, None
    
    def render(self):
        """Render the curriculum assistant UI and return selected text"""
        # --- Custom CSS: Make Search buttons red (curriculum navigation only) ---
        st.markdown('''
        <style>
        /* Red buttons for curriculum navigation Search buttons only */
        button[key^="find_step_topic_"] {
            background-color: #d32f2f !important;
            color: #fff !important;
            border: none !important;
        }
        button[key^="find_step_topic_"]:hover {
            background-color: #b71c1c !important;
            color: #fff !important;
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


        # --- New: Age dropdown above free-text topic search ---
        # --- Final: Only Age -> Topic -> Small Steps UI ---
        # Age dropdown
        ages = sorted(self.df['age'].dropna().unique(), key=lambda x: int(str(x).split('-')[0]) if '-' in str(x) else 0)
        age_options = ['Age ?'] + ages
        if 'curr_year' not in st.session_state or st.session_state.curr_year not in age_options:
            st.session_state.curr_year = 'Age ?'
        if 'year_select_topic_search' not in st.session_state or st.session_state.year_select_topic_search not in age_options:
            st.session_state.year_select_topic_search = st.session_state.curr_year
        # Keep Age control compact on every rerun.
        st.markdown("""
        <style>
        div[data-testid="stSelectbox"] label[aria-label="Age"] ~ div:first-child,
        div[data-testid="stSelectbox"][aria-label="Age"] > div:first-child {
            width: 8ch !important;
            min-width: 8ch !important;
            max-width: 8ch !important;
        }
        </style>
        """, unsafe_allow_html=True)
        age_col, _age_spacer_col = st.columns([1, 6])
        with age_col:
            selected_year = st.selectbox(
                "Age",
                age_options,
                key="year_select_topic_search",
                label_visibility="collapsed"
            )
        if selected_year != st.session_state.curr_year:
            st.session_state.curr_year = selected_year
            st.session_state.curr_difficulty = 'All'
            st.session_state.curr_topic = 'Topic ?'
            # Reset dependent widget states immediately so dropdown text refreshes on age change.
            st.session_state.difficulty_select_topic_search = 'All'
            st.session_state.topic_select_topic_search = 'Topic ?'
            self._clear_parent_results_state()
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

        # Only show Topic dropdown after Age is selected (and difficulty if required)
        if st.session_state.curr_year != 'Age ?' and (not show_difficulty or st.session_state.curr_difficulty != 'All'):
            filtered_df = self.df[self.df['age'] == st.session_state.curr_year]
            if show_difficulty:
                filtered_df = filtered_df[filtered_df['difficulty'] == st.session_state.curr_difficulty]
            # Preserve CSV order instead of sorting alphabetically
            topics = filtered_df['topic'].dropna().unique().tolist()
            topic_options = ['Topic ?'] + topics
            if 'curr_topic' not in st.session_state or st.session_state.curr_topic not in topic_options:
                st.session_state.curr_topic = 'Topic ?'
            if 'topic_select_topic_search' not in st.session_state or st.session_state.topic_select_topic_search not in topic_options:
                st.session_state.topic_select_topic_search = st.session_state.curr_topic
            selected_topic = st.selectbox(
                "Topic",
                topic_options,
                key="topic_select_topic_search",
                label_visibility="collapsed"
            )
            if selected_topic != st.session_state.curr_topic:
                st.session_state.curr_topic = selected_topic
                self._clear_parent_results_state()
                st.rerun()

            # Show small steps if topic selected
            if st.session_state.curr_topic != 'Topic ?':
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
                            col_content, col_button = st.columns([9, 1])
                            with col_content:
                                st.markdown(f"**{display_step_num}.** {step_text}")
                                if example_text:
                                    st.caption(example_text)
                            with col_button:
                                step_id = str(row.get('small_step_id', '')).strip()
                                button_key = f"find_step_topic_{display_step_num}_{step_id}" if step_id else f"find_step_topic_{display_step_num}"
                                if st.button("Search", key=button_key, help="Find videos for this step"):
                                    difficulty_val = row.get('difficulty', '')
                                    if pd.isna(difficulty_val):
                                        difficulty_val = ''
                                    st.session_state.pending_insertion = {
                                        'action': 'small_step_search',
                                        'year': row['year'],
                                        'term': row['term'],
                                        'difficulty': difficulty_val,
                                        'topic': row['topic'],
                                        'small_step': step_text,
                                        'small_step_desc': example_text if example_text else full_desc,
                                        'small_step_full_desc': full_desc,
                                        'small_step_id': row['small_step_id'],
                                        'small_step_num': int(row['small_step_num']),
                                        'small_step_num_in_topic': int(row['small_step_num_in_topic']),
                                        'display_small_step_num_in_topic': display_step_num,
                                        'age': row['age'],
                                        'display_text': step_text if not example_text else f"{step_text} - {example_text}"
                                    }
                                    st.rerun()
                    else:
                        st.caption("No small steps available for this topic.")
                else:
                    st.caption("No non-duplicate small steps available for this topic.")
        return None, None
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
