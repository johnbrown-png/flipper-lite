# GUI Workflow Diagram

## Complete User Journey

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER STARTS HERE                             │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │  Launch GUI            │
                    │  (3 methods available) │
                    └────────┬───────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ launch_gui.py│    │launch_gui.bat│    │gui_pipeline.py│
│              │    │              │    │              │
│ •Validates   │    │ •Quick start │    │ •Direct run  │
│ •Checks deps │    │ •Windows     │    │              │
│ •Helpful msgs│    │              │    │              │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                    │
       └───────────────────┴────────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │   GUI Window Opens     │
              │   (1200x700 pixels)    │
              └────────┬───────────────┘
                       │
                       ▼
              ┌────────────────────────┐
              │  User Sees Interface:  │
              │                        │
              │  • Input Parameters    │
              │  • Buttons             │
              │  • Empty Results Table │
              │  • Console Output      │
              └────────┬───────────────┘
                       │
                       ▼
         ┌─────────────────────────────┐
         │ User Action?                │
         └─┬───────────────────────────┘
           │
    ┌──────┴──────┬──────────────┬─────────────┐
    │             │              │             │
    ▼             ▼              ▼             ▼
Configure     Run Extract  Refresh Results  Stop
Parameters                                 (during run)
```

## Detailed Workflow Branches

### Branch 1: Configure Parameters

```
Configure Parameters
         │
         ├─► Number of Videos
         │   └─► Enter value (e.g., 50)
         │
         ├─► Max Duration
         │   └─► Enter seconds (e.g., 600)
         │
         └─► Channel Selection
             └─► Choose from dropdown
                 └─► Loaded from channels.csv
```

### Branch 2: Run Extraction

```
Click "Run Extraction"
         │
         ▼
    Validation
         │
    ┌────┴────┐
    │         │
   Pass      Fail
    │         │
    │         └─► Show Error Dialog
    │             └─► Return to GUI
    │
    ▼
Disable Run Button
Enable Stop Button
    │
    ▼
Create Background Thread
    │
    ▼
┌───────────────────────────────────────────────┐
│        Background Thread Execution            │
├───────────────────────────────────────────────┤
│                                               │
│  1. Initialize EnhancedCaptionExtractor       │
│           │                                   │
│           ▼                                   │
│  2. Fetch Videos from YouTube Channel         │
│           │                                   │
│           ▼                                   │
│  3. For Each Video:                           │
│     ┌─────────────────────┐                  │
│     │ Check if Running?   │                  │
│     └──┬──────────────────┘                  │
│        │                                      │
│       Yes                                     │
│        │                                      │
│        ▼                                      │
│     Get Video Duration                        │
│        │                                      │
│        ▼                                      │
│     ┌────────────────────┐                   │
│     │ Duration OK?       │                   │
│     └──┬──────────┬──────┘                   │
│        │          │                           │
│       Yes        No                           │
│        │          │                           │
│        │          └─► Skip (add to table)    │
│        │                                      │
│        ▼                                      │
│     Extract Captions                          │
│        │                                      │
│        ▼                                      │
│     ┌────────────────────┐                   │
│     │ Captions Found?    │                   │
│     └──┬──────────┬──────┘                   │
│        │          │                           │
│       Yes        No                           │
│        │          │                           │
│        │          └─► Skip (add to table)    │
│        │                                      │
│        ▼                                      │
│     Save to Files                             │
│        │                                      │
│        ├─► *.json (with timestamps)          │
│        └─► *.txt (formatted text)            │
│        │                                      │
│        ▼                                      │
│     Update Results Table                      │
│     (thread-safe via root.after)              │
│        │                                      │
│        ▼                                      │
│     Log to Console                            │
│        │                                      │
│        └─► Next Video ◄───┘                  │
│                                               │
│  4. All Videos Processed or Stopped           │
│           │                                   │
│           ▼                                   │
│  5. Show Summary                              │
│           │                                   │
│           ▼                                   │
│  6. Re-enable Buttons                         │
│                                               │
└───────────────────────────────────────────────┘
         │
         ▼
    Extraction Complete
         │
         ▼
    User Reviews Results
```

### Branch 3: Refresh Results

```
Click "Refresh Results"
         │
         ▼
Clear Results Table
         │
         ▼
Scan chunked_output/ Directory
         │
         ▼
For Each *_chunked.json File:
    │
    ├─► Extract video_id from filename
    │
    ├─► Query YouTube API
    │       └─► Get video details
    │           ├─► Title
    │           ├─► Duration
    │           └─► Tags
    │
    └─► Add Row to Results Table
            └─► Mark as "Existing"
         │
         ▼
Display Count in Status Bar
         │
         ▼
User Can View All Previously
Extracted Videos
```

### Branch 4: Stop Extraction

```
Click "Stop"
    │
    ▼
Set is_running = False
    │
    ▼
Background Thread Checks Flag
    │
    ▼
Completes Current Video
    │
    ▼
Exits Loop Gracefully
    │
    ▼
Shows "Stopped by user" Message
    │
    ▼
Re-enables Run Button
Disables Stop Button
```

## Data Flow Diagram

```
┌──────────────┐
│  User Input  │
│              │
│ • Num Videos │
│ • Max Dur    │
│ • Channel    │
└──────┬───────┘
       │
       ▼
┌──────────────┐      ┌──────────────┐
│   GUI        │──────│  Validation  │
│  Variables   │      │              │
└──────┬───────┘      └──────────────┘
       │
       ▼
┌──────────────────┐
│ channels.csv     │◄─── Read
│                  │
│ channel_id       │
│ channel_name     │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ YouTube API      │
│                  │
│ • Get videos     │
│ • Get duration   │
│ • Get metadata   │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Transcript API   │
│                  │
│ • Fetch captions │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ EnhancedCaption  │
│ Extractor        │
│                  │
│ • Clean text     │
│ • Add punctuation│
└──────┬───────────┘
       │
       ├───────────────────────────┐
       │                           │
       ▼                           ▼
┌──────────────┐          ┌──────────────┐
│ captions_    │          │ GUI Results  │
│ output/      │          │ Table        │
│              │          │              │
│ *.json       │          │ • Video ID   │
│ *.txt        │          │ • Title      │
└──────────────┘          │ • Duration   │
                          │ • Tags       │
                          │ • Status     │
                          └──────────────┘
```

## State Transition Diagram

```
                    ┌──────────┐
                    │  Ready   │ ◄────┐
                    └────┬─────┘      │
                         │            │
                  Click "Run"         │
                         │            │
                         ▼            │
                 ┌──────────────┐    │
                 │ Validating   │    │
                 └───┬──────────┘    │
                     │               │
              ┌──────┴──────┐        │
              │             │        │
            Valid        Invalid     │
              │             │        │
              │             └────────┤
              │                      │
              ▼                      │
     ┌────────────────┐              │
     │ Initializing   │              │
     └────┬───────────┘              │
          │                          │
          ▼                          │
  ┌───────────────┐                  │
  │  Fetching     │                  │
  │   Videos      │                  │
  └───┬───────────┘                  │
      │                              │
      ▼                              │
  ┌───────────────┐   Click Stop     │
  │  Processing   │───────────┐      │
  │  Video N/M    │           │      │
  └───┬───────────┘           │      │
      │                       │      │
      ▼                       ▼      │
  ┌───────────────┐   ┌─────────────┴┐
  │  Extracting   │   │   Stopping   │
  │   Captions    │   │              │
  └───┬───────────┘   └───────┬──────┘
      │                       │
      ▼                       │
  ┌───────────────┐           │
  │    Saving     │           │
  │    Files      │           │
  └───┬───────────┘           │
      │                       │
      └───────┬───────────────┘
              │
              ▼
      ┌───────────────┐
      │   Complete    │
      └───┬───────────┘
          │
          └───────────────────┘
```

## User Experience Timeline

```
Time  │ User Action         │ GUI State          │ Background Thread
──────┼────────────────────┼───────────────────┼──────────────────
0:00  │ Launch GUI          │ Window Opens       │ Not Started
      │                     │ Load channels.csv  │
0:05  │ Enter parameters    │ Fields Active      │ Not Started
0:10  │ Click "Run"         │ Validation...      │ Not Started
0:11  │ -                   │ Run btn disabled   │ Thread Created
      │                     │ Stop btn enabled   │
0:12  │ -                   │ Status: Fetching   │ API Call: Get videos
0:15  │ -                   │ Status: Found 100  │ API Call: Complete
0:16  │ -                   │ Status: Process 1  │ Get duration
0:17  │ -                   │ Console: Duration  │ Extract captions
0:20  │ -                   │ Console: Saved     │ Save files
      │                     │ Table: +1 row      │
0:21  │ -                   │ Status: Process 2  │ Next video...
0:22  │ User watches        │ Table updates      │ Processing...
...   │ progress            │ Console scrolls    │
5:00  │ -                   │ Status: Complete   │ Thread Ended
      │                     │ Run btn enabled    │
      │                     │ Stop btn disabled  │
5:05  │ Review results      │ Scroll table       │ Not Running
5:10  │ Click "Refresh"     │ Table refreshes    │ API Calls
5:15  │ View updated data   │ All existing shown │ Complete
```

## Integration with Full Pipeline

```
┌─────────────────────────────────────────────────────────┐
│                    GUI Pipeline                         │
│  gui_pipeline.py → User Interface for Extraction        │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ Produces
                     ▼
          ┌──────────────────────┐
          │  captions_output/    │
          │  [channel]/*.json    │
          │  [channel]/*.txt     │
          └──────────┬───────────┘
                     │
                     │ Next Step
                     ▼
          ┌──────────────────────┐
          │ chunk_transcripts.py │
          │ Break into chunks    │
          └──────────┬───────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │ chunked_output/      │
          │ *_chunked.json       │
          └──────────┬───────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │generate_embeddings.py│
          │ Create vectors       │
          └──────────┬───────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │ embeddings_output/   │
          │ embeddings.json      │
          └──────────┬───────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │ build_faiss_index.py │
          │ Create search index  │
          └──────────┬───────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │   faiss_index/       │
          │   index.faiss        │
          └──────────┬───────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │   search_faiss.py    │
          │   Query System       │
          └──────────────────────┘
```

This comprehensive workflow shows every step from launch to final results!
