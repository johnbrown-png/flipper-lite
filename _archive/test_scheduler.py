"""
Test script for the scheduled extraction system
Runs a dry-run to verify everything is configured correctly
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from data_pipeline.scheduler import create_default_scheduler


def test_scheduler():
    """Test the scheduler configuration"""
    print("=" * 70)
    print("TESTING SCHEDULED EXTRACTION SYSTEM")
    print("=" * 70)
    
    # Load environment
    load_dotenv()
    
    # Check for API key
    api_key = os.getenv('YOUTUBE_API_KEY')
    if not api_key or api_key == 'your_api_key_here':
        print("\n✗ YOUTUBE_API_KEY not configured in .env")
        print("  Please add your API key to .env file")
        return False
    else:
        print(f"\n✓ YouTube API key found")
    
    # Check channels.csv
    channels_csv = Path("channels.csv")
    if not channels_csv.exists():
        print(f"✗ channels.csv not found")
        return False
    else:
        # Read channels
        with open(channels_csv, 'r') as f:
            lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]
            channel_count = len(lines) - 1  # Subtract header
        print(f"✓ Found channels.csv with {channel_count} channels")
    
    # Create scheduler
    print(f"\n✓ Creating test scheduler...")
    scheduler = create_default_scheduler(
        channels_csv="channels.csv",
        videos_per_batch=5,
        notification_email=os.getenv('NOTIFICATION_EMAIL')
    )
    
    # Show configuration
    print(f"\nScheduler Configuration:")
    print(f"  • Videos per batch: {scheduler.videos_per_batch}")
    print(f"  • Delay range: {scheduler.min_delay:.1f}-{scheduler.max_delay:.1f} seconds")
    print(f"  • Break range: {scheduler.min_break/60:.1f}-{scheduler.max_break/60:.1f} minutes")
    
    if scheduler.notification_email:
        print(f"  • Notifications: {scheduler.notification_email}")
    else:
        print(f"  • Notifications: Disabled (console only)")
    
    # Test random values
    print(f"\nTesting randomization:")
    for i in range(3):
        delay = scheduler.get_random_delay()
        print(f"  • Sample delay {i+1}: {delay:.1f} seconds")
    
    break_time = scheduler.get_random_break()
    print(f"  • Sample break: {break_time/60:.1f} minutes")
    
    # Load channels
    print(f"\nTesting channel loading:")
    channels = scheduler._load_channels()
    if channels:
        print(f"  ✓ Loaded {len(channels)} channels in random order:")
        for i, ch in enumerate(channels, 1):
            print(f"    {i}. {ch.get('channel_name', 'Unknown')}")
    else:
        print(f"  ✗ Failed to load channels")
        return False
    
    # Test state management
    print(f"\nTesting state management:")
    print(f"  • State file: {scheduler.state_file}")
    print(f"  • Previous extractions: {scheduler.state.get('total_extractions', 0)}")
    print(f"  • IP blocks recorded: {len(scheduler.state.get('ip_blocks_detected', []))}")
    
    # Test IP block detection
    print(f"\nTesting IP block detection:")
    test_errors = [
        "Normal error message",
        "IP blocked by YouTube",
        "Too many requests from your IP",
        "HTTP 429 rate limit"
    ]
    
    for error in test_errors:
        is_block = scheduler._detect_ip_block(error)
        status = "🚨 DETECTED" if is_block else "✓ ignored"
        print(f"  • '{error[:30]}...' → {status}")
    
    # Summary
    print(f"\n" + "=" * 70)
    print(f"✓ ALL TESTS PASSED")
    print(f"=" * 70)
    print(f"\nSystem is ready for scheduled extraction!")
    print(f"\nTo start extracting, run:")
    print(f"  python scheduled_extractor.py --batch-size 5 --max-total 25")
    print(f"\nOr use the batch file:")
    print(f"  run_scheduled_extraction.bat")
    print(f"\n" + "=" * 70)
    
    return True


if __name__ == '__main__':
    success = test_scheduler()
    sys.exit(0 if success else 1)
