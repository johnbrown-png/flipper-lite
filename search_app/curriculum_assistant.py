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
        self.df = self._load_curriculum()
        
        if self.df is None:
            st.warning("Curriculum data not available")
            return None, None
        
        # Check if there's a pending search from previous interaction
        if 'pending_insertion' in st.session_state and st.session_state.pending_insertion:
            insertion_data = st.session_state.pending_insertion
            st.session_state.pending_insertion = None
            # For small_step_search, return the whole dict as 'text'
            if insertion_data['action'] == 'small_step_search':
                return insertion_data['action'], insertion_data
            else:
                return None, None
        
        # Initialize session state for selections with default placeholder values
        if 'curr_year' not in st.session_state:
            st.session_state.curr_year = 'Age ?'
        if 'curr_term' not in st.session_state:
            st.session_state.curr_term = 'Term ?'
        if 'curr_topic' not in st.session_state:
            st.session_state.curr_topic = 'Topic ?'
        if 'curr_difficulty' not in st.session_state:
            st.session_state.curr_difficulty = 'All'
        
        # Track if user has made a selection (to show blank initially)
        if 'user_has_selected' not in st.session_state:
            st.session_state.user_has_selected = False
        
        # Check if we need difficulty filter (Year 10 or Year 11)
        has_difficulty = 'Difficulty' in self.df.columns
        # Map Age to Year for difficulty check
        age_to_year_map = dict(zip(self.df['Age'], self.df['Year']))
        curr_year_group = age_to_year_map.get(st.session_state.curr_year, '')
        show_difficulty = has_difficulty and curr_year_group in ['Year 10', 'Year 11']
        
        # Create horizontal row for dropdowns with proportional widths
        # Year and Term get smaller proportions (1 unit each), Topic gets larger (3 units)
        if show_difficulty:
            col_year, col_diff, col_term, col_topic = st.columns([1, 1, 1, 3])
        else:
            col_year, col_term, col_topic = st.columns([1, 1, 3])
        
        # Add CSS for right-justified dropdown options
        st.markdown("""
        <style>
        /* Right-justify dropdown options */
        div[data-baseweb="select"] > div {
            text-align: right;
        }
        </style>
        """, unsafe_allow_html=True)
        
        with col_year:
            # Filter 1: Age Group - with 'Age ?' as default
            # Sort ages by extracting the first number (5-6, 6-7, etc.)
            ages = sorted(self.df['Age'].unique(), key=lambda x: int(x.split('-')[0]) if '-' in str(x) else 0)
            ages = ['Age ?'] + ages  # Add default option
            year_index = ages.index(st.session_state.curr_year) if st.session_state.curr_year in ages else 0
            selected_year = st.selectbox(
                "Age",
                ages,
                index=year_index,
                key="year_select",
                label_visibility="collapsed"
            )
            
            # Update if year changed
            if selected_year != st.session_state.curr_year:
                st.session_state.curr_year = selected_year
                st.session_state.curr_difficulty = 'All'
                # Reset dependent selections to default
                st.session_state.curr_term = 'Term ?'
                st.session_state.curr_topic = 'Topic ?'
                st.rerun()
            
        # Get year dataframe only if a valid age is selected
        if st.session_state.curr_year != 'Age ?':
            year_df = self.df[self.df['Age'] == st.session_state.curr_year]
        else:
            year_df = pd.DataFrame()  # Empty dataframe
        
        # Filter 2: Difficulty (only for Year 10/11)
        if show_difficulty:
            with col_diff:
                difficulty_options = ['All', 'Foundation', 'Higher']
                diff_index = difficulty_options.index(st.session_state.curr_difficulty)
                selected_difficulty = st.selectbox(
                    "Level",
                    difficulty_options,
                    index=diff_index,
                    key="diff_select",
                    label_visibility="collapsed"
                )
                
                if selected_difficulty != st.session_state.curr_difficulty:
                    st.session_state.curr_difficulty = selected_difficulty
                    st.rerun()
                
            # Apply difficulty filter
            if st.session_state.curr_difficulty != 'All':
                year_df = year_df[year_df['Difficulty'] == st.session_state.curr_difficulty]
        
        with col_term:
            # Filter 3: Term - with 'Term ?' as default
            if not year_df.empty:
                terms = ['Term ?'] + list(year_df['Term'].unique())
            else:
                terms = ['Term ?']
            term_index = terms.index(st.session_state.curr_term) if st.session_state.curr_term in terms else 0
            selected_term = st.selectbox(
                "Term",
                terms,
                index=term_index,
                key="term_select",
                label_visibility="collapsed"
            )
            
            if selected_term != st.session_state.curr_term:
                st.session_state.curr_term = selected_term
                # Reset topic to default
                st.session_state.curr_topic = 'Topic ?'
                st.rerun()
        
        # Get term dataframe only if a valid term is selected
        if st.session_state.curr_term != 'Term ?' and not year_df.empty:
            term_df = year_df[year_df['Term'] == st.session_state.curr_term]
        else:
            term_df = pd.DataFrame()  # Empty dataframe
        
        with col_topic:
            # Filter 4: Topic - with 'Topic ?' as default
            if not term_df.empty:
                topics = ['Topic ?'] + list(term_df['Topic'].unique())
            else:
                topics = ['Topic ?']
            topic_index = topics.index(st.session_state.curr_topic) if st.session_state.curr_topic in topics else 0
            selected_topic = st.selectbox(
                "Topic",
                topics,
                index=topic_index,
                key="topic_select",
                label_visibility="collapsed"
            )
            
            if selected_topic != st.session_state.curr_topic:
                st.session_state.curr_topic = selected_topic
                st.rerun()
        
        # Only display content if all selections are made (not defaults)
        if (st.session_state.curr_year != 'Age ?' and 
            st.session_state.curr_term != 'Term ?' and 
            st.session_state.curr_topic != 'Topic ?'):
            
            # Get the row for selected combination
            if not term_df.empty:
                topic_df = term_df[term_df['Topic'] == st.session_state.curr_topic]
                if not topic_df.empty:
                    row = topic_df.iloc[0]
                else:
                    return None, None
            else:
                return None, None
        
            # SMALL STEPS - Vertical Layout with compact design (no title banner)
            small_steps = []
            for i in range(1, 41):  # Read up to 40 small steps
                step_col = f"Small Step {i}"
                example_col = f"SS{i}_desc_short"
                full_desc_col = f"SS{i}_desc"
                
                if step_col in row.index and pd.notna(row[step_col]) and str(row[step_col]).strip():
                    step_text = str(row[step_col]).strip()
                    
                    # Get full description for LLM scoring
                    full_desc = ""
                    if full_desc_col in row.index and pd.notna(row[full_desc_col]):
                        full_desc = str(row[full_desc_col]).strip()
                    
                    # Include full example text if available (no truncation)
                    example_text = ""
                    if example_col in row.index and pd.notna(row[example_col]) and str(row[example_col]).strip():
                        example_text = str(row[example_col]).strip()
                    
                    small_steps.append((i, step_text, example_text, full_desc))
            
            # Display small steps vertically with Find buttons on the right
            if small_steps:
                for step_num, step_text, example_text, full_desc in small_steps:
                    # Each step in a row: 90% content, 10% button
                    col_content, col_button = st.columns([9, 1])
                    
                    with col_content:
                        # Display step number and title
                        st.markdown(f"**{step_num}.** {step_text}")
                        # Display full example if available
                        if example_text:
                            st.caption(example_text)
                    
                    with col_button:
                        # Compact Find button on the right
                        if st.button("🔍", key=f"find_step{step_num}", help="Find videos for this step"):
                            # Handle NaN in difficulty - convert to empty string
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
