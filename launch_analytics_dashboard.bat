@echo off
REM Launcher for the private analytics dashboard (Module D, see docs\delivery.md)
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  .venv\Scripts\python.exe -m streamlit run analytics\analytics_dashboard.py
) else (
  python -m streamlit run analytics\analytics_dashboard.py
)
endlocal
