"""
Scheduled Caption Extractor with Bot Detection Avoidance

This script uses the conservative scheduler to extract captions safely
while avoiding YouTube's bot detection systems.

Usage:
    python scheduled_extractor.py --batch-size 5 --email your@email.com
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from data_pipeline.caption_extractor import YouTubeCaptionExtractor
from data_pipeline.scheduler import create_default_scheduler


class ScheduledCaptionExtractor:
    """Caption extractor with integrated conservative scheduling"""
    
    def __init__(
        self,
        api_key: str,
        channels_csv: str,
        output_dir: str = "data/captions_output",
        videos_per_batch: int = 5,
        max_video_duration: int = 1200,
        notification_email: Optional[str] = None
    ):
        """
        Initialize scheduled extractor
        
        Args:
            api_key: YouTube API key
            channels_csv: Path to channels CSV
            output_dir: Directory for caption output
            videos_per_batch: Videos to process before break
            max_video_duration: Maximum video duration in seconds (default: 1200 = 20 minutes)
            notification_email: Email for notifications
        """
        self.api_key = api_key
        self.channels_csv = channels_csv
        self.output_dir = output_dir
        self.videos_per_batch = videos_per_batch
        self.max_video_duration = max_video_duration
        
        # Create scheduler
        self.scheduler = create_default_scheduler(
            channels_csv=channels_csv,
            videos_per_batch=videos_per_batch,
            notification_email=notification_email
        )
        
        # Create extractor (will be recreated per session to avoid issues)
        self.extractor = None
    
    def _create_extractor(self):
        """Create a fresh extractor instance"""
        self.extractor = YouTubeCaptionExtractor(
            api_key=self.api_key,
            output_dir=self.output_dir,
            cache_file="data/api_cache.json",
            delay_between_videos=0.5,  # Minimal delay, scheduler handles timing
            random_delay_range=(0.5, 1.0),  # Minimal delay
            videos_per_batch=999,  # Disable extractor's break, scheduler handles it
            break_duration_range=(0, 0),  # Disable extractor's break
            max_video_duration=self.max_video_duration
        )
    
    def run_scheduled_extraction(
        self,
        max_videos_total: Optional[int] = None,
        max_videos_per_channel: int = 50
    ):
        """
        Run scheduled extraction with bot avoidance
        
        Args:
            max_videos_total: Maximum total videos to extract (None = unlimited)
            max_videos_per_channel: Maximum videos per channel per run
        """
        print("=" * 80)
        print("SCHEDULED YOUTUBE CAPTION EXTRACTION")
        print("=" * 80)
        print(f"Configuration:")
        print(f"  • Videos per batch: {self.videos_per_batch}")
        print(f"  • Delay between videos: {self.scheduler.min_delay:.1f}-{self.scheduler.max_delay:.1f}s")
        print(f"  • Break duration: {self.scheduler.min_break/60:.1f}-{self.scheduler.max_break/60:.1f} min")
        print(f"  • Channels CSV: {self.channels_csv}")
        print(f"  • Output directory: {self.output_dir}")
        if max_videos_total:
            print(f"  • Max videos this session: {max_videos_total}")
        print("=" * 80 + "\n")
        
        # Load channels (randomized order)
        channels = self.scheduler._load_channels()
        if not channels:
            print("✗ No channels to process")
            return
        
        # Create extractor
        self._create_extractor()
        
        # Get already downloaded videos to exclude
        downloaded_ids = self.extractor.get_downloaded_video_ids()
        print(f"✓ Found {len(downloaded_ids)} already-downloaded videos (will skip)\n")
        
        # Process channels in random order
        videos_in_current_batch = 0
        
        for channel_idx, channel in enumerate(channels, 1):
            # Check if we hit total limit
            if max_videos_total and self.scheduler.total_extracted >= max_videos_total:
                print(f"\n✓ Reached maximum of {max_videos_total} videos for this session")
                break
            
            # Check for IP block
            if self.scheduler.check_ip_block():
                break
            
            channel_id = channel.get('channel_id', '')
            channel_name = channel.get('channel_name', 'Unknown')
            
            print(f"\n{'='*80}")
            print(f"CHANNEL {channel_idx}/{len(channels)}: {channel_name}")
            print(f"{'='*80}")
            
            # Get videos for this channel
            try:
                videos = self.extractor.get_channel_videos(channel_id, max_videos_per_channel)
                
                if not videos:
                    print(f"  ⚠ No videos found for this channel")
                    continue
                
                # Filter out already downloaded
                videos = [v for v in videos if v['video_id'] not in downloaded_ids]
                print(f"  → {len(videos)} new videos to process\n")
                
                if not videos:
                    continue
                
                # Process videos from this channel
                for video_idx, video in enumerate(videos, 1):
                    # Check limits
                    if max_videos_total and self.scheduler.total_extracted >= max_videos_total:
                        break
                    
                    if self.scheduler.check_ip_block():
                        break
                    
                    video_id = video['video_id']
                    title = video['title'][:60]
                    
                    print(f"  [{video_idx}/{len(videos)}] {title}...")
                    
                    # Extract caption
                    try:
                        caption_data = self.extractor.extract_caption(video_id, verbose=True)
                        
                        if caption_data:
                            # Save the caption
                            self.extractor.save_caption(video, caption_data, channel_name)
                            
                            # Record successful extraction
                            self.scheduler.record_extraction(channel_id, video_id, True)
                            videos_in_current_batch += 1
                            
                            print(f"      ✓ Extracted ({self.scheduler.total_extracted} total)")
                            
                            # Add to downloaded list
                            downloaded_ids.append(video_id)
                            
                        else:
                            print(f"      ✗ No captions available")
                    
                    except Exception as e:
                        error_msg = str(e)
                        print(f"      ✗ Error: {error_msg[:100]}")
                        
                        # Check for IP block
                        if self.scheduler.check_ip_block(error_msg):
                            break
                    
                    # Should we take a break?
                    if self.scheduler.should_take_break(videos_in_current_batch):
                        # Take break only if there are more videos to process
                        has_more = (video_idx < len(videos) or 
                                   channel_idx < len(channels) or
                                   (max_videos_total and self.scheduler.total_extracted < max_videos_total))
                        
                        if has_more:
                            self.scheduler.take_break()
                            videos_in_current_batch = 0  # Reset batch counter
                    
                    # Delay between videos (if not taking a break)
                    elif video_idx < len(videos) or channel_idx < len(channels):
                        delay = self.scheduler.get_random_delay()
                        print(f"      ⏱ Waiting {delay:.1f}s...")
                        import time
                        time.sleep(delay)
                
                # Stop if IP blocked
                if self.scheduler.check_ip_block():
                    break
            
            except Exception as e:
                error_msg = str(e)
                print(f"\n  ✗ Error processing channel: {error_msg[:100]}")
                
                # Check for IP block or quota
                if self.scheduler.check_ip_block(error_msg):
                    break
                
                if 'quota' in error_msg.lower():
                    print(f"\n  ⚠ QUOTA EXCEEDED - Stopping extraction")
                    self.scheduler._send_notification(
                        subject="YouTube API Quota Exceeded",
                        message=f"The YouTube API quota has been exceeded.\n\nExtracted {self.scheduler.total_extracted} videos before limit was reached."
                    )
                    break
                
                # Continue to next channel
                continue
        
        # Print session summary
        self.scheduler.print_session_summary()
        
        # Send completion notification if not blocked
        if not self.scheduler.ip_blocked and self.scheduler.total_extracted > 0:
            self.scheduler._send_notification(
                subject=f"✓ Extraction Session Complete",
                message=f"Successfully extracted {self.scheduler.total_extracted} videos.\n\nThe scheduler is ready for the next run."
            )


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Scheduled YouTube caption extraction with bot avoidance"
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=5,
        help='Number of videos to extract before taking a break (default: 5)'
    )
    parser.add_argument(
        '--max-total',
        type=int,
        default=None,
        help='Maximum total videos to extract in this session (default: unlimited)'
    )
    parser.add_argument(
        '--max-per-channel',
        type=int,
        default=50,
        help='Maximum videos per channel (default: 50)'
    )
    parser.add_argument(
        '--email',
        type=str,
        default=None,
        help='Email address for notifications (optional)'
    )
    parser.add_argument(
        '--channels-csv',
        type=str,
        default='channels.csv',
        help='Path to channels CSV file (default: channels.csv)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='data/captions_output',
        help='Output directory for captions (default: data/captions_output)'
    )
    parser.add_argument(
        '--max-duration',
        type=int,
        default=1200,
        help='Maximum video duration in seconds (default: 1200 = 20 minutes, use 150 for short videos only)'
    )
    
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Get API key
    api_key = os.getenv('YOUTUBE_API_KEY')
    if not api_key or api_key == 'your_api_key_here':
        print("✗ Error: YOUTUBE_API_KEY not found in .env file")
        print("  Get your API key from: https://console.cloud.google.com/apis/credentials")
        return 1
    
    # Create and run scheduled extractor
    extractor = ScheduledCaptionExtractor(
        api_key=api_key,
        channels_csv=args.channels_csv,
        output_dir=args.output_dir,
        videos_per_batch=args.batch_size,
        max_video_duration=args.max_duration,
        notification_email=args.email
    )
    
    extractor.run_scheduled_extraction(
        max_videos_total=args.max_total,
        max_videos_per_channel=args.max_per_channel
    )
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
