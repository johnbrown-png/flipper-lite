"""
Curriculum indexing and caching.

Loads curriculum CSV, builds searchable text corpus, and manages lookups.
"""

import pandas as pd
from pathlib import Path
from typing import Optional, List, Dict
import re


class CurriculumIndex:
    """
    Manages curriculum data and searchable text index.
    """
    
    def __init__(self, curriculum_csv_path: str):
        """
        Initialize curriculum index.
        
        Args:
            curriculum_csv_path: Path to curriculum_08052026_small_steps.csv
        """
        self.curriculum_path = Path(curriculum_csv_path)
        self.df = None
        self.searchable_text = None  # Dict: small_step_id → searchable text
        self._load_curriculum()
    
    def _load_curriculum(self):
        """Load curriculum CSV and build searchable index."""
        if not self.curriculum_path.exists():
            raise FileNotFoundError(f"Curriculum file not found: {self.curriculum_path}")
        
        self.df = pd.read_csv(self.curriculum_path)
        self._build_searchable_index()
    
    def _build_searchable_index(self):
        """Build searchable text for each small step."""
        self.searchable_text = {}
        
        for _, row in self.df.iterrows():
            small_step_id = str(row.get('small_step_id', '')).strip()
            if not small_step_id:
                continue
            
            # Combine all relevant fields into searchable text
            topic = str(row.get('topic', '')).strip()
            small_step_name = str(row.get('small_step_name', '')).strip()
            ss_desc = str(row.get('ss_desc', '')).strip()
            ss_wr_desc = str(row.get('ss_wr_desc', '')).strip()
            
            # Priority weighting: name > topic > ss_desc > ss_wr_desc
            # (longer text at end to avoid overwhelming with description)
            parts = [small_step_name, topic, ss_desc, ss_wr_desc]
            searchable_text = ' '.join([p for p in parts if p])
            
            if searchable_text:
                self.searchable_text[small_step_id] = self._normalize_text(searchable_text)
    
    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalize text for indexing: lowercase, strip punctuation."""
        text = text.lower()
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def get_searchable_text_all(self) -> Dict[str, str]:
        """Get all searchable text indexed by small_step_id."""
        return self.searchable_text.copy()
    
    def get_curriculum_row(self, small_step_id: str) -> Optional[Dict]:
        """
        Get full curriculum row for a small step.
        
        Args:
            small_step_id: Unique small step identifier
        
        Returns:
            Dict with all columns, or None if not found
        """
        if self.df is None or self.df.empty:
            return None
        
        matches = self.df[self.df['small_step_id'] == small_step_id]
        if matches.empty:
            return None
        
        return matches.iloc[0].to_dict()
    
    def get_small_steps_for_display(self, small_step_ids: List[str]) -> List[Dict]:
        """
        Get display-ready data for a list of small step IDs.
        
        Args:
            small_step_ids: List of small_step_id values
        
        Returns:
            List of dicts with: small_step_id, topic, small_step_name, ss_desc, year, age
        """
        results = []
        for ss_id in small_step_ids:
            row = self.get_curriculum_row(ss_id)
            if row:
                results.append({
                    'small_step_id': row.get('small_step_id'),
                    'topic': row.get('topic', ''),
                    'small_step_name': row.get('small_step_name', ''),
                    'ss_desc': row.get('ss_desc', ''),
                    'ss_wr_desc': row.get('ss_wr_desc', ''),
                    'year': row.get('year', ''),
                    'age': row.get('age', ''),
                    'term': row.get('term', ''),
                    'difficulty': row.get('difficulty', ''),
                })
        return results
    
    def filter_by_epoch(self, epoch_name: str) -> pd.DataFrame:
        """
        Filter curriculum to a specific epoch.
        
        Args:
            epoch_name: Key from EPOCHS dict (or None for all)
        
        Returns:
            Filtered DataFrame
        """
        if not epoch_name or epoch_name == 'All':
            return self.df.copy()
        
        from .epoch_definitions import filter_curriculum_by_epoch
        return filter_curriculum_by_epoch(self.df, epoch_name)
    
    def get_searchable_text_for_epoch(self, epoch_name: str) -> Dict[str, str]:
        """
        Get searchable text for small steps in a specific epoch.
        
        Args:
            epoch_name: Key from EPOCHS dict
        
        Returns:
            Dict: small_step_id → searchable text (filtered by epoch)
        """
        filtered_df = self.filter_by_epoch(epoch_name)
        result = {}
        
        for _, row in filtered_df.iterrows():
            ss_id = str(row.get('small_step_id', '')).strip()
            if ss_id in self.searchable_text:
                result[ss_id] = self.searchable_text[ss_id]
        
        return result
