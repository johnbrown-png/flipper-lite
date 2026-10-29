"""
OBSOLETE: This module is no longer used in the pipeline.

Readability scoring has been replaced with LLM-based instruction quality assessment.
This file is kept for reference only and should not be called by active code.

---

Calculate readability scores for video transcripts.

This module calculates Flesch Reading Ease and Flesch-Kincaid Grade Level
for video transcripts to help rank videos by educational appropriateness.
"""

import json
from pathlib import Path
from typing import Dict, Optional
import re


class ReadabilityCalculator:
    """Calculate readability metrics for video transcripts"""
    
    def __init__(self, output_file: str = "data/video_readability.json"):
        """
        Initialize the readability calculator
        
        Args:
            output_file: Path to save readability scores JSON
        """
        self.output_file = Path(output_file)
        self.scores = self._load_existing_scores()
        
        # Try to import textstat
        try:
            import textstat
            self.textstat = textstat
        except ImportError:
            raise ImportError(
                "textstat library not found. Please install it:\n"
                "pip install textstat"
            )
    
    def _load_existing_scores(self) -> Dict:
        """Load existing readability scores if available"""
        if self.output_file.exists():
            with open(self.output_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _save_scores(self):
        """Save readability scores to JSON file"""
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(self.scores, f, indent=2)
    
    def _extract_transcript_text(self, caption_data: Dict) -> str:
        """
        Extract full transcript text from caption JSON
        
        Args:
            caption_data: Caption JSON data
        
        Returns:
            Full transcript as string
        """
        # Handle different caption formats
        transcript_items = caption_data.get('transcript', caption_data.get('captions', []))
        
        if not transcript_items:
            return ""
        
        # Join all text segments
        full_text = " ".join([item.get('text', '') for item in transcript_items])
        return full_text.strip()
    
    def _add_sentence_boundaries(self, text: str, caption_data: Dict) -> str:
        """
        Add periods at likely sentence boundaries using multiple heuristics
        
        YouTube auto-captions lack punctuation. We use timing data and
        word counting to infer sentence boundaries.
        
        Args:
            text: Raw transcript text
            caption_data: Caption JSON with timing data
        
        Returns:
            Text with added sentence boundaries
        """
        transcript_items = caption_data.get('transcript', caption_data.get('captions', []))
        
        if not transcript_items:
            return text
        
        # Build text with periods at pause boundaries
        segments = []
        word_count = 0
        words_since_period = 0
        
        for i, item in enumerate(transcript_items):
            text_segment = item.get('text', '').strip()
            
            if not text_segment:
                continue
            
            # Count words in this segment
            segment_words = len(text_segment.split())
            word_count += segment_words
            words_since_period += segment_words
            
            add_period = False
            
            # Strategy 1: Check timing gap (for videos with good timing)
            if i < len(transcript_items) - 1:
                current_end = item.get('start', 0) + item.get('duration', 0)
                next_start = transcript_items[i + 1].get('start', 0)
                gap = next_start - current_end
                
                # If gap > 0.8 seconds, likely a sentence boundary
                if gap > 0.8:
                    add_period = True
            else:
                # Last segment always gets period
                add_period = True
            
            # Strategy 2: Add period every ~15-20 words (fallback for videos with overlapping timestamps)
            # This ensures we get multiple sentences even if timing detection fails
            if words_since_period >= 18:
                add_period = True
            
            # Strategy 3: Look for natural sentence endings (question words, etc.)
            # If we haven't had a period in a while and see these patterns, add one
            if words_since_period >= 10:
                lower_segment = text_segment.lower()
                # Common question/statement ending patterns
                if any(lower_segment.endswith(word) for word in [
                    'right', 'yes', 'no', 'okay', 'ok', 'good', 'great', 
                    'done', 'there', 'that', 'this', 'see', 'look'
                ]):
                    add_period = True
            
            if add_period:
                text_segment += '.'
                words_since_period = 0
            
            segments.append(text_segment)
        
        return " ".join(segments)
    
    def calculate_readability(
        self,
        video_id: str,
        caption_file: Path,
        add_punctuation: bool = True
    ) -> Dict:
        """
        Calculate readability scores for a video
        
        Args:
            video_id: Video ID
            caption_file: Path to caption JSON file
            add_punctuation: Whether to infer sentence boundaries
        
        Returns:
            Dictionary with readability scores
        """
        # Load caption data
        with open(caption_file, 'r', encoding='utf-8') as f:
            caption_data = json.load(f)
        
        # Extract text
        text = self._extract_transcript_text(caption_data)
        
        if not text or len(text) < 100:
            return {
                'video_id': video_id,
                'flesch_reading_ease': None,
                'flesch_kincaid_grade': None,
                'word_count': 0,
                'error': 'Insufficient text'
            }
        
        # Add sentence boundaries for better accuracy
        if add_punctuation:
            text = self._add_sentence_boundaries(text, caption_data)
        
        # Calculate readability scores
        try:
            flesch_ease = self.textstat.flesch_reading_ease(text)
            flesch_grade = self.textstat.flesch_kincaid_grade(text)
            word_count = self.textstat.lexicon_count(text, removepunct=True)
            
            return {
                'video_id': video_id,
                'title': caption_data.get('title', ''),
                'flesch_reading_ease': round(flesch_ease, 2),
                'flesch_kincaid_grade': round(flesch_grade, 2),
                'word_count': word_count
            }
        except Exception as e:
            return {
                'video_id': video_id,
                'flesch_reading_ease': None,
                'flesch_kincaid_grade': None,
                'word_count': 0,
                'error': str(e)
            }
    
    def process_caption_file(
        self,
        caption_file: Path,
        force_recalculate: bool = False
    ) -> Optional[Dict]:
        """
        Process a single caption file and calculate readability
        
        Args:
            caption_file: Path to caption JSON file
            force_recalculate: Recalculate even if scores exist
        
        Returns:
            Readability scores or None if skipped
        """
        # Extract video_id from filename
        # Format: {video_id}.json or {video_id}_captions.json
        video_id = caption_file.stem.replace('_captions', '')
        
        # Skip if already calculated
        if video_id in self.scores and not force_recalculate:
            return None
        
        # Calculate readability
        scores = self.calculate_readability(video_id, caption_file)
        
        # Store scores
        self.scores[video_id] = scores
        
        return scores
    
    def process_directory(
        self,
        captions_dir: Path,
        force_recalculate: bool = False,
        save_interval: int = 100
    ) -> Dict:
        """
        Process all caption files in a directory
        
        Args:
            captions_dir: Directory containing caption JSON files
            force_recalculate: Recalculate all scores
            save_interval: Save scores every N files
        
        Returns:
            Processing statistics
        """
        captions_dir = Path(captions_dir)
        
        # Find all caption files (search recursively for channel subdirectories)
        caption_files = list(captions_dir.glob('**/*.json'))
        
        if not caption_files:
            print(f"✗ No caption files found in {captions_dir}")
            return {'processed': 0, 'skipped': 0, 'errors': 0}
        
        print(f"\n📄 Found {len(caption_files)} caption files")
        print(f"📁 Output file: {self.output_file}")
        
        if not force_recalculate:
            existing_count = len(self.scores)
            print(f"ℹ️  {existing_count} videos already have readability scores")
        
        print()
        
        stats = {
            'processed': 0,
            'skipped': 0,
            'errors': 0,
            'total': len(caption_files)
        }
        
        for i, caption_file in enumerate(caption_files, 1):
            try:
                result = self.process_caption_file(caption_file, force_recalculate)
                
                if result is None:
                    stats['skipped'] += 1
                    if i % 100 == 0:
                        print(f"⏭️  Progress: {i}/{len(caption_files)} ({stats['skipped']} skipped)")
                elif result.get('error'):
                    stats['errors'] += 1
                    print(f"⚠️  {caption_file.name}: {result['error']}")
                else:
                    stats['processed'] += 1
                    if stats['processed'] % 50 == 0:
                        print(f"✓ Processed {stats['processed']} videos...")
                
                # Save periodically
                if stats['processed'] % save_interval == 0:
                    self._save_scores()
                    
            except Exception as e:
                stats['errors'] += 1
                print(f"✗ Error processing {caption_file.name}: {e}")
        
        # Final save
        self._save_scores()
        
        print(f"\n✓ Readability calculation completed")
        print(f"  Processed: {stats['processed']} new videos")
        print(f"  Skipped: {stats['skipped']} (already calculated)")
        print(f"  Errors: {stats['errors']}")
        print(f"  Total scores: {len(self.scores)}")
        
        return stats
    
    def get_score(self, video_id: str) -> Optional[Dict]:
        """
        Get readability score for a video
        
        Args:
            video_id: Video ID
        
        Returns:
            Readability scores or None if not found
        """
        return self.scores.get(video_id)
    
    def get_all_scores(self) -> Dict:
        """Get all readability scores"""
        return self.scores.copy()


def interpret_flesch_ease(score: float) -> str:
    """
    Interpret Flesch Reading Ease score
    
    Args:
        score: Flesch Reading Ease score (0-100)
    
    Returns:
        Human-readable interpretation
    """
    if score >= 90:
        return "Very Easy (5th grade)"
    elif score >= 80:
        return "Easy (6th grade)"
    elif score >= 70:
        return "Fairly Easy (7th grade)"
    elif score >= 60:
        return "Standard (8th-9th grade)"
    elif score >= 50:
        return "Fairly Difficult (10th-12th grade)"
    elif score >= 30:
        return "Difficult (College)"
    else:
        return "Very Difficult (College graduate)"


def interpret_flesch_grade(grade: float) -> str:
    """
    Interpret Flesch-Kincaid Grade Level
    
    Args:
        grade: Grade level score
    
    Returns:
        Human-readable interpretation
    """
    if grade <= 5:
        return "Elementary School"
    elif grade <= 8:
        return "Middle School"
    elif grade <= 12:
        return "High School"
    elif grade <= 16:
        return "College"
    else:
        return "Graduate School"
