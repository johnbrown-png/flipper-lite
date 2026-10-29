@echo off
REM Conservative Caption Extraction Scheduler
REM Extracts 5 videos at a time with breaks to avoid bot detection

echo ========================================
echo YouTube Caption Extraction Scheduler
echo ========================================
echo.
echo This script will:
echo - Extract 5 videos at a time
echo - Take 2-5 minute breaks between batches
echo - Randomize channel order
echo - Detect and stop on IP blocks
echo - Send notifications on issues
echo.

python scheduled_extractor.py --batch-size 5 --max-total 25

echo.
echo ========================================
echo Extraction session complete
echo ========================================
pause
