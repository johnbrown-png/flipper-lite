"""
Generate vector embeddings from chunked transcripts using OpenAI API.

This script:
1. Loads chunked transcript files
2. Generates embeddings using text-embedding-3-large
3. Saves embeddings with metadata for vector search
"""

import os
import json
import time
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict

from openai import OpenAI
from dotenv import load_dotenv


@dataclass
class EmbeddingMetadata:
    """Metadata for a single embedding"""
    video_id: str
    title: str
    channel: str
    published_at: str
    language: str
    duration: int
    is_song: bool
    chunk_index: int
    start_token: int
    end_token: int
    token_count: int
    text: str
    start_time: float
    end_time: float
    embedding_model: str
    embedding_dimension: int


class EmbeddingGenerator:
    """Generate embeddings from text chunks using OpenAI API"""
    
    def __init__(
        self,
        api_key: str,
        input_dir: str = None,
        output_dir: str = None,
        model: str = "text-embedding-3-large",
        dimensions: Optional[int] = None,
        batch_size: int = 100,
        rate_limit_delay: float = 0.1
    ):
        """
        Initialize the embedding generator
        
        Args:
            api_key: OpenAI API key
            input_dir: Input directory containing chunked files
            output_dir: Output directory for embeddings
            model: Embedding model name (text-embedding-3-large or text-embedding-3-small)
            dimensions: Optional dimension reduction (text-embedding-3-large: max 3072)
            batch_size: Number of texts to embed in one API call
            rate_limit_delay: Delay between API calls in seconds
        """
        self.client = OpenAI(api_key=api_key)
        self.input_dir = Path(input_dir) if input_dir else None
        self.output_dir = Path(output_dir) if output_dir else None
        self.model = model
        self.dimensions = dimensions
        self.batch_size = batch_size
        self.rate_limit_delay = rate_limit_delay
        
        # Get default dimensions for model
        if dimensions is None:
            self.dimensions = 3072 if "large" in model else 1536
        
        print(f"✓ Initialized OpenAI client")
        print(f"  Model: {model}")
        print(f"  Dimensions: {self.dimensions}")
        print(f"  Batch size: {batch_size}")
    
    def load_chunked_file(self, json_path: Path) -> Dict:
        """Load a chunked transcript file"""
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text
        
        Args:
            text: Text to embed
        
        Returns:
            List of floats representing the embedding vector
        """
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=self.dimensions
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"  ✗ Error generating embedding: {e}")
            raise
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in one API call
        
        Args:
            texts: List of texts to embed
        
        Returns:
            List of embedding vectors
        """
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=texts,
                dimensions=self.dimensions
            )
            # Sort by index to ensure correct order
            embeddings = sorted(response.data, key=lambda x: x.index)
            return [emb.embedding for emb in embeddings]
        except Exception as e:
            print(f"  ✗ Error generating batch embeddings: {e}")
            raise
    
    def process_chunked_file(
        self,
        json_path: Path,
        use_batch: bool = True
    ) -> List[Dict]:
        """
        Process a chunked transcript file and generate embeddings
        
        Args:
            json_path: Path to chunked JSON file
            use_batch: Whether to use batch API calls
        
        Returns:
            List of dictionaries with embeddings and metadata
        """
        # Load chunked data
        data = self.load_chunked_file(json_path)
        chunks = data.get('chunks', [])
        
        if not chunks:
            print(f"  ⚠ No chunks found in {json_path.name}")
            return []
        
        results = []
        
        if use_batch and len(chunks) > 1:
            # Batch processing
            texts = [chunk['text'] for chunk in chunks]
            
            # Process in batches
            for i in range(0, len(texts), self.batch_size):
                batch_texts = texts[i:i + self.batch_size]
                batch_chunks = chunks[i:i + self.batch_size]
                
                embeddings = self.generate_embeddings_batch(batch_texts)
                
                # Create result objects
                for chunk, embedding in zip(batch_chunks, embeddings):
                    metadata = EmbeddingMetadata(
                        video_id=data['video_id'],
                        title=data['title'],
                        channel=data.get('channel', 'Unknown'),
                        published_at=data['published_at'],
                        language=data.get('language', 'en'),
                        duration=data.get('duration', 0),
                        is_song=data.get('is_song', False),
                        chunk_index=chunk['chunk_index'],
                        start_token=chunk['start_token'],
                        end_token=chunk['end_token'],
                        token_count=chunk['token_count'],
                        text=chunk['text'],
                        start_time=chunk.get('start_time', 0),
                        end_time=chunk.get('end_time', 0),
                        embedding_model=self.model,
                        embedding_dimension=self.dimensions
                    )
                    
                    results.append({
                        'metadata': asdict(metadata),
                        'embedding': embedding
                    })
                
                # Rate limiting
                if i + self.batch_size < len(texts):
                    time.sleep(self.rate_limit_delay)
        else:
            # Single processing
            for chunk in chunks:
                embedding = self.generate_embedding(chunk['text'])
                
                metadata = EmbeddingMetadata(
                    video_id=data['video_id'],
                    title=data['title'],
                    channel=data.get('channel', 'Unknown'),
                    published_at=data['published_at'],
                    language=data.get('language', 'en'),
                    duration=data.get('duration', 0),
                    is_song=data.get('is_song', False),
                    chunk_index=chunk['chunk_index'],
                    start_token=chunk['start_token'],
                    end_token=chunk['end_token'],
                    token_count=chunk['token_count'],
                    text=chunk['text'],
                    start_time=chunk.get('start_time', 0),
                    end_time=chunk.get('end_time', 0),
                    embedding_model=self.model,
                    embedding_dimension=self.dimensions
                )
                
                results.append({
                    'metadata': asdict(metadata),
                    'embedding': embedding
                })
                
                # Rate limiting
                time.sleep(self.rate_limit_delay)
        
        return results
    
    def process_directory(
        self,
        input_dir: Path,
        output_dir: Path,
        use_batch: bool = True,
        skip_existing: bool = True
    ) -> Dict[str, int]:
        """
        Process all chunked files in a directory
        
        Args:
            input_dir: Directory containing chunked JSON files
            output_dir: Directory to save embeddings
            use_batch: Whether to use batch API calls
            skip_existing: If True, skip files that already have embeddings
        
        Returns:
            Dictionary with processing statistics
        """
        output_dir.mkdir(exist_ok=True, parents=True)
        
        # Find all chunked JSON files
        json_files = list(input_dir.glob('*_chunked.json'))
        
        if not json_files:
            print(f"✗ No chunked files found in {input_dir}")
            return {'processed': 0, 'total_embeddings': 0, 'failed': 0, 'skipped': 0}
        
        print(f"\n📄 Found {len(json_files)} chunked files")
        print(f"📁 Output directory: {output_dir}")
        
        # Check for existing embeddings if skip_existing is True
        existing_embeddings = set()
        if skip_existing:
            existing_files = list(output_dir.glob('*_embeddings.json'))
            existing_embeddings = {f.stem.replace('_embeddings', '') for f in existing_files}
            if existing_embeddings:
                print(f"ℹ️  Found {len(existing_embeddings)} existing embeddings (will skip)")
        
        print()
        
        stats = {
            'processed': 0,
            'total_embeddings': 0,
            'failed': 0,
            'skipped': 0
        }
        
        for json_file in json_files:
            try:
                # Extract video_id from filename (before _chunked.json)
                video_id = json_file.stem.replace('_chunked', '')
                
                # Check if embeddings already exist
                if skip_existing and video_id in existing_embeddings:
                    print(f"⏭️  Skipping: {json_file.name} (already embedded)")
                    stats['skipped'] += 1
                    continue
                
                print(f"Processing: {json_file.name}")
                
                # Generate embeddings
                results = self.process_chunked_file(json_file, use_batch)
                
                if results:
                    # Save embeddings
                    video_id = results[0]['metadata']['video_id']
                    output_file = output_dir / f"{video_id}_embeddings.json"
                    
                    output_data = {
                        'video_id': video_id,
                        'title': results[0]['metadata']['title'],
                        'published_at': results[0]['metadata']['published_at'],
                        'embedding_model': self.model,
                        'embedding_dimension': self.dimensions,
                        'total_chunks': len(results),
                        'embeddings': results
                    }
                    
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(output_data, f, indent=2, ensure_ascii=False)
                    
                    print(f"  ✓ Generated {len(results)} embeddings")
                    print(f"  💾 Saved: {output_file.name}")
                    
                    stats['processed'] += 1
                    stats['total_embeddings'] += len(results)
                
            except Exception as e:
                print(f"  ✗ Error processing {json_file.name}: {e}")
                stats['failed'] += 1
                continue
            
            print()
        
        return stats
    
    def process_all_chunks(self):
        """
        Process all chunked files from input_dir to output_dir, skip_existing=True)
        
        return {
            'files_processed': stats['processed'],
            'total_embeddings': stats['total_embeddings'],
            'skipped': stats.get('skipped', 0)
        """
        if not self.input_dir or not self.output_dir:
            raise ValueError("input_dir and output_dir must be set")
        
        stats = self.process_directory(self.input_dir, self.output_dir, use_batch=True)
        
        return {
            'files_processed': stats['processed'],
            'total_embeddings': stats['total_embeddings']
        }
    
    def save_consolidated_embeddings(
        self,
        embeddings_dir: Path,
        output_file: Path
    ):
        """
        Consolidate all embeddings into a single file
        
        Args:
            embeddings_dir: Directory containing individual embedding files
            output_file: Output file for consolidated embeddings
        """
        print("\n📦 Consolidating embeddings...")
        
        all_embeddings = []
        embedding_files = list(embeddings_dir.glob('*_embeddings.json'))
        
        for emb_file in embedding_files:
            with open(emb_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                all_embeddings.extend(data['embeddings'])
        
        consolidated = {
            'embedding_model': self.model,
            'embedding_dimension': self.dimensions,
            'total_videos': len(embedding_files),
            'total_embeddings': len(all_embeddings),
            'embeddings': all_embeddings
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(consolidated, f, indent=2, ensure_ascii=False)
        
        print(f"  ✓ Consolidated {len(all_embeddings)} embeddings from {len(embedding_files)} videos")
        print(f"  💾 Saved: {output_file}")


def main():
    """Main entry point"""
    # Load environment variables
    load_dotenv()
    
    print("=" * 70)
    print("Video Transcript Embedding Generation Pipeline")
    print("=" * 70)
    print()
    
    # Get API key
    api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key or api_key == 'your_api_key_here':
        print("✗ Error: Please set OPENAI_API_KEY in .env file")
        print("  Get your API key from: https://platform.openai.com/api-keys")
        return
    
    # Configuration
    model = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-large')
    dimensions = os.getenv('EMBEDDING_DIMENSIONS', None)
    if dimensions:
        dimensions = int(dimensions)
    
    # Initialize generator
    generator = EmbeddingGenerator(
        api_key=api_key,
        model=model,
        dimensions=dimensions,
        batch_size=100,
        rate_limit_delay=0.1
    )
    
    print()
    
    # Set paths
    input_dir = Path('chunked_output')
    output_dir = Path('embeddings_output')
    
    if not input_dir.exists():
        print(f"✗ Input directory not found: {input_dir}")
        return
    
    # Process all chunked files, skip_existing=True)
    
    # Create consolidated file
    if stats['processed'] > 0:
        consolidated_file = Path('embeddings_consolidated.json')
        generator.save_consolidated_embeddings(output_dir, consolidated_file)
    
    print()
    print("=" * 70)
    print(f"✓ Pipeline completed!")
    print(f"  Videos processed: {stats['processed']}")
    print(f"  Videos skipped: {stats.get('skipped', 0)} (already embedded)")
    print(f"  Total embeddings: {stats['total_embeddings']}")
    print(f"  Failed: {stats['failed']}")
    print(f"  Output: {output_dir.absolute()}")
    print("=" * 70)


if __name__ == '__main__':
    main()
