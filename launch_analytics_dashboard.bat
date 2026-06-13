
@echo off
setlocal
if exist ".venv\Scripts\python.exe" (
  .venv\Scripts\python.exe -m streamlit run analytics_dashboard.py
) else (
  python -m streamlit run analytics_dashboard.py
)
