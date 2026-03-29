"""
Curriculum Assistant for White Rose Maths
Provides cascading filters for searching curriculum content
"""


import pandas as pd
import streamlit as st
from pathlib import Path


class CurriculumAssistant:
    """Helper for navigating the White Rose Maths curriculum"""
    
    def __init__(self, csv_path):
        """Initialize with path to curriculum CSV"""
        self.csv_path = Path(csv_path)
        self.df = None
        self._load_curriculum()
    
    @st.cache_data
    def _load_curriculum(_self):
        """Load and cache the curriculum data"""
        try:
            df = pd.read_csv(_self.csv_path)
            return df
        except FileNotFoundError:
            st.error(f"Curriculum file not found: {_self.csv_path}")
            return None
        except Exception as e:
            st.error(f"Error loading curriculum: {e}")
            return None
    
    def render(self):
        """Render the curriculum assistant UI and return selected text"""
        # --- Custom CSS: Make all buttons red in this component ---
        st.markdown('''
        <style>
        button[kind="secondary"], button[data-testid="baseButton-secondary"], button[data-testid="baseButton-primary"] {
            background-color: #d32f2f !important;
            color: #fff !important;
            border: none !important;
        }
        button[kind="secondary"]:hover, button[data-testid="baseButton-secondary"]:hover, button[data-testid="baseButton-primary"]:hover {
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
        ages = sorted(self.df['Age'].unique(), key=lambda x: int(str(x).split('-')[0]) if '-' in str(x) else 0)
        age_options = ['Age ?'] + ages
        if 'curr_year' not in st.session_state or st.session_state.curr_year not in age_options:
            st.session_state.curr_year = 'Age ?'
        # Custom CSS for Age dropdown width
            st.markdown("""
            <style>
            /* Set Age dropdown width to 15ch for all selectboxes labeled Age */
            div[data-testid="stSelectbox"] label[aria-label="Age"] ~ div:first-child,
            div[data-testid="stSelectbox"][aria-label="Age"] > div:first-child {
                width: 15ch !important;
                min-width: 15ch !important;
                max-width: 15ch !important;
            }
            </style>
            """, unsafe_allow_html=True)
        selected_year = st.selectbox(
            "Age",
            age_options,
            index=age_options.index(st.session_state.curr_year),
            key="year_select_topic_search",
            label_visibility="collapsed"
        )
        if selected_year != st.session_state.curr_year:
            st.session_state.curr_year = selected_year
            st.session_state.curr_difficulty = 'All'
            st.session_state.curr_topic = 'Topic ?'
            st.rerun()

        # Difficulty dropdown for ages 14-15 and 15-16
        show_difficulty = st.session_state.curr_year in ['14-15', '15-16']
        difficulty_options = ['All', 'Foundation', 'Higher']
        if show_difficulty:
            if 'curr_difficulty' not in st.session_state or st.session_state.curr_difficulty not in difficulty_options:
                st.session_state.curr_difficulty = 'All'
            selected_difficulty = st.selectbox(
                "Difficulty",
                difficulty_options,
                index=difficulty_options.index(st.session_state.curr_difficulty),
                key="difficulty_select_topic_search",
                label_visibility="collapsed"
            )
            if selected_difficulty != st.session_state.curr_difficulty:
                st.session_state.curr_difficulty = selected_difficulty
                st.session_state.curr_topic = 'Topic ?'
                st.rerun()

        # Only show Topic dropdown after Age is selected (and difficulty if required)
        if st.session_state.curr_year != 'Age ?' and (not show_difficulty or st.session_state.curr_difficulty != 'All'):
            filtered_df = self.df[self.df['Age'] == st.session_state.curr_year]
            if show_difficulty:
                filtered_df = filtered_df[filtered_df['Difficulty'] == st.session_state.curr_difficulty]
            topics = sorted(filtered_df['Topic'].dropna().unique())
            topic_options = ['Topic ?'] + topics
            if 'curr_topic' not in st.session_state or st.session_state.curr_topic not in topic_options:
                st.session_state.curr_topic = 'Topic ?'
            selected_topic = st.selectbox(
                "Topic",
                topic_options,
                index=topic_options.index(st.session_state.curr_topic),
                key="topic_select_topic_search",
                label_visibility="collapsed"
            )
            if selected_topic != st.session_state.curr_topic:
                st.session_state.curr_topic = selected_topic
                st.rerun()

            # Show small steps if topic selected
            if st.session_state.curr_topic != 'Topic ?':
                topic_row = filtered_df[filtered_df['Topic'] == st.session_state.curr_topic]
                if not topic_row.empty:
                    row = topic_row.iloc[0]
                    small_steps = []
                    for i in range(1, 41):
                        step_col = f"Small Step {i}"
                        example_col = f"SS{i}_desc_short"
                        full_desc_col = f"SS{i}_desc"
                        if step_col in row.index and pd.notna(row[step_col]) and str(row[step_col]).strip():
                            step_text = str(row[step_col]).strip()
                            full_desc = ""
                            if full_desc_col in row.index and pd.notna(row[full_desc_col]):
                                full_desc = str(row[full_desc_col]).strip()
                            example_text = ""
                            if example_col in row.index and pd.notna(row[example_col]) and str(row[example_col]).strip():
                                example_text = str(row[example_col]).strip()
                            small_steps.append((i, step_text, example_text, full_desc))
                    if small_steps:
                        for step_num, step_text, example_text, full_desc in small_steps:
                            col_content, col_button = st.columns([9, 1])
                            with col_content:
                                st.markdown(f"**{step_num}.** {step_text}")
                                if example_text:
                                    st.caption(example_text)
                            with col_button:
                                if st.button("Search", key=f"find_step_topic_{step_num}", help="Find videos for this step"):
                                    difficulty_val = row.get('Difficulty', '')
                                    if pd.isna(difficulty_val):
                                        difficulty_val = ''
                                    st.session_state.pending_insertion = {
                                        'action': 'small_step_search',
                                        'year': row['Year'],
                                        'term': row['Term'],
                                        'difficulty': difficulty_val,
                                        'topic': row['Topic'],
                                        'small_step': step_text,
                                        'small_step_desc': full_desc,
                                        'age': row['Age'],
                                        'display_text': step_text if not example_text else f"{step_text} - {example_text}"
                                    }
                                    st.rerun()
                    else:
                        st.caption("No small steps available for this topic.")
                else:
                    st.caption("No data found for this topic.")
        return None, None
        return None, None
    
    def get_stats(self):
        """Get curriculum statistics"""
        if self.df is None:
            return {}
        
        return {
            'total_entries': len(self.df),
            'year_groups': len(self.df['Year'].unique()),
            'topics': len(self.df['Topic'].unique())
        }
