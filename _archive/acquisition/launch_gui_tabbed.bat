@echo off
echo.
echo ==================================================
echo   YouTube Caption Extraction Pipeline
echo ==================================================
echo.
echo Starting unified GUI with three extraction methods:
echo  - Channel Extraction (bulk from channels.csv)
echo  - Video ID Extraction (specific videos)
echo  - Topic Search (discover videos by keywords)
echo.

python gui_main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Error: Failed to launch GUI
    echo.
    pause
)
