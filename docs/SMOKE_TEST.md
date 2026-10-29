# Smoke test (5 minutes)

Run after any tidy-up, move or rename. Nothing here calls a paid API.

## 1. Automated checks

```powershell
.venv\Scripts\python.exe tools\smoke_test.py
```

Compiles every live `.py` file, imports the shared packages, runs `--help` on the
command-line tools, and confirms the files the deployed app reads still exist.
Must end with `All smoke checks passed.`

## 2. Manual checks

| Check | How | Pass when |
|---|---|---|
| Video acquisition GUI | `launch_video_acquisition.bat` | Window opens with Channel Extraction, Video IDs and Topic Search tabs |
| Quality assurance GUI | `launch_quality_assurance.bat` | Window opens, boot stages complete, a small step loads its picks |
| Public app | `.venv\Scripts\streamlit.exe run flipper_lite.py` | Pick a Year/Block/Step; three video cards show; a thought prompt opens |
| Analytics dashboard (optional) | `launch_analytics_dashboard.bat` | Password prompt appears |

## 3. Undo

Every tidy-up step is a separate git commit. The state before the tidy-up is
tagged `pre-tidy-baseline`:

```powershell
git log --oneline          # find the step to undo
git revert <commit>        # undo one step
```
