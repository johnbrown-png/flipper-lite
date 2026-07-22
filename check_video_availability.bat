@echo off
REM Check YouTube video availability for Flipper videos
REM This script checks whether videos in qa.csv are still accessible

echo.
echo ====================================================================
echo YouTube Video Availability Checker
echo ====================================================================
echo.
echo This will check all videos in qa.csv against YouTube API
echo.

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Run the availability checker
python check_video_availability.py --source qa --output reports\video_availability_check.csv

echo.
echo ====================================================================
echo Check complete! Reports saved to reports\ folder:
echo   - video_availability_check.csv (full report)
echo   - unavailable_video_availability_check.csv (problems only)
echo   - deletion_candidates_video_availability_check.csv (for deletion)
echo ====================================================================
echo.
pause
