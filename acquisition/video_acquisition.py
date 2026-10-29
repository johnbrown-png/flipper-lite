"""
Video Acquisition GUI (formerly gui_main.py) - Module A, see docs/acquisition.md.

Tabs: Channel Extraction (channels.csv), Video IDs, Topic Search (find YouTube
videos by title/keywords). Extracts captions, then chunks, embeds and adds them to
the local FAISS index.

Launch from the project root: launch_video_acquisition.bat
"""

import os
import csv
import json
import threading
import re
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from pathlib import Path
from datetime import datetime
import sys
import winsound  # For auditory alerts on completion

# Data paths below (channels.csv, data/..., extraction_state.json) are relative to the project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

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
    ROW_TO_END_VIDEO_LIMIT = 1000

    @staticmethod
    def _sanitize_path_component(value, fallback="unknown"):
        """Make a filename/folder component safe for Windows and cross-platform filesystems."""
        safe = (value or "").strip()
        safe = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', safe)
        safe = safe.replace(' ', '_')
        safe = safe.strip(' .')
        return safe or fallback
    
    def __init__(self, root):
        self.root = root
        self.root.title("Flipper - Video Acquisition")
        self.root.geometry("1200x850")
        
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
        self.search_max_duration_var = tk.StringVar(value="800")
        self.search_max_results_var = tk.StringVar(value="40")
        self.search_results = []
        self.selected_videos = set()
        self.hide_extracted_var = tk.BooleanVar(value=False)
        self.search_region_var = tk.StringVar(value="GB")
        self.search_education_only_var = tk.BooleanVar(value=False)
        self.downloaded_video_ids = set()  # Cache of already-extracted video IDs
        
        # Search history tracking
        self.search_history_file = Path('search_history.json')
        self.search_history = []  # List of {timestamp, query, video_ids}
        self.video_sources = {}  # Maps video_id -> [list of search queries that found it]
        self.load_search_history()
        
        # Extraction thread
        self.extraction_thread = None
        self.is_running = False
        self._channels_loaded = False
        self._early_log_buffer = []  # Buffer for messages before console exists
        self.channel_map = {}  # Maps display_name -> full channel info
        self.channel_entries = []  # Ordered list of channel rows from channels.csv
        self.base_channel_map = {}  # Maps channel_name -> channel_id (for search filter)
        
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
        status_frame.columnconfigure(1, weight=1)
        
        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT, padx=(0, 5))
        status_label = ttk.Label(status_frame, textvariable=self.status_var, foreground="blue")
        status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
    
    def create_channel_tab(self):
        """Create the channel extraction tab (with processing controls)"""
        # Create scrollable container for this tab
        tab_container = ttk.Frame(self.notebook)
        self.notebook.add(tab_container, text="📺 Channel Extraction")
        
        tab_container.columnconfigure(0, weight=1)
        tab_container.rowconfigure(0, weight=1)
        
        # Create canvas for scrolling
        canvas = tk.Canvas(tab_container, bg='white')
        canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        scrollbar = ttk.Scrollbar(tab_container, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Main frame inside canvas
        tab = ttk.Frame(canvas, padding="10")
        canvas_window = canvas.create_window((0, 0), window=tab, anchor="nw")
        
        # Bind events for scrolling
        def on_frame_configure(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
        
        def on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)
        
        tab.bind("<Configure>", on_frame_configure)
        canvas.bind("<Configure>", on_canvas_configure)
        
        # Configure grid
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(4, weight=1)
        
        # Input section
        input_frame = ttk.LabelFrame(tab, text="Extraction Parameters", padding="10")
        input_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        input_frame.columnconfigure(1, weight=1)
        
        # Number of videos
        ttk.Label(input_frame, text="Number of Videos:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(input_frame, textvariable=self.num_videos_var, width=15).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(input_frame, text="(How many videos to extract)").grid(row=0, column=2, sticky=tk.W)
        
        # Max duration
        ttk.Label(input_frame, text="Max Video Duration (seconds):").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(input_frame, textvariable=self.max_duration_var, width=15).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(input_frame, text="(Videos longer than this will be skipped)").grid(row=1, column=2, sticky=tk.W)
        
        # Channel name with refresh button
        ttk.Label(input_frame, text="Channel Name or ID:").grid(row=2, column=0, sticky=tk.W, pady=5)
        
        # Frame to hold combobox and refresh button
        channel_control_frame = ttk.Frame(input_frame)
        channel_control_frame.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        self.channel_combo = ttk.Combobox(channel_control_frame, textvariable=self.channel_name_var, width=70)
        self.channel_combo.pack(side=tk.LEFT)
        
        ttk.Button(channel_control_frame, text="🔄", command=self.refresh_channels, width=3).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(input_frame, text="(Type channel name/ID or select from list)").grid(row=2, column=2, sticky=tk.W)
        
        # Region code
        ttk.Label(input_frame, text="Region Code:").grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Entry(input_frame, textvariable=self.region_code_var, width=15).grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(input_frame, text="(2-letter country code: GB, US, etc.)").grid(row=3, column=2, sticky=tk.W)
        
        # Button frames
        button_frame_top = ttk.Frame(tab)
        button_frame_top.grid(row=1, column=0, columnspan=3, pady=(5, 0))
        
        button_frame_bottom = ttk.Frame(tab)
        button_frame_bottom.grid(row=2, column=0, columnspan=3, pady=(5, 10))
        
        # Top row: Extraction buttons
        ttk.Label(button_frame_top, text="Step 1-2:", font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=(0, 5))
        
        self.run_button = ttk.Button(button_frame_top, text="▶ Extract", command=self.start_extraction, width=18)
        self.run_button.pack(side=tk.LEFT, padx=5)

        self.run_from_row_button = ttk.Button(
            button_frame_top,
            text="▶ Extract From This Row To End",
            command=self.start_extraction_from_row_to_end,
            width=30
        )
        self.run_from_row_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(button_frame_top, text="⏹ Stop", command=self.stop_extraction, width=12, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame_top, text="🔍 Test IP Block", command=self.run_ip_block_test, width=18).pack(side=tk.LEFT, padx=5)
        
        # Bottom row: Utility buttons
        ttk.Button(button_frame_bottom, text="🔗 Chunk", command=self.chunk_all_captions, width=18).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame_bottom, text="🔄 Refresh Results", command=self.refresh_results, width=18).pack(side=tk.LEFT, padx=5)
        
        # Results section
        results_frame = ttk.LabelFrame(tab, text="Processing Results", padding="10")
        results_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        # Results table
        self.create_results_table(results_frame)
        
        # Console output
        console_frame = ttk.LabelFrame(tab, text="Console Output", padding="10")
        console_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E))
        console_frame.columnconfigure(0, weight=1)
        
        self.console = scrolledtext.ScrolledText(console_frame, height=8, wrap=tk.WORD)
        self.console.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Processing section with progress indicators
        self.create_processing_section(tab)
    
    def create_processing_section(self, parent):
        """Create the processing section with buttons and progress visualization"""
        processing_frame = ttk.LabelFrame(parent, text="Processing & Progress", padding="10")
        processing_frame.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        processing_frame.columnconfigure(1, weight=1)
        
        # Buttons frame - left side
        buttons_frame = ttk.Frame(processing_frame)
        buttons_frame.grid(row=0, column=0, sticky=(tk.N, tk.W), padx=(0, 20))
        
        ttk.Label(buttons_frame, text="Step 3-4:", font=('Arial', 9, 'bold')).pack(anchor=tk.W, pady=(0, 10))
        
        self.embed_button = ttk.Button(buttons_frame, text="🧠 Generate Embeddings", command=self.start_embedding, width=22)
        self.embed_button.pack(pady=5)
        
        self.index_button = ttk.Button(buttons_frame, text="� Update Index", command=self.start_indexing, width=22)
        self.index_button.pack(pady=5)
        
        # Force rebuild checkbox
        self.force_rebuild_var = tk.BooleanVar(value=False)
        force_rebuild_cb = ttk.Checkbutton(
            buttons_frame, 
            text="Force full rebuild",
            variable=self.force_rebuild_var
        )
        force_rebuild_cb.pack(anchor=tk.W, padx=(10, 0), pady=(0, 5))
        
        # Progress Summary frame - right side
        progress_frame = ttk.LabelFrame(processing_frame, text="📊 Progress Summary", padding="10")
        progress_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Refresh button at top
        refresh_btn = ttk.Button(progress_frame, text="🔄 Refresh Stats", command=self.refresh_progress_stats)
        refresh_btn.pack(pady=(0, 5))
        
        # Create scrollable text widget for stats
        stats_container = ttk.Frame(progress_frame)
        stats_container.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(stats_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.progress_text = tk.Text(
            stats_container, 
            height=20, 
            width=45, 
            bg='#f9f9f9', 
            relief=tk.FLAT, 
            font=('Consolas', 9),
            yscrollcommand=scrollbar.set,
            wrap=tk.WORD
        )
        self.progress_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.progress_text.yview)
        self.progress_text.config(state=tk.DISABLED)
        
        # Schedule initial stats load
        self.root.after(500, self.refresh_progress_stats)
    
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
        self.search_channel_filter.set('All channels')
        
        # Hide already-extracted videos checkbox
        hide_extracted_check = ttk.Checkbutton(
            search_frame, 
            text="Hide already-extracted videos",
            variable=self.hide_extracted_var,
            command=self.refresh_search_display
        )
        hide_extracted_check.grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)

        # Region code
        ttk.Label(search_frame, text="Region Code:").grid(row=5, column=0, sticky=tk.W, pady=5)
        ttk.Entry(search_frame, textvariable=self.search_region_var, width=10).grid(row=5, column=1, sticky=tk.W, padx=5)

        # Education category filter
        education_check = ttk.Checkbutton(
            search_frame,
            text="Education category only (YouTube cat. 27)",
            variable=self.search_education_only_var,
        )
        education_check.grid(row=6, column=1, sticky=tk.W, padx=5, pady=5)

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
        ttk.Button(button_frame, text="📎 Append to CSV", 
                  command=self.append_to_csv, width=20).pack(side=tk.LEFT, padx=5)
        
        # Search results table
        results_frame = ttk.LabelFrame(tab, text="Search Results", padding="10")
        results_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        # Create treeview for search results
        columns = ("select", "video_id", "title", "channel", "duration", "found_in")
        self.search_tree = ttk.Treeview(results_frame, columns=columns, show="headings", height=15)
        
        self.search_tree.heading("select", text="☐")
        self.search_tree.heading("video_id", text="Video ID")
        self.search_tree.heading("title", text="Title")
        self.search_tree.heading("channel", text="Channel")
        self.search_tree.heading("duration", text="Duration")
        self.search_tree.heading("found_in", text="Previously Found In")
        
        self.search_tree.column("select", width=40, anchor=tk.CENTER)
        self.search_tree.column("video_id", width=100)
        self.search_tree.column("title", width=300)
        self.search_tree.column("channel", width=120)
        self.search_tree.column("duration", width=80, anchor=tk.CENTER)
        self.search_tree.column("found_in", width=200)
        
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
        """Create the results table for channel extraction"""
        # Create treeview with scrollbar
        tree_frame = ttk.Frame(parent)
        tree_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        
        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")
        
        # Treeview
        self.results_tree = ttk.Treeview(
            tree_frame,
            columns=("video_id", "title", "duration", "extraction", "chunking"),
            show="headings",
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set,
            height=10
        )
        
        # Configure scrollbars
        vsb.config(command=self.results_tree.yview)
        hsb.config(command=self.results_tree.xview)
        
        # Define columns
        self.results_tree.heading("video_id", text="Video ID")
        self.results_tree.heading("title", text="Video Title")
        self.results_tree.heading("duration", text="Duration (s)")
        self.results_tree.heading("extraction", text="Extraction")
        self.results_tree.heading("chunking", text="Chunking")
        
        # Column widths
        self.results_tree.column("video_id", width=120, minwidth=100)
        self.results_tree.column("title", width=300, minwidth=200)
        self.results_tree.column("duration", width=100, minwidth=80)
        self.results_tree.column("extraction", width=150, minwidth=100)
        self.results_tree.column("chunking", width=150, minwidth=100)
        
        # Grid layout
        self.results_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        vsb.grid(row=0, column=1, sticky=(tk.N, tk.S))
        hsb.grid(row=1, column=0, sticky=(tk.W, tk.E))
    
    # ==================== CHANNEL EXTRACTION METHODS ====================
    
    def load_channels(self):
        """Load channels from channels.csv"""
        if self._channels_loaded:
            return
        
        try:
            channels_file = Path('channels.csv')
            if not channels_file.exists():
                error_msg = f"channels.csv not found at {channels_file.absolute()}"
                self.log_console(f"Warning: {error_msg}")
                messagebox.showwarning("Channels Not Found", error_msg)
                return
            
            with open(channels_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                channels = list(reader)
                
            if not channels:
                error_msg = "channels.csv is empty or has no data"
                self.log_console(f"Warning: {error_msg}")
                messagebox.showwarning("No Channels", error_msg)
                return
            
            # Create display names that include playlist info
            display_names = []
            self.channel_map = {}  # Maps display_name -> full channel info dict
            self.channel_entries = []  # Ordered list of valid rows
            self.base_channel_map = {}  # Maps base channel_name -> channel_id
            
            for row_index, ch in enumerate(channels):
                # Validate required fields
                if 'channel_id' not in ch or 'channel_name' not in ch:
                    self.log_console(f"Warning: Skipping invalid channel entry: {ch}")
                    continue
                
                # Handle None values from CSV
                if not ch['channel_id'] or not ch['channel_name']:
                    self.log_console(f"Warning: Skipping channel with empty ID or name: {ch}")
                    continue
                    
                playlist_id = ch.get('playlist_id', '') or ''  # Handle None
                playlist_id = playlist_id.strip()
                
                # Create unique display name
                if playlist_id:
                    # Include playlist ID in display name for clarity
                    display_name = f"{ch['channel_name']} - {playlist_id}"
                    # Append playlist_name as suffix if available
                    playlist_name = (ch.get('playlist_name', '') or '').strip()
                    if playlist_name:
                        display_name = f"{display_name} ({playlist_name})"
                else:
                    display_name = ch['channel_name']

                source_line = row_index + 2
                if display_name in self.channel_map:
                    display_name = f"{display_name} [row {source_line}]"
                
                display_names.append(display_name)

                # Store full channel info (including playlist_id and source row)
                channel_entry = {
                    'channel_id': ch['channel_id'],
                    'channel_name': ch['channel_name'],
                    'playlist_id': playlist_id if playlist_id else None,
                    'playlist_name': (ch.get('playlist_name', '') or '').strip() or None,
                    'display_name': display_name,
                    'row_index': len(self.channel_entries),
                    'source_line': source_line
                }
                self.channel_map[display_name] = channel_entry
                self.channel_entries.append(channel_entry)
                
                # Store base channel mapping (for search filter)
                self.base_channel_map[ch['channel_name']] = ch['channel_id']
            
            if not display_names:
                error_msg = "No valid channels found in channels.csv"
                self.log_console(f"Warning: {error_msg}")
                messagebox.showwarning("No Valid Channels", error_msg)
                return
            
            # Update the combobox values
            self.channel_combo['values'] = display_names
            
            # Update search channel filter (use base channel names without playlist)
            if hasattr(self, 'search_channel_filter'):
                base_channel_names = list(set([ch['channel_name'] for ch in channels]))
                self.search_channel_filter['values'] = ['All channels'] + base_channel_names
            
            # Set default selection
            if display_names:
                self.channel_name_var.set(display_names[0])
                
            self._channels_loaded = True
            self.log_console(f"✓ Loaded {len(display_names)} channel/playlist entry(s)")
            
        except Exception as e:
            error_msg = f"Error loading channels: {e}"
            self.log_console(error_msg)
            messagebox.showerror("Error Loading Channels", error_msg)
            import traceback
            traceback.print_exc()

    def refresh_channels(self):
        """Reload channels from channels.csv"""
        self._channels_loaded = False
        self.load_channels()
        self.log_console("Channels refreshed from channels.csv")
    
    def log_console(self, message):
        """Add message to console output"""
        # Print to stdout for debugging
        print(f"[GUI LOG] {message}")
        
        if not hasattr(self, 'console'):
            # Buffer messages before console exists
            if hasattr(self, '_early_log_buffer'):
                self._early_log_buffer.append(message)
            return
            
        # Flush any buffered messages first
        if hasattr(self, '_early_log_buffer') and self._early_log_buffer:
            for buffered_msg in self._early_log_buffer:
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.console.insert(tk.END, f"[{timestamp}] {buffered_msg}\n")
            self._early_log_buffer.clear()
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.console.insert(tk.END, f"[{timestamp}] {message}\n")
        
        # Limit console to 500 lines for performance
        MAX_CONSOLE_LINES = 500
        line_count = int(self.console.index('end-1c').split('.')[0])
        if line_count > MAX_CONSOLE_LINES:
            self.console.delete('1.0', f'{line_count - MAX_CONSOLE_LINES}.0')
        
        self.console.see(tk.END)
        self.root.update_idletasks()
    
    def validate_inputs(self):
        """Validate user inputs"""
        return self.validate_extraction_inputs(require_num_videos=True)

    def validate_extraction_inputs(self, require_num_videos=True):
        """Validate extraction inputs for single-row and multi-row runs"""
        if require_num_videos:
            try:
                num_videos = int(self.num_videos_var.get())
                if num_videos <= 0:
                    raise ValueError("Number of videos must be positive")
            except ValueError as e:
                messagebox.showerror("Invalid Input", f"Number of videos: {e}")
                return False
        
        try:
            max_duration = int(self.max_duration_var.get())
            if max_duration <= 0:
                raise ValueError("Duration must be positive")
        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Max duration: {e}")
            return False
        
        channel_name = self.channel_name_var.get().strip()
        if not channel_name:
            messagebox.showerror("Invalid Input", "Please enter a channel name or ID")
            return False
        
        if not get_youtube_api_key():
            messagebox.showerror("Configuration Error", "YOUTUBE_API_KEY not found in .env file")
            return False
        
        return True

    def set_extraction_controls(self, is_running):
        """Enable or disable extraction controls"""
        self.run_button.config(state=tk.DISABLED if is_running else tk.NORMAL)
        self.run_from_row_button.config(state=tk.DISABLED if is_running else tk.NORMAL)
        self.stop_button.config(state=tk.NORMAL if is_running else tk.DISABLED)

    def begin_extraction(self, target):
        """Start a threaded extraction run"""
        self.set_extraction_controls(True)
        self.is_running = True
        self.console.delete(1.0, tk.END)
        self._extraction_log_counter = 0  # Track for logging every Nth video
        self.extraction_thread = threading.Thread(target=target, daemon=True)
        self.extraction_thread.start()

    def get_selected_channel_entry(self):
        """Return the currently selected channel entry from channels.csv"""
        display_name = self.channel_name_var.get().strip()
        return self.channel_map.get(display_name)

    def create_extraction_components(self, max_duration):
        """Create the scheduler, extractor, and downloaded ID cache for an extraction run"""
        from data_pipeline.scheduler import ExtractionScheduler
        from data_pipeline.caption_extractor import YouTubeCaptionExtractor

        scheduler = ExtractionScheduler(
            channels_csv='channels.csv',
            state_file='extraction_state.json',
            videos_per_batch=5,
            min_delay_between_videos=0.3,
            max_delay_between_videos=0.5,
            min_break_duration=15.0,
            max_break_duration=20.0,
            notification_email=None,
            state_save_batch_size=20
        )

        extractor = YouTubeCaptionExtractor(
            api_key=get_youtube_api_key(),
            output_dir='data/captions_output',
            cache_file='data/api_cache.json',
            delay_between_videos=0.5,
            random_delay_range=(0.5, 1.0),
            videos_per_batch=999,
            break_duration_range=(0, 0),
            max_video_duration=max_duration
        )

        downloaded_ids = set(extractor.get_downloaded_video_ids())
        return scheduler, extractor, downloaded_ids
    
    def start_extraction(self):
        """Start the extraction process in a separate thread"""
        if not self.validate_extraction_inputs(require_num_videos=True):
            return
        
        if self.is_running:
            messagebox.showinfo("Info", "Extraction is already running")
            return

        self.begin_extraction(self.run_extraction)

    def start_extraction_from_row_to_end(self):
        """Extract every channel/playlist row from the selected CSV row to the end of channels.csv"""
        if not self.validate_extraction_inputs(require_num_videos=False):
            return

        if self.is_running:
            messagebox.showinfo("Info", "Extraction is already running")
            return

        selected_entry = self.get_selected_channel_entry()
        if not selected_entry:
            messagebox.showerror(
                "Selection Required",
                "Select a channel or playlist from the channels.csv list before using Extract From This Row To End."
            )
            return

        self.begin_extraction(self.run_extraction_from_row_to_end)
    
    def stop_extraction(self):
        """Stop the extraction process"""
        self.is_running = False
        self.status_var.set("Stopping...")
        self.log_console("Stop requested by user")
    
    def run_extraction(self):
        """Run the extraction process (runs in separate thread)"""
        try:
            max_duration = int(self.max_duration_var.get())
            display_name = self.channel_name_var.get().strip()
            region_code = self.region_code_var.get().strip().upper()
            selected_entry = self.get_selected_channel_entry()

            if selected_entry:
                entry = selected_entry
            else:
                entry = {
                    'channel_id': display_name,
                    'channel_name': display_name.replace('UC', '').replace('UU', '')[:20],
                    'playlist_id': None,
                    'playlist_name': None,
                    'display_name': display_name,
                    'row_index': None,
                    'source_line': None
                }

            num_videos = int(self.num_videos_var.get())
            scheduler, extractor, downloaded_ids = self.create_extraction_components(max_duration)
            self.log_console(f"Found {len(downloaded_ids)} already-downloaded videos (will skip)")

            summary = self.extract_channel_entry(
                entry=entry,
                extractor=extractor,
                scheduler=scheduler,
                downloaded_ids=downloaded_ids,
                num_videos=num_videos,
                region_code=region_code
            )

            # Force save any remaining batched state before final summary
            if hasattr(scheduler, '_extractions_since_save') and scheduler._extractions_since_save > 0:
                scheduler._save_state()

            self.log_console("\n" + "="*60)
            self.log_console("✓ Extraction Complete!")
            self.log_console(f"  Extracted: {summary['extracted_count']} videos")
            self.log_console(f"  Skipped: {summary['skipped_count']} videos")
            self.log_console("="*60)

            self.root.after(0, self.refresh_progress_stats)

            if scheduler.ip_blocked:
                final_message = f"Stopped after IP block. Extracted {summary['extracted_count']} videos"
            elif not self.is_running:
                final_message = f"Stopped. Extracted {summary['extracted_count']} videos"
            else:
                final_message = f"Complete! Extracted {summary['extracted_count']} videos"

            self.finalize_extraction(final_message)
            
        except Exception as e:
            self.log_console(f"\n❌ Error: {e}")
            self.status_var.set(f"Error: {e}")
            messagebox.showerror("Extraction Error", str(e))
            self.finalize_extraction(f"Error: {e}")

    def run_extraction_from_row_to_end(self):
        """Run extraction for each channels.csv row from the selected row to the end of file"""
        try:
            selected_entry = self.get_selected_channel_entry()
            if not selected_entry:
                raise ValueError("No channels.csv row selected")

            max_duration = int(self.max_duration_var.get())
            region_code = self.region_code_var.get().strip().upper()
            scheduler, extractor, downloaded_ids = self.create_extraction_components(max_duration)

            start_index = selected_entry['row_index']
            entries_to_process = self.channel_entries[start_index:]

            self.log_console(f"Found {len(downloaded_ids)} already-downloaded videos (will skip)")
            self.log_console("=" * 60)
            self.log_console(
                f"Starting Extract From This Row To End at channels.csv line {selected_entry['source_line']}"
            )
            self.log_console(
                f"Rows queued: {len(entries_to_process)} (line {selected_entry['source_line']} through end of file)"
            )
            self.log_console(
                f"Per-row video cap: {self.ROW_TO_END_VIDEO_LIMIT} (effectively all available videos)"
            )
            self.log_console("=" * 60)

            total_extracted = 0
            total_skipped = 0
            rows_completed = 0

            for row_offset, entry in enumerate(entries_to_process, start=1):
                if not self.is_running:
                    break

                self.log_console("\n" + "-" * 60)
                self.log_console(
                    f"Row {entry['source_line']} ({row_offset}/{len(entries_to_process)}): {entry['channel_name']}"
                )
                if entry.get('playlist_id'):
                    self.log_console(f"Playlist: {entry['playlist_id']}")
                elif entry.get('playlist_name'):
                    self.log_console(f"Playlist Name: {entry['playlist_name']}")

                summary = self.extract_channel_entry(
                    entry=entry,
                    extractor=extractor,
                    scheduler=scheduler,
                    downloaded_ids=downloaded_ids,
                    num_videos=self.ROW_TO_END_VIDEO_LIMIT,
                    region_code=region_code,
                    run_label=f"Row {entry['source_line']} ({row_offset}/{len(entries_to_process)})"
                )

                total_extracted += summary['extracted_count']
                total_skipped += summary['skipped_count']
                rows_completed += 1

                if scheduler.ip_blocked:
                    break

            # Force save any remaining batched state before final summary
            if hasattr(scheduler, '_extractions_since_save') and scheduler._extractions_since_save > 0:
                scheduler._save_state()

            self.log_console("\n" + "=" * 60)
            self.log_console("✓ Row-to-end extraction finished")
            self.log_console(f"  Rows processed: {rows_completed}/{len(entries_to_process)}")
            self.log_console(f"  Extracted: {total_extracted} videos")
            self.log_console(f"  Skipped: {total_skipped} videos")
            self.log_console("=" * 60)

            self.root.after(0, self.refresh_progress_stats)

            if scheduler.ip_blocked:
                final_message = (
                    f"Stopped after IP block. Processed {rows_completed} row(s), extracted {total_extracted} videos"
                )
            elif not self.is_running:
                final_message = f"Stopped. Processed {rows_completed} row(s), extracted {total_extracted} videos"
            else:
                final_message = f"Complete! Processed {rows_completed} row(s), extracted {total_extracted} videos"

            self.finalize_extraction(final_message)

        except Exception as e:
            self.log_console(f"\n❌ Error: {e}")
            self.status_var.set(f"Error: {e}")
            messagebox.showerror("Extraction Error", str(e))
            self.finalize_extraction(f"Error: {e}")

    def extract_channel_entry(self, entry, extractor, scheduler, downloaded_ids, num_videos, region_code, run_label=None):
        """Extract and chunk captions for a single channel or playlist entry"""
        channel_id = entry['channel_id']
        channel_name = entry['channel_name']
        playlist_id = entry.get('playlist_id')
        source_line = entry.get('source_line')

        self.status_var.set("Initializing...")
        self.log_console("=" * 60)
        self.log_console("Starting YouTube Caption Extraction (Conservative Mode)")
        if run_label:
            self.log_console(f"Run: {run_label}")
        if source_line is not None:
            self.log_console(f"channels.csv line: {source_line}")
        self.log_console(f"Channel: {channel_name}")
        if playlist_id:
            self.log_console(f"Playlist: {playlist_id}")
        self.log_console(f"Target Videos: {num_videos}")
        self.log_console(f"Max Duration: {self.max_duration_var.get()}s")
        self.log_console(f"Region Code: {region_code}")
        self.log_console("=" * 60)
        self.log_console("Bot Avoidance: 5 videos/batch, 8-15s delays, 30-60s breaks")
        self.log_console("=" * 60)

        self.status_var.set("Fetching videos from channel/playlist...")
        if playlist_id:
            self.log_console(f"\nFetching videos from playlist {playlist_id}...")
        else:
            self.log_console("\nFetching videos from channel...")

        videos = extractor.get_channel_videos(channel_id, max_results=500, playlist_id=playlist_id)

        if not self.is_running:
            return {'extracted_count': 0, 'skipped_count': 0}

        videos = [video for video in videos if video['video_id'] not in downloaded_ids]
        self.log_console(f"Found {len(videos)} new videos to process")

        extracted_count = 0
        skipped_count = 0
        extracted_videos = []
        videos_in_batch = 0

        for video in videos:
            if not self.is_running or extracted_count >= num_videos:
                break

            if scheduler.check_ip_block():
                self.log_console("\n" + "=" * 60)
                self.log_console("🚨 IP BLOCK DETECTED - Stopping extraction")
                self.log_console("=" * 60)
                messagebox.showwarning(
                    "IP Block Detected",
                    "YouTube has blocked your IP.\n\nWait 2-6 hours before trying again,\nor use a different network/VPN."
                )
                break

            video_id = video['video_id']
            title = video['title']
            duration = video.get('duration', 0)

            # Log summary every 10 videos to reduce console spam
            self._extraction_log_counter += 1
            should_log = (self._extraction_log_counter % 10 == 1)

            self.status_var.set(f"Extracting {extracted_count + 1}/{num_videos}: {title[:50]}...")
            if should_log:
                self.log_console(f"\n[{extracted_count + 1}/{num_videos}] Processing batch ({self._extraction_log_counter - 10} to {self._extraction_log_counter})...")
                self.log_console(f"  Last: {title[:60]}... ({duration}s)")

            try:
                caption_data = extractor.extract_caption(video_id, verbose=False)

                if caption_data is None:
                    if should_log or extracted_count == 0:
                        self.log_console("  ⏭️  Skipped: No captions (shown for 1st in batch)")
                    skipped_count += 1
                    self.add_result_row(video_id, title, duration, "Skipped (no captions)", "N/A")
                    continue

                extractor.save_caption(video, caption_data, channel_name)

                if should_log or extracted_count == 0:
                    self.log_console("  ✓ Extracted and saved")
                extracted_count += 1
                videos_in_batch += 1
                downloaded_ids.add(video_id)

                scheduler.record_extraction(channel_id, video_id, True)

                safe_channel_name = self._sanitize_path_component(channel_name, fallback='unknown_channel')
                channel_dir = Path('data/captions_output') / safe_channel_name
                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()[:100]
                json_path = channel_dir / f"{safe_title}_{video_id}.json"

                self.add_result_row(video_id, title, duration, "✓ Extracted", "Pending")
                extracted_videos.append({'video_id': video_id, 'title': title, 'json_path': json_path})

            except Exception as e:
                error_msg = str(e)
                self.log_console(f"  ✗ Error: {error_msg}")

                if scheduler.check_ip_block(error_msg):
                    self.log_console("\n" + "=" * 60)
                    self.log_console("🚨 IP BLOCK DETECTED - Stopping extraction")
                    self.log_console("=" * 60)
                    messagebox.showwarning(
                        "IP Block Detected",
                        "YouTube has blocked your IP.\n\nWait 2-6 hours before trying again,\nor use a different network/VPN."
                    )
                    break

            if scheduler.should_take_break(videos_in_batch) and extracted_count < num_videos:
                break_duration = scheduler.get_random_break()
                self.log_console(f"\n☕ Taking {break_duration/60:.1f} minute break to avoid bot detection...")
                self.status_var.set(f"Break time ({break_duration/60:.1f} min) - Bot avoidance")

                import time
                remaining = break_duration
                while remaining > 0 and self.is_running:
                    sleep_time = min(5, remaining)
                    time.sleep(sleep_time)
                    remaining -= sleep_time

                if self.is_running:
                    self.log_console("  ✓ Break complete, resuming...")
                videos_in_batch = 0

            elif extracted_count < num_videos and self.is_running:
                import time
                delay = scheduler.get_random_delay()
                if should_log or self._extraction_log_counter <= 2:
                    self.log_console(f"  ⏱ Waiting {delay:.1f}s...")
                time.sleep(delay)

        if extracted_videos and self.is_running:
            self.log_console("\n" + "=" * 60)
            self.log_console("Starting Chunking Process")
            self.log_console("=" * 60)
            self.status_var.set("Chunking transcripts...")

            from data_pipeline.chunker import TranscriptChunker

            chunker = TranscriptChunker(
                input_dir='data/captions_output',
                output_dir='data/chunked_output',
                chunk_size=100,
                chunk_overlap=20
            )

            for idx, video_info in enumerate(extracted_videos, 1):
                if not self.is_running:
                    break

                video_id = video_info['video_id']
                title = video_info['title']

                self.status_var.set(f"Chunking {idx}/{len(extracted_videos)}: {title[:50]}...")
                self.log_console(f"\n[{idx}/{len(extracted_videos)}] Chunking {title[:60]}...")
                self.update_chunking_status(video_id, "Chunking...")

                try:
                    result = chunker.process_transcript(video_info['json_path'])

                    if result:
                        output_file = Path('data/chunked_output') / f"{result['video_id']}_chunked.json"
                        with open(output_file, 'w', encoding='utf-8') as f:
                            json.dump(result, f, indent=2, ensure_ascii=False)

                        self.log_console(f"  ✓ Chunked: {output_file.name}")
                        self.update_chunking_status(video_id, "✓ Chunked")
                    else:
                        self.log_console("  ⚠️  Failed to chunk")
                        self.update_chunking_status(video_id, "✗ Failed")
                except Exception as e:
                    self.log_console(f"  ✗ Chunking error: {e}")
                    self.update_chunking_status(video_id, "✗ Error")

        return {'extracted_count': extracted_count, 'skipped_count': skipped_count}
    
    def add_result_row(self, video_id, title, duration, extraction_status, chunking_status="Pending"):
        """Add a row to the results table (thread-safe)"""
        def _add():
            MAX_VISIBLE_RESULTS = 100
            children = self.results_tree.get_children()
            if len(children) >= MAX_VISIBLE_RESULTS:
                self.results_tree.delete(children[0])
            
            duration_display = str(int(duration)) if duration else "0"
            
            self.results_tree.insert(
                "", 
                tk.END, 
                values=(video_id, title, duration_display, extraction_status, chunking_status),
                tags=(video_id,)
            )
        self.root.after(0, _add)
    
    def update_chunking_status(self, video_id, chunking_status):
        """Update chunking status for a specific video"""
        def _update():
            for item in self.results_tree.get_children():
                values = self.results_tree.item(item, 'values')
                if values[0] == video_id:
                    self.results_tree.item(item, values=(values[0], values[1], values[2], values[3], chunking_status))
                    break
        self.root.after(0, _update)
    
    def finalize_extraction(self, message):
        """Clean up after extraction completes"""
        def _finalize():
            self.status_var.set(message)
            self.set_extraction_controls(False)
            self.is_running = False
            
            # Play auditory alert to notify user of completion
            try:
                # Play system asterisk sound (pleasant chime)
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception as e:
                # Silently fail if sound doesn't work
                pass
        self.root.after(0, _finalize)
    
    def refresh_results(self):
        """Refresh the results table from existing files"""
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        self.log_console("Refreshing results from existing files...")
        
        try:
            chunked_dir = Path('data/chunked_output')
            if not chunked_dir.exists():
                self.log_console("No chunked_output directory found")
                return
            
            chunked_files = list(chunked_dir.glob('*_chunked.json'))
            self.log_console(f"Found {len(chunked_files)} processed videos")
            
            for file in sorted(chunked_files)[:100]:
                video_id = file.stem.replace('_chunked', '')
                
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        title = data.get('title', 'Unknown')
                        
                    self.results_tree.insert(
                        "", 
                        tk.END, 
                        values=(video_id, title, "N/A", "✓ Existing", "✓ Existing")
                    )
                except Exception as e:
                    self.log_console(f"Error loading {video_id}: {e}")
            
            self.status_var.set(f"Loaded {len(chunked_files)} existing results")
            self.log_console("Results refreshed")
            self.refresh_progress_stats()
            
        except Exception as e:
            self.log_console(f"Error refreshing results: {e}")
    
    def run_ip_block_test(self):
        """Run IP block test in a separate thread"""
        if self.is_running:
            messagebox.showinfo("Info", "Please wait for current operation to finish")
            return
        
        self.console.delete(1.0, tk.END)
        self.log_console("Starting IP block test...")
        self.status_var.set("Running IP block test...")
        
        def _run_test():
            old_stdout = None
            try:
                import test_ip_block
                import io
                import sys
                old_stdout = sys.stdout
                sys.stdout = io.StringIO()
                
                test_ip_block.main()
                
                output = sys.stdout.getvalue()
                sys.stdout = old_stdout
                
                self.root.after(0, lambda: self.console.insert(tk.END, output))
                self.root.after(0, lambda: self.console.see(tk.END))
                self.root.after(0, lambda: self.status_var.set("IP block test completed"))
                
            except Exception as e:
                if old_stdout is not None:
                    sys.stdout = old_stdout
                error_msg = f"Error running IP block test: {e}"
                self.root.after(0, lambda: self.log_console(error_msg))
                self.root.after(0, lambda: self.status_var.set("IP block test failed"))
        
        threading.Thread(target=_run_test, daemon=True).start()
    
    def chunk_all_captions(self):
        """Process all caption files that don't have chunked versions yet"""
        if self.is_running:
            messagebox.showinfo("Info", "Please wait for current operation to finish")
            return
        
        captions_dir = Path('data/captions_output')
        chunked_dir = Path('data/chunked_output')
        
        caption_files = list(captions_dir.glob('**/*.json'))
        
        chunked_ids = set()
        if chunked_dir.exists():
            for f in chunked_dir.glob('*_chunked.json'):
                video_id = f.stem.replace('_chunked', '')
                chunked_ids.add(video_id)
        
        files_to_chunk = []
        for caption_file in caption_files:
            # Extract video ID (last 11 characters of filename, YouTube IDs are always 11 chars)
            video_id = caption_file.stem[-11:]
            if video_id not in chunked_ids:
                files_to_chunk.append(caption_file)
        
        if not files_to_chunk:
            messagebox.showinfo("Info", f"All {len(caption_files)} caption files are already chunked!")
            return
        
        response = messagebox.askyesno(
            "Chunk",
            f"Found {len(caption_files)} total caption files.\n{len(chunked_ids)} already chunked.\n{len(files_to_chunk)} need chunking.\n\nProcess these {len(files_to_chunk)} files?"
        )
        
        if not response:
            return
        
        self.run_button.config(state=tk.DISABLED)
        self.embed_button.config(state=tk.DISABLED)
        self.index_button.config(state=tk.DISABLED)
        self.is_running = True
        
        self.console.delete(1.0, tk.END)
        
        threading.Thread(target=self.run_all_chunking, args=(files_to_chunk,), daemon=True).start()
    
    def run_all_chunking(self, files_to_chunk):
        """Process all caption files for chunking"""
        try:
            from data_pipeline.chunker import TranscriptChunker
            
            self.log_console("="*60)
            self.log_console("CHUNKING ALL CAPTIONS")
            self.log_console("="*60)
            self.log_console(f"Files to process: {len(files_to_chunk)}")
            
            chunker = TranscriptChunker(
                input_dir='data/captions_output',
                output_dir='data/chunked_output',
                chunk_size=100,
                chunk_overlap=20
            )
            
            processed = 0
            failed = 0
            
            for idx, caption_file in enumerate(files_to_chunk, 1):
                try:
                    self.status_var.set(f"Chunking {idx}/{len(files_to_chunk)}: {caption_file.name[:40]}...")
                    self.log_console(f"\n[{idx}/{len(files_to_chunk)}] {caption_file.name}")
                    
                    result = chunker.process_transcript(caption_file)
                    
                    if result:
                        output_file = Path('data/chunked_output') / f"{result['video_id']}_chunked.json"
                        with open(output_file, 'w', encoding='utf-8') as f:
                            json.dump(result, f, indent=2, ensure_ascii=False)
                        
                        self.log_console(f"  ✓ Chunked: {output_file.name} ({result['total_chunks']} chunks)")
                        processed += 1
                    else:
                        self.log_console(f"  ⚠️  Failed to chunk")
                        failed += 1
                except Exception as e:
                    self.log_console(f"  ✗ Error: {e}")
                    failed += 1
            
            self.log_console("\n" + "="*60)
            self.log_console("✓ CHUNKING COMPLETE!")
            self.log_console(f"  Processed: {processed}")
            self.log_console(f"  Failed: {failed}")
            self.log_console("="*60)
            
            self.status_var.set(f"Chunking complete: {processed} files processed")
            messagebox.showinfo("Success", f"Chunked {processed} files!\n{failed} failed.")
            
        except Exception as e:
            self.log_console(f"\n❌ Error: {e}")
            self.status_var.set(f"Chunking error: {e}")
            messagebox.showerror("Chunking Error", str(e))
        finally:
            self.run_button.config(state=tk.NORMAL)
            self.embed_button.config(state=tk.NORMAL)
            self.index_button.config(state=tk.NORMAL)
            self.is_running = False
    
    # ==================== PROCESSING METHODS ====================
    
    def refresh_progress_stats(self):
        """Refresh and display progress statistics (totals only for fast loading)"""
        try:
            self.progress_text.config(state=tk.NORMAL)
            self.progress_text.delete('1.0', tk.END)
            
            self.progress_text.insert(tk.END, "═" * 42 + "\n", 'header')
            self.progress_text.insert(tk.END, "  PIPELINE PROGRESS STATISTICS\n", 'header')
            self.progress_text.insert(tk.END, "═" * 42 + "\n\n", 'header')
            
            stats = self.get_pipeline_statistics()
            
            # Display totals only (fast loading)
            self.progress_text.insert(tk.END, "📊 PIPELINE TOTALS\n", 'section')
            self.progress_text.insert(tk.END, "─" * 42 + "\n\n")
            
            self.progress_text.insert(tk.END, "  📹 Extracted:  ", 'label')
            self.progress_text.insert(tk.END, f"{stats['totals']['extracted']:>6} videos\n\n", 'value')
            
            self.progress_text.insert(tk.END, "  🔗 Chunked:    ", 'label')
            self.progress_text.insert(tk.END, f"{stats['totals']['chunked']:>6} videos\n\n", 'value')
            
            self.progress_text.insert(tk.END, "  🧠 Embedded:   ", 'label')
            self.progress_text.insert(tk.END, f"{stats['totals']['embedded']:>6} videos\n\n", 'value')
            
            self.progress_text.insert(tk.END, "  📊 Indexed:    ", 'label')
            self.progress_text.insert(tk.END, f"{stats['totals']['indexed']:>6} videos\n\n", 'value')
            
            self.progress_text.insert(tk.END, "\n" + "─" * 42 + "\n")
            self.progress_text.insert(tk.END, f"Last updated: {datetime.now().strftime('%H:%M:%S')}\n", 'footer')
            
            # Configure tags
            self.progress_text.tag_config('header', font=('Consolas', 9, 'bold'))
            self.progress_text.tag_config('section', font=('Consolas', 10, 'bold'), foreground='#2c3e50')
            self.progress_text.tag_config('label', font=('Consolas', 9))
            self.progress_text.tag_config('value', font=('Consolas', 10, 'bold'), foreground='#27ae60')
            self.progress_text.tag_config('footer', font=('Consolas', 8), foreground='#7f8c8d')
            
            self.progress_text.config(state=tk.DISABLED)
            
        except Exception as e:
            self.progress_text.config(state=tk.NORMAL)
            self.progress_text.delete('1.0', tk.END)
            self.progress_text.insert(tk.END, f"Error loading statistics:\n{str(e)}")
            self.progress_text.config(state=tk.DISABLED)
    
    def get_pipeline_statistics(self):
        """Get pipeline statistics (totals only for fast performance)"""
        stats = {
            'totals': {'extracted': 0, 'chunked': 0, 'embedded': 0, 'indexed': 0}
        }
        
        try:
            # Count extracted videos (all channels)
            captions_dir = Path('data/captions_output')
            if captions_dir.exists():
                for channel_dir in captions_dir.iterdir():
                    if channel_dir.is_dir():
                        count = sum(1 for _ in channel_dir.glob('*.json'))
                        stats['totals']['extracted'] += count
            
            # Count chunked videos
            chunked_dir = Path('data/chunked_output')
            if chunked_dir.exists():
                stats['totals']['chunked'] = sum(1 for _ in chunked_dir.glob('*_chunked.json'))
            
            # Count embedded videos
            embeddings_dir = Path('data/embeddings_output')
            if embeddings_dir.exists():
                stats['totals']['embedded'] = sum(1 for _ in embeddings_dir.glob('*_embeddings.json'))
            
            # Count indexed videos
            metadata_file = Path('data/faiss_index/faiss_index_metadata.json')
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    metadata_list = data.get('metadata', data)
                    
                    # Just count unique video IDs
                    video_ids = set()
                    for entry in metadata_list:
                        if isinstance(entry, dict) and 'video_id' in entry:
                            video_ids.add(entry['video_id'])
                    
                    stats['totals']['indexed'] = len(video_ids)
        
        except Exception as e:
            print(f"Error gathering statistics: {e}")
        
        return stats
    
    # Removed find_channel_for_video() method - no longer needed for totals-only statistics
    
    def start_embedding(self):
        """Start the embedding generation process"""
        if self.is_running:
            messagebox.showinfo("Info", "Please wait for current operation to finish")
            return
        
        chunked_dir = Path('data/chunked_output')
        if not chunked_dir.exists() or not list(chunked_dir.glob('*_chunked.json')):
            messagebox.showwarning("No Data", "No chunked transcripts found. Please run extraction first.")
            return
        
        chunked_files = list(chunked_dir.glob('*_chunked.json'))
        response = messagebox.askyesno(
            "Generate Embeddings",
            f"Found {len(chunked_files)} chunked files.\n\nThis will use OpenAI API (costs money).\n\nContinue?"
        )
        
        if not response:
            return
        
        self.run_button.config(state=tk.DISABLED)
        self.embed_button.config(state=tk.DISABLED)
        self.index_button.config(state=tk.DISABLED)
        self.is_running = True
        
        self.console.delete(1.0, tk.END)
        
        threading.Thread(target=self.run_embedding, daemon=True).start()
    
    def run_embedding(self):
        """Run the embedding generation process"""
        try:
            from shared.config import OPENAI_API_KEY, EMBEDDING_MODEL, EMBEDDING_DIMENSIONS, CHUNKED_DIR, EMBEDDINGS_DIR
            from data_pipeline.embedder import EmbeddingGenerator
            
            self.status_var.set("Generating embeddings...")
            self.log_console("="*60)
            self.log_console("GENERATING EMBEDDINGS")
            self.log_console("="*60)
            self.log_console(f"Model: {EMBEDDING_MODEL}")
            self.log_console(f"Dimensions: {EMBEDDING_DIMENSIONS}")
            
            embedder = EmbeddingGenerator(
                api_key=OPENAI_API_KEY,
                input_dir=str(CHUNKED_DIR),
                output_dir=str(EMBEDDINGS_DIR),
                model=EMBEDDING_MODEL,
                dimensions=EMBEDDING_DIMENSIONS
            )
            
            stats = embedder.process_all_chunks()
            
            self.log_console("\n" + "="*60)
            self.log_console("✓ EMBEDDING GENERATION COMPLETE!")
            self.log_console(f"  Files processed: {stats['files_processed']}")
            self.log_console(f"  Files skipped: {stats.get('skipped', 0)} (already embedded)")
            self.log_console(f"  Total embeddings: {stats['total_embeddings']}")
            self.log_console("="*60)
            
            if stats.get('skipped', 0) > 0:
                self.status_var.set(f"Embeddings: {stats['total_embeddings']} new, {stats['skipped']} skipped")
            else:
                self.status_var.set(f"Embeddings complete: {stats['total_embeddings']} vectors")
            
            self.refresh_progress_stats()
            
            messagebox.showinfo("Success", f"Generated {stats['total_embeddings']} embeddings!\n\nSkipped {stats.get('skipped', 0)} already-embedded files.")
            
        except Exception as e:
            self.log_console(f"\n❌ Error: {e}")
            self.status_var.set(f"Embedding error: {e}")
            messagebox.showerror("Embedding Error", str(e))
        finally:
            self.run_button.config(state=tk.NORMAL)
            self.embed_button.config(state=tk.NORMAL)
            self.index_button.config(state=tk.NORMAL)
            self.is_running = False
    
    def start_indexing(self):
        """Start the FAISS index building process"""
        if self.is_running:
            messagebox.showinfo("Info", "Please wait for current operation to finish")
            return
        
        embeddings_dir = Path('data/embeddings_output')
        if not embeddings_dir.exists() or not list(embeddings_dir.glob('*.json')):
            messagebox.showwarning("No Data", "No embeddings found. Please generate embeddings first.")
            return
        
        embedding_files = list(embeddings_dir.glob('*.json'))
        response = messagebox.askyesno(
            "Build Search Index",
            f"Found {len(embedding_files)} embedding files.\n\nBuild FAISS search index?\n\nThis may take a few minutes."
        )
        
        if not response:
            return
        
        self.run_button.config(state=tk.DISABLED)
        self.embed_button.config(state=tk.DISABLED)
        self.index_button.config(state=tk.DISABLED)
        self.is_running = True
        
        self.console.delete(1.0, tk.END)
        
        threading.Thread(target=self.run_indexing, daemon=True).start()
    
    def run_indexing(self):
        """Run the FAISS index building process (incremental by default)"""
        try:
            from shared.config import EMBEDDING_DIMENSIONS, EMBEDDINGS_DIR, FAISS_INDEX_DIR
            from data_pipeline.indexer import FAISSIndexBuilder
            
            # Check force rebuild checkbox
            force_rebuild = self.force_rebuild_var.get()
            
            # Check if index exists to show appropriate message
            index_exists = (FAISS_INDEX_DIR / 'faiss_index.bin').exists()
            
            if force_rebuild:
                action_word = "Rebuilding"
                self.log_console("⚠️  FORCE REBUILD MODE - This will take longer")
            else:
                action_word = "Updating" if index_exists else "Building"
            
            self.status_var.set(f"{action_word} FAISS index...")
            self.log_console("="*60)
            self.log_console(f"{action_word.upper()} FAISS SEARCH INDEX")
            self.log_console("="*60)
            self.log_console(f"Dimension: {EMBEDDING_DIMENSIONS}")
            if force_rebuild:
                self.log_console("Mode: Full rebuild from scratch")
            elif index_exists:
                self.log_console("Mode: Incremental update (fast!)")
            else:
                self.log_console("Mode: Initial build")
            
            indexer = FAISSIndexBuilder(
                embeddings_dir=str(EMBEDDINGS_DIR),
                output_dir=str(FAISS_INDEX_DIR),
                dimension=EMBEDDING_DIMENSIONS
            )
            
            # Use force_rebuild setting from checkbox
            stats = indexer.build_index(force_rebuild=force_rebuild)
            
            self.log_console("\n" + "="*60)
            self.log_console(f"✓ FAISS INDEX {action_word.upper()}!")
            if 'vectors_added' in stats and stats['vectors_added'] > 0:
                self.log_console(f"  Vectors added: {stats['vectors_added']}")
            self.log_console(f"  Total vectors: {stats['total_vectors']}")
            self.log_console(f"  Unique videos: {stats['unique_videos']}")
            self.log_console(f"  Index file: {FAISS_INDEX_DIR / 'faiss_index.bin'}")
            self.log_console("="*60)
            self.log_console("\n🎉 You can now search your videos!")
            
            self.refresh_progress_stats()
            
            # Show appropriate success message
            if 'vectors_added' in stats and stats['vectors_added'] > 0:
                message = f"Added {stats['vectors_added']} new vectors!\nTotal: {stats['total_vectors']} vectors\n\nYou can now use the search app."
            else:
                message = f"Search index built with {stats['total_vectors']} vectors!\n\nYou can now use the search app."
            
            self.status_var.set(f"Index complete: {stats['total_vectors']} vectors")
            messagebox.showinfo("Success", message)
            
        except Exception as e:
            self.log_console(f"\n❌ Error: {e}")
            self.status_var.set(f"Indexing error: {e}")
            messagebox.showerror("Indexing Error", str(e))
        finally:
            self.run_button.config(state=tk.NORMAL)
            self.embed_button.config(state=tk.NORMAL)
            self.index_button.config(state=tk.NORMAL)
            self.is_running = False
    
    # ==================== VIDEO ID EXTRACTION METHODS ====================
    
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
                    import csv
                    reader = csv.DictReader(f)
                    video_ids = []
                    for row in reader:
                        if 'video_id' in row:
                            video_ids.append(row['video_id'])
                    content = '\n'.join(video_ids)
                else:
                    content = f.read()
            
            self.video_ids_text.delete('1.0', tk.END)
            self.video_ids_text.insert('1.0', content)
            self.video_ids_file_label.config(text=f"Loaded: {Path(file_path).name}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file: {e}")
    
    def clear_video_ids(self):
        """Clear the video IDs text box"""
        self.video_ids_text.delete('1.0', tk.END)
        self.video_ids_file_label.config(text="No file loaded")
        self.video_id_results.delete('1.0', tk.END)
    
    def start_video_id_extraction(self):
        """Start extraction for specified video IDs"""
        content = self.video_ids_text.get('1.0', tk.END).strip()
        if not content:
            messagebox.showwarning("Warning", "Please enter video IDs or load from file")
            return
        
        # Parse video IDs
        video_ids = []
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
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
        
        threading.Thread(target=self.run_video_id_extraction, args=(video_ids,), daemon=True).start()
    
    def run_video_id_extraction(self, video_ids):
        """Run the video ID extraction (in background thread)"""
        try:
            from data_pipeline.scheduler import ExtractionScheduler
            from data_pipeline.caption_extractor import YouTubeCaptionExtractor
            
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
                if scheduler.check_ip_block():
                    self.video_id_results.insert(tk.END, "\n" + "="*60 + "\n")
                    self.video_id_results.insert(tk.END, "🚨 IP BLOCK DETECTED - Stopping extraction\n")
                    self.video_id_results.insert(tk.END, "="*60 + "\n")
                    self.video_id_results.see(tk.END)
                    self.root.after(0, lambda: messagebox.showwarning(
                        "IP Block Detected",
                        "YouTube has blocked your IP.\n\nWait 2-6 hours before trying again,\nor use a different network/VPN."
                    ))
                    break
                
                self.video_id_results.insert(tk.END, f"[{i}/{len(video_ids)}] Processing {video_id}...\n")
                self.video_id_results.see(tk.END)
                
                try:
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
                    
                    if scheduler.check_ip_block(error_msg):
                        self.video_id_results.insert(tk.END, "\n" + "="*60 + "\n")
                        self.video_id_results.insert(tk.END, "🚨 IP BLOCK DETECTED - Stopping extraction\n")
                        self.video_id_results.insert(tk.END, "="*60 + "\n")
                        self.video_id_results.see(tk.END)
                        self.root.after(0, lambda: messagebox.showwarning(
                            "IP Block Detected",
                            "YouTube has blocked your IP.\n\nWait 2-6 hours before trying again,\nor use a different network/VPN."
                        ))
                        break
                
                self.video_id_results.see(tk.END)
                
                # Take breaks
                if scheduler.should_take_break(videos_in_batch) and i < len(video_ids):
                    break_duration = scheduler.get_random_break()
                    self.video_id_results.insert(tk.END, f"\n☕ Taking {break_duration/60:.1f} minute break to avoid bot detection...\n")
                    self.video_id_results.see(tk.END)
                    
                    import time
                    remaining = break_duration
                    while remaining > 0:
                        sleep_time = min(5, remaining)
                        time.sleep(sleep_time)
                        remaining -= sleep_time
                    
                    self.video_id_results.insert(tk.END, f"  ✓ Break complete, resuming...\n\n")
                    self.video_id_results.see(tk.END)
                    videos_in_batch = 0
                
                # Delay between videos
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
            
            # Play auditory alert to notify user of completion
            try:
                # Play system asterisk sound (pleasant chime)
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception as e:
                # Silently fail if sound doesn't work
                pass
            
        except Exception as e:
            self.video_id_results.insert(tk.END, f"\n✗ Error: {str(e)}\n")
            self.video_id_results.see(tk.END)
    
    # ==================== SEARCH HISTORY METHODS ====================
    
    def load_search_history(self):
        """Load search history from JSON file"""
        if not self.search_history_file.exists():
            self.search_history = []
            self.video_sources = {}
            return
        
        try:
            with open(self.search_history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.search_history = data.get('searches', [])
                
                # Rebuild video_sources index for fast lookups
                self.video_sources = {}
                for search in self.search_history:
                    query = search['query']
                    for video_id in search.get('video_ids', []):
                        if video_id not in self.video_sources:
                            self.video_sources[video_id] = []
                        if query not in self.video_sources[video_id]:
                            self.video_sources[video_id].append(query)
                
                print(f"✓ Loaded search history: {len(self.search_history)} searches, {len(self.video_sources)} unique videos")
        except Exception as e:
            print(f"⚠ Could not load search history: {e}")
            self.search_history = []
            self.video_sources = {}
    
    def save_search_history(self):
        """Save search history to JSON file"""
        try:
            data = {
                'searches': self.search_history,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.search_history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠ Could not save search history: {e}")
    
    def record_search(self, query: str, video_ids: List[str]):
        """Record a search in the history"""
        # Add to history
        search_entry = {
            'timestamp': datetime.now().isoformat(),
            'query': query,
            'video_ids': video_ids
        }
        self.search_history.append(search_entry)
        
        # Update video_sources index
        for video_id in video_ids:
            if video_id not in self.video_sources:
                self.video_sources[video_id] = []
            if query not in self.video_sources[video_id]:
                self.video_sources[video_id].append(query)
        
        # Save to file (async to avoid blocking)
        self.save_search_history()
    
    # ==================== TOPIC SEARCH METHODS ====================
    
    def search_videos(self):
        """Search for videos by topic"""
        query = self.search_query_var.get().strip()
        if not query:
            messagebox.showwarning("Warning", "Please enter search keywords")
            return
        
        for item in self.search_tree.get_children():
            self.search_tree.delete(item)
        
        self.selected_videos.clear()
        self.status_var.set("Searching...")
        
        threading.Thread(target=self.run_search, args=(query,), daemon=True).start()

    def _lexical_rerank(self, query: str, results: list) -> list:
        """Re-rank results by fraction of query tokens matched in title + description."""
        import re
        _STOPWORDS = {
            'a', 'an', 'the', 'of', 'to', 'and', 'in', 'for', 'with', 'is', 'are',
            'on', 'at', 'by', 'this', 'that', 'it', 'or', 'be', 'as', 'from',
            'how', 'what', 'which', 'do', 'does', 'your', 'my', 'can', 'will',
            'than', 'up', 'not', 'you', 'we', 'they',
        }
        tokens = set(re.findall(r'[a-z0-9]+', query.lower())) - _STOPWORDS
        if not tokens:
            return results

        def _score(r):
            text = (r.get('title', '') + ' ' + r.get('description', '')).lower()
            return len(tokens & set(re.findall(r'[a-z0-9]+', text))) / len(tokens)

        return sorted(results, key=_score, reverse=True)

    def run_search(self, query):
        """Run the search (in background thread)"""
        try:
            from data_pipeline.caption_extractor import YouTubeCaptionExtractor
            
            max_duration = int(self.search_max_duration_var.get())
            max_results = int(self.search_max_results_var.get())
            region_code = self.search_region_var.get().strip().upper() or 'GB'
            category_id = '27' if self.search_education_only_var.get() else None

            extractor = YouTubeCaptionExtractor(
                api_key=get_youtube_api_key(),
                output_dir='data/captions_output',
                use_proxy=True
            )

            # Get downloaded video IDs to identify duplicates
            self.downloaded_video_ids = set(extractor.get_downloaded_video_ids())

            # Get channel filter
            channel_filter = self.search_channel_filter.get()
            channel_ids = None
            if channel_filter != 'All channels' and channel_filter in self.base_channel_map:
                channel_ids = [self.base_channel_map[channel_filter]]

            # Search with region/category; two-pass is handled inside extractor
            results = extractor.search_videos_by_topic(
                query,
                max_results=max_results,
                channel_ids=channel_ids,
                max_duration=max_duration,
                region_code=region_code,
                video_category_id=category_id
            )

            # Lexical rerank: boost results whose title/description best cover query tokens
            results = self._lexical_rerank(query, results)

            self.search_results = results
            
            # Record this search in history
            video_ids = [r['video_id'] for r in results]
            self.record_search(query, video_ids)
            
            # Count new vs already-extracted vs previously found in searches
            already_extracted = sum(1 for r in results if r['video_id'] in self.downloaded_video_ids)
            previously_found = sum(1 for r in results if r['video_id'] in self.video_sources and len(self.video_sources[r['video_id']]) > 1)
            new_to_searches = len(results) - previously_found
            
            self.root.after(0, self.display_search_results, results)
            self.root.after(0, lambda: self.status_var.set(
                f"Found {len(results)} videos ({new_to_searches} new to searches, {previously_found} from previous searches, {already_extracted} already extracted)"
            ))
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Search Error", str(e)))
            self.root.after(0, lambda: self.status_var.set("Search failed"))
    
    def display_search_results(self, results):
        """Display search results in the tree"""
        hide_extracted = self.hide_extracted_var.get()
        current_query = self.search_query_var.get().strip()
        
        for result in results:
            video_id = result['video_id']
            is_extracted = video_id in self.downloaded_video_ids
            
            # Skip already-extracted videos if hide option is enabled
            if hide_extracted and is_extracted:
                continue
            
            # Use different icon for already-extracted videos
            if is_extracted:
                checkbox = "✓"  # Already extracted - show checkmark
            else:
                checkbox = "☐"  # Not extracted - show empty box
            
            # Get previous searches that found this video (excluding current search)
            previous_searches = []
            if video_id in self.video_sources:
                previous_searches = [q for q in self.video_sources[video_id] if q != current_query]
            
            # Format "Previously Found In" column
            if previous_searches:
                # Show first 2 searches, truncate if needed
                if len(previous_searches) == 1:
                    found_in_text = f"⚠️ {previous_searches[0][:40]}"
                elif len(previous_searches) == 2:
                    found_in_text = f"⚠️ {previous_searches[0][:25]}, {previous_searches[1][:25]}"
                else:
                    found_in_text = f"⚠️ {previous_searches[0][:25]} +{len(previous_searches)-1} more"
            else:
                found_in_text = "✨ NEW"
            
            duration_str = f"{result['duration']//60}m {result['duration']%60}s"
            self.search_tree.insert('', 'end', values=(
                checkbox,
                video_id,
                result['title'][:50],
                result['channel_name'][:18],
                duration_str,
                found_in_text
            ))
    
    def refresh_search_display(self):
        """Refresh the search results display when hide checkbox is toggled"""
        # Clear current display
        for item in self.search_tree.get_children():
            self.search_tree.delete(item)
        
        # Redisplay with current filter settings
        if self.search_results:
            self.display_search_results(self.search_results)
    
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
        
        # Don't allow selection of already-extracted videos
        if video_id in self.downloaded_video_ids:
            return
        
        if video_id in self.selected_videos:
            self.selected_videos.remove(video_id)
            values[0] = "☐"
        else:
            self.selected_videos.add(video_id)
            values[0] = "☑"
        
        self.search_tree.item(item, values=values)
    
    def select_all_search_results(self):
        """Select all search results (excluding already-extracted)"""
        for item in self.search_tree.get_children():
            values = list(self.search_tree.item(item, 'values'))
            video_id = values[1]
            
            # Skip already-extracted videos
            if video_id in self.downloaded_video_ids:
                continue
            
            values[0] = "☑"
            self.selected_videos.add(video_id)
            self.search_tree.item(item, values=values)
    
    def deselect_all_search_results(self):
        """Deselect all search results"""
        for item in self.search_tree.get_children():
            values = list(self.search_tree.item(item, 'values'))
            video_id = values[1]
            
            # Only change checkbox for non-extracted videos
            if video_id not in self.downloaded_video_ids:
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
    
    def append_to_csv(self):
        """Append selected video IDs to an existing CSV file (with duplicate detection)"""
        if not self.selected_videos:
            messagebox.showwarning("Warning", "No videos selected")
            return
        
        # Ask user to select existing CSV file
        file_path = filedialog.askopenfilename(
            title="Select CSV file to append to",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            # Read existing video IDs from CSV to check for duplicates
            existing_ids = set()
            file_exists_and_has_data = False
            
            if Path(file_path).exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    header = next(reader, None)  # Skip header if present
                    for row in reader:
                        if row:  # Skip empty rows
                            existing_ids.add(row[0])  # First column is video_id
                            file_exists_and_has_data = True
            
            # Filter out duplicates from selected videos
            videos_to_append = []
            duplicates = []
            
            for result in self.search_results:
                if result['video_id'] in self.selected_videos:
                    if result['video_id'] in existing_ids:
                        duplicates.append(result['video_id'])
                    else:
                        videos_to_append.append(result)
            
            # If no new videos to append, inform user
            if not videos_to_append:
                if duplicates:
                    messagebox.showinfo(
                        "No New Videos", 
                        f"All {len(duplicates)} selected video(s) already exist in the CSV.\nNo videos were appended."
                    )
                else:
                    messagebox.showwarning("Warning", "No videos to append")
                return
            
            # Append new videos to CSV
            with open(file_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Write header if file is empty or newly created
                if not file_exists_and_has_data:
                    writer.writerow(["video_id", "title", "channel", "duration"])
                
                # Write new video data
                for result in videos_to_append:
                    writer.writerow([
                        result['video_id'],
                        result['title'],
                        result['channel_name'],
                        result['duration']
                    ])
            
            # Success message with details
            message = f"Successfully appended {len(videos_to_append)} video(s) to {Path(file_path).name}"
            if duplicates:
                message += f"\n\nSkipped {len(duplicates)} duplicate(s)"
            
            messagebox.showinfo("Success", message)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to append to CSV: {e}")


def main():
    """Main entry point"""
    root = tk.Tk()
    app = PipelineGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
