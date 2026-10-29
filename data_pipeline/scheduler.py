"""
Conservative Scheduler for YouTube Caption Extraction

This scheduler implements bot-detection avoidance strategies:
- Processes small batches with configurable delays
- Randomizes channel order to avoid patterns
- Detects IP blocks and stops immediately
- Sends notifications on critical events
- Maintains state for resumable operations
"""

import os
import csv
import json
import time
import random
import smtplib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class ExtractionScheduler:
    """Conservative scheduler for caption extraction with bot detection avoidance"""
    
    def __init__(
        self,
        channels_csv: str,
        state_file: str = "extraction_state.json",
        videos_per_batch: int = 5,
        min_delay_between_videos: float = 8.0,
        max_delay_between_videos: float = 15.0,
        min_break_duration: float = 120.0,  # 2 minutes
        max_break_duration: float = 300.0,  # 5 minutes
        notification_email: Optional[str] = None,
        smtp_config: Optional[Dict] = None,
        state_save_batch_size: int = 20
    ):
        """
        Initialize the extraction scheduler
        
        Args:
            channels_csv: Path to CSV file with channel information
            state_file: Path to JSON file for storing scheduler state
            videos_per_batch: Number of videos to extract before taking a break
            min_delay_between_videos: Minimum delay between video extractions (seconds)
            max_delay_between_videos: Maximum delay between video extractions (seconds)
            min_break_duration: Minimum break duration between batches (seconds)
            max_break_duration: Maximum break duration between batches (seconds)
            notification_email: Email address to send notifications to
            smtp_config: SMTP configuration for sending notifications
            state_save_batch_size: Number of videos to extract before saving state (batch optimization)
        """
        self.channels_csv = Path(channels_csv)
        self.state_file = Path(state_file)
        self.videos_per_batch = videos_per_batch
        self.min_delay = min_delay_between_videos
        self.max_delay = max_delay_between_videos
        self.min_break = min_break_duration
        self.max_break = max_break_duration
        self.notification_email = notification_email
        self.smtp_config = smtp_config or {}
        self.state_save_batch_size = state_save_batch_size
        self._extractions_since_save = 0
        
        self.state = self._load_state()
        self.ip_blocked = False
        self.total_extracted = 0
        self.session_start = datetime.now()
    
    def _load_state(self) -> Dict:
        """Load scheduler state from file"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                print(f"✓ Loaded scheduler state from {self.state_file}")
                return state
            except Exception as e:
                print(f"⚠ Could not load state file: {e}")
        
        return {
            'last_session': None,
            'channels_processed': [],
            'videos_extracted': {},
            'ip_blocks_detected': [],
            'total_extractions': 0
        }
    
    def _save_state(self):
        """Save scheduler state to file"""
        try:
            self.state['last_session'] = datetime.now().isoformat()
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"⚠ Could not save state file: {e}")
    
    def _load_channels(self) -> List[Dict[str, str]]:
        """Load and randomize channel list"""
        channels = []
        try:
            with open(self.channels_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                channels = list(reader)
            
            # Randomize channel order to avoid patterns
            random.shuffle(channels)
            print(f"✓ Loaded {len(channels)} channels (randomized order)")
            return channels
            
        except Exception as e:
            print(f"✗ Error loading channels: {e}")
            return []
    
    def _send_notification(self, subject: str, message: str):
        """Send email notification"""
        if not self.notification_email or not self.smtp_config:
            print(f"\n📧 Notification: {subject}")
            print(f"   {message}")
            return
        
        try:
            smtp_server = self.smtp_config.get('server', 'smtp.gmail.com')
            smtp_port = self.smtp_config.get('port', 587)
            smtp_user = self.smtp_config.get('username')
            smtp_pass = self.smtp_config.get('password')
            
            if not smtp_user or not smtp_pass:
                print(f"⚠ SMTP credentials not configured, skipping email")
                return
            
            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = self.notification_email
            msg['Subject'] = f"[Caption Extractor] {subject}"
            
            body = f"""
YouTube Caption Extraction Alert

{message}

Session Details:
- Start Time: {self.session_start.strftime('%Y-%m-%d %H:%M:%S')}
- Videos Extracted: {self.total_extracted}
- Status: {'IP BLOCKED' if self.ip_blocked else 'RUNNING'}

This is an automated notification from your caption extraction scheduler.
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
            server.quit()
            
            print(f"✓ Notification sent to {self.notification_email}")
            
        except Exception as e:
            print(f"⚠ Could not send notification: {e}")
    
    def _detect_ip_block(self, error_message: str) -> bool:
        """
        Detect if an error indicates IP blocking
        
        Args:
            error_message: Error message to analyze
            
        Returns:
            True if IP block detected, False otherwise
        """
        error_lower = error_message.lower()
        block_indicators = [
            'ipblocked',
            'ip blocked',
            'ip block',
            'too many requests',
            'rate limit',
            '429',
            'temporarily blocked',
            'suspicious traffic',
            'unusual traffic',
            'automated requests'
        ]
        
        return any(indicator in error_lower for indicator in block_indicators)
    
    def check_ip_block(self, error_message: Optional[str] = None) -> bool:
        """
        Check if IP block has been detected
        
        Args:
            error_message: Optional error message to check
            
        Returns:
            True if IP block detected, False otherwise
        """
        if error_message and self._detect_ip_block(error_message):
            self.ip_blocked = True
            
            # Record the IP block
            block_record = {
                'timestamp': datetime.now().isoformat(),
                'message': error_message[:200],
                'videos_extracted': self.total_extracted
            }
            self.state['ip_blocks_detected'].append(block_record)
            self._save_state()
            
            # Send notification
            self._send_notification(
                subject="🚨 IP Block Detected",
                message=f"""
YouTube has blocked your IP address.

Error: {error_message[:200]}

The extraction has been stopped automatically.

Recommended actions:
1. Wait 2-6 hours before retrying
2. Use a VPN or different network
3. Reduce batch size or increase delays
4. Check if using a cloud/datacenter IP (often blocked)

The scheduler will resume from where it left off when you run it again.
                """
            )
            
            print(f"\n{'='*70}")
            print(f"🚨 IP BLOCK DETECTED!")
            print(f"{'='*70}")
            print(f"Error: {error_message[:200]}")
            print(f"\nExtraction stopped to avoid further blocking.")
            print(f"Total videos extracted this session: {self.total_extracted}")
            print(f"\n⏰ Wait 2-6 hours before retrying or use a different network/VPN")
            print(f"{'='*70}\n")
            
            return True
        
        return self.ip_blocked
    
    def get_random_delay(self) -> float:
        """Get a random delay between videos"""
        return random.uniform(self.min_delay, self.max_delay)
    
    def get_random_break(self) -> float:
        """Get a random break duration between batches"""
        return random.uniform(self.min_break, self.max_break)
    
    def should_take_break(self, videos_in_batch: int) -> bool:
        """Determine if we should take a break"""
        return videos_in_batch >= self.videos_per_batch
    
    def take_break(self):
        """Take a session break"""
        break_duration = self.get_random_break()
        break_minutes = break_duration / 60
        
        print(f"\n{'='*70}")
        print(f"☕ TAKING SESSION BREAK")
        print(f"{'='*70}")
        print(f"Duration: {break_minutes:.1f} minutes ({break_duration:.0f} seconds)")
        print(f"Reason: Processed {self.videos_per_batch} videos in this batch")
        print(f"Total extracted this session: {self.total_extracted}")
        print(f"\nThis helps avoid bot detection by simulating human behavior.")
        print(f"Break will end at: {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*70}\n")
        
        # Show countdown in minutes
        remaining = break_duration
        while remaining > 0:
            if remaining > 60:
                print(f"  ⏱ Break time remaining: {remaining/60:.1f} minutes...", end='\r')
            else:
                print(f"  ⏱ Break time remaining: {remaining:.0f} seconds...   ", end='\r')
            
            sleep_time = min(10, remaining)  # Update every 10 seconds
            time.sleep(sleep_time)
            remaining -= sleep_time
        
        print(f"\n  ✓ Break complete! Resuming extraction...\n")
    
    def record_extraction(self, channel_id: str, video_id: str, success: bool):
        """Record a video extraction attempt (batches state saves for performance)"""
        if success:
            self.total_extracted += 1
            self.state['total_extractions'] += 1
            
            if channel_id not in self.state['videos_extracted']:
                self.state['videos_extracted'][channel_id] = []
            
            self.state['videos_extracted'][channel_id].append({
                'video_id': video_id,
                'timestamp': datetime.now().isoformat()
            })
            
            # Batch state saves: only write to disk every N videos
            self._extractions_since_save += 1
            if self._extractions_since_save >= self.state_save_batch_size:
                self._save_state()
                self._extractions_since_save = 0
    
    def get_extraction_stats(self) -> Dict:
        """Get extraction statistics"""
        return {
            'session_start': self.session_start.isoformat(),
            'session_extracted': self.total_extracted,
            'total_all_time': self.state['total_extractions'],
            'ip_blocked': self.ip_blocked,
            'channels_processed': len(self.state['channels_processed']),
            'ip_blocks_all_time': len(self.state['ip_blocks_detected'])
        }
    
    def print_session_summary(self):
        """Print session summary"""
        # Save any remaining state before printing summary
        if self._extractions_since_save > 0:
            self._save_state()
            self._extractions_since_save = 0
        
        duration = (datetime.now() - self.session_start).total_seconds() / 60
        stats = self.get_extraction_stats()
        
        print(f"\n{'='*70}")
        print(f"SESSION SUMMARY")
        print(f"{'='*70}")
        print(f"Duration: {duration:.1f} minutes")
        print(f"Videos extracted this session: {stats['session_extracted']}")
        print(f"Total videos all-time: {stats['total_all_time']}")
        print(f"Status: {'🚨 IP BLOCKED' if self.ip_blocked else '✓ COMPLETED'}")
        
        if stats['ip_blocks_all_time'] > 0:
            print(f"IP blocks encountered (all-time): {stats['ip_blocks_all_time']}")
        
        print(f"{'='*70}\n")
        
        if self.ip_blocked:
            print(f"⚠ IMPORTANT: Wait 2-6 hours before running again")
            print(f"             or use a different network/VPN\n")


def create_default_scheduler(
    channels_csv: str = "channels.csv",
    videos_per_batch: int = 5,
    notification_email: Optional[str] = None
) -> ExtractionScheduler:
    """
    Create a scheduler with default conservative settings
    
    Args:
        channels_csv: Path to channels CSV file
        videos_per_batch: Number of videos per batch (default: 5)
        notification_email: Email for notifications (optional)
        
    Returns:
        Configured ExtractionScheduler instance
    """
    # Load SMTP config from environment if available
    smtp_config = None
    if os.getenv('SMTP_SERVER'):
        smtp_config = {
            'server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
            'port': int(os.getenv('SMTP_PORT', 587)),
            'username': os.getenv('SMTP_USERNAME'),
            'password': os.getenv('SMTP_PASSWORD')
        }
    
    scheduler = ExtractionScheduler(
        channels_csv=channels_csv,
        videos_per_batch=videos_per_batch,
        min_delay_between_videos=8.0,
        max_delay_between_videos=15.0,
        min_break_duration=120.0,  # 2 minutes
        max_break_duration=300.0,  # 5 minutes
        notification_email=notification_email or os.getenv('NOTIFICATION_EMAIL'),
        smtp_config=smtp_config
    )
    
    return scheduler
