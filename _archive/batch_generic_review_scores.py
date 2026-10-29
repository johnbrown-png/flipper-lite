"""
Helper script to review instruction quality scores

This script helps you review scored videos in various ways:
- Show top/bottom scored videos
- Show videos in specific score ranges
- Show random samples
- Compare scores with video metadata

Usage:
  python review_instruction_scores.py --top 10
  python review_instruction_scores.py --bottom 10
  python review_instruction_scores.py --range 70 89
  python review_instruction_scores.py --random 5
  python review_instruction_scores.py --video-id VIDEO_ID
"""

import json
import argparse
import random
from pathlib import Path


def load_scores(score_file: str):
    """Load instruction quality scores"""
    path = Path(score_file)
    if not path.exists():
        print(f"❌ Score file not found: {score_file}")
        return None
    
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def print_video(video_data: dict, show_justification: bool = True):
    """Print a single video's information"""
    print(f"\nTitle: {video_data.get('title', 'Unknown')}")
    print(f"Score: {video_data.get('score', 'N/A')}/100")
    if show_justification:
        print(f"Justification: {video_data.get('justification', 'N/A')}")
    print(f"Video ID: {video_data.get('video_id', 'Unknown')}")
    print(f"YouTube URL: https://www.youtube.com/watch?v={video_data.get('video_id', '')}")
    print(f"Scored at: {video_data.get('scored_at', 'Unknown')}")
    print("-" * 80)


def main():
    parser = argparse.ArgumentParser(description='Review instruction quality scores')
    
    parser.add_argument('--file', default='data/video_instruction_quality.json',
                        help='Score file path')
    
    parser.add_argument('--top', type=int, metavar='N',
                        help='Show top N highest scored videos')
    
    parser.add_argument('--bottom', type=int, metavar='N',
                        help='Show bottom N lowest scored videos')
    
    parser.add_argument('--range', nargs=2, type=int, metavar=('LOW', 'HIGH'),
                        help='Show videos in score range (e.g., --range 70 89)')
    
    parser.add_argument('--random', type=int, metavar='N',
                        help='Show N random videos')
    
    parser.add_argument('--video-id', type=str,
                        help='Show specific video by ID')
    
    parser.add_argument('--stats', action='store_true',
                        help='Show overall statistics')
    
    parser.add_argument('--no-justification', action='store_true',
                        help='Hide justification text (compact view)')
    
    args = parser.parse_args()
    
    # Load scores
    scores = load_scores(args.file)
    if scores is None:
        return 1
    
    if not scores:
        print("No videos scored yet.")
        return 0
    
    print(f"\n{'='*80}")
    print(f"INSTRUCTION QUALITY SCORE REVIEW")
    print(f"{'='*80}")
    print(f"Total scored videos: {len(scores)}\n")
    
    # Statistics
    if args.stats or (not any([args.top, args.bottom, args.range, args.random, args.video_id])):
        score_values = [v['score'] for v in scores.values()]
        print(f"Average score: {sum(score_values)/len(score_values):.1f}/100")
        print(f"Highest score: {max(score_values)}/100")
        print(f"Lowest score: {min(score_values)}/100")
        print(f"Median score: {sorted(score_values)[len(score_values)//2]}/100")
        
        # Distribution
        print(f"\nScore Distribution:")
        ranges = [(0, 29, "Very poor"), (30, 49, "Weak"), (50, 69, "Adequate"), 
                  (70, 89, "Good"), (90, 100, "Excellent")]
        for low, high, label in ranges:
            count = sum(1 for s in score_values if low <= s <= high)
            pct = count / len(score_values) * 100
            bar = '█' * int(pct / 2)
            print(f"  {low:3d}-{high:3d} ({label:10s}): {count:4d} videos ({pct:5.1f}%) {bar}")
        
        if args.stats:
            return 0
    
    show_just = not args.no_justification
    
    # Top N
    if args.top:
        sorted_videos = sorted(scores.items(), key=lambda x: x[1]['score'], reverse=True)
        print(f"\n{'='*80}")
        print(f"TOP {args.top} HIGHEST SCORED VIDEOS")
        print(f"{'='*80}")
        for i, (video_id, video_data) in enumerate(sorted_videos[:args.top], 1):
            print(f"\n#{i}")
            print_video(video_data, show_just)
    
    # Bottom N
    if args.bottom:
        sorted_videos = sorted(scores.items(), key=lambda x: x[1]['score'])
        print(f"\n{'='*80}")
        print(f"BOTTOM {args.bottom} LOWEST SCORED VIDEOS")
        print(f"{'='*80}")
        for i, (video_id, video_data) in enumerate(sorted_videos[:args.bottom], 1):
            print(f"\n#{i}")
            print_video(video_data, show_just)
    
    # Range
    if args.range:
        low, high = args.range
        in_range = [(vid, data) for vid, data in scores.items() 
                    if low <= data['score'] <= high]
        in_range.sort(key=lambda x: x[1]['score'], reverse=True)
        
        print(f"\n{'='*80}")
        print(f"VIDEOS SCORED {low}-{high} ({len(in_range)} videos)")
        print(f"{'='*80}")
        for video_id, video_data in in_range:
            print_video(video_data, show_just)
    
    # Random
    if args.random:
        sample_ids = random.sample(list(scores.keys()), min(args.random, len(scores)))
        print(f"\n{'='*80}")
        print(f"RANDOM SAMPLE ({args.random} videos)")
        print(f"{'='*80}")
        for video_id in sample_ids:
            print_video(scores[video_id], show_just)
    
    # Specific video
    if args.video_id:
        if args.video_id in scores:
            print(f"\n{'='*80}")
            print(f"VIDEO DETAILS")
            print(f"{'='*80}")
            print_video(scores[args.video_id], show_just=True)
        else:
            print(f"\n❌ Video ID not found: {args.video_id}")
            print(f"   (Video may not be scored yet)")
    
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
