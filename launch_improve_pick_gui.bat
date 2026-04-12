@echo off
REM Launcher for Improve Pick QA GUI
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo Error: virtual environment not found at .venv\Scripts\pythonw.exe
    echo Create it first, then install requirements.
    pause
    exit /b 1
)

start "" ".venv\Scripts\pythonw.exe" "Improve_pick\gui_precompute_recommendation_qa.py"
endlocal
