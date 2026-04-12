@echo off
REM Launcher for Improve Pick QA GUI
setlocal
cd /d "%~dp0"

echo Starting Improve Pick QA GUI...
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Error: virtual environment not found at .venv\Scripts\python.exe
    echo Create it first, then install requirements.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" Improve_pick\gui_precompute_recommendation_qa.py

if errorlevel 1 (
    echo.
    echo GUI exited with an error.
    pause
)

endlocal
