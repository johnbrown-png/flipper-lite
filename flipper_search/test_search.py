"""
Test and demo script for flipper_search.

Usage:
    python -m flipper_search.test_search --query "adding fractions"
    python -m flipper_search.test_search --curriculum path/to/curriculum.csv --query "gradient"
"""

import argparse
import sys
from pathlib import Path

from curriculum_index import CurriculumIndex
from search_engine import SearchEngine


def test_search(
    curriculum_csv_path: str,
    query: str,
    embeddings_path: str = None,
    top_k: int = 10,
    use_semantic: bool = True,
):
    """
    Run a test search and print results.
    
    Args:
        curriculum_csv_path: Path to curriculum CSV
        query: Search query
        embeddings_path: Path to precomputed embeddings
        top_k: Number of results
        use_semantic: Whether to use semantic search
    """
    print("=" * 80)
    print(f"Flipper Search - Test Search")
    print("=" * 80)
    print()
    
    # Load curriculum
    print(f"Loading curriculum: {curriculum_csv_path}")
    try:
        index = CurriculumIndex(curriculum_csv_path)
        print(f"✓ Loaded {len(index.embedding_ids)} small steps")
    except Exception as e:
        print(f"✗ Failed to load curriculum: {e}")
        return False
    print()
    
    # Initialize search engine
    print(f"Initializing search engine (semantic={use_semantic})...")
    try:
        engine = SearchEngine(
            index,
            embeddings_path=embeddings_path,
            use_semantic=use_semantic,
        )
        print("✓ Search engine initialized")
    except Exception as e:
        print(f"✗ Failed to initialize search engine: {e}")
        return False
    print()
    
    # Run search
    print(f"Searching for: '{query}'")
    print()
    
    try:
        results = engine.search(query, top_k=top_k)
        
        if not results:
            print("No results found.")
            return True
        
        print(f"Found {len(results)} results:\n")
        
        for idx, result in enumerate(results, 1):
            print(f"{idx}. {result.get('small_step_name', 'Untitled')}")
            print(f"   Topic: {result.get('topic', 'N/A')}")
            print(f"   Year: {result.get('year', 'N/A')} | Age: {result.get('age', 'N/A')}")
            
            # Scores
            scores = []
            if 'lexical_score' in result:
                scores.append(f"Lexical: {result['lexical_score']:.1%}")
            if 'semantic_score' in result:
                scores.append(f"Semantic: {result['semantic_score']:.1%}")
            if 'combined_score' in result:
                scores.append(f"Combined: {result['combined_score']:.1%}")
            
            if scores:
                print(f"   {' | '.join(scores)}")
            
            # ss_desc preview
            ss_desc = result.get('ss_desc', '')
            if ss_desc:
                preview = ss_desc[:100] + "..." if len(ss_desc) > 100 else ss_desc
                print(f"   Description: {preview}")
            
            print()
        
        print("=" * 80)
        return True
    
    except Exception as e:
        print(f"✗ Search failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(
        description="Test flipper_search with a sample query"
    )
    parser.add_argument(
        '--curriculum',
        type=str,
        default='Curriculum/Maths/curriculum_08052026_small_steps.csv',
        help='Path to curriculum CSV'
    )
    parser.add_argument(
        '--query',
        type=str,
        required=True,
        help='Search query'
    )
    parser.add_argument(
        '--embeddings',
        type=str,
        default='data/curriculum_embeddings.npy',
        help='Path to precomputed embeddings'
    )
    parser.add_argument(
        '--top-k',
        type=int,
        default=10,
        help='Number of results'
    )
    parser.add_argument(
        '--no-semantic',
        action='store_true',
        help='Disable semantic reranking (lexical-only)'
    )
    
    args = parser.parse_args()
    
    # Check if embeddings exist
    embeddings_path = args.embeddings
    if not Path(embeddings_path).exists():
        print(f"⚠ Warning: Embeddings file not found: {embeddings_path}")
        print("  Run: python -m flipper_search.build_index")
        print("  Or use: --no-semantic for lexical-only search")
        embeddings_path = None
        if not args.no_semantic:
            print()
    
    success = test_search(
        args.curriculum,
        args.query,
        embeddings_path=embeddings_path,
        top_k=args.top_k,
        use_semantic=not args.no_semantic,
    )
    
    exit(0 if success else 1)


if __name__ == '__main__':
    main()
