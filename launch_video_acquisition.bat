@echo off
REM Launcher for the Video Acquisition GUI (Module A, see docs\acquisition.md)
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Error: Virtual environment not found!
    echo Please create a virtual environment first:
    echo   python -m venv .venv
    echo   .venv\Scripts\activate
    echo   pip install -r requirements.txt
    pause
    exit /b 1
)

if not exist ".env" (
    echo Warning: .env file not found!
    echo Please create .env with your YOUTUBE_API_KEY
    echo.
)

".venv\Scripts\python.exe" acquisition\video_acquisition.py

if errorlevel 1 (
    echo.
    echo GUI exited with an error.
    pause
)
endlocal
