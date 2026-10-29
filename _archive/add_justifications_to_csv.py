"""
Add instruction justifications to precomputed_recommendations_flat.csv
without re-running expensive LLM calls.

This script extracts justifications from the existing instruction_quality_runtime_cache.json
and adds them to the CSV file.
"""

import pandas as pd
import json
from pathlib import Path


def add_justifications_to_csv(
    csv_path='precomputed_recommendations_flat.csv',
    cache_path='data/instruction_quality_runtime_cache.json',
    output_path=None
):
    """
    Add instruction_justification column to existing CSV using cached data.
    
    Args:
        csv_path: Path to the precomputed recommendations CSV
        cache_path: Path to the instruction quality runtime cache JSON
        output_path: Output path (defaults to overwriting csv_path)
    """
    if output_path is None:
        output_path = csv_path
    
    print(f"Loading CSV from {csv_path}...")
    df = pd.read_csv(csv_path)
    original_rows = len(df)
    print(f"  Loaded {original_rows} rows")
    
    print(f"\nLoading instruction quality cache from {cache_path}...")
    cache_file = Path(cache_path)
    if not cache_file.exists():
        print(f"  ❌ Cache file not found at {cache_path}")
        print(f"  Cannot add justifications without cache data.")
        return
    
    with open(cache_file, 'r', encoding='utf-8') as f:
        cache = json.load(f)
    print(f"  Loaded {len(cache)} cached instruction quality scores")
    
    # Build lookup: cache key is "{video_id}|{age}|{small_step}"
    print("\nMapping justifications to videos...")
    justifications_added = 0
    justifications_missing = 0
    
    # Add instruction_justification column if it doesn't exist
    if 'instruction_justification' not in df.columns:
        df['instruction_justification'] = ''
    
    for idx, row in df.iterrows():
        video_id = row.get('video_id', '')
        
        # Skip empty video IDs
        if not video_id or pd.isna(video_id) or str(video_id).strip() == '':
            df.at[idx, 'instruction_justification'] = ''
            continue
        
        # Extract age from curriculum context
        # Age might be in year column or separate age column
        year = row.get('year', '')
        age = ''
        
        # Try to extract age from year column
        # Year format examples: "Year 1", "Year 2", "Reception"
        if 'year' in df.columns and row.get('year'):
            year_str = str(row['year'])
            if 'Reception' in year_str:
                age = '4-5'
            elif 'Year 1' in year_str:
                age = '5-6'
            elif 'Year 2' in year_str:
                age = '6-7'
            elif 'Year 3' in year_str:
                age = '7-8'
            elif 'Year 4' in year_str:
                age = '8-9'
            elif 'Year 5' in year_str:
                age = '9-10'
            elif 'Year 6' in year_str:
                age = '10-11'
        
        small_step = row.get('small_step', '')
        
        # Build cache key
        cache_key = f"{video_id}|{age}|{small_step}"
        
        # Look up in cache
        if cache_key in cache:
            justification = cache[cache_key].get('justification', '')
            df.at[idx, 'instruction_justification'] = justification
            justifications_added += 1
        else:
            df.at[idx, 'instruction_justification'] = ''
            justifications_missing += 1
    
    print(f"\n✅ Justifications added: {justifications_added}")
    print(f"⚠️  Justifications missing: {justifications_missing}")
    
    # Save updated CSV
    print(f"\nSaving updated CSV to {output_path}...")
    df.to_csv(output_path, index=False)
    print(f"✅ Complete! Updated CSV saved to {output_path}")
    
    # Show sample
    print("\n📝 Sample justifications:")
    print("=" * 80)
    sample_with_justification = df[df['instruction_justification'].str.len() > 0].head(3)
    for idx, row in sample_with_justification.iterrows():
        print(f"\nVideo: {row['video_title']}")
        print(f"Topic: {row['topic']} - {row['small_step']}")
        print(f"Instruction Score: {row['instruction_quality_score']}")
        print(f"Justification: {row['instruction_justification']}")
        print("-" * 80)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Add instruction justifications to precomputed CSV from cache'
    )
    parser.add_argument(
        '--csv',
        default='precomputed_recommendations_flat.csv',
        help='Path to the precomputed recommendations CSV'
    )
    parser.add_argument(
        '--cache',
        default='data/instruction_quality_runtime_cache.json',
        help='Path to instruction quality runtime cache JSON'
    )
    parser.add_argument(
        '--output',
        help='Output CSV path (defaults to overwriting input CSV)'
    )
    
    args = parser.parse_args()
    
    add_justifications_to_csv(
        csv_path=args.csv,
        cache_path=args.cache,
        output_path=args.output
    )
