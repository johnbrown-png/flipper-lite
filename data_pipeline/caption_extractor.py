"""
YouTube Caption Extractor Pipeline

This script extracts auto-generated captions from YouTube videos 
from specified channels listed in a CSV file.
"""

import os
import csv
import json
import time
import random
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from youtube_transcript_api.proxies import WebshareProxyConfig
from dotenv import load_dotenv


class YouTubeCaptionExtractor:
    """Main class for extracting captions from YouTube channels"""
    
    def __init__(self, api_key: str, output_dir: str = "captions_output", cache_file: str = "api_cache.json", delay_between_videos: float = 10.0, random_delay_range: tuple = (8.0, 15.0), videos_per_batch: int = 5, break_duration_range: tuple = (60.0, 180.0), use_proxy: bool = True, proxy_locations: List[str] = None, max_video_duration: int = 1200):
        """
        Initialize the caption extractor
        
        Args:
            api_key: YouTube Data API v3 key
            output_dir: Directory to save extracted captions
            cache_file: Path to cache file for API responses
            delay_between_videos: Base delay in seconds between processing videos
            random_delay_range: Tuple of (min, max) seconds for randomized delays
            videos_per_batch: Number of videos to process before taking a break
            break_duration_range: Tuple of (min, max) seconds for session breaks
            use_proxy: Whether to use proxy for transcript requests (default: True)
            proxy_locations: List of country codes to filter proxy IPs (e.g., ['gb', 'us']). Default: ['gb', 'us', 'ca']
            max_video_duration: Maximum video duration in seconds (default: 1200 = 20 minutes, None = no limit)
        """
        self.api_key = api_key
        self._youtube = None  # Lazy-load YouTube client
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.cache_file = Path(cache_file)
        self.cache = self._load_cache()
        self.max_retries = 3
        self.base_delay = 2  # seconds
        self.delay_between_videos = delay_between_videos
        self.random_delay_range = random_delay_range
        self.use_proxy = use_proxy
        # Default to UK, US, and Canada for educational content (BBC, Khan Academy, etc.)
        self.proxy_locations = proxy_locations if proxy_locations is not None else ['gb', 'us', 'ca']
        self.videos_per_batch = videos_per_batch
        self.break_duration_range = break_duration_range
        self.max_video_duration = max_video_duration
        # Cache for downloaded IDs (populated once per session)
        self._downloaded_ids_cache = None
        self._cache_populated = False
    
    @property
    def youtube(self):
        """Lazy-load YouTube API client only when needed"""
        if self._youtube is None:
            from googleapiclient.discovery import build
            self._youtube = build('youtube', 'v3', developerKey=self.api_key)
        return self._youtube

    def _sanitize_path_component(self, value: str, fallback: str = "unknown") -> str:
        """Make a filename/folder component safe for Windows and cross-platform filesystems."""
        safe = (value or "").strip()
        safe = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', safe)
        safe = safe.replace(' ', '_')
        safe = safe.strip(' .')
        return safe or fallback
    
    def _load_cache(self) -> Dict:
        """Load cache from file or return empty cache"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                print(f"✓ Loaded cache from {self.cache_file}")
                return cache
            except Exception as e:
                print(f"⚠ Could not load cache: {e}")
                return {'channels': {}, 'videos': {}}
        return {'channels': {}, 'videos': {}}
    
    def _save_cache(self):
        """Save cache to file (compact format for performance)"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f)  # No indent for compact format
        except Exception as e:
            print(f"⚠ Could not save cache: {e}")
    
    def _api_call_with_retry(self, api_request, operation_name: str):
        """Execute API call with exponential backoff retry logic"""
        for attempt in range(self.max_retries):
            try:
                return api_request.execute()
            except HttpError as e:
                error_code = e.resp.status
                
                # Handle quota exceeded
                if error_code == 403 and 'quotaExceeded' in str(e):
                    print(f"\n✗ QUOTA EXCEEDED! Daily limit reached.")
                    print(f"  Your quota resets at midnight Pacific Time.")
                    raise
                
                # Handle rate limiting
                elif error_code == 429 or (error_code == 403 and 'rateLimitExceeded' in str(e)):
                    wait_time = self.base_delay * (2 ** attempt)
                    print(f"  ⚠ Rate limited. Waiting {wait_time}s before retry {attempt + 1}/{self.max_retries}...")
                    time.sleep(wait_time)
                    continue
                
                # Other HTTP errors
                else:
                    if attempt < self.max_retries - 1:
                        wait_time = self.base_delay * (2 ** attempt)
                        print(f"  ⚠ Error {error_code} in {operation_name}. Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"  ✗ Error {error_code} in {operation_name}: {str(e)}")
                        raise
            
            except Exception as e:
                if attempt < self.max_retries - 1:
                    wait_time = self.base_delay * (2 ** attempt)
                    print(f"  ⚠ Unexpected error in {operation_name}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise
        
        raise Exception(f"Failed after {self.max_retries} retries")
    
    def get_downloaded_video_ids(self) -> List[str]:
        """Scan output directory and return list of already-downloaded video IDs (cached per session)"""
        # Return cached result if already populated in this session
        if self._cache_populated:
            return self._downloaded_ids_cache
        
        video_ids = []
        for json_file in self.output_dir.rglob('*.json'):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'video_id' in data:
                        video_ids.append(data['video_id'])
            except:
                continue
        
        if video_ids:
            print(f"✓ Found {len(video_ids)} already-downloaded videos")
        
        # Cache the result for future calls in this session
        self._downloaded_ids_cache = video_ids
        self._cache_populated = True
        return video_ids
    
    def get_proxy_locations_for_channel(self, channel_name: str) -> List[str]:
        """
        Determine optimal proxy locations based on channel name
        
        Args:
            channel_name: Name of the channel
            
        Returns:
            List of country codes for proxy filtering
        """
        channel_lower = channel_name.lower()
        
        # BBC content is restricted to UK
        if 'bbc' in channel_lower:
            return ['gb']
        
        # UK-based educational content
        if any(keyword in channel_lower for keyword in ['british', 'uk ', 'england', 'scotland', 'wales']):
            return ['gb']
        
        # Other channels use broader locations (US, Canada, etc.)
        return ['gb', 'us', 'ca']
        
    def load_channels_from_csv(self, csv_path: str) -> List[Dict[str, str]]:
        """
        Load channel information from CSV file
        
        Args:
            csv_path: Path to CSV file with channel_id, channel_name, and optional playlist_id columns
            
        Returns:
            List of dictionaries containing channel information
        """
        try:
            df = pd.read_csv(csv_path)
            channels = df.to_dict('records')
            print(f"✓ Loaded {len(channels)} channels from {csv_path}")
            
            # Count how many have custom playlists
            custom_playlists = sum(1 for c in channels if c.get('playlist_id') and str(c.get('playlist_id')).strip())
            if custom_playlists > 0:
                print(f"  → {custom_playlists} channel(s) using custom playlists")
            
            return channels
        except Exception as e:
            print(f"✗ Error loading CSV: {e}")
            return []
    
    def get_channel_videos(self, channel_id: str, max_results: int = 50, playlist_id: str = None) -> List[Dict]:
        """
        Get list of videos from a YouTube channel or specific playlist (with caching)
        
        Args:
            channel_id: YouTube channel ID
            max_results: Maximum number of videos to retrieve
            playlist_id: Optional specific playlist ID (e.g., 'PLxyz123'). If None, uses channel's uploads playlist.
            
        Returns:
            List of video information dictionaries
        """
        # Check cache for this channel's video list (include max_duration and playlist_id in cache key)
        cache_key = f"{channel_id}_{max_results}_{self.max_video_duration}_{playlist_id or 'uploads'}"
        if cache_key in self.cache.get('videos', {}):
            cached_videos = self.cache['videos'][cache_key]
            print(f"  ✓ Using cached video list ({len(cached_videos)} videos)")
            return cached_videos
        
        videos = []
        
        try:
            # Use provided playlist_id or fetch channel's uploads playlist
            if playlist_id:
                print(f"  → Using custom playlist: {playlist_id}")
            else:
                # Check cache for playlist ID
                if channel_id in self.cache.get('channels', {}):
                    playlist_id = self.cache['channels'][channel_id]
                    print(f"  ✓ Using cached playlist ID")
                else:
                    # Get uploads playlist ID
                    request = self.youtube.channels().list(
                        part='contentDetails',
                        id=channel_id
                    )
                    response = self._api_call_with_retry(request, "channels.list")
                    
                    if not response.get('items'):
                        print(f"  ✗ Channel not found: {channel_id}")
                        return videos
                    
                    playlist_id = response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
                    
                    # Cache the playlist ID
                    if 'channels' not in self.cache:
                        self.cache['channels'] = {}
                    self.cache['channels'][channel_id] = playlist_id
                    self._save_cache()
            
            print(f"  → Fetching videos from playlist...")
            
            # Get videos from uploads playlist
            next_page_token = None
            while len(videos) < max_results:
                request = self.youtube.playlistItems().list(
                    part='snippet',
                    playlistId=playlist_id,
                    maxResults=min(50, max_results - len(videos)),
                    pageToken=next_page_token
                )
                response = self._api_call_with_retry(request, "playlistItems.list")
                
                for item in response.get('items', []):
                    video_id = item['snippet']['resourceId']['videoId']
                    video_info = {
                        'video_id': video_id,
                        'title': item['snippet']['title'],
                        'published_at': item['snippet']['publishedAt']
                    }
                    videos.append(video_info)
                
                print(f"  → Retrieved {len(videos)} videos so far...")
                
                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break
                
                # Add small random delay between pagination requests
                time.sleep(random.uniform(1.0, 3.0))
            
            print(f"  ✓ Found {len(videos)} videos (before duration filter)")
            
            # Filter by duration using configured max_video_duration (if set)
            filtered_videos = self.filter_by_duration(videos, max_duration=getattr(self, 'max_video_duration', None))
            print(f"  ✓ {len(filtered_videos)} videos after filtering")
            
            # Cache the video list
            if 'videos' not in self.cache:
                self.cache['videos'] = {}
            self.cache['videos'][cache_key] = filtered_videos
            self._save_cache()
            
            return filtered_videos
            
        except Exception as e:
            print(f"  ✗ Error fetching videos: {e}")
            return videos
    
    def filter_by_duration(self, videos: List[Dict], max_duration: int = None) -> List[Dict]:
        """
        Filter videos by duration
        
        Args:
            videos: List of video information dictionaries
            max_duration: Maximum duration in seconds (None = no limit, default: 300 = 5 minutes)
            
        Returns:
            Filtered list of videos
        """
        if not videos:
            return videos
        
        # If no max_duration specified, return all videos
        if max_duration is None:
            return videos
        
        filtered = []
        video_ids = [v['video_id'] for v in videos]
        
        try:
            # Get video details in batches of 50
            for i in range(0, len(video_ids), 50):
                batch_ids = video_ids[i:i+50]
                request = self.youtube.videos().list(
                    part='contentDetails',
                    id=','.join(batch_ids)
                )
                response = self._api_call_with_retry(request, "videos.list")
                
                # Create duration map
                duration_map = {}
                for item in response.get('items', []):
                    video_id = item['id']
                    duration_str = item['contentDetails']['duration']  # Format: PT#M#S
                    # Parse ISO 8601 duration
                    import re
                    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
                    if match:
                        hours = int(match.group(1) or 0)
                        minutes = int(match.group(2) or 0)
                        seconds = int(match.group(3) or 0)
                        total_seconds = hours * 3600 + minutes * 60 + seconds
                        duration_map[video_id] = total_seconds
                
                # Filter videos
                for video in videos[i:i+50]:
                    video_id = video['video_id']
                    if video_id in duration_map and duration_map[video_id] <= max_duration:
                        video['duration'] = duration_map[video_id]
                        filtered.append(video)
            
            return filtered
            
        except Exception as e:
            print(f"  ⚠ Warning: Could not filter by duration: {e}")
            return videos
    
    def extract_caption(self, video_id: str, verbose: bool = False) -> Optional[Dict]:
        """
        Extract auto-generated caption from a video
        
        Args:
            video_id: YouTube video ID
            verbose: If True, show detailed error messages
            
        Returns:
            Dictionary containing caption data or None if not available
        """
        try:
            # Create API instance - try with proxy first if enabled, then fallback to no proxy
            attempts = []
            
            if self.use_proxy:
                # Use proxy with location filtering to avoid geo-blocks and reduce latency
                attempts.append(('proxy', YouTubeTranscriptApi(
                    proxy_config=WebshareProxyConfig(
                        proxy_username="fuyxmmoi",
                        proxy_password="8xdrwuvrznki",
                        filter_ip_locations=self.proxy_locations,
                    )
                )))
            
            # Always add no-proxy as fallback
            attempts.append(('direct', YouTubeTranscriptApi()))
            
            last_error = None
            for method_name, api in attempts:
                try:
                    if method_name == 'proxy':
                        print(f"[*] Trying with Webshare proxy (locations: {', '.join(self.proxy_locations).upper()})...")
                    else:
                        print("[*] Trying direct connection...")
                    
                    # Explicitly request English transcripts (including auto-generated)
                    caption_data = api.fetch(video_id, ['en'])
                    
                    if verbose:
                        print(f"  [+] Success using {method_name} connection")
                    
                    return {
                        'transcript': [{'text': seg.text, 'start': seg.start, 'duration': seg.duration} for seg in caption_data],
                        'language': 'en',
                        'is_generated': True
                    }
                except Exception as e:
                    last_error = e
                    error_msg = str(e).lower()
                    
                    # If it's a geo-block or unplayable error with proxy, try without proxy
                    if 'unplayable' in error_msg or 'country' in error_msg:
                        if verbose and method_name == 'proxy':
                            print(f"  [!] Video geo-blocked via proxy, trying direct connection...")
                        continue
                    else:
                        # For other errors, break and handle below
                        raise
            
            # If we get here, all attempts failed, raise the last error
            if last_error:
                raise last_error
            
        except Exception as e:
            # Handle different types of errors
            error_msg = str(e).lower()
            
            # IP blocked by YouTube
            if 'ipblocked' in error_msg or 'ip' in error_msg and 'block' in error_msg:
                if verbose:
                    print(f"\n[!] IP BLOCKED: YouTube is blocking requests from your IP")
                    print(f"   This usually means too many requests or cloud provider IP")
                    print(f"   Solutions:")
                    print(f"   1. Wait a few hours before trying again")
                    print(f"   2. Use a VPN or different network")
                    print(f"   3. Set up cookies/proxy (see youtube-transcript-api docs)")
                return None
            
            # Geo-blocked video
            if 'unplayable' in error_msg or 'country' in error_msg:
                if verbose:
                    print(f"\n[!] GEO-BLOCKED: Video not available in your country")
                return None
            
            # No captions available
            if 'no transcripts' in error_msg or 'disabled' in error_msg or 'not found' in error_msg:
                return None
            
            # Unknown error
            if verbose:
                print(f"\n[!] ERROR: {str(e)[:100]}")
            return None
    
    def save_caption(self, video_info: Dict, caption_data: Dict, channel_name: str):
        """
        Save caption data to file
        
        Args:
            video_info: Video information dictionary
            caption_data: Caption data dictionary
            channel_name: Name of the channel
        """
        # Helper function to detect songs
        def is_song_title(title: str) -> bool:
            title_lower = title.lower()
            song_keywords = [
                'song', 'sing', 'singing', 'music', 'musical',
                'rhyme', 'nursery rhyme', 'lullaby', 'melody',
                'anthem', 'tune', 'karaoke', '🎵', '🎶', '♪', '♫'
            ]
            return any(keyword in title_lower for keyword in song_keywords)
        
        resolved_channel_name = video_info.get('channel_name') or channel_name
        resolved_channel_id = video_info.get('channel_id', '')
        resolved_duration = video_info.get('duration')

        # Fallback: enrich missing metadata for callers that only pass minimal video_info.
        if resolved_duration is None or resolved_duration == '':
            fallback_meta = self.get_video_metadata(video_info['video_id'])
            if fallback_meta:
                resolved_channel_name = fallback_meta.get('channel_name', resolved_channel_name)
                resolved_channel_id = fallback_meta.get('channel_id', resolved_channel_id)
                resolved_duration = fallback_meta.get('duration', resolved_duration)

        # Create channel directory
        safe_channel_name = self._sanitize_path_component(str(resolved_channel_name), fallback='unknown_channel')
        channel_dir = self.output_dir / safe_channel_name
        channel_dir.mkdir(exist_ok=True)
        
        # Sanitize filename
        safe_title = "".join(c for c in video_info['title'] if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_title = safe_title[:100]  # Limit length
        
        # Clean transcript items - remove bracketed descriptions
        cleaned_transcript = []
        for item in caption_data['transcript']:
            # Remove anything in square brackets (background sounds, music descriptions, etc.)
            cleaned_text = re.sub(r'\[.*?\]', '', item['text'])
            # Clean up extra spaces
            cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
            if cleaned_text:  # Only keep non-empty text
                cleaned_transcript.append({
                    'text': cleaned_text,
                    'start': item['start'],
                    'duration': item['duration']
                })
        
        # Save as JSON
        output_file = channel_dir / f"{safe_title}_{video_info['video_id']}.json"
        
        output_data = {
            'video_id': video_info['video_id'],
            'title': video_info['title'],
            'channel': resolved_channel_name,
            'channel_id': resolved_channel_id,
            'published_at': video_info['published_at'],
            'duration': resolved_duration,
            'is_song': is_song_title(video_info['title']),
            'language': caption_data['language'],
            'is_auto_generated': caption_data['is_generated'],
            'extracted_at': datetime.now().isoformat(),
            'transcript': cleaned_transcript
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        # Also save as plain text (cleaned)
        text_file = channel_dir / f"{safe_title}_{video_info['video_id']}.txt"
        full_text = " ".join([item['text'] for item in cleaned_transcript])
        
        # Clean text: remove '>>' markers and extra spaces
        cleaned_text = full_text.replace('>>', '').replace('  ', ' ').strip()
        
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(cleaned_text)
    
    def process_channel(self, channel_info: Dict, max_videos: int = 50, exclude_video_ids: List[str] = None, auto_exclude_downloaded: bool = True, verbose: bool = False):
        """
        Process a single channel and extract captions from its videos
        
        Args:
            channel_info: Dictionary with channel_id, channel_name, and optional playlist_id
            max_videos: Maximum number of videos to process
            exclude_video_ids: List of video IDs to exclude from processing
            auto_exclude_downloaded: Automatically exclude already-downloaded videos
            verbose: Show detailed error messages
        """
        channel_id = channel_info.get('channel_id', '')
        channel_name = channel_info.get('channel_name', 'Unknown')
        playlist_id = channel_info.get('playlist_id', None) or None  # Convert empty string to None
        
        if exclude_video_ids is None:
            exclude_video_ids = []
        
        # Auto-detect already downloaded videos
        if auto_exclude_downloaded:
            downloaded_ids = self.get_downloaded_video_ids()
            exclude_video_ids = list(set(exclude_video_ids + downloaded_ids))
        
        # Set proxy locations based on channel
        original_proxy_locations = self.proxy_locations
        self.proxy_locations = self.get_proxy_locations_for_channel(channel_name)
        
        print(f"\n🎬 Processing channel: {channel_name} ({channel_id})")
        if playlist_id:
            print(f"  → Using custom playlist: {playlist_id}")
        print(f"  → Proxy locations: {', '.join(self.proxy_locations).upper()}")
        
        # Get videos
        videos = self.get_channel_videos(channel_id, max_videos, playlist_id=playlist_id)
        
        if not videos:
            print(f"  ⚠ No videos found for this channel")
            return
        
        # Filter out excluded video IDs
        videos = [v for v in videos if v['video_id'] not in exclude_video_ids]
        print(f"  → {len(videos)} videos after excluding already-downloaded videos")
        
        # Extract captions
        success_count = 0
        ip_blocked = False
        
        for i, video in enumerate(videos, 1):
            video_id = video['video_id']
            print(f"  [{i}/{len(videos)}] {video['title'][:60]}... (ID: {video_id})", end=" ")
            
            # Show verbose errors on first video only to avoid spam
            verbose_mode = verbose or i == 1
            caption_data = self.extract_caption(video['video_id'], verbose=verbose_mode)
            
            if caption_data:
                self.save_caption(video, caption_data, channel_name)
                success_count += 1
                print("✓")
            else:
                print("✗ No captions")
                # Check if this is an IP block issue
                if 'ipblocked' in str(caption_data).lower() or ip_blocked:
                    ip_blocked = True
            
            # If IP is blocked, warn user and stop trying
            if ip_blocked and i == 1:
                print(f"\n  ⚠ WARNING: YouTube appears to be blocking your IP")
                print(f"  → Continuing to try other videos, but they may all fail")
            
            # Stop after successfully extracting the desired number
            if success_count >= max_videos:
                print(f"  → Reached target of {max_videos} successful extractions")
                break
            
            # Rate limiting: randomized delay between videos to appear more human
            if i < len(videos):
                # Use randomized delay to avoid predictable bot patterns
                delay = random.uniform(self.random_delay_range[0], self.random_delay_range[1])
                print(f"  ⏱ Waiting {delay:.1f}s...")
                time.sleep(delay)
                
                # Session break after processing a batch
                if success_count > 0 and success_count % self.videos_per_batch == 0 and i < len(videos):
                    break_time = random.uniform(self.break_duration_range[0], self.break_duration_range[1])
                    print(f"\n  ☕ Taking session break ({break_time/60:.1f} minutes) to avoid bot detection...")
                    time.sleep(break_time)
                    print(f"  ✓ Resuming extraction...\n")
        
        print(f"  ✓ Successfully extracted captions from {success_count}/{len(videos)} videos")
        
        # Final warning if no videos extracted
        if success_count == 0 and len(videos) > 0:
            print(f"\n  ⚠ ISSUE: No captions extracted from any videos!")
            print(f"  → Possible causes:")
            print(f"     1. IP blocked by YouTube (most common)")
            print(f"     2. Videos geo-blocked in your region")
            print(f"     3. Videos have no captions available")
            print(f"  → Try: Wait a few hours, use VPN, or different network")
        
        # Restore original proxy locations
        self.proxy_locations = original_proxy_locations
    
    def get_video_metadata(self, video_id: str) -> Optional[Dict]:
        """
        Get metadata for a single video by ID
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Dictionary with video metadata or None if not found
        """
        try:
            request = self.youtube.videos().list(
                part='snippet,contentDetails,statistics',
                id=video_id
            )
            response = self._api_call_with_retry(request, "videos.list")
            
            if not response.get('items'):
                print(f"  ✗ Video not found: {video_id}")
                return None
            
            item = response['items'][0]
            snippet = item['snippet']
            content_details = item['contentDetails']
            
            # Parse duration
            duration_str = content_details['duration']
            import re
            match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
            if match:
                hours = int(match.group(1) or 0)
                minutes = int(match.group(2) or 0)
                seconds = int(match.group(3) or 0)
                total_seconds = hours * 3600 + minutes * 60 + seconds
            else:
                total_seconds = 0
            
            return {
                'video_id': video_id,
                'title': snippet['title'],
                'channel_name': snippet['channelTitle'],
                'channel_id': snippet['channelId'],
                'published_at': snippet['publishedAt'],
                'duration': total_seconds,
                'description': snippet.get('description', ''),
                'tags': snippet.get('tags', [])
            }
        except Exception as e:
            print(f"  ✗ Error fetching video metadata: {e}")
            return None
    
    def extract_single_video(self, video_id: str, output_subfolder: str = "Custom_Videos", verbose: bool = True) -> bool:
        """
        Extract caption from a single video by ID
        
        Args:
            video_id: YouTube video ID
            output_subfolder: Subfolder name for organizing output (deprecated - uses actual channel name)
            verbose: Show detailed messages
            
        Returns:
            True if extraction successful, False otherwise
        """
        print(f"\n📹 Extracting video: {video_id}")
        
        # Get video metadata
        video_info = self.get_video_metadata(video_id)
        if not video_info:
            return False
        
        print(f"  Title: {video_info['title']}")
        print(f"  Channel: {video_info['channel_name']}")
        print(f"  Duration: {video_info['duration']}s")
        
        # Check if already downloaded
        downloaded_ids = self.get_downloaded_video_ids()
        if video_id in downloaded_ids:
            print(f"  ⚠ Video already extracted, skipping...")
            return False
        
        # Extract caption
        caption_data = self.extract_caption(video_id, verbose=verbose)
        
        if caption_data:
            # Save caption using actual channel name for proper metadata
            self.save_caption(video_info, caption_data, video_info['channel_name'])
            print(f"  ✓ Caption extracted successfully")
            return True
        else:
            print(f"  ✗ No captions available")
            return False
    
    def search_videos_by_topic(self, query: str, max_results: int = 20,
                               channel_ids: List[str] = None,
                               max_duration: int = None,
                               min_date: str = None,
                               region_code: str = 'GB',
                               video_category_id: str = None) -> List[Dict]:
        """
        Search for videos by topic/keywords using YouTube API
        
        Args:
            query: Search query/keywords
            max_results: Maximum number of results to return
            channel_ids: Optional list of channel IDs to limit search
            max_duration: Maximum video duration in seconds
            min_date: Minimum publish date (ISO 8601 format)
            region_code: ISO 3166-1 alpha-2 region code, e.g. 'GB' (default) or 'US'
            video_category_id: YouTube category ID string, e.g. '27' for Education
            
        Returns:
            List of video information dictionaries
        """
        print(f"\n🔍 Searching for: '{query}'")
        
        try:
            results = []
            
            # Determine video duration filter
            duration_filter = None
            if max_duration:
                if max_duration <= 240:  # 4 minutes
                    duration_filter = 'short'
                elif max_duration <= 1200:  # 20 minutes
                    duration_filter = 'medium'
                # else: no filter (includes long videos)
            
            # Base search parameters (q is added per-pass below)
            base_params = {
                'part': 'snippet',
                'type': 'video',
                'maxResults': min(50, max_results),
                'relevanceLanguage': 'en',
                'order': 'relevance',
                'regionCode': region_code,
            }
            if video_category_id:
                base_params['videoCategoryId'] = video_category_id
            if duration_filter:
                base_params['videoDuration'] = duration_filter
            if min_date:
                base_params['publishedAfter'] = min_date

            channels_to_search = channel_ids if channel_ids else [None]
            seen_video_ids = set()

            def _collect_pass(q_str, remaining):
                """Run one search API pass and return deduplicated new results."""
                params = dict(base_params)
                params['q'] = q_str
                pass_results = []
                for ch_id in channels_to_search:
                    if len(pass_results) >= remaining:
                        break
                    if ch_id:
                        params['channelId'] = ch_id
                        print(f"  → Searching channel: {ch_id}")
                    elif 'channelId' in params:
                        del params['channelId']
                    request = self.youtube.search().list(**params)
                    response = self._api_call_with_retry(request, "search.list")
                    for item in response.get('items', []):
                        if len(pass_results) >= remaining:
                            break
                        video_id = item['id']['videoId']
                        if video_id in seen_video_ids:
                            continue
                        seen_video_ids.add(video_id)
                        snippet = item['snippet']
                        pass_results.append({
                            'video_id': video_id,
                            'title': snippet['title'],
                            'channel_name': snippet['channelTitle'],
                            'channel_id': snippet['channelId'],
                            'published_at': snippet['publishedAt'],
                            'description': snippet.get('description', '')[:200],
                            'thumbnail': snippet['thumbnails']['default']['url']
                        })
                return pass_results

            # Pass 1: exact quoted phrase for higher precision
            quoted_q = f'"{query}"'
            print(f"  → Pass 1 (quoted phrase): {quoted_q}")
            results.extend(_collect_pass(quoted_q, max_results))

            # Pass 2: broaden to unquoted query if pass 1 returns too few results
            TWO_PASS_THRESHOLD = 5
            if len(results) < TWO_PASS_THRESHOLD:
                print(f"  → Pass 2 (unquoted): {query}")
                results.extend(_collect_pass(query, max_results - len(results)))

            # Get detailed info (including exact duration) for all results
            if results:
                video_ids = [v['video_id'] for v in results]
                detailed_results = []
                
                for i in range(0, len(video_ids), 50):
                    batch_ids = video_ids[i:i+50]
                    request = self.youtube.videos().list(
                        part='contentDetails,statistics',
                        id=','.join(batch_ids)
                    )
                    details_response = self._api_call_with_retry(request, "videos.list")
                    
                    for item in details_response.get('items', []):
                        video_id = item['id']
                        duration_str = item['contentDetails']['duration']
                        
                        # Parse duration
                        import re
                        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
                        if match:
                            hours = int(match.group(1) or 0)
                            minutes = int(match.group(2) or 0)
                            seconds = int(match.group(3) or 0)
                            total_seconds = hours * 3600 + minutes * 60 + seconds
                        else:
                            total_seconds = 0
                        
                        # Find matching result and add duration
                        for result in results:
                            if result['video_id'] == video_id:
                                result['duration'] = total_seconds
                                result['view_count'] = item.get('statistics', {}).get('viewCount', 0)
                                
                                # Filter by max_duration if specified
                                if not max_duration or total_seconds <= max_duration:
                                    detailed_results.append(result)
                                break
                
                results = detailed_results
            
            print(f"  ✓ Found {len(results)} videos")
            return results
            
        except Exception as e:
            print(f"  ✗ Search error: {e}")
            return []
    
    def run_pipeline(self, csv_path: str, max_videos_per_channel: int = 50, exclude_video_ids: List[str] = None, auto_exclude_downloaded: bool = True, verbose: bool = True):
        """
        Run the complete extraction pipeline
        
        Args:
            csv_path: Path to CSV file with channel information
            max_videos_per_channel: Maximum videos to process per channel
            exclude_video_ids: List of video IDs to exclude from processing
            auto_exclude_downloaded: Automatically exclude already-downloaded videos
            verbose: Show detailed error messages
        """
        print("=" * 70)
        print("YouTube Caption Extraction Pipeline")
        print("=" * 70)
        
        # Load channels
        channels = self.load_channels_from_csv(csv_path)
        
        if not channels:
            print("\n✗ No channels to process")
            return
        
        # Process each channel
        for channel in channels:
            try:
                self.process_channel(channel, max_videos_per_channel, exclude_video_ids, auto_exclude_downloaded, verbose)
            except Exception as e:
                print(f"\n✗ Error processing channel {channel.get('channel_name')}: {e}")
                
                # If quota exceeded, stop processing
                if 'quotaExceeded' in str(e):
                    print(f"\n⚠ Stopping pipeline due to quota limits.")
                    break
                continue
        
        print("\n" + "=" * 70)
        print(f"✓ Pipeline completed! Captions saved to: {self.output_dir.absolute()}")
        print("=" * 70)


def main():
    """Main entry point for the script"""
    # Load environment variables
    load_dotenv()
    
    # Get configuration
    api_key = os.getenv('YOUTUBE_API_KEY')
    max_videos = 1  # Extract just 1 new video
    output_dir = os.getenv('OUTPUT_DIR', 'captions_output')
    
    if not api_key or api_key == 'your_api_key_here':
        print("✗ Error: Please set YOUTUBE_API_KEY in .env file")
        print("  Get your API key from: https://console.cloud.google.com/apis/credentials")
        return
    
    # Initialize extractor (uses default max_video_duration of 1200 seconds)
    extractor = YouTubeCaptionExtractor(api_key, output_dir)
    
    # Run pipeline (auto-excludes already downloaded videos)
    csv_path = 'channels.csv'
    extractor.run_pipeline(csv_path, max_videos, auto_exclude_downloaded=True)


if __name__ == '__main__':
    main()
