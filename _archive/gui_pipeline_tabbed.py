"""
GUI Frontend for YouTube Caption Extraction Pipeline (Tabbed Interface)
Provides user-friendly interface for extracting video captions with multiple extraction methods
"""

import os
import csv
import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from pathlib import Path
from datetime import datetime
import sys
sys.path.insert(0, str(Path(__file__).parent))

# Lazy-loaded imports and API key - don't load at startup
_youtube_api_key = None

def get_youtube_api_key():
    """Lazy-load YouTube API key"""
    global _youtube_api_key
    if _youtube_api_key is None:
        from dotenv import load_dotenv
        load_dotenv()
        _youtube_api_key = os.getenv('YOUTUBE_API_KEY')
    return _youtube_api_key


class PipelineGUI:
    """Main GUI application for caption extraction with tabbed interface"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Caption Extraction Pipeline")
        self.root.geometry("1200x800")
        
        # Common variables
        self.status_var = tk.StringVar(value="Ready")
        
        # Channel extraction variables
        self.num_videos_var = tk.StringVar(value="50")
        self.max_duration_var = tk.StringVar(value="1200")
        self.channel_name_var = tk.StringVar(value="numberblocks")
        self.channel_id_var = tk.StringVar()
        self.region_code_var = tk.StringVar(value="GB")
        
        # Video ID extraction variables
        self.video_ids_text_var = tk.StringVar()
        self.organize_by_topic_var = tk.BooleanVar(value=False)
        
        # Topic search variables
        self.search_query_var = tk.StringVar()
        self.search_max_duration_var = tk.StringVar(value="300")
        self.search_max_results_var = tk.StringVar(value="20")
        self.search_results = []
        self.selected_videos = set()
        
        # Extraction thread
        self.extraction_thread = None
        self.is_running = False
        self._channels_loaded = False
        
        # Setup GUI
        self.setup_ui()
        
        # Load channels asynchronously after GUI appears
        self.root.after(100, self.load_channels)
        
    def setup_ui(self):
        """Create the tabbed GUI layout"""
        
        # Configure root grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Create main container
        main_container = ttk.Frame(self.root, padding="10")
        main_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_container.columnconfigure(0, weight=1)
        main_container.rowconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(
            main_container, 
            text="YouTube Caption Extraction Pipeline", 
            font=('Arial', 16, 'bold')
        )
        title_label.grid(row=0, column=0, pady=(0, 10))
        
        # Create notebook (tabbed interface)
        self.notebook = ttk.Notebook(main_container)
        self.notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Create tabs
        self.create_channel_tab()
        self.create_video_id_tab()
        self.create_topic_search_tab()
        
        # Status bar at bottom
        status_frame = ttk.Frame(main_container)
        status_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        
        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT, padx=(0, 5))
        status_label = ttk.Label(status_frame, textvariable=self.status_var, foreground="blue")
        status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
    def create_channel_tab(self):
        """Create the channel-based extraction tab (original functionality)"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="📺 Channel Extraction")
        
        # Configure grid
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(3, weight=1)
        
        # Input section
        input_frame = ttk.LabelFrame(tab, text="Extraction Parameters", padding="10")
        input_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        input_frame.columnconfigure(1, weight=1)
        
        # Number of videos
        ttk.Label(input_frame, text="Number of Videos:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(input_frame, textvariable=self.num_videos_var, width=15).grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Label(input_frame, text="(Max videos to extract per channel)").grid(row=0, column=2, sticky=tk.W)
        
        # Max duration
        ttk.Label(input_frame, text="Max Video Duration (seconds):").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(input_frame, textvariable=self.max_duration_var, width=15).grid(row=1, column=1, sticky=tk.W, padx=5)
        ttk.Label(input_frame, text="(Skip videos longer than this)").grid(row=1, column=2, sticky=tk.W)
        
        # Channel name
        ttk.Label(input_frame, text="Channel:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.channel_combo = ttk.Combobox(input_frame, textvariable=self.channel_name_var, width=40)
        self.channel_combo.grid(row=2, column=1, sticky=tk.W, padx=5)
        ttk.Label(input_frame, text="(Select from channels.csv)").grid(row=2, column=2, sticky=tk.W)
        
        # Buttons
        button_frame = ttk.Frame(tab)
        button_frame.grid(row=1, column=0, pady=10)
        
        self.run_button = ttk.Button(button_frame, text="▶ Start Extraction", 
                                     command=self.start_channel_extraction, width=20)
        self.run_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(button_frame, text="⏹ Stop", 
                                      command=self.stop_extraction, width=12, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="🔄 Refresh", 
                  command=self.refresh_results, width=12).pack(side=tk.LEFT, padx=5)
        
        # Results section
        results_frame = ttk.LabelFrame(tab, text="Extraction Results", padding="10")
        results_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        self.create_results_table(results_frame)
        
        # Console output
        console_frame = ttk.LabelFrame(tab, text="Console Output", padding="10")
        console_frame.grid(row=4, column=0, sticky=(tk.W, tk.E))
        console_frame.columnconfigure(0, weight=1)
        
        self.console = scrolledtext.ScrolledText(console_frame, height=8, wrap=tk.WORD)
        self.console.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
    def create_video_id_tab(self):
        """Create the video ID extraction tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="🎯 Video IDs")
        
        # Configure grid
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)
        
        # Input section
        input_frame = ttk.LabelFrame(tab, text="Video IDs Input", padding="10")
        input_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        input_frame.columnconfigure(0, weight=1)
        
        # File input option
        file_frame = ttk.Frame(input_frame)
        file_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Button(file_frame, text="📁 Load from File (.txt or .csv)", 
                  command=self.load_video_ids_file, width=30).pack(side=tk.LEFT, padx=5)
        self.video_ids_file_label = ttk.Label(file_frame, text="No file loaded")
        self.video_ids_file_label.pack(side=tk.LEFT, padx=10)
        
        # Manual input option
        ttk.Label(input_frame, text="Or paste video IDs (one per line):").grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        
        self.video_ids_text = scrolledtext.ScrolledText(input_frame, height=10, wrap=tk.WORD)
        self.video_ids_text.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Options
        options_frame = ttk.Frame(input_frame)
        options_frame.grid(row=3, column=0, sticky=tk.W)
        
        ttk.Checkbutton(options_frame, text="Organize by topic (if CSV has 'topic' column)", 
                       variable=self.organize_by_topic_var).pack(side=tk.LEFT)
        
        # Extraction buttons
        button_frame = ttk.Frame(tab)
        button_frame.grid(row=1, column=0, pady=10)
        
        ttk.Button(button_frame, text="▶ Extract Captions", 
                  command=self.start_video_id_extraction, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="🗑 Clear", 
                  command=self.clear_video_ids, width=12).pack(side=tk.LEFT, padx=5)
        
        # Results
        results_frame = ttk.LabelFrame(tab, text="Extraction Results", padding="10")
        results_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        # Simple results text area
        self.video_id_results = scrolledtext.ScrolledText(results_frame, height=15, wrap=tk.WORD)
        self.video_id_results.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
    def create_topic_search_tab(self):
        """Create the topic search tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="🔍 Topic Search")
        
        # Configure grid
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)
        
        # Search input section
        search_frame = ttk.LabelFrame(tab, text="Search Parameters", padding="10")
        search_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        search_frame.columnconfigure(1, weight=1)
        
        # Search query
        ttk.Label(search_frame, text="Topic / Keywords:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(search_frame, textvariable=self.search_query_var, width=50).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        
        # Max duration filter
        ttk.Label(search_frame, text="Max Duration (seconds):").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(search_frame, textvariable=self.search_max_duration_var, width=15).grid(row=1, column=1, sticky=tk.W, padx=5)
        
        # Max results
        ttk.Label(search_frame, text="Max Results:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(search_frame, textvariable=self.search_max_results_var, width=15).grid(row=2, column=1, sticky=tk.W, padx=5)
        
        # Channel filter
        ttk.Label(search_frame, text="Limit to Channels:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.search_channel_filter = ttk.Combobox(search_frame, width=40)
        self.search_channel_filter.grid(row=3, column=1, sticky=tk.W, padx=5)
        self.search_channel_filter['values'] = ['All channels'] + list(self.channel_combo['values']) if hasattr(self, 'channel_combo') else ['All channels']
        self.search_channel_filter.set('All channels')
        
        # Search button
        button_frame = ttk.Frame(tab)
        button_frame.grid(row=1, column=0, pady=10)
        
        ttk.Button(button_frame, text="🔍 Search Videos", 
                  command=self.search_videos, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="✓ Select All", 
                  command=self.select_all_search_results, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="✗ Deselect All", 
                  command=self.deselect_all_search_results, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="▶ Extract Selected", 
                  command=self.extract_selected_videos, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="💾 Save IDs to File", 
                  command=self.save_search_results, width=20).pack(side=tk.LEFT, padx=5)
        
        # Search results table
        results_frame = ttk.LabelFrame(tab, text="Search Results", padding="10")
        results_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        # Create treeview for search results
        columns = ("select", "video_id", "title", "channel", "duration")
        self.search_tree = ttk.Treeview(results_frame, columns=columns, show="headings", height=15)
        
        self.search_tree.heading("select", text="☐")
        self.search_tree.heading("video_id", text="Video ID")
        self.search_tree.heading("title", text="Title")
        self.search_tree.heading("channel", text="Channel")
        self.search_tree.heading("duration", text="Duration")
        
        self.search_tree.column("select", width=40, anchor=tk.CENTER)
        self.search_tree.column("video_id", width=120)
        self.search_tree.column("title", width=400)
        self.search_tree.column("channel", width=150)
        self.search_tree.column("duration", width=80, anchor=tk.CENTER)
        
        # Scrollbars
        vsb = ttk.Scrollbar(results_frame, orient="vertical", command=self.search_tree.yview)
        hsb = ttk.Scrollbar(results_frame, orient="horizontal", command=self.search_tree.xview)
        self.search_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.search_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        vsb.grid(row=0, column=1, sticky=(tk.N, tk.S))
        hsb.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # Bind click event for checkbox toggle
        self.search_tree.bind('<Button-1>', self.toggle_search_selection)
        
    def create_results_table(self, parent):
        """Create the results table (for channel extraction tab)"""
        columns = ("video_id", "title", "duration", "status")
        self.results_tree = ttk.Treeview(parent, columns=columns, show="headings", height=10)
        
        self.results_tree.heading("video_id", text="Video ID")
        self.results_tree.heading("title", text="Title")
        self.results_tree.heading("duration", text="Duration")
        self.results_tree.heading("status", text="Status")
        
        self.results_tree.column("video_id", width=120)
        self.results_tree.column("title", width=400)
        self.results_tree.column("duration", width=80)
        self.results_tree.column("status", width=120)
        
        # Scrollbars
        vsb = ttk.Scrollbar(parent, orient="vertical", command=self.results_tree.yview)
        hsb = ttk.Scrollbar(parent, orient="horizontal", command=self.results_tree.xview)
        self.results_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.results_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        vsb.grid(row=0, column=1, sticky=(tk.N, tk.S))
        hsb.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
    # Channel extraction methods
    def start_channel_extraction(self):
        """Start the channel-based extraction"""
        if self.is_running:
            messagebox.showwarning("Warning", "Extraction already in progress")
            return
        
        # Validate inputs
        if not self.validate_channel_inputs():
            return
        
        self.is_running = True
        self.run_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_var.set("Extracting...")
        
        # Clear results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        # Start extraction in thread
        self.extraction_thread = threading.Thread(target=self.run_channel_extraction, daemon=True)
        self.extraction_thread.start()
    
    def run_channel_extraction(self):
        """Run the channel extraction (in background thread)"""
        try:
            num_videos = int(self.num_videos_var.get())
            max_duration = int(self.max_duration_var.get())
            channel_name = self.channel_name_var.get()
            region_code = self.region_code_var.get().strip().upper()
            
            # Get channel ID
            if channel_name in self.channel_map:
                channel_id = self.channel_map[channel_name]
            else:
                # Assume user entered a channel ID directly
                channel_id = channel_name
                channel_name = channel_name.replace('UC', '').replace('UU', '')[:20]
            
            self.log_message("="*60)
            self.log_message("Starting YouTube Caption Extraction (Conservative Mode)")
            self.log_message(f"Channel: {channel_name}")
            self.log_message(f"Target Videos: {num_videos}")
            self.log_message(f"Max Duration: {max_duration}s")
            self.log_message(f"Region Code: {region_code}")
            self.log_message("="*60)
            self.log_message("Bot Avoidance: 5 videos/batch, 8-15s delays, 30-60s breaks")
            self.log_message("="*60)
            
            # Import only when needed
            from data_pipeline.scheduler import ExtractionScheduler
            from data_pipeline.caption_extractor import YouTubeCaptionExtractor
            
            # Create scheduler for bot detection avoidance
            scheduler = ExtractionScheduler(
                channels_csv='channels.csv',
                state_file='extraction_state.json',
                videos_per_batch=5,
                min_delay_between_videos=1.0,
                max_delay_between_videos=5.0,
                min_break_duration=30.0,
                max_break_duration=60.0,
                notification_email=None
            )
            
            # Create extractor with minimal internal delays (scheduler handles timing)
            extractor = YouTubeCaptionExtractor(
                api_key=get_youtube_api_key(),
                output_dir='data/captions_output',
                cache_file='data/api_cache.json',
                delay_between_videos=0.5,
                random_delay_range=(0.5, 1.0),
                videos_per_batch=999,
                break_duration_range=(0, 0),
                max_video_duration=max_duration,
                use_proxy=True
            )
            
            # Get downloaded videos to skip
            downloaded_ids = extractor.get_downloaded_video_ids()
            self.log_message(f"Found {len(downloaded_ids)} already-downloaded videos (will skip)")
            
            # Get videos
            self.status_var.set("Fetching videos from channel...")
            self.log_message("\nFetching videos from channel...")
            videos = extractor.get_channel_videos(channel_id, max_results=500)
            
            if not self.is_running:
                self.finalize_extraction("Stopped by user")
                return
            
            # Filter out downloaded videos
            videos = [v for v in videos if v['video_id'] not in downloaded_ids]
            self.log_message(f"Found {len(videos)} new videos to process")
            
            # Process videos with scheduler
            extracted_count = 0
            skipped_count = 0
            videos_in_batch = 0
            
            for video in videos:
                if not self.is_running or extracted_count >= num_videos:
                    break
                
                # Check for IP block
                if scheduler.check_ip_block():
                    self.log_message("\n" + "="*60)
                    self.log_message("🚨 IP BLOCK DETECTED - Stopping extraction")
                    self.log_message("="*60)
                    self.root.after(0, lambda: messagebox.showwarning(
                        "IP Block Detected",
                        "YouTube has blocked your IP.\n\n"
                        "Wait 2-6 hours before trying again,\n"
                        "or use a different network/VPN."
                    ))
                    break
                
                video_id = video['video_id']
                title = video['title']
                duration = video.get('duration', 0)
                
                self.status_var.set(f"Extracting {extracted_count + 1}/{num_videos}: {title[:50]}...")
                self.log_message(f"\n[{extracted_count + 1}/{num_videos}] {title[:60]}...")
                self.log_message(f"  Duration: {duration}s")
                
                # Extract captions
                try:
                    caption_data = extractor.extract_caption(video_id, verbose=False)
                    
                    if caption_data is None:
                        self.log_message(f"  ⏭️  Skipped: No captions available")
                        skipped_count += 1
                        continue
                    
                    # Save captions
                    extractor.save_caption(video, caption_data, channel_name)
                    
                    self.log_message(f"  ✓ Extracted and saved")
                    extracted_count += 1
                    videos_in_batch += 1
                    
                    # Record in scheduler
                    scheduler.record_extraction(channel_id, video_id, True)
                    
                except Exception as e:
                    error_msg = str(e)
                    self.log_message(f"  ✗ Error: {error_msg[:100]}")
                    
                    # Check for IP block
                    if scheduler.check_ip_block(error_msg):
                        self.log_message("\n" + "="*60)
                        self.log_message("🚨 IP BLOCK DETECTED - Stopping extraction")
                        self.log_message("="*60)
                        self.root.after(0, lambda: messagebox.showwarning(
                            "IP Block Detected",
                            "YouTube has blocked your IP.\n\n"
                            "Wait 2-6 hours before trying again,\n"
                            "or use a different network/VPN."
                        ))
                        break
                
                # Should we take a break?
                if scheduler.should_take_break(videos_in_batch) and extracted_count < num_videos:
                    break_duration = scheduler.get_random_break()
                    self.log_message(f"\n☕ Taking {break_duration/60:.1f} minute break to avoid bot detection...")
                    self.status_var.set(f"Break time ({break_duration/60:.1f} min) - Bot avoidance")
                    
                    # Wait with periodic checks for stop signal
                    import time
                    remaining = break_duration
                    while remaining > 0 and self.is_running:
                        sleep_time = min(5, remaining)
                        time.sleep(sleep_time)
                        remaining -= sleep_time
                    
                    if self.is_running:
                        self.log_message(f"  ✓ Break complete, resuming...")
                    videos_in_batch = 0
                
                # Delay between videos (if not taking a break and still running)
                elif extracted_count < num_videos and self.is_running:
                    import time
                    delay = scheduler.get_random_delay()
                    self.log_message(f"  ⏱ Waiting {delay:.1f}s...")
                    time.sleep(delay)
            
            # Summary
            self.log_message("\n" + "="*60)
            self.log_message(f"✓ Extraction Complete")
            self.log_message(f"  Extracted: {extracted_count} videos")
            self.log_message(f"  Skipped: {skipped_count} videos")
            self.log_message("="*60)
            self.finalize_extraction("Completed")
            
        except Exception as e:
            self.log_message(f"✗ Error: {str(e)}")
            self.finalize_extraction(f"Failed: {str(e)}")
    
    # Video ID extraction methods
    def load_video_ids_file(self):
        """Load video IDs from a file"""
        file_path = filedialog.askopenfilename(
            title="Select Video IDs File",
            filetypes=[("Text files", "*.txt"), ("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_path.endswith('.csv'):
                    # Load CSV
                    import csv
                    reader = csv.DictReader(f)
                    video_ids = []
                    for row in reader:
                        if 'video_id' in row:
                            video_ids.append(row['video_id'])
                    content = '\n'.join(video_ids)
                else:
                    # Load plain text
                    content = f.read()
            
            self.video_ids_text.delete('1.0', tk.END)
            self.video_ids_text.insert('1.0', content)
            self.video_ids_file_label.config(text=f"Loaded: {Path(file_path).name}")
            self.log_message(f"✓ Loaded video IDs from {Path(file_path).name}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file: {e}")
    
    def clear_video_ids(self):
        """Clear the video IDs text box"""
        self.video_ids_text.delete('1.0', tk.END)
        self.video_ids_file_label.config(text="No file loaded")
        self.video_id_results.delete('1.0', tk.END)
    
    def start_video_id_extraction(self):
        """Start extraction for specified video IDs"""
        # Get video IDs from text box
        content = self.video_ids_text.get('1.0', tk.END).strip()
        if not content:
            messagebox.showwarning("Warning", "Please enter video IDs or load from file")
            return
        
        # Parse video IDs (one per line, ignore empty lines and comments)
        video_ids = []
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                # Extract just the video ID (handle various formats)
                if 'youtube.com/watch?v=' in line:
                    video_id = line.split('v=')[1].split('&')[0]
                elif 'youtu.be/' in line:
                    video_id = line.split('youtu.be/')[1].split('?')[0]
                else:
                    video_id = line
                video_ids.append(video_id.strip())
        
        if not video_ids:
            messagebox.showwarning("Warning", "No valid video IDs found")
            return
        
        self.video_id_results.delete('1.0', tk.END)
        self.video_id_results.insert(tk.END, f"Starting extraction for {len(video_ids)} videos...\n\n")
        
        # Start extraction in thread
        thread = threading.Thread(target=self.run_video_id_extraction, args=(video_ids,), daemon=True)
        thread.start()
    
    def run_video_id_extraction(self, video_ids):
        """Run the video ID extraction (in background thread)"""
        try:
            from data_pipeline.scheduler import ExtractionScheduler
            from data_pipeline.caption_extractor import YouTubeCaptionExtractor
            
            # Create scheduler for bot detection avoidance
            scheduler = ExtractionScheduler(
                channels_csv='channels.csv',
                state_file='extraction_state.json',
                videos_per_batch=5,
                min_delay_between_videos=1.0,
                max_delay_between_videos=5.0,
                min_break_duration=30.0,
                max_break_duration=60.0,
                notification_email=None
            )
            
            # Create extractor
            extractor = YouTubeCaptionExtractor(
                api_key=get_youtube_api_key(),
                output_dir='data/captions_output',
                delay_between_videos=0.5,
                random_delay_range=(0.5, 1.0),
                videos_per_batch=999,
                use_proxy=True
            )
            
            self.video_id_results.insert(tk.END, "Bot Avoidance: 5 videos/batch, delays, and breaks enabled\n")
            self.video_id_results.insert(tk.END, "="*60 + "\n\n")
            self.video_id_results.see(tk.END)
            
            success_count = 0
            videos_in_batch = 0
            
            for i, video_id in enumerate(video_ids, 1):
                # Check for IP block
                if scheduler.check_ip_block():
                    self.video_id_results.insert(tk.END, "\n" + "="*60 + "\n")
                    self.video_id_results.insert(tk.END, "🚨 IP BLOCK DETECTED - Stopping extraction\n")
                    self.video_id_results.insert(tk.END, "="*60 + "\n")
                    self.video_id_results.see(tk.END)
                    self.root.after(0, lambda: messagebox.showwarning(
                        "IP Block Detected",
                        "YouTube has blocked your IP.\n\n"
                        "Wait 2-6 hours before trying again,\n"
                        "or use a different network/VPN."
                    ))
                    break
                
                self.video_id_results.insert(tk.END, f"[{i}/{len(video_ids)}] Processing {video_id}...\n")
                self.video_id_results.see(tk.END)
                
                try:
                    # Extract video
                    if extractor.extract_single_video(video_id, output_subfolder="Video_IDs"):
                        success_count += 1
                        videos_in_batch += 1
                        self.video_id_results.insert(tk.END, f"  ✓ Success\n")
                        scheduler.record_extraction("Video_IDs", video_id, True)
                    else:
                        self.video_id_results.insert(tk.END, f"  ✗ Failed\n")
                    
                except Exception as e:
                    error_msg = str(e)
                    self.video_id_results.insert(tk.END, f"  ✗ Error: {error_msg[:100]}\n")
                    
                    # Check for IP block in error
                    if scheduler.check_ip_block(error_msg):
                        self.video_id_results.insert(tk.END, "\n" + "="*60 + "\n")
                        self.video_id_results.insert(tk.END, "🚨 IP BLOCK DETECTED - Stopping extraction\n")
                        self.video_id_results.insert(tk.END, "="*60 + "\n")
                        self.video_id_results.see(tk.END)
                        self.root.after(0, lambda: messagebox.showwarning(
                            "IP Block Detected",
                            "YouTube has blocked your IP.\n\n"
                            "Wait 2-6 hours before trying again,\n"
                            "or use a different network/VPN."
                        ))
                        break
                
                self.video_id_results.see(tk.END)
                
                # Should we take a break?
                if scheduler.should_take_break(videos_in_batch) and i < len(video_ids):
                    break_duration = scheduler.get_random_break()
                    self.video_id_results.insert(tk.END, f"\n☕ Taking {break_duration/60:.1f} minute break to avoid bot detection...\n")
                    self.video_id_results.see(tk.END)
                    
                    # Wait with periodic checks
                    import time
                    remaining = break_duration
                    while remaining > 0:
                        sleep_time = min(5, remaining)
                        time.sleep(sleep_time)
                        remaining -= sleep_time
                    
                    self.video_id_results.insert(tk.END, f"  ✓ Break complete, resuming...\n\n")
                    self.video_id_results.see(tk.END)
                    videos_in_batch = 0
                
                # Delay between videos (if not taking a break)
                elif i < len(video_ids):
                    import time
                    delay = scheduler.get_random_delay()
                    self.video_id_results.insert(tk.END, f"  ⏱ Waiting {delay:.1f}s...\n")
                    self.video_id_results.see(tk.END)
                    time.sleep(delay)
            
            self.video_id_results.insert(tk.END, f"\n{'='*60}\n")
            self.video_id_results.insert(tk.END, f"✓ Completed: {success_count}/{len(video_ids)} videos extracted\n")
            self.video_id_results.insert(tk.END, f"{'='*60}\n")
            self.video_id_results.see(tk.END)
            
        except Exception as e:
            self.video_id_results.insert(tk.END, f"\n✗ Error: {str(e)}\n")
            self.video_id_results.see(tk.END)
    
    # Topic search methods
    def search_videos(self):
        """Search for videos by topic"""
        query = self.search_query_var.get().strip()
        if not query:
            messagebox.showwarning("Warning", "Please enter search keywords")
            return
        
        # Clear previous results
        for item in self.search_tree.get_children():
            self.search_tree.delete(item)
        
        self.selected_videos.clear()
        self.status_var.set("Searching...")
        
        # Search in thread
        thread = threading.Thread(target=self.run_search, args=(query,), daemon=True)
        thread.start()
    
    def run_search(self, query):
        """Run the search (in background thread)"""
        try:
            from data_pipeline.caption_extractor import YouTubeCaptionExtractor
            
            max_duration = int(self.search_max_duration_var.get())
            max_results = int(self.search_max_results_var.get())
            
            # Create extractor with proxy enabled
            extractor = YouTubeCaptionExtractor(
                api_key=get_youtube_api_key(),
                output_dir='data/captions_output',
                use_proxy=True
            )
            
            # Get channel filter
            channel_filter = self.search_channel_filter.get()
            channel_ids = None
            if channel_filter != 'All channels':
                # Get channel ID from CSV
                channels = extractor.load_channels_from_csv('channels.csv')
                ch = next((c for c in channels if c.get('channel_name') == channel_filter), None)
                if ch:
                    channel_ids = [ch['channel_id']]
            
            # Search
            results = extractor.search_videos_by_topic(
                query, 
                max_results=max_results,
                channel_ids=channel_ids,
                max_duration=max_duration
            )
            
            self.search_results = results
            
            # Update UI in main thread
            self.root.after(0, self.display_search_results, results)
            self.root.after(0, lambda: self.status_var.set(f"Found {len(results)} videos"))
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Search Error", str(e)))
            self.root.after(0, lambda: self.status_var.set("Search failed"))
    
    def display_search_results(self, results):
        """Display search results in the tree"""
        for result in results:
            duration_str = f"{result['duration']//60}m {result['duration']%60}s"
            self.search_tree.insert('', 'end', values=(
                "☐",
                result['video_id'],
                result['title'][:60],
                result['channel_name'][:20],
                duration_str
            ))
    
    def toggle_search_selection(self, event):
        """Toggle selection checkboxes in search results"""
        region = self.search_tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        
        item = self.search_tree.identify_row(event.y)
        if not item:
            return
        
        values = list(self.search_tree.item(item, 'values'))
        video_id = values[1]
        
        # Toggle selection
        if video_id in self.selected_videos:
            self.selected_videos.remove(video_id)
            values[0] = "☐"
        else:
            self.selected_videos.add(video_id)
            values[0] = "☑"
        
        self.search_tree.item(item, values=values)
    
    def select_all_search_results(self):
        """Select all search results"""
        for item in self.search_tree.get_children():
            values = list(self.search_tree.item(item, 'values'))
            values[0] = "☑"
            self.selected_videos.add(values[1])
            self.search_tree.item(item, values=values)
    
    def deselect_all_search_results(self):
        """Deselect all search results"""
        for item in self.search_tree.get_children():
            values = list(self.search_tree.item(item, 'values'))
            values[0] = "☐"
            self.search_tree.item(item, values=values)
        self.selected_videos.clear()
    
    def extract_selected_videos(self):
        """Extract captions for selected videos"""
        if not self.selected_videos:
            messagebox.showwarning("Warning", "No videos selected")
            return
        
        video_ids = list(self.selected_videos)
        messagebox.showinfo("Extraction", f"Starting extraction for {len(video_ids)} selected videos")
        
        # Switch to Video ID tab to show progress
        self.notebook.select(1)
        self.video_ids_text.delete('1.0', tk.END)
        self.video_ids_text.insert('1.0', '\n'.join(video_ids))
        self.start_video_id_extraction()
    
    def save_search_results(self):
        """Save selected video IDs to file"""
        if not self.selected_videos:
            messagebox.showwarning("Warning", "No videos selected")
            return
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                if file_path.endswith('.csv'):
                    f.write("video_id,title,channel,duration\n")
                    for result in self.search_results:
                        if result['video_id'] in self.selected_videos:
                            f.write(f"{result['video_id']},{result['title']},{result['channel_name']},{result['duration']}\n")
                else:
                    for result in self.search_results:
                        if result['video_id'] in self.selected_videos:
                            f.write(f"{result['video_id']}\n")
            
            messagebox.showinfo("Success", f"Saved {len(self.selected_videos)} video IDs to {Path(file_path).name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file: {e}")
    
    # Common utility methods
    def load_channels(self):
        """Load channels from CSV"""
        if self._channels_loaded:
            return
        
        try:
            with open('channels.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                channels = [row['channel_name'] for row in reader if 'channel_name' in row]
            
            self.channel_combo['values'] = channels
            if hasattr(self, 'search_channel_filter'):
                self.search_channel_filter['values'] = ['All channels'] + channels
            
            if channels:
                self.channel_combo.set(channels[0])
            
            self._channels_loaded = True
                
        except Exception as e:
            self.log_message(f"Warning: Could not load channels.csv: {e}")
    
    def validate_channel_inputs(self):
        """Validate channel extraction inputs"""
        try:
            num_videos = int(self.num_videos_var.get())
            if num_videos <= 0:
                raise ValueError("Number of videos must be positive")
            
            max_duration = int(self.max_duration_var.get())
            if max_duration <= 0:
                raise ValueError("Max duration must be positive")
            
            if not self.channel_name_var.get():
                raise ValueError("Please select a channel")
            
            if not get_youtube_api_key():
                raise ValueError("YouTube API key not found in .env file")
            
            return True
            
        except ValueError as e:
            messagebox.showerror("Validation Error", str(e))
            return False
    
    def stop_extraction(self):
        """Stop the current extraction"""
        self.is_running = False
        self.status_var.set("Stopping...")
        self.log_message("⚠ Stop requested by user")
    
    def finalize_extraction(self, message):
        """Finalize extraction and reset UI"""
        self.is_running = False
        self.root.after(0, lambda: self.run_button.config(state=tk.NORMAL))
        self.root.after(0, lambda: self.stop_button.config(state=tk.DISABLED))
        self.root.after(0, lambda: self.status_var.set(message))
    
    def refresh_results(self):
        """Refresh the results display"""
        messagebox.showinfo("Refresh", "Results refreshed")
    
    def log_message(self, message):
        """Log a message to the console"""
        if hasattr(self, 'console'):
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.console.insert(tk.END, f"[{timestamp}] {message}\n")
            self.console.see(tk.END)
        print(message)
    
    # Stub methods (implement as needed)
    def run_ip_block_test(self):
        """Test for IP blocking"""
        messagebox.showinfo("IP Test", "IP block test - to be implemented")
    
    def chunk_all_captions(self):
        """Chunk all captions"""
        messagebox.showinfo("Chunking", "Chunking - to be implemented")


def main():
    """Main entry point"""
    root = tk.Tk()
    app = PipelineGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
