"""
GUI Frontend for YouTube Caption Extraction Pipeline
Provides user-friendly interface for extracting video captions
"""

import os
import csv
import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
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
    """Main GUI application for caption extraction"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Caption Extraction Pipeline")
        self.root.geometry("1200x700")
        
        # Variables
        self.num_videos_var = tk.StringVar(value="50")
        self.max_duration_var = tk.StringVar(value="1200")
        self.channel_name_var = tk.StringVar(value="numberblocks")
        self.channel_id_var = tk.StringVar()
        self.region_code_var = tk.StringVar(value="GB")
        self.status_var = tk.StringVar(value="Ready")
        
        # Extraction thread
        self.extraction_thread = None
        self.is_running = False
        self._channels_loaded = False
        
        # Setup GUI
        self.setup_ui()
        
        # Load channels asynchronously after GUI appears
        self.root.after(100, self.load_channels)
        
    def setup_ui(self):
        """Create the GUI layout"""
        
        # Configure root grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Create main container with canvas and scrollbar
        container = ttk.Frame(self.root)
        container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)
        
        # Create canvas
        canvas = tk.Canvas(container, bg='white')
        canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Create scrollbar
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Configure canvas
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Create main frame inside canvas
        main_frame = ttk.Frame(canvas, padding="10")
        canvas_frame = canvas.create_window((0, 0), window=main_frame, anchor="nw")
        
        # Configure main frame
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(5, weight=1)
        
        # Bind configure event to update scroll region
        def on_frame_configure(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
        
        def on_canvas_configure(event):
            # Update the width of the frame to match canvas width
            canvas.itemconfig(canvas_frame, width=event.width)
        
        main_frame.bind("<Configure>", on_frame_configure)
        canvas.bind("<Configure>", on_canvas_configure)
        
        # Bind mousewheel for scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        # Store references
        self.canvas = canvas
        self.main_frame = main_frame
        
        # Title
        title_label = ttk.Label(
            main_frame, 
            text="YouTube Caption Extraction Pipeline", 
            font=('Arial', 16, 'bold')
        )
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Input section
        input_frame = ttk.LabelFrame(main_frame, text="Extraction Parameters", padding="10")
        input_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        input_frame.columnconfigure(1, weight=1)
        
        # Number of videos
        ttk.Label(input_frame, text="Number of Videos:").grid(row=0, column=0, sticky=tk.W, pady=5)
        num_videos_entry = ttk.Entry(input_frame, textvariable=self.num_videos_var, width=15)
        num_videos_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(input_frame, text="(How many videos to extract)").grid(row=0, column=2, sticky=tk.W)
        
        # Max duration
        ttk.Label(input_frame, text="Max Video Duration (seconds):").grid(row=1, column=0, sticky=tk.W, pady=5)
        max_duration_entry = ttk.Entry(input_frame, textvariable=self.max_duration_var, width=15)
        max_duration_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(input_frame, text="(Videos longer than this will be skipped)").grid(row=1, column=2, sticky=tk.W)
        
        # Channel name
        ttk.Label(input_frame, text="Channel Name or ID:").grid(row=2, column=0, sticky=tk.W, pady=5)
        channel_combo = ttk.Combobox(input_frame, textvariable=self.channel_name_var, width=30)
        channel_combo.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        self.channel_combo = channel_combo
        ttk.Label(input_frame, text="(Type channel name/ID or select from list)").grid(row=2, column=2, sticky=tk.W)
        
        # Region code
        ttk.Label(input_frame, text="Region Code:").grid(row=3, column=0, sticky=tk.W, pady=5)
        region_entry = ttk.Entry(input_frame, textvariable=self.region_code_var, width=15)
        region_entry.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(input_frame, text="(2-letter country code: GB, US, etc.)").grid(row=3, column=2, sticky=tk.W)
        
        # Button frames - organized in two rows
        button_frame_top = ttk.Frame(main_frame)
        button_frame_top.grid(row=2, column=0, columnspan=3, pady=(5, 0))
        
        button_frame_bottom = ttk.Frame(main_frame)
        button_frame_bottom.grid(row=3, column=0, columnspan=3, pady=(5, 10))
        
        # Top row: Extraction buttons
        ttk.Label(button_frame_top, text="Step 1-2:", font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=(0, 5))
        
        self.run_button = ttk.Button(
            button_frame_top, 
            text="▶ Extract", 
            command=self.start_extraction,
            width=18
        )
        self.run_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(
            button_frame_top, 
            text="⏹ Stop", 
            command=self.stop_extraction,
            width=12,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            button_frame_top, 
            text="🔍 Test IP Block", 
            command=self.run_ip_block_test,
            width=18
        ).pack(side=tk.LEFT, padx=5)
        
        # Bottom row: Utility buttons
        ttk.Button(
            button_frame_bottom, 
            text="🔗 Chunk", 
            command=self.chunk_all_captions,
            width=18
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            button_frame_bottom, 
            text="�🔄 Refresh Results", 
            command=self.refresh_results,
            width=18
        ).pack(side=tk.LEFT, padx=5)
        
        # Status bar
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        status_frame.columnconfigure(1, weight=1)
        
        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT, padx=(0, 5))
        status_label = ttk.Label(status_frame, textvariable=self.status_var, foreground="blue")
        status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Results section
        results_frame = ttk.LabelFrame(main_frame, text="Processing Results", padding="10")
        results_frame.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        # Results table
        self.create_results_table(results_frame)
        
        # Console output
        console_frame = ttk.LabelFrame(main_frame, text="Console Output", padding="10")
        console_frame.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))
        console_frame.columnconfigure(0, weight=1)
        
        self.console = scrolledtext.ScrolledText(console_frame, height=8, wrap=tk.WORD)
        self.console.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Processing section with progress indicators
        self.create_processing_section(main_frame)
        
    def create_processing_section(self, parent):
        """Create the processing section with buttons and progress visualization"""
        processing_frame = ttk.LabelFrame(parent, text="Processing & Progress", padding="10")
        processing_frame.grid(row=7, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        processing_frame.columnconfigure(1, weight=1)
        
        # Buttons frame - left side
        buttons_frame = ttk.Frame(processing_frame)
        buttons_frame.grid(row=0, column=0, sticky=(tk.N, tk.W), padx=(0, 20))
        
        ttk.Label(buttons_frame, text="Step 3-4:", font=('Arial', 9, 'bold')).pack(anchor=tk.W, pady=(0, 10))
        
        self.embed_button = ttk.Button(
            buttons_frame, 
            text="🧠 Generate Embeddings", 
            command=self.start_embedding,
            width=22
        )
        self.embed_button.pack(pady=5)
        
        self.index_button = ttk.Button(
            buttons_frame, 
            text="📊 Build Search Index", 
            command=self.start_indexing,
            width=22
        )
        self.index_button.pack(pady=5)
        
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
        
    def refresh_progress_stats(self):
        """Refresh and display progress statistics with channel breakdowns"""
        try:
            self.progress_text.config(state=tk.NORMAL)
            self.progress_text.delete('1.0', tk.END)
            
            # Header
            self.progress_text.insert(tk.END, "═" * 42 + "\n", 'header')
            self.progress_text.insert(tk.END, "  PIPELINE PROGRESS STATISTICS\n", 'header')
            self.progress_text.insert(tk.END, "═" * 42 + "\n\n", 'header')
            
            # Get stats
            stats = self.get_pipeline_statistics()
            
            # Display totals
            self.progress_text.insert(tk.END, "📋 TOTALS:\n", 'section')
            self.progress_text.insert(tk.END, "─" * 42 + "\n")
            self.progress_text.insert(tk.END, f"  Extracted:  {stats['totals']['extracted']:>6} videos\n")
            self.progress_text.insert(tk.END, f"  Chunked:    {stats['totals']['chunked']:>6} videos\n")
            self.progress_text.insert(tk.END, f"  Embedded:   {stats['totals']['embedded']:>6} videos\n")
            self.progress_text.insert(tk.END, f"  Indexed:    {stats['totals']['indexed']:>6} videos\n")
            self.progress_text.insert(tk.END, "\n")
            
            # Display by channel - Extracted
            if stats['by_channel']['extracted']:
                self.progress_text.insert(tk.END, "📺 BY CHANNEL - Extracted:\n", 'section')
                self.progress_text.insert(tk.END, "─" * 42 + "\n")
                for channel, count in sorted(stats['by_channel']['extracted'].items(), key=lambda x: x[1], reverse=True):
                    channel_display = channel[:30] + "..." if len(channel) > 30 else channel
                    self.progress_text.insert(tk.END, f"  {channel_display:<33} {count:>6}\n")
                self.progress_text.insert(tk.END, "\n")
            
            # Display by channel - Embedded
            if stats['by_channel']['embedded']:
                self.progress_text.insert(tk.END, "🔢 BY CHANNEL - Embedded:\n", 'section')
                self.progress_text.insert(tk.END, "─" * 42 + "\n")
                for channel, count in sorted(stats['by_channel']['embedded'].items(), key=lambda x: x[1], reverse=True):
                    channel_display = channel[:30] + "..." if len(channel) > 30 else channel
                    self.progress_text.insert(tk.END, f"  {channel_display:<33} {count:>6}\n")
                self.progress_text.insert(tk.END, "\n")
            
            # Display by channel - Indexed
            if stats['by_channel']['indexed']:
                self.progress_text.insert(tk.END, "🔍 BY CHANNEL - Indexed:\n", 'section')
                self.progress_text.insert(tk.END, "─" * 42 + "\n")
                for channel, count in sorted(stats['by_channel']['indexed'].items(), key=lambda x: x[1], reverse=True):
                    channel_display = channel[:30] + "..." if len(channel) > 30 else channel
                    self.progress_text.insert(tk.END, f"  {channel_display:<33} {count:>6}\n")
                self.progress_text.insert(tk.END, "\n")
            
            # Footer
            self.progress_text.insert(tk.END, "─" * 42 + "\n")
            self.progress_text.insert(tk.END, f"Last updated: {datetime.now().strftime('%H:%M:%S')}\n", 'footer')
            
            # Configure tags
            self.progress_text.tag_config('header', font=('Consolas', 9, 'bold'))
            self.progress_text.tag_config('section', font=('Consolas', 9, 'bold'), foreground='#2c3e50')
            self.progress_text.tag_config('footer', font=('Consolas', 8), foreground='#7f8c8d')
            
            self.progress_text.config(state=tk.DISABLED)
            
        except Exception as e:
            self.progress_text.config(state=tk.NORMAL)
            self.progress_text.delete('1.0', tk.END)
            self.progress_text.insert(tk.END, f"Error loading statistics:\n{str(e)}")
            self.progress_text.config(state=tk.DISABLED)
    
    def get_pipeline_statistics(self):
        """Get comprehensive pipeline statistics with channel breakdowns"""
        stats = {
            'totals': {
                'extracted': 0,
                'chunked': 0,
                'embedded': 0,
                'indexed': 0
            },
            'by_channel': {
                'extracted': {},
                'embedded': {},
                'indexed': {}
            }
        }
        
        try:
            # Count extracted videos by channel
            captions_dir = Path('data/captions_output')
            if captions_dir.exists():
                for channel_dir in captions_dir.iterdir():
                    if channel_dir.is_dir():
                        count = sum(1 for _ in channel_dir.glob('*.json'))
                        if count > 0:
                            stats['by_channel']['extracted'][channel_dir.name] = count
                            stats['totals']['extracted'] += count
            
            # Count chunked videos
            chunked_dir = Path('data/chunked_output')
            if chunked_dir.exists():
                stats['totals']['chunked'] = sum(1 for _ in chunked_dir.glob('*_chunked.json'))
            
            # Count embedded videos by channel
            embeddings_dir = Path('data/embeddings_output')
            if embeddings_dir.exists():
                for emb_file in embeddings_dir.glob('*_embeddings.json'):
                    # Get video ID from filename
                    video_id = emb_file.stem.replace('_embeddings', '')
                    # Find which channel this video belongs to
                    channel = self.find_channel_for_video(video_id)
                    if channel:
                        stats['by_channel']['embedded'][channel] = stats['by_channel']['embedded'].get(channel, 0) + 1
                    stats['totals']['embedded'] += 1
            
            # Count indexed videos by channel
            metadata_file = Path('data/faiss_index/faiss_index_metadata.json')
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    metadata_list = data.get('metadata', data)
                    
                    # Track unique videos and their channels
                    video_channels = {}
                    for entry in metadata_list:
                        if isinstance(entry, dict) and 'video_id' in entry:
                            video_id = entry['video_id']
                            if video_id not in video_channels:
                                # Try to get channel from metadata or find it
                                channel = entry.get('channel', entry.get('channel_name'))
                                if not channel:
                                    channel = self.find_channel_for_video(video_id)
                                video_channels[video_id] = channel or 'Unknown'
                    
                    # Count by channel
                    for channel in video_channels.values():
                        stats['by_channel']['indexed'][channel] = stats['by_channel']['indexed'].get(channel, 0) + 1
                    
                    stats['totals']['indexed'] = len(video_channels)
        
        except Exception as e:
            print(f"Error gathering statistics: {e}")
        
        return stats
    
    def find_channel_for_video(self, video_id):
        """Find which channel a video belongs to by checking captions_output and chunked files"""
        try:
            # First try captions_output directory structure
            captions_dir = Path('data/captions_output')
            if captions_dir.exists():
                for channel_dir in captions_dir.iterdir():
                    if channel_dir.is_dir():
                        # Check if this video exists in this channel
                        for json_file in channel_dir.glob('*.json'):
                            if json_file.stem.endswith(f'_{video_id}'):
                                return channel_dir.name
            
            # If not found in captions_output, try to get from chunked file
            chunked_file = Path(f'data/chunked_output/{video_id}_chunked.json')
            if chunked_file.exists():
                with open(chunked_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Try to extract channel from various possible fields
                    if 'channel' in data:
                        return data['channel']
                    elif 'channel_name' in data:
                        return data['channel_name']
                    # If we have the title, we might be able to infer channel from common patterns
                    # For now, return the video as found but channel unknown
                    return 'Other'  # At least we found it
            
            return 'Unknown'
        except Exception as e:
            return 'Unknown'
    
    def create_results_table(self, parent):
        """Create the results table with scrollbar"""
        
        # Create treeview with scrollbar
        tree_frame = ttk.Frame(parent)
        tree_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        
        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")
        
        # Configure style for single-line rows
        style = ttk.Style()
        style.configure("Treeview", rowheight=25)
        
        # Treeview
        self.results_tree = ttk.Treeview(
            tree_frame,
            columns=("video_id", "title", "duration", "extraction", "chunking"),
            show="headings",
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set,
            height=10  # Display 10 rows
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
        
    def load_channels(self):
        """Load channels from channels.csv"""
        if self._channels_loaded:
            return
        
        try:
            channels_file = Path('channels.csv')
            if channels_file.exists():
                with open(channels_file, 'r') as f:
                    reader = csv.DictReader(f)
                    channels = list(reader)
                    
                channel_names = [ch['channel_name'] for ch in channels]
                self.channel_combo['values'] = channel_names
                
                # Store channel mapping
                self.channel_map = {ch['channel_name']: ch['channel_id'] for ch in channels}
                
                if channel_names:
                    self.channel_name_var.set(channel_names[0])
                    
                self._channels_loaded = True
                self.log_console(f"Loaded {len(channel_names)} channel(s)")
            else:
                self.log_console("Warning: channels.csv not found")
                messagebox.showwarning("Warning", "channels.csv not found. Please create this file.")
        except Exception as e:
            self.log_console(f"Error loading channels: {e}")
            messagebox.showerror("Error", f"Failed to load channels: {e}")
    
    def log_console(self, message):
        """Add message to console output - keeps only recent 500 lines for performance"""
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
    
    def start_extraction(self):
        """Start the extraction process in a separate thread"""
        if not self.validate_inputs():
            return
        
        if self.is_running:
            messagebox.showinfo("Info", "Extraction is already running")
            return
        
        # Disable run button, enable stop button
        self.run_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.is_running = True
        
        # Clear console
        self.console.delete(1.0, tk.END)
        
        # Start extraction thread
        self.extraction_thread = threading.Thread(target=self.run_extraction, daemon=True)
        self.extraction_thread.start()
    
    def stop_extraction(self):
        """Stop the extraction process"""
        self.is_running = False
        self.status_var.set("Stopping...")
        self.log_console("Stop requested by user")
    
    def chunk_all_captions(self):
        """Process all caption files that don't have chunked versions yet"""
        if self.is_running:
            messagebox.showinfo("Info", "Please wait for current operation to finish")
            return
        
        # Count caption and chunked files
        from pathlib import Path
        captions_dir = Path('data/captions_output')
        chunked_dir = Path('data/chunked_output')
        
        # Find all caption JSON files
        caption_files = list(captions_dir.glob('**/*.json'))
        
        # Find existing chunked files (extract video IDs)
        chunked_ids = set()
        if chunked_dir.exists():
            for f in chunked_dir.glob('*_chunked.json'):
                video_id = f.stem.replace('_chunked', '')
                chunked_ids.add(video_id)
        
        # Find caption files that need chunking
        files_to_chunk = []
        for caption_file in caption_files:
            # Extract video_id from filename (last part before .json)
            video_id = caption_file.stem.split('_')[-1]
            if video_id not in chunked_ids:
                files_to_chunk.append(caption_file)
        
        if not files_to_chunk:
            messagebox.showinfo("Info", f"All {len(caption_files)} caption files are already chunked!")
            return
        
        # Confirm with user
        response = messagebox.askyesno(
            "Chunk",
            f"Found {len(caption_files)} total caption files.\n"
            f"{len(chunked_ids)} already chunked.\n"
            f"{len(files_to_chunk)} need chunking.\n\n"
            f"Process these {len(files_to_chunk)} files?"
        )
        
        if not response:
            return
        
        # Disable buttons
        self.run_button.config(state=tk.DISABLED)
        self.embed_button.config(state=tk.DISABLED)
        self.index_button.config(state=tk.DISABLED)
        self.is_running = True
        
        # Clear console
        self.console.delete(1.0, tk.END)
        
        # Start chunking thread
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
                    
                    # Process transcript
                    result = chunker.process_transcript(caption_file)
                    
                    if result:
                        # Save chunked output
                        output_file = Path('data/chunked_output') / f"{result['video_id']}_chunked.json"
                        with open(output_file, 'w', encoding='utf-8') as f:
                            import json
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
    
    def run_extraction(self):
        """Run the extraction process (runs in separate thread)"""
        try:
            # Get parameters
            num_videos = int(self.num_videos_var.get())
            max_duration = int(self.max_duration_var.get())
            channel_name = self.channel_name_var.get().strip()
            region_code = self.region_code_var.get().strip().upper()
            
            # Check if it's a known channel or custom input
            if channel_name in self.channel_map:
                channel_id = self.channel_map[channel_name]
            else:
                # Assume user entered a channel ID directly
                channel_id = channel_name
                # Use a sanitized version for directory name
                channel_name = channel_name.replace('UC', '').replace('UU', '')[:20]
            
            self.status_var.set("Initializing...")
            self.log_console("="*60)
            self.log_console("Starting YouTube Caption Extraction (Conservative Mode)")
            self.log_console(f"Channel: {channel_name}")
            self.log_console(f"Target Videos: {num_videos}")
            self.log_console(f"Max Duration: {max_duration}s")
            self.log_console(f"Region Code: {region_code}")
            self.log_console("="*60)
            self.log_console("Bot Avoidance: 5 videos/batch, 8-15s delays, 30-60s breaks")
            self.log_console("="*60)
            
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
                min_break_duration=30.0,  # 30 seconds
                max_break_duration=60.0,  # 1 minute
                notification_email=None  # GUI handles notifications
            )
            
            # Create custom extractor that reports progress
            extractor = YouTubeCaptionExtractor(
                api_key=get_youtube_api_key(),
                output_dir='data/captions_output',
                cache_file='data/api_cache.json',
                delay_between_videos=0.5,  # Minimal, scheduler handles timing
                random_delay_range=(0.5, 1.0),
                videos_per_batch=999,  # Disabled, scheduler handles this
                break_duration_range=(0, 0),
                max_video_duration=max_duration
            )
            
            # Get downloaded videos to skip
            downloaded_ids = extractor.get_downloaded_video_ids()
            self.log_console(f"Found {len(downloaded_ids)} already-downloaded videos (will skip)")
            
            # Get videos
            self.status_var.set("Fetching videos from channel...")
            self.log_console("\nFetching videos from channel...")
            videos = extractor.get_channel_videos(channel_id, max_results=500)
            
            if not self.is_running:
                self.finalize_extraction("Stopped by user")
                return
            
            # Filter out downloaded videos
            videos = [v for v in videos if v['video_id'] not in downloaded_ids]
            self.log_console(f"Found {len(videos)} new videos to process")
            
            # Process videos with scheduler
            extracted_count = 0
            skipped_count = 0
            extracted_videos = []  # Track successfully extracted videos for chunking
            videos_in_batch = 0
            
            for video in videos:
                if not self.is_running or extracted_count >= num_videos:
                    break
                
                # Check for IP block
                if scheduler.check_ip_block():
                    self.log_console("\n" + "="*60)
                    self.log_console("🚨 IP BLOCK DETECTED - Stopping extraction")
                    self.log_console("="*60)
                    messagebox.showwarning(
                        "IP Block Detected",
                        "YouTube has blocked your IP.\n\n"
                        "Wait 2-6 hours before trying again,\n"
                        "or use a different network/VPN."
                    )
                    break
                
                video_id = video['video_id']
                title = video['title']
                duration = video.get('duration', 0)
                
                self.status_var.set(f"Extracting {extracted_count + 1}/{num_videos}: {title[:50]}...")
                self.log_console(f"\n[{extracted_count + 1}/{num_videos}] {title[:60]}...")
                self.log_console(f"  Duration: {duration}s")
                
                # Extract captions
                try:
                    caption_data = extractor.extract_caption(video_id, verbose=False)
                    
                    if caption_data is None:
                        self.log_console(f"  ⏭️  Skipped: No captions available")
                        skipped_count += 1
                        self.add_result_row(video_id, title, duration, "Skipped (no captions)", "N/A")
                        continue
                    
                    # Save captions
                    extractor.save_caption(video, caption_data, channel_name)
                    
                    self.log_console(f"  ✓ Extracted and saved")
                    extracted_count += 1
                    videos_in_batch += 1
                    
                    # Record in scheduler
                    scheduler.record_extraction(channel_id, video_id, True)
                    
                    # Find the saved JSON file
                    channel_dir = Path('data/captions_output') / channel_name.replace(' ', '_')
                    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()[:100]
                    json_path = channel_dir / f"{safe_title}_{video_id}.json"
                    
                    self.add_result_row(video_id, title, duration, "✓ Extracted", "Pending")
                    extracted_videos.append({'video_id': video_id, 'title': title, 'json_path': json_path})
                    
                except Exception as e:
                    error_msg = str(e)
                    self.log_console(f"  ✗ Error: {error_msg[:100]}")
                    
                    # Check for IP block
                    if scheduler.check_ip_block(error_msg):
                        self.log_console("\n" + "="*60)
                        self.log_console("🚨 IP BLOCK DETECTED - Stopping extraction")
                        self.log_console("="*60)
                        messagebox.showwarning(
                            "IP Block Detected",
                            "YouTube has blocked your IP.\n\n"
                            "Wait 2-6 hours before trying again,\n"
                            "or use a different network/VPN."
                        )
                        break
                
                # Should we take a break?
                if scheduler.should_take_break(videos_in_batch) and extracted_count < num_videos:
                    break_duration = scheduler.get_random_break()
                    self.log_console(f"\n☕ Taking {break_duration/60:.1f} minute break to avoid bot detection...")
                    self.status_var.set(f"Break time ({break_duration/60:.1f} min) - Bot avoidance")
                    
                    # Wait with periodic checks for stop signal
                    import time
                    remaining = break_duration
                    while remaining > 0 and self.is_running:
                        sleep_time = min(5, remaining)
                        time.sleep(sleep_time)
                        remaining -= sleep_time
                    
                    if self.is_running:
                        self.log_console(f"  ✓ Break complete, resuming...")
                    videos_in_batch = 0
                
                # Delay between videos (if not taking a break and still running)
                elif extracted_count < num_videos and self.is_running:
                    import time
                    delay = scheduler.get_random_delay()
                    self.log_console(f"  ⏱ Waiting {delay:.1f}s...")
                    time.sleep(delay)
            
            # Chunk extracted transcripts
            if extracted_videos and self.is_running:
                self.log_console("\n" + "="*60)
                self.log_console("Starting Chunking Process")
                self.log_console("="*60)
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
                        # Chunk the transcript
                        result = chunker.process_transcript(video_info['json_path'])
                        
                        if result:
                            # Save chunked output
                            output_file = Path('data/chunked_output') / f"{result['video_id']}_chunked.json"
                            with open(output_file, 'w', encoding='utf-8') as f:
                                import json
                                json.dump(result, f, indent=2, ensure_ascii=False)
                            
                            self.log_console(f"  ✓ Chunked: {output_file.name}")
                            self.update_chunking_status(video_id, "✓ Chunked")
                        else:
                            self.log_console(f"  ⚠️  Failed to chunk")
                            self.update_chunking_status(video_id, "✗ Failed")
                    except Exception as e:
                        self.log_console(f"  ✗ Chunking error: {e}")
                        self.update_chunking_status(video_id, f"✗ Error")
            
            # Summary
            self.log_console("\n" + "="*60)
            self.log_console("✓ Extraction Complete!")
            self.log_console(f"  Extracted: {extracted_count} videos")
            self.log_console(f"  Skipped: {skipped_count} videos")
            self.log_console("="*60)
            
            # Update progress display
            self.root.after(0, self.refresh_progress_stats)
            
            self.finalize_extraction(f"Complete! Extracted {extracted_count} videos")
            
        except Exception as e:
            self.log_console(f"\n❌ Error: {e}")
            self.status_var.set(f"Error: {e}")
            messagebox.showerror("Extraction Error", str(e))
            self.finalize_extraction(f"Error: {e}")
    
    def add_result_row(self, video_id, title, duration, extraction_status, chunking_status="Pending"):
        """Add a row to the results table (thread-safe) - keeps only recent entries"""
        def _add():
            # Limit table to 100 most recent entries for performance
            MAX_VISIBLE_RESULTS = 100
            children = self.results_tree.get_children()
            if len(children) >= MAX_VISIBLE_RESULTS:
                # Remove oldest entry
                self.results_tree.delete(children[0])
            
            # Format duration for display
            duration_display = str(int(duration)) if duration else "0"
            
            # Store item ID for later updates
            item_id = self.results_tree.insert(
                "", 
                tk.END, 
                values=(video_id, title, duration_display, extraction_status, chunking_status),
                tags=(video_id,)
            )
        self.root.after(0, _add)
    
    def update_chunking_status(self, video_id, chunking_status):
        """Update chunking status for a specific video (thread-safe)"""
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
            self.run_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.is_running = False
        self.root.after(0, _finalize)
    
    def refresh_results(self):
        """Refresh the results table from existing files"""
        # Clear current results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        self.log_console("Refreshing results from existing files...")
        
        try:
            # Check chunked output directory
            chunked_dir = Path('data/chunked_output')
            if not chunked_dir.exists():
                self.log_console("No chunked_output directory found")
                return
            
            # Get all chunked files
            chunked_files = list(chunked_dir.glob('*_chunked.json'))
            self.log_console(f"Found {len(chunked_files)} processed videos")
            
            # Load video details - just show what we have
            for file in sorted(chunked_files)[:100]:  # Limit to 100 for display
                video_id = file.stem.replace('_chunked', '')
                
                # Try to get title from chunked file
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
                    self.results_tree.insert(
                        "", 
                        tk.END, 
                        values=(video_id, "Unknown", "N/A", "Error loading", "Unknown")
                    )
            
            self.status_var.set(f"Loaded {len(chunked_files)} existing results")
            self.log_console("Results refreshed")
            
            # Update progress display
            self.refresh_progress_stats()
            
        except Exception as e:
            self.log_console(f"Error refreshing results: {e}")
            messagebox.showerror("Error", f"Failed to refresh results: {e}")
    
    def run_ip_block_test(self):
        """Run IP block test in a separate thread"""
        if self.is_running:
            messagebox.showinfo("Info", "Please wait for current operation to finish")
            return
        
        # Clear console
        self.console.delete(1.0, tk.END)
        self.log_console("Starting IP block test...")
        self.status_var.set("Running IP block test...")
        
        # Run in separate thread
        def _run_test():
            try:
                import test_ip_block
                
                # Redirect stdout to capture test output
                import io
                import sys
                old_stdout = sys.stdout
                sys.stdout = io.StringIO()
                
                # Run the test
                test_ip_block.main()
                
                # Get output
                output = sys.stdout.getvalue()
                sys.stdout = old_stdout
                
                # Display output in console
                self.root.after(0, lambda: self.console.insert(tk.END, output))
                self.root.after(0, lambda: self.console.see(tk.END))
                self.root.after(0, lambda: self.status_var.set("IP block test completed"))
                
            except Exception as e:
                sys.stdout = old_stdout
                error_msg = f"Error running IP block test: {e}"
                self.root.after(0, lambda: self.log_console(error_msg))
                self.root.after(0, lambda: self.status_var.set("IP block test failed"))
        
        test_thread = threading.Thread(target=_run_test, daemon=True)
        test_thread.start()
    
    def start_embedding(self):
        """Start the embedding generation process"""
        if self.is_running:
            messagebox.showinfo("Info", "Please wait for current operation to finish")
            return
        
        # Check if there are chunked files to process
        chunked_dir = Path('data/chunked_output')
        if not chunked_dir.exists() or not list(chunked_dir.glob('*_chunked.json')):
            messagebox.showwarning("No Data", "No chunked transcripts found. Please run extraction first.")
            return
        
        # Confirm with user
        chunked_files = list(chunked_dir.glob('*_chunked.json'))
        response = messagebox.askyesno(
            "Generate Embeddings",
            f"Found {len(chunked_files)} chunked files.\n\nThis will use OpenAI API (costs money).\n\nContinue?"
        )
        
        if not response:
            return
        
        # Disable buttons
        self.run_button.config(state=tk.DISABLED)
        self.embed_button.config(state=tk.DISABLED)
        self.index_button.config(state=tk.DISABLED)
        self.is_running = True
        
        # Clear console
        self.console.delete(1.0, tk.END)
        
        # Start embedding thread
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
            
            # Process all chunks
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
            
            # Update progress display
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
        
        # Check if there are embeddings to index
        embeddings_dir = Path('data/embeddings_output')
        if not embeddings_dir.exists() or not list(embeddings_dir.glob('*.json')):
            messagebox.showwarning("No Data", "No embeddings found. Please generate embeddings first.")
            return
        
        # Confirm with user
        embedding_files = list(embeddings_dir.glob('*.json'))
        response = messagebox.askyesno(
            "Build Search Index",
            f"Found {len(embedding_files)} embedding files.\n\nBuild FAISS search index?\n\nThis may take a few minutes."
        )
        
        if not response:
            return
        
        # Disable buttons
        self.run_button.config(state=tk.DISABLED)
        self.embed_button.config(state=tk.DISABLED)
        self.index_button.config(state=tk.DISABLED)
        self.is_running = True
        
        # Clear console
        self.console.delete(1.0, tk.END)
        
        # Start indexing thread
        threading.Thread(target=self.run_indexing, daemon=True).start()
    
    def run_indexing(self):
        """Run the FAISS index building process"""
        try:
            from shared.config import EMBEDDING_DIMENSIONS, EMBEDDINGS_DIR, FAISS_INDEX_DIR
            from data_pipeline.indexer import FAISSIndexBuilder
            
            self.status_var.set("Building FAISS index...")
            self.log_console("="*60)
            self.log_console("BUILDING FAISS SEARCH INDEX")
            self.log_console("="*60)
            self.log_console(f"Dimension: {EMBEDDING_DIMENSIONS}")
            
            indexer = FAISSIndexBuilder(
                embeddings_dir=str(EMBEDDINGS_DIR),
                output_dir=str(FAISS_INDEX_DIR),
                dimension=EMBEDDING_DIMENSIONS
            )
            
            # Build index
            stats = indexer.build_index()
            
            self.log_console("\n" + "="*60)
            self.log_console("✓ FAISS INDEX BUILT!")
            self.log_console(f"  Total vectors: {stats['total_vectors']}")
            self.log_console(f"  Unique videos: {stats['unique_videos']}")
            self.log_console(f"  Index file: {FAISS_INDEX_DIR / 'faiss_index.index'}")
            self.log_console("="*60)
            self.log_console("\n🎉 You can now search your videos!")
            
            # Update progress display
            self.refresh_progress_stats()
            
            self.status_var.set(f"Index complete: {stats['total_vectors']} vectors")
            messagebox.showinfo("Success", f"Search index built with {stats['total_vectors']} vectors!\n\nYou can now use the search app.")
            
        except Exception as e:
            self.log_console(f"\n❌ Error: {e}")
            self.status_var.set(f"Indexing error: {e}")
            messagebox.showerror("Indexing Error", str(e))
        finally:
            self.run_button.config(state=tk.NORMAL)
            self.embed_button.config(state=tk.NORMAL)
            self.index_button.config(state=tk.NORMAL)
            self.is_running = False


def main():
    """Main entry point"""
    root = tk.Tk()
    app = PipelineGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

