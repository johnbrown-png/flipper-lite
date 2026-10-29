"""
Chunk video transcripts for vector embedding and semantic search.

This script:
1. Loads transcripts from JSON files
2. Tokenizes text using tiktoken (cl100k_base - used by text-embedding-3 models)
3. Chunks with sliding window: 250 tokens, 40 token overlap
4. Outputs chunks as JSON with metadata
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Tuple
import tiktoken


class TranscriptChunker:
    """Chunks video transcripts for vector embedding"""
    
    def __init__(
        self,
        input_dir: str = None,
        output_dir: str = None,
        chunk_size: int = 250,
        overlap: int = 40,
        chunk_overlap: int = None,  # Alias for overlap
        sentence_boundary_margin: int = 20,
        model_name: str = "cl100k_base"
    ):
        """
        Initialize the chunker
        
        Args:
            input_dir: Input directory containing caption files
            output_dir: Output directory for chunked files
            chunk_size: Target chunk size in tokens
            overlap: Number of overlapping tokens between chunks
            chunk_overlap: Alias for overlap (for compatibility)
            sentence_boundary_margin: Soft boundary margin for sentence breaks
            model_name: Tokenizer model (cl100k_base for text-embedding-3-*)
        """
        self.input_dir = Path(input_dir) if input_dir else None
        self.output_dir = Path(output_dir) if output_dir else None
        self.chunk_size = chunk_size
        self.overlap = chunk_overlap if chunk_overlap is not None else overlap
        self.sentence_boundary_margin = sentence_boundary_margin
        
        # Initialize tokenizer (cl100k_base is used by text-embedding-3-small/large)
        try:
            self.tokenizer = tiktoken.get_encoding(model_name)
        except Exception as e:
            print(f"Warning: Could not load {model_name}, using cl100k_base")
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        print(f"Initialized tokenizer: {model_name}")
        print(f"  Chunk size: {chunk_size} tokens")
        print(f"  Overlap: {overlap} tokens")
        print(f"  Sentence boundary margin: +/-{sentence_boundary_margin} tokens")
    
    def load_transcript(self, json_path: Path) -> Dict:
        """Load transcript from JSON file"""
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_full_text(self, transcript_data: Dict) -> str:
        """Extract full text from transcript data"""
        # Try 'transcript' key (old format) or 'captions' key (new format)
        transcript_items = transcript_data.get('transcript', transcript_data.get('captions', []))
        full_text = " ".join([item['text'] for item in transcript_items])
        return full_text.strip()
    
    def build_timestamp_map(self, transcript_data: Dict) -> List[Dict]:
        """
        Build a map from character positions to timestamps
        
        Args:
            transcript_data: Transcript data with segments
        
        Returns:
            List of dictionaries with {char_start, char_end, time_start, time_end}
        """
        timestamp_map = []
        transcript_items = transcript_data.get('transcript', transcript_data.get('captions', []))
        
        char_position = 0
        for item in transcript_items:
            text = item['text']
            text_length = len(text)
            
            timestamp_map.append({
                'char_start': char_position,
                'char_end': char_position + text_length,
                'time_start': item.get('start', 0),
                'time_end': item.get('start', 0) + item.get('duration', 0)
            })
            
            # Account for the space added when joining
            char_position += text_length + 1  # +1 for space
        
        return timestamp_map
    
    def get_chunk_timestamps(self, chunk_text: str, full_text: str, timestamp_map: List[Dict]) -> tuple:
        """
        Find the start and end timestamps for a chunk of text
        
        Args:
            chunk_text: The chunk text
            full_text: The full transcript text
            timestamp_map: Map of character positions to timestamps
        
        Returns:
            Tuple of (start_time, end_time) in seconds
        """
        # Find where this chunk appears in the full text
        chunk_start_char = full_text.find(chunk_text)
        
        if chunk_start_char == -1:
            return (0, 0)  # Fallback if not found
        
        chunk_end_char = chunk_start_char + len(chunk_text)
        
        # Find timestamps that overlap with this character range
        start_time = None
        end_time = None
        
        for segment in timestamp_map:
            # Check if segment overlaps with chunk
            if segment['char_end'] > chunk_start_char and segment['char_start'] < chunk_end_char:
                if start_time is None:
                    start_time = segment['time_start']
                end_time = segment['time_end']
        
        return (start_time or 0, end_time or 0)
    
    def find_sentence_boundaries(self, text: str) -> List[int]:
        """
        Find sentence boundaries in text (character positions)
        
        Returns list of character indices where sentences end
        """
        # Match sentence endings: . ! ? followed by space/end
        pattern = r'[.!?]+(?:\s+|$)'
        boundaries = [0]  # Start of text
        
        for match in re.finditer(pattern, text):
            boundaries.append(match.end())
        
        if boundaries[-1] != len(text):
            boundaries.append(len(text))
        
        return boundaries
    
    def find_best_break_point(
        self,
        tokens: List[int],
        target_end: int,
        text: str,
        sentence_boundaries: List[int]
    ) -> int:
        """
        Find the best break point considering sentence boundaries
        
        Args:
            tokens: List of token IDs
            target_end: Target end position (in tokens)
            text: Original text
            sentence_boundaries: List of character positions for sentence ends
        
        Returns:
            Best break point (token index)
        """
        # Hard constraint: don't exceed chunk_size
        if target_end > len(tokens):
            return len(tokens)
        
        # Calculate margin in tokens
        margin_start = max(0, target_end - self.sentence_boundary_margin)
        margin_end = min(len(tokens), target_end + self.sentence_boundary_margin)
        
        # Decode tokens in the margin to find character positions
        best_break = target_end
        best_distance = float('inf')
        
        for token_idx in range(margin_start, margin_end + 1):
            # Decode up to this point to get character position
            decoded = self.tokenizer.decode(tokens[:token_idx])
            char_pos = len(decoded)
            
            # Find nearest sentence boundary
            for boundary in sentence_boundaries:
                if boundary <= char_pos:
                    distance = abs(char_pos - boundary)
                    if distance < best_distance and boundary > 0:
                        best_distance = distance
                        best_break = token_idx
        
        # If no good sentence boundary found, use target
        if best_distance > self.sentence_boundary_margin * 2:
            return target_end
        
        return best_break
    
    def chunk_tokens(
        self,
        text: str,
        tokens: List[int],
        sentence_boundaries: List[int],
        timestamp_map: List[Dict] = None
    ) -> List[Dict]:
        """
        Chunk tokens with sliding window and soft sentence boundaries
        
        Args:
            text: Original text
            tokens: List of token IDs
            sentence_boundaries: Character positions of sentence ends
            timestamp_map: Optional map of character positions to timestamps
        
        Returns:
            List of chunk dictionaries
        """
        chunks = []
        start_idx = 0
        chunk_index = 0
        
        while start_idx < len(tokens):
            # Calculate target end (hard constraint)
            target_end = start_idx + self.chunk_size
            
            # Find best break point (with soft sentence boundary consideration)
            if target_end < len(tokens):
                end_idx = self.find_best_break_point(
                    tokens,
                    target_end,
                    text,
                    sentence_boundaries
                )
            else:
                end_idx = len(tokens)
            
            # Extract chunk tokens
            chunk_tokens = tokens[start_idx:end_idx]
            chunk_text = self.tokenizer.decode(chunk_tokens)
            
            # Create chunk metadata
            chunk = {
                'chunk_index': chunk_index,
                'start_token': start_idx,
                'end_token': end_idx,
                'token_count': len(chunk_tokens),
                'text': chunk_text.strip()
            }
            
            # Add timestamps if available
            if timestamp_map:
                start_time, end_time = self.get_chunk_timestamps(chunk_text, text, timestamp_map)
                chunk['start_time'] = round(start_time, 2)
                chunk['end_time'] = round(end_time, 2)
            
            chunks.append(chunk)
            
            # Move to next chunk with overlap
            start_idx = end_idx - self.overlap
            
            # Prevent infinite loop if we're at the end
            if end_idx >= len(tokens):
                break
            
            chunk_index += 1
        
        return chunks
    
    def process_transcript(self, json_path: Path) -> Dict:
        """
        Process a single transcript file
        
        Args:
            json_path: Path to JSON transcript file
        
        Returns:
            Dictionary with video metadata and chunks
        """
        # Load transcript
        transcript_data = self.load_transcript(json_path)
        
        # Extract text
        full_text = self.get_full_text(transcript_data)
        
        if not full_text:
            print(f"  ⚠ No text found in {json_path.name}")
            return None
        
        # Tokenize
        tokens = self.tokenizer.encode(full_text)
        
        # Build timestamp map
        timestamp_map = self.build_timestamp_map(transcript_data)
        
        # Find sentence boundaries
        sentence_boundaries = self.find_sentence_boundaries(full_text)
        
        # Chunk tokens with timestamps
        chunks = self.chunk_tokens(full_text, tokens, sentence_boundaries, timestamp_map)
        
        # Extract channel from directory structure (parent directory name)
        channel = json_path.parent.name if json_path.parent.name != 'captions_output' else 'Unknown'
        
        # Prepare output with all metadata
        result = {
            'video_id': transcript_data.get('video_id', ''),
            'title': transcript_data.get('title', ''),
            'channel': channel,
            'published_at': transcript_data.get('published_at', ''),
            'language': transcript_data.get('language', 'en'),
            'duration': transcript_data.get('duration'),
            'is_song': transcript_data.get('is_song', False),
            'total_tokens': len(tokens),
            'total_chunks': len(chunks),
            'chunks': chunks
        }
        
        return result
    
    def process_directory(
        self,
        input_dir: Path,
        output_dir: Path
    ) -> List[str]:
        """
        Process all transcript files in a directory
        
        Args:
            input_dir: Directory containing JSON transcript files
            output_dir: Directory to save chunked output
        
        Returns:
            List of processed video IDs
        """
        output_dir.mkdir(exist_ok=True, parents=True)
        
        # Find all JSON files
        json_files = list(input_dir.rglob('*.json'))
        
        if not json_files:
            print(f"✗ No JSON files found in {input_dir}")
            return []
        
        print(f"\n📄 Found {len(json_files)} transcript files")
        print(f"📁 Output directory: {output_dir}")
        print()
        
        processed = []
        
        for json_file in json_files:
            try:
                print(f"Processing: {json_file.name}")
                
                # Process transcript
                result = self.process_transcript(json_file)
                
                if result:
                    # Save chunked output
                    video_id = result['video_id']
                    output_file = output_dir / f"{video_id}_chunked.json"
                    
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(result, f, indent=2, ensure_ascii=False)
                    
                    print(f"  {result['total_chunks']} chunks ({result['total_tokens']} tokens)")
                    print(f"  💾 Saved: {output_file.name}")
                    
                    processed.append(video_id)
                
            except Exception as e:
                print(f"  ✗ Error processing {json_file.name}: {e}")
                continue
            
            print()
        
        return processed
    
    def process_all_captions(self):
        """
        Process all caption files from input_dir to output_dir
        Wrapper method for pipeline integration
        
        Returns:
            Dictionary with processing statistics
        """
        if not self.input_dir or not self.output_dir:
            raise ValueError("input_dir and output_dir must be set")
        
        processed = self.process_directory(self.input_dir, self.output_dir)
        
        # Calculate total chunks
        total_chunks = 0
        if self.output_dir.exists():
            for chunk_file in self.output_dir.glob('*_chunked.json'):
                try:
                    with open(chunk_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        total_chunks += data.get('total_chunks', 0)
                except:
                    pass
        
        return {
            'files_processed': len(processed),
            'total_chunks': total_chunks
        }


def main():
    """Main entry point"""
    print("=" * 70)
    print("Video Transcript Chunking Pipeline")
    print("=" * 70)
    print()
    
    # Initialize chunker
    chunker = TranscriptChunker(
        chunk_size=250,
        overlap=40,
        sentence_boundary_margin=20
    )
    
    print()
    
    # Set paths
    input_dir = Path('captions_output/numberblocks')
    output_dir = Path('chunked_output')
    
    if not input_dir.exists():
        print(f"✗ Input directory not found: {input_dir}")
        return
    
    # Process all transcripts
    processed = chunker.process_directory(input_dir, output_dir)
    
    print("=" * 70)
    print(f"Pipeline completed!")
    print(f"  Processed: {len(processed)} videos")
    print(f"  Output: {output_dir.absolute()}")
    print("=" * 70)


if __name__ == '__main__':
    main()
