@echo off
REM Check YouTube video availability for Flipper videos
REM This script checks whether videos in qa.csv are still accessible

REM Change to script directory
cd /d "%~dp0"

title YouTube Video Availability Checker

echo.
echo ====================================================================
echo YouTube Video Availability Checker
echo ====================================================================
echo.
echo Working directory: %CD%
echo.
echo This will check all videos in qa.csv against YouTube API
echo.

REM Check if virtual environment exists
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found at .venv\Scripts\python.exe
    echo Please ensure the virtual environment is set up correctly.
    echo.
    pause
    exit /b 1
)

REM Run the availability checker using venv Python directly
echo Starting video availability check...
echo.
.venv\Scripts\python.exe check_video_availability.py --source qa --output reports\video_availability_check.csv

if errorlevel 1 (
    echo.
    echo ====================================================================
    echo ERROR: Video availability check failed!
    echo Check the error messages above for details.
    echo ====================================================================
    echo.
    pause
    exit /b 1
)

echo.
echo ====================================================================
echo Check complete! Reports saved to reports\ folder:
echo   - video_availability_check.csv (full report)
echo   - unavailable_video_availability_check.csv (all problems)
echo   - deletion_candidates_video_availability_check.csv (REPLACE THESE)
echo   - embedding_disabled_video_availability_check.csv (watchable but won't embed)
echo.
echo NOTE: Videos in 'embedding_disabled' ARE viewable on YouTube
echo       but WON'T play in Flipper's embedded player.
echo ====================================================================
echo.
echo Opening reports folder...
start "" "%CD%\reports"
echo.
echo.
echo Press any key to close this window...
pause >nul
