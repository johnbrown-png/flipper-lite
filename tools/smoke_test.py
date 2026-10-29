"""Quick, cost-free smoke test for the Flipper project.

Run from the project root after any tidy-up or refactor:

    .venv\\Scripts\\python.exe tools\\smoke_test.py

Checks (no API calls, no GUI windows):
1. Every live .py file compiles.
2. Shared packages import.
3. Command-line tools start and print --help.
4. Files the deployed Streamlit app reads at fixed paths still exist.

Then do the manual checks in docs/SMOKE_TEST.md (launch GUIs and the app).
"""
from __future__ import annotations

import py_compile
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".venv", ".git", "_archive", "__pycache__", "data", "captions_output", "Topic_Downloads"}

IMPORTS = [
    "shared.config",
    "shared.curriculum_schema",
    "shared.pick_engine",
    "shared.analytics",
    "shared.email_sender",
    "shared.step_selection",
    "search_app.curriculum_assistant",
    "thoughtprompt.page",
    "flipper_search.streamlit_ui",
    "data_pipeline.deletion_tracker",
    "data_pipeline.instruction_quality_scorer",
    "query_embedder",
    "shared.email_sender",
    "shared.step_selection",
    "thoughtprompt.visual_generator",
    "flipper_search.search_engine",
]

GUI_MODULES = [
    "acquisition/video_acquisition.py",
    "quality_assurance/quality_assurance.py",
]

CLI_HELP = [
    ["acquisition/delete_content.py", "--help"],
    ["acquisition/export_channel_playlists.py", "--help"],
    ["quality_assurance/check_video_availability.py", "--help"],
    ["quality_assurance/precompute_curriculum_recommendations.py", "--help"],
    ["Curriculum/Maths/ss_desc_summariser/summariser.py", "--help"],
    ["Curriculum/Maths/pdf_extractor/merge_backfill_ss_wr_desc.py", "--help"],
    ["data_pipeline/run_pipeline.py", "--help"],
    ["analytics/analytics_webhook_server.py", "--help"],
]

DEPLOY_FILES = [
    "flipper_lite.py",
    "requirements.txt",
    "runtime.txt",
    "precomputed_recommendations_flat_qa.csv",
    "precomputed_recommendations_flat.csv",
    "Curriculum/Maths/curriculum_08052026_small_steps.csv",
    "shared/styles/flipper_lite.css",
    "thoughtprompt/pilot_output/thought_prompts_multiplechoice.csv",
    ".streamlit/config.toml",
    "static/landing/teacher.jpg",
    "static/landing/parent.jpg",
    "static/landing/homeschool.jpg",
]


def live_python_files() -> list[Path]:
    return [
        p for p in ROOT.rglob("*.py")
        if not any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts)
    ]


def main() -> int:
    failures: list[str] = []

    files = live_python_files()
    for path in files:
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            failures.append(f"compile: {path.relative_to(ROOT)}: {exc.msg}")
    print(f"[1] compiled {len(files)} files")

    sys.path.insert(0, str(ROOT))
    for module in IMPORTS:
        try:
            __import__(module)
        except Exception as exc:
            failures.append(f"import: {module}: {exc!r}")
    for rel in GUI_MODULES:
        # Load in a child process: GUI modules may chdir or mutate sys.path at import time.
        loader = (
            "import importlib.util, sys; "
            f"spec = importlib.util.spec_from_file_location('gui_check', r'{ROOT / rel}'); "
            "module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)"
        )
        result = subprocess.run(
            [sys.executable, "-c", loader], cwd=ROOT, capture_output=True, text=True, timeout=300
        )
        if result.returncode != 0:
            failures.append(f"gui import: {rel}: {result.stderr.strip()[-300:]}")
    print(f"[2] imported {len(IMPORTS)} modules and {len(GUI_MODULES)} GUI modules (no window)")

    for cmd in CLI_HELP:
        script = ROOT / cmd[0]
        if not script.exists():
            failures.append(f"cli: missing {cmd[0]}")
            continue
        result = subprocess.run(
            [sys.executable, *cmd], cwd=ROOT, capture_output=True, text=True, timeout=180
        )
        if result.returncode != 0:
            failures.append(f"cli: {' '.join(cmd)} exited {result.returncode}: {result.stderr.strip()[-300:]}")
    print(f"[3] ran {len(CLI_HELP)} CLI --help checks")

    for rel in DEPLOY_FILES:
        if not (ROOT / rel).exists():
            failures.append(f"deploy: missing {rel}")
    print(f"[4] checked {len(DEPLOY_FILES)} deploy-critical files")

    if failures:
        print("\nFAILURES:")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("\nAll smoke checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
