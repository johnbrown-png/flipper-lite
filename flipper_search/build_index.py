"""
Offline script to precompute curriculum embeddings.

Run once to embed all curriculum small steps, save embeddings for fast runtime retrieval.
Usage:
    python -m flipper_search.build_index --curriculum Curriculum/Maths/curriculum_08052026_small_steps.csv --output data/curriculum_embeddings.npy
"""

import argparse
import numpy as np
from pathlib import Path
import os
from dotenv import load_dotenv

from .curriculum_index import CurriculumIndex


def build_embeddings(
    curriculum_csv_path: str,
    output_path: str,
    batch_size: int = 50,
):
    """
    Precompute embeddings for all curriculum small steps.
    
    Args:
        curriculum_csv_path: Path to curriculum CSV
        output_path: Output path for .npy embeddings file
        batch_size: Batch size for embedding API calls
    """
    print("=" * 80)
    print("Flipper Search - Curriculum Embedding Builder")
    print("=" * 80)
    print()
    
    # Load curriculum
    print(f"Loading curriculum from: {curriculum_csv_path}")
    index = CurriculumIndex(curriculum_csv_path)
    print(f"✓ Loaded {len(index.get_searchable_text_all())} small steps")
    print()
    
    # Initialize embedder
    print("Initializing OpenAI embedder...")
    try:
        from query_embedder import QueryEmbedder
        load_dotenv()
        api_key = os.getenv('OPENAI_API_KEY')
        embedder = QueryEmbedder(api_key=api_key)
        print("✓ QueryEmbedder initialized")
    except Exception as e:
        print(f"✗ Failed to initialize embedder: {e}")
        return False
    print()
    
    # Get all texts
    searchable_texts_dict = index.get_searchable_text_all()
    small_step_ids = list(searchable_texts_dict.keys())
    texts = [searchable_texts_dict[ss_id] for ss_id in small_step_ids]
    
    # Embed in batches
    print(f"Embedding {len(texts)} texts in batches of {batch_size}...")
    all_embeddings = []
    total_batches = (len(texts) + batch_size - 1) // batch_size
    
    for batch_idx in range(0, len(texts), batch_size):
        batch_texts = texts[batch_idx:batch_idx + batch_size]
        batch_num = batch_idx // batch_size + 1
        
        try:
            embeddings = embedder.embed_batch(batch_texts)
            all_embeddings.extend(embeddings)
            print(f"  Batch {batch_num}/{total_batches}: {len(batch_texts)} texts embedded")
        except Exception as e:
            print(f"  ✗ Batch {batch_num} failed: {e}")
            print(f"    Trying single-query fallback...")
            for text in batch_texts:
                try:
                    emb = embedder.embed_query(text)
                    all_embeddings.append(emb[0])
                except Exception as e2:
                    print(f"    ✗ Could not embed: {text[:50]}... Error: {e2}")
                    # Use zero embedding as fallback
                    all_embeddings.append(np.zeros(3072))
    
    print()
    
    # Convert to numpy array
    embeddings_array = np.array(all_embeddings).astype('float32')
    print(f"Embeddings shape: {embeddings_array.shape}")
    
    # Save
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(str(output_path), embeddings_array)
    print(f"✓ Saved embeddings to: {output_path}")
    
    # Save metadata (mapping of small_step_id to embedding index)
    metadata = {
        'small_step_ids': small_step_ids,
        'embedding_shape': embeddings_array.shape,
        'total_steps': len(small_step_ids),
    }
    
    import json
    metadata_path = output_path.with_suffix('.json')
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"✓ Saved metadata to: {metadata_path}")
    print()
    
    print("=" * 80)
    print("✓ Embedding build complete!")
    print("=" * 80)
    
    return True


def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(
        description="Precompute curriculum embeddings for flipper_search"
    )
    parser.add_argument(
        '--curriculum',
        type=str,
        default='Curriculum/Maths/curriculum_08052026_small_steps.csv',
        help='Path to curriculum CSV'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='data/curriculum_embeddings.npy',
        help='Output path for embeddings file'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=50,
        help='Batch size for embedding API calls'
    )
    
    args = parser.parse_args()
    
    success = build_embeddings(
        args.curriculum,
        args.output,
        batch_size=args.batch_size,
    )
    
    exit(0 if success else 1)


if __name__ == '__main__':
    main()
