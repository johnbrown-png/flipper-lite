# GUI Pipeline Architecture

## Component Structure

```
gui_pipeline.py
│
├── PipelineGUI (Main GUI Class)
│   │
│   ├── __init__(root)
│   │   ├── Initialize tkinter root window
│   │   ├── Setup variables (StringVars for inputs)
│   │   ├── Create UI components
│   │   └── Load channels from CSV
│   │
│   ├── UI Components
│   │   ├── setup_ui()
│   │   │   ├── Title Label
│   │   │   ├── Input Frame
│   │   │   │   ├── Number of Videos Entry
│   │   │   │   ├── Max Duration Entry
│   │   │   │   └── Channel Combobox
│   │   │   ├── Button Frame
│   │   │   │   ├── Run Button
│   │   │   │   ├── Stop Button
│   │   │   │   └── Refresh Button
│   │   │   ├── Status Bar
│   │   │   ├── Results Table (Treeview)
│   │   │   └── Console Output (ScrolledText)
│   │   │
│   │   └── create_results_table(parent)
│   │       ├── Treeview with 5 columns
│   │       ├── Vertical Scrollbar
│   │       └── Horizontal Scrollbar
│   │
│   ├── Data Management
│   │   ├── load_channels()
│   │   │   └── Read channels.csv → Populate combobox
│   │   │
│   │   ├── validate_inputs()
│   │   │   ├── Check number of videos > 0
│   │   │   ├── Check duration > 0
│   │   │   ├── Check channel selected
│   │   │   └── Check API key exists
│   │   │
│   │   └── add_result_row(video_id, title, duration, tags, status)
│   │       └── Thread-safe insert into Treeview
│   │
│   ├── Extraction Control
│   │   ├── start_extraction()
│   │   │   ├── Validate inputs
│   │   │   ├── Disable run button
│   │   │   ├── Enable stop button
│   │   │   └── Start extraction thread
│   │   │
│   │   ├── run_extraction() [RUNS IN SEPARATE THREAD]
│   │   │   ├── Get parameters
│   │   │   ├── Create EnhancedCaptionExtractor
│   │   │   ├── Fetch videos from channel
│   │   │   ├── For each video:
│   │   │   │   ├── Check if should stop
│   │   │   │   ├── Get video duration
│   │   │   │   ├── Filter by duration
│   │   │   │   ├── Extract captions
│   │   │   │   ├── Save to files
│   │   │   │   └── Update results table
│   │   │   └── Display summary
│   │   │
│   │   ├── stop_extraction()
│   │   │   └── Set is_running = False
│   │   │
│   │   └── finalize_extraction(message)
│   │       ├── Update status
│   │       ├── Re-enable run button
│   │       └── Disable stop button
│   │
│   ├── Results Management
│   │   └── refresh_results()
│   │       ├── Clear results table
│   │       ├── Scan chunked_output/ directory
│   │       ├── For each chunked file:
│   │       │   ├── Extract video_id
│   │       │   ├── Query YouTube API
│   │       │   ├── Get title, duration, tags
│   │       │   └── Add to results table
│   │       └── Update status
│   │
│   └── Logging
│       └── log_console(message)
│           ├── Add timestamp
│           ├── Insert to console widget
│           └── Auto-scroll to end
│
└── main()
    ├── Create Tk root window
    ├── Initialize PipelineGUI
    └── Start mainloop
```

## Data Flow

```
User Input → Validation → Extraction Thread → API Calls → Results
    ↓            ↓              ↓                  ↓          ↓
GUI Fields   Check Values   Background      YouTube API   Table
                               Process       Transcript    Update
                                                API
```

## Thread Architecture

```
Main Thread (GUI)                Background Thread (Extraction)
─────────────────               ──────────────────────────────
┌─────────────────┐            ┌──────────────────────────┐
│  Tkinter Event  │            │  run_extraction()        │
│      Loop       │            │                          │
│                 │            │  1. Get parameters       │
│  - Handle UI    │            │  2. Create extractor     │
│  - Update table │◄───────────┤  3. Fetch videos         │
│  - Show console │   Thread   │  4. Process each video   │
│  - Button clicks│   Safe     │  5. Extract captions     │
│                 │   Updates  │  6. Save files           │
│  Never blocks!  │            │  7. Update UI (via root) │
└─────────────────┘            │                          │
                               │  Can be stopped anytime  │
                               └──────────────────────────┘
```

## File Integration

```
┌──────────────────────────────────────────────────────┐
│                    gui_pipeline.py                    │
└───────────────────┬──────────────────────────────────┘
                    │
        ┌───────────┼───────────┬──────────────┐
        │           │           │              │
        ▼           ▼           ▼              ▼
┌───────────┐ ┌──────────┐ ┌─────────┐ ┌────────────┐
│channels.csv│ │   .env   │ │extract_ │ │captions_   │
│            │ │          │ │addition │ │output/     │
│Channel IDs │ │API Key   │ │al_videos│ │            │
└───────────┘ └──────────┘ │.py      │ │JSON & TXT  │
                            │         │ │files       │
                            │Extractor│ └────────────┘
                            └─────────┘
```

## Error Handling Flow

```
User Action
    │
    ├─► Validation Error
    │   └─► Show messagebox
    │       Stop execution
    │
    ├─► API Error
    │   └─► Log to console
    │       Continue with next video
    │
    ├─► No Captions
    │   └─► Log to console
    │       Mark as skipped
    │       Continue
    │
    └─► Duration Filter
        └─► Log to console
            Mark as skipped
            Continue
```

## State Management

```
GUI State Variables:
────────────────────
• num_videos_var      (StringVar) → User input for video count
• max_duration_var    (StringVar) → User input for duration filter
• channel_name_var    (StringVar) → Selected channel name
• channel_id_var      (StringVar) → Corresponding channel ID
• status_var          (StringVar) → Status bar message
• is_running          (bool)      → Extraction in progress flag
• extraction_thread   (Thread)    → Background worker thread

Widget States:
──────────────
• run_button          → Disabled during extraction
• stop_button         → Enabled during extraction
• results_tree        → Always responsive
• console             → Auto-scrolling, read-only
```

## UI Update Pattern

All UI updates from background thread use this pattern:

```python
def background_task():
    # Do work in background thread
    result = process_data()
    
    # Update UI safely
    def update_ui():
        self.status_var.set("Done!")
        self.results_tree.insert("", tk.END, values=result)
    
    # Schedule on main thread
    self.root.after(0, update_ui)
```

## Execution Flow Example

```
1. User clicks "Run Extraction"
   ↓
2. validate_inputs() checks all fields
   ↓
3. start_extraction() creates background thread
   ↓
4. run_extraction() starts in background
   ├─► Fetch channel videos
   ├─► For each video:
   │   ├─► Check duration
   │   ├─► Extract captions
   │   ├─► Save files
   │   └─► Update table (thread-safe)
   └─► Show summary
   ↓
5. finalize_extraction() re-enables buttons
   ↓
6. User can click "Refresh Results"
   ↓
7. refresh_results() loads existing files
   └─► Query API for each video
       └─► Update table with metadata
```

## Key Features Implementation

### Real-time Progress
```
Console Output (ScrolledText)
├─► log_console() adds timestamped messages
├─► Auto-scrolls to latest message
└─► Updated from extraction thread
```

### Results Table
```
Treeview Widget
├─► 5 columns (video_id, title, duration, tags, status)
├─► Sortable columns
├─► Horizontal & vertical scrolling
└─► Thread-safe updates via root.after()
```

### Stop Control
```
is_running flag
├─► Checked in extraction loop
├─► Graceful shutdown
└─► Current video completes
```

### Channel Management
```
channels.csv → load_channels()
├─► Parse CSV file
├─► Create channel_map dictionary
├─► Populate combobox
└─► Ready for selection
```

This architecture ensures a responsive UI while performing long-running extraction tasks!
