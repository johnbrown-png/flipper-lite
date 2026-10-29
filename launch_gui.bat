@echo off
REM Launcher for YouTube Caption Extraction GUI
echo Starting YouTube Caption Extraction GUI...
echo.

REM Check if virtual environment exists
if not exist ".venv\Scripts\python.exe" (
    echo Error: Virtual environment not found!
    echo Please create a virtual environment first:
    echo   python -m venv .venv
    echo   .venv\Scripts\activate
    echo   pip install -r requirements.txt
    pause
    exit /b 1
)

REM Check if .env file exists
if not exist ".env" (
    echo Warning: .env file not found!
    echo Please create .env with your YOUTUBE_API_KEY
    echo.
)

REM Run the GUI
".venv\Scripts\python.exe" gui_main.py

if errorlevel 1 (
    echo.
    echo GUI exited with an error.
    pause
)
