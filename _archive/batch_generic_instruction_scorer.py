"""
Score videos for instructional quality using LLM evaluation

This script provides a controlled workflow for scoring videos:
1. First run: Score 50 random sample videos → STOP for review
2. After review: Score all remaining videos
3. Re-score: Adjust prompt and re-test if needed

Usage:
  python score_instruction_quality.py --sample           # Score 50 random videos (initial test)
  python score_instruction_quality.py --continue         # Score all remaining videos
  python score_instruction_quality.py --rescore-sample   # Re-score the 50 sample videos
  python score_instruction_quality.py --stats            # Show statistics only
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from data_pipeline.instruction_quality_scorer import InstructionQualityScorer


def main():
    parser = argparse.ArgumentParser(
        description='Score videos for instructional quality',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python score_instruction_quality.py --sample
      Score 50 random videos as a test sample
  
  python score_instruction_quality.py --continue
      Score all remaining unscored videos (after reviewing sample)
  
  python score_instruction_quality.py --rescore-sample
      Re-score the 50 sample videos (if you adjusted the prompt)
  
  python score_instruction_quality.py --video-ids VIDEO_ID1 VIDEO_ID2
      Score specific videos by video ID
  
  python score_instruction_quality.py --stats
      Show statistics about scored videos
        """
    )
    
    parser.add_argument(
        '--sample',
        action='store_true',
        help='Score 50 random sample videos and stop (for initial testing)'
    )
    
    parser.add_argument(
        '--continue',
        dest='continue_scoring',
        action='store_true',
        help='Score all remaining unscored videos'
    )
    
    parser.add_argument(
        '--rescore-sample',
        action='store_true',
        help='Re-score the previously sampled 50 videos (useful after prompt adjustments)'
    )
    
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics about scored videos'
    )
    
    parser.add_argument(
        '--video-ids',
        nargs='+',
        help='Score specific video(s) by video ID (space-separated list)'
    )
    
    parser.add_argument(
        '--sample-size',
        type=int,
        default=50,
        help='Number of videos to sample (default: 50)'
    )
    
    parser.add_argument(
        '--model',
        default='gpt-4o-mini',
        help='OpenAI model to use (default: gpt-4o-mini)'
    )
    
    parser.add_argument(
        '--output',
        default='data/video_instruction_quality.json',
        help='Output JSON file path'
    )
    
    parser.add_argument(
        '--api-cache',
        default='data/api_cache.json',
        help='API cache file path (deprecated, use --video-source)'
    )
    
    parser.add_argument(
        '--video-source',
        choices=['inventory', 'api_cache'],
        default='inventory',
        help='Video source: inventory (video_inventory.csv) or api_cache (data/api_cache.json). Default: inventory'
    )
    
    parser.add_argument(
        '--video-inventory',
        default='video_inventory.csv',
        help='Video inventory CSV file path'
    )
    
    args = parser.parse_args()
    
    # Initialize scorer
    print("=" * 80)
    print("INSTRUCTION QUALITY SCORER")
    print("=" * 80)
    
    try:
        scorer = InstructionQualityScorer(
            model=args.model,
            output_file=args.output,
            delay_between_requests=1.0  # 1 second between API calls
        )
    except Exception as e:
        print(f"\n❌ Error initializing scorer: {e}")
        return 1
    
    # Handle --stats mode
    if args.stats:
        scorer.print_statistics()
        scorer.print_sample_results(num_samples=10)
        return 0
    
    # Load video list
    try:
        if args.video_source == 'inventory':
            video_list = scorer.get_video_list_from_inventory(args.video_inventory)
            print(f"\n📹 Loaded {len(video_list)} videos from inventory ({args.video_inventory})")
        else:
            video_list = scorer.get_video_list_from_cache(args.api_cache)
            print(f"\n📹 Loaded {len(video_list)} videos from API cache ({args.api_cache})")
    except Exception as e:
        print(f"\n❌ Error loading video list: {e}")
        return 1
    
    # Handle different modes
    if args.sample:
        # Sample mode: Score 50 random videos
        print(f"\n{'='*80}")
        print(f"MODE: SAMPLE (Testing on {args.sample_size} random videos)")
        print(f"{'='*80}")
        print(f"\nThis will score {args.sample_size} randomly selected videos.")
        print(f"After scoring, you should:")
        print(f"  1. Review the results in {args.output}")
        print(f"  2. Check sample videos manually")
        print(f"  3. If satisfied, run with --continue to score all videos")
        print(f"  4. If not satisfied, adjust prompt and use --rescore-sample")
        
        proceed = input(f"\nProceed with sampling {args.sample_size} videos? (yes/no): ")
        if proceed.lower() not in ['yes', 'y']:
            print("Aborted.")
            return 0
        
        # Sample videos
        sample = scorer.sample_videos(video_list, sample_size=args.sample_size)
        
        if not sample:
            print("\n⚠️  No unscored videos to sample!")
            return 0
        
        # Score sample
        print(f"\n🚀 Starting to score {len(sample)} videos...")
        stats = scorer.score_videos(sample, save_interval=5, verbose=True)
        
        # Print results
        print(f"\n{'='*80}")
        print(f"SAMPLE SCORING COMPLETE")
        print(f"{'='*80}")
        print(f"Processed: {stats['processed']}")
        print(f"Scored: {stats['scored']}")
        print(f"Skipped: {stats['skipped']}")
        print(f"Already scored: {stats['already_scored']}")
        print(f"Failed: {stats['failed']}")
        
        if stats['skip_reasons']:
            print(f"\nSkip reasons:")
            for reason, count in stats['skip_reasons'].items():
                print(f"  {reason}: {count}")
        
        scorer.print_statistics()
        scorer.print_sample_results(num_samples=5)
        
        print(f"\n{'='*80}")
        print(f"NEXT STEPS:")
        print(f"{'='*80}")
        print(f"1. Review scored videos in: {args.output}")
        print(f"2. Check video quality manually by watching a few")
        print(f"3. Review the sample results printed above")
        print(f"\nIf satisfied with scoring:")
        print(f"  python score_instruction_quality.py --continue")
        print(f"\nIf you want to adjust the prompt and re-test:")
        print(f"  1. Edit the EVALUATION_PROMPT in data_pipeline/instruction_quality_scorer.py")
        print(f"  2. Delete the scored sample: delete the entries in {args.output}")
        print(f"  3. Run: python score_instruction_quality.py --sample")
        print(f"\nTo view statistics anytime:")
        print(f"  python score_instruction_quality.py --stats")
        print(f"{'='*80}\n")
        
    elif args.continue_scoring:
        # Continue mode: Score all remaining videos
        print(f"\n{'='*80}")
        print(f"MODE: CONTINUE (Scoring all remaining videos)")
        print(f"{'='*80}")
        
        # Filter out already scored
        unscored = [(vid, meta) for vid, meta in video_list if vid not in scorer.scores]
        
        print(f"\nVideos already scored: {len(scorer.scores)}")
        print(f"Videos remaining to score: {len(unscored)}")
        
        if not unscored:
            print("\n✅ All videos already scored!")
            scorer.print_statistics()
            return 0
        
        # Estimate cost and time
        avg_tokens_per_video = 2000  # input + output
        total_tokens = len(unscored) * avg_tokens_per_video
        estimated_cost = (total_tokens / 1_000_000) * 0.50  # Approximate cost for gpt-4o-mini
        estimated_time_minutes = (len(unscored) * 2) / 60  # ~2 seconds per video
        
        print(f"\nEstimated cost: ${estimated_cost:.2f}")
        print(f"Estimated time: {estimated_time_minutes:.1f} minutes")
        
        proceed = input(f"\nProceed with scoring {len(unscored)} videos? (yes/no): ")
        if proceed.lower() not in ['yes', 'y']:
            print("Aborted.")
            return 0
        
        # Score all unscored videos
        print(f"\n🚀 Starting to score {len(unscored)} videos...")
        stats = scorer.score_videos(unscored, save_interval=10, verbose=True)
        
        # Print results
        print(f"\n{'='*80}")
        print(f"SCORING COMPLETE")
        print(f"{'='*80}")
        print(f"Processed: {stats['processed']}")
        print(f"Scored: {stats['scored']}")
        print(f"Skipped: {stats['skipped']}")
        print(f"Failed: {stats['failed']}")
        
        if stats['skip_reasons']:
            print(f"\nSkip reasons:")
            for reason, count in stats['skip_reasons'].items():
                print(f"  {reason}: {count}")
        
        scorer.print_statistics()
        
        print(f"\n✅ All videos scored! Results saved to: {args.output}")
        print(f"\nNext step: Integrate scores into video ranking system")
        
    elif args.rescore_sample:
        # Rescore mode: Re-score sample after prompt adjustment
        print(f"\n{'='*80}")
        print(f"MODE: RESCORE SAMPLE")
        print(f"{'='*80}")
        print(f"\n⚠️  This will DELETE existing scores and re-score {args.sample_size} videos.")
        print(f"Use this if you've adjusted the EVALUATION_PROMPT and want to re-test.")
        
        proceed = input(f"\nProceed with re-scoring? (yes/no): ")
        if proceed.lower() not in ['yes', 'y']:
            print("Aborted.")
            return 0
        
        # Clear existing scores
        scorer.scores = {}
        scorer._save_scores()
        print(f"✓ Cleared existing scores")
        
        # Sample and score
        sample = scorer.sample_videos(video_list, sample_size=args.sample_size)
        
        print(f"\n🚀 Starting to re-score {len(sample)} videos...")
        stats = scorer.score_videos(sample, save_interval=5, verbose=True)
        
        # Print results
        print(f"\n{'='*80}")
        print(f"RE-SCORING COMPLETE")
        print(f"{'='*80}")
        scorer.print_statistics()
        scorer.print_sample_results(num_samples=5)
        
    elif args.video_ids:
        # Video IDs mode: Score specific videos by ID
        print(f"\n{'='*80}")
        print(f"MODE: SCORE SPECIFIC VIDEOS")
        print(f"{'='*80}")
        print(f"\nScoring {len(args.video_ids)} specific video(s): {', '.join(args.video_ids)}")
        
        # Filter video list to only include requested IDs
        video_dict = {vid: meta for vid, meta in video_list}
        requested_videos = []
        missing_ids = []
        
        for video_id in args.video_ids:
            if video_id in video_dict:
                requested_videos.append((video_id, video_dict[video_id]))
            else:
                missing_ids.append(video_id)
        
        if missing_ids:
            print(f"\n⚠️  Warning: {len(missing_ids)} video ID(s) not found in cache:")
            for vid in missing_ids:
                print(f"    - {vid}")
        
        if not requested_videos:
            print(f"\n❌ No valid video IDs found to score")
            return 1
        
        print(f"\nFound {len(requested_videos)} video(s) to score")
        
        # Check which are already scored
        already_scored = [vid for vid, _ in requested_videos if vid in scorer.scores]
        if already_scored:
            print(f"Already scored: {len(already_scored)}")
            print(f"  {', '.join(already_scored)}")
            rescore = input(f"\nRe-score already scored videos? (yes/no): ")
            if rescore.lower() in ['yes', 'y']:
                # Remove from scores dict to force re-scoring
                for vid in already_scored:
                    del scorer.scores[vid]
                scorer._save_scores()
                print(f"✓ Cleared scores for re-scoring")
        
        # Score the requested videos
        print(f"\n🚀 Starting to score {len(requested_videos)} video(s)...")
        stats = scorer.score_videos(requested_videos, save_interval=1, verbose=True)
        
        # Print results
        print(f"\n{'='*80}")
        print(f"SCORING COMPLETE")
        print(f"{'='*80}")
        print(f"Processed: {stats['processed']}")
        print(f"Scored: {stats['scored']}")
        print(f"Skipped: {stats['skipped']}")
        print(f"Already scored: {stats['already_scored']}")
        print(f"Failed: {stats['failed']}")
        
        if stats['skip_reasons']:
            print(f"\nSkip reasons:")
            for reason, count in stats['skip_reasons'].items():
                print(f"  {reason}: {count}")
        
        # Print scores for requested videos
        print(f"\n{'='*80}")
        print(f"SCORED VIDEO RESULTS")
        print(f"{'='*80}")
        for video_id in args.video_ids:
            if video_id in scorer.scores:
                score_data = scorer.scores[video_id]
                print(f"\n📹 {score_data.get('title', video_id)}")
                print(f"   Video ID: {video_id}")
                print(f"   Score: {score_data['score']}/100")
                print(f"   Justification: {score_data['justification']}")
            else:
                print(f"\n⚠️  {video_id}: Not scored (see skip reasons above)")
        print(f"\n{'='*80}\n")
        
    else:
        # No mode specified
        parser.print_help()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
