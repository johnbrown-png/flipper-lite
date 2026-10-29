"""
Backfill Readability Scores for Existing Videos

This script calculates readability scores for all existing caption files
and saves them to data/video_readability.json. This only needs to be run once
for existing videos. New videos will have readability calculated automatically
during the pipeline.

Usage:
    python backfill_readability.py [--force] [--captions-dir data/captions]
"""

import sys
from pathlib import Path
import argparse

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from data_pipeline.readability_calculator import ReadabilityCalculator


def main():
    """Run readability calculation for all existing videos"""
    
    parser = argparse.ArgumentParser(
        description="Calculate readability scores for existing video captions"
    )
    parser.add_argument(
        '--captions-dir',
        type=str,
        default='data/captions_output',
        help='Directory containing caption files (default: data/captions_output)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='data/video_readability.json',
        help='Output JSON file for readability scores (default: data/video_readability.json)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Recalculate scores for all videos, even if they already exist'
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("BACKFILL READABILITY SCORES")
    print("=" * 80)
    print()
    print("This will calculate Flesch Reading Ease and Flesch-Kincaid Grade Level")
    print("for all videos with existing captions.")
    print()
    
    # Check if captions directory exists
    captions_dir = Path(args.captions_dir)
    if not captions_dir.exists():
        print(f"✗ Captions directory not found: {captions_dir}")
        print("  Please run caption extraction first.")
        return 1
    
    # Initialize calculator
    try:
        calculator = ReadabilityCalculator(output_file=args.output)
    except ImportError as e:
        print(f"✗ {e}")
        print("\nPlease install textstat:")
        print("  pip install textstat")
        return 1
    
    # Process all caption files
    stats = calculator.process_directory(
        captions_dir=captions_dir,
        force_recalculate=args.force
    )
    
    print("\n" + "=" * 80)
    print("BACKFILL COMPLETED")
    print("=" * 80)
    print(f"\nReadability scores saved to: {args.output}")
    print("\nYou can now use these scores in flipper.py for search re-ranking.")
    print("=" * 80)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
