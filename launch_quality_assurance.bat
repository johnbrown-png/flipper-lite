@echo off
REM Launcher for the Quality Assurance GUI (Module C, see docs\quality_assurance.md)
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo Error: virtual environment not found at .venv\Scripts\pythonw.exe
    echo Create it first, then install requirements.
    pause
    exit /b 1
)

start "" ".venv\Scripts\pythonw.exe" "quality_assurance\quality_assurance.py"
endlocal
