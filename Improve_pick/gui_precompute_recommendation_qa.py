"""Standalone GUI for targeted ss_wr_desc QA experiments.

This MVP focuses on fast manual iteration:
- choose a curriculum small step
- view current ss_wr_desc
- test a candidate wording
- inspect top-3 results with quick open links
- score each result with a color-coded 1-10 rating
- save candidate text and ratings to qa.csv outputs
"""

from __future__ import annotations

import asyncio
from datetime import datetime
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
from typing import Any
import webbrowser

import pandas as pd
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

# Ensure imports work when script is launched from Improve_pick/
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from precompute_curriculum_recommendations import load_faiss_index
from query_embedder import QueryEmbedder
from data_pipeline.deletion_tracker import DeletionTracker
from data_pipeline.instruction_quality_scorer import InstructionQualityScorer
from shared.curriculum_schema import curriculum_to_long_df
from shared.pick_engine import (
    build_query_text,
    build_stage2_shortlist as shared_build_stage2_shortlist,
    calculate_cosine_similarity,
    compute_stage3_score as shared_compute_stage3_score,
    compute_stage4_final_score as shared_compute_stage4_final_score,
    load_validated_override_map,
    resolve_validated_desc,
    score_stage2_survivors_async as shared_score_stage2_survivors_async,
    upsert_validated_override,
)


CURRICULUM_PATH = project_root / "Curriculum" / "Maths" / "curriculum_08052026_small_steps.csv"
TARGET_OVERRIDES_PATH = project_root / "qa" / "targeted_ss_wr_desc_overrides.csv"
APPROVED_CANDIDATES_PATH = project_root / "qa" / "approved_ss_wr_desc_candidates.csv"
CANONICAL_OVERRIDE_PATH = project_root / "qa" / "ss_desc_validated_overrides.csv"
QA_TRACKING_PATH = project_root / "qa" / "qa.csv"
VIDEOS_TO_DELETE_PATH = project_root / "videos_to_delete" / "videos_to_delete.csv"
MANUAL_PRECOMP_OVERRIDE_PATH = project_root / "qa" / "manual_precomputed_overrides.csv"
WILDCARD_OVERRIDE_PATH = project_root / "qa" / "wildcards" / "wildcards.csv"
QA_REFERENCE_OUTPUT_PATH = project_root / "precomputed_recommendations_flat_qa.csv"
STEP_KNOCKOUT_PATH = project_root / "qa" / "step_video_knockouts.csv"
DUP_FLAGGED_PATH = project_root / "qa" / "dup_flagged_steps.csv"
QA_COMMAND_LOG_PATH = project_root / "qa" / "logs" / "qa_command_log.txt"
TOP_K = 3
CANDIDATE_DISPLAY_K = 10
LOW_CANDIDATE_RATING_THRESHOLD = 7
SEMANTIC_PREVIEW_K = 5
SEMANTIC_PREVIEW_CHUNKS = 40
SEMANTIC_PREVIEW_DEBOUNCE_MS = 550
CONSTRAINTS_GATE_DEFAULT_K = 20
CONSTRAINTS_GATE_MAX_K = 80
SEMANTIC_WEIGHT = 0.55
ALIGNMENT_WEIGHT = 0.20
INSTRUCTION_WEIGHT = 0.25

SHOW_SHOW_UNSAVED_ONLY_CONTROL = False
SHOW_AWAITING_DOWNLOAD_CONTROL = False
SHOW_FULL_REBUILD_CONTROL = False
SHOW_APPROVE_UPDATE_CONTROL = False
SHOW_CLEAR_OVERRIDE_CONTROL = False
SHOW_LIVE_SEMANTIC_PREVIEW = False
SHOW_ALIGNMENT_TAB = False
SHOW_STAGE4_TAB = False

# Dup proximity review tuning constants
DUP_REVIEW_W = 10               # distance window: penalty decays to zero at this step distance
DUP_REVIEW_K_SHRINK = 6        # shrinkage constant: stabilises low-evidence steps
DUP_REVIEW_DEFAULT_TOP_PCT = 5  # default top-% of steps shown as hotspots
DUP_NEIGHBOUR_RADIUS = 3        # adjacent steps shown either side in Dup Neighbours panel

JOB_STATE_IDLE = "idle"
JOB_STATE_RUNNING = "running"
JOB_STATE_FAILED = "failed"
JOB_STATE_DONE = "done"
JOB_STATE_CANCELLED = "cancelled"
WINDOWS_CTRL_C_EXIT_CODES = {3221225786, -1073741510}


def build_qa_columns() -> list[str]:
    columns = [
        "updated_at",
        "small_step_id",
        "topic",
        "small_step_name",
        "baseline_ss_wr_desc",
        "candidate_ss_wr_desc",
        "constraints_text",
        "awaiting download and faiss update",
        "notes",
    ]

    for source in ("current", "candidate"):
        limit = TOP_K if source == "current" else CANDIDATE_DISPLAY_K
        for rank in range(1, limit + 1):
            prefix = f"{source}_{rank}"
            columns.extend(
                [
                    f"{prefix}_video_id",
                    f"{prefix}_video_title",
                    f"{prefix}_channel",
                    f"{prefix}_rating_1_10",
                    f"{prefix}_combined_score",
                    f"{prefix}_semantic_score",
                    f"{prefix}_instruction_score",
                    f"{prefix}_alignment_score",
                ]
            )

    return columns


QA_COLUMNS = build_qa_columns()


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def format_duration_hms(seconds: object) -> str:
    if seconds is None or seconds == "":
        return ""
    try:
        total_seconds = int(float(seconds))
    except (TypeError, ValueError):
        return ""

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def build_faiss_video_lookup(metadata: list[dict[str, object]]) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for item in metadata:
        video_id = clean_text(item.get("video_id"))
        if not video_id or video_id in lookup:
            continue
        lookup[video_id] = {
            "channel": clean_text(item.get("channel")),
            "duration_formatted": format_duration_hms(item.get("duration")),
        }
    return lookup


def _atomic_write_csv(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    df.to_csv(temp_path, index=False)
    os.replace(temp_path, output_path)


def _read_wildcard_rows(path: Path) -> pd.DataFrame:
    columns = ["video_id", "channel", "title", "small_step_num", "small_step_id", "ss_wr_desc"]
    if not path.exists():
        return pd.DataFrame(columns=columns)

    wildcard_df = pd.read_csv(path, on_bad_lines="skip")
    for col in columns:
        if col not in wildcard_df.columns:
            wildcard_df[col] = ""
    wildcard_df = wildcard_df[columns].copy()
    for col in ("video_id", "channel", "title", "small_step_id"):
        wildcard_df[col] = wildcard_df[col].map(clean_text)
    wildcard_df["ss_wr_desc"] = wildcard_df["ss_wr_desc"].map(clean_text)

    # Backward-compatibility: some files place the step identifier in ss_wr_desc
    # and the long description text in small_step_id. Normalize to small_step_id.
    small_step_id_is_step = wildcard_df["small_step_id"].str.startswith("Year ", na=False)
    ss_wr_desc_is_step = wildcard_df["ss_wr_desc"].str.startswith("Year ", na=False)
    swap_mask = (~small_step_id_is_step) & ss_wr_desc_is_step
    wildcard_df.loc[swap_mask, "small_step_id"] = wildcard_df.loc[swap_mask, "ss_wr_desc"]

    wildcard_df = wildcard_df[
        (wildcard_df["small_step_id"].str.len() > 0)
        & ((wildcard_df["video_id"].str.len() > 0) | (wildcard_df["title"].str.len() > 0))
    ].copy()
    wildcard_df = wildcard_df.drop_duplicates(subset=["small_step_id"], keep="last")
    return wildcard_df


def load_video_lookup() -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    video_inventory_path = project_root / "video_inventory" / "video_inventory.csv"
    if not video_inventory_path.exists():
        return lookup

    inventory_df = pd.read_csv(video_inventory_path)
    for _, row in inventory_df.iterrows():
        video_id = clean_text(row.get("video_id"))
        if not video_id:
            continue
        lookup[video_id] = {
            "channel": clean_text(row.get("channel")),
            "duration_formatted": clean_text(row.get("duration_formatted")),
        }
    return lookup


def rating_to_color(rating: int) -> str:
    """Return a red->amber->green gradient color for rating 1..10."""
    clamped = max(1, min(10, rating))
    t = (clamped - 1) / 9.0

    # Piecewise interpolation: red -> amber -> green
    red = (215, 48, 39)
    amber = (253, 174, 97)
    green = (26, 152, 80)

    if t <= 0.5:
        local_t = t / 0.5
        rgb = tuple(int(red[i] + (amber[i] - red[i]) * local_t) for i in range(3))
    else:
        local_t = (t - 0.5) / 0.5
        rgb = tuple(int(amber[i] + (green[i] - amber[i]) * local_t) for i in range(3))

    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def text_color_for_bg(hex_color: str) -> str:
    """Choose black/white text color for readability on a background color."""
    value = hex_color.lstrip("#")
    if len(value) != 6:
        return "black"

    r = int(value[0:2], 16)
    g = int(value[2:4], 16)
    b = int(value[4:6], 16)
    luminance = (0.299 * r) + (0.587 * g) + (0.114 * b)
    return "black" if luminance > 150 else "white"


def split_constraint_terms(raw_value: object) -> list[str]:
    text = clean_text(raw_value)
    if not text:
        return []
    return [part.strip().lower() for part in re.split(r"[,;]", text) if part.strip()]


def parse_upper_bound(raw_value: object) -> int | None:
    text = clean_text(raw_value).lower()
    if not text:
        return None
    match = re.search(r"up to\s*(\d+)", text)
    if match:
        return int(match.group(1))
    return None


def parse_constraints_text_block(raw_value: object) -> dict[str, str]:
    """Parse free-form constraints text into simple gate rule buckets.

    Supported line formats:
    - must_include: term1, term2
    - must_not_include: term3; term4
    - numeric_bounds: up to 10
    - reject_rule: divisible by 10

    Any non-empty unlabeled line is treated as a must_not_include token.
    """
    text = clean_text(raw_value)
    parsed = {
        "must_include": "",
        "must_not_include": "",
        "numeric_bounds": "",
        "reject_rule": "",
    }

    if not text:
        return parsed

    loose_not_include_terms: list[str] = []
    for line in text.splitlines():
        line_text = line.strip()
        if not line_text:
            continue

        if ":" in line_text:
            key, value = line_text.split(":", 1)
        elif "=" in line_text:
            key, value = line_text.split("=", 1)
        else:
            loose_not_include_terms.append(line_text)
            continue

        key_norm = key.strip().lower().replace("-", "_").replace(" ", "_").replace("/", "_")
        value_norm = value.strip()
        if not value_norm:
            continue

        if key_norm in parsed:
            parsed[key_norm] = value_norm
        elif key_norm in {"must_include_terms", "include"}:
            parsed["must_include"] = value_norm
        elif key_norm in {"must_not_include_terms", "exclude", "block", "blocked_terms"}:
            parsed["must_not_include"] = value_norm
        elif key_norm in {"numerical_domain", "numeric_domain", "numerical_domain_bounds"}:
            parsed["numeric_bounds"] = value_norm
        elif key_norm in {"reject_rule_fail_gate", "fail_gate", "reject"}:
            parsed["reject_rule"] = value_norm

    if loose_not_include_terms:
        existing = parsed["must_not_include"]
        extra = "; ".join(loose_not_include_terms)
        parsed["must_not_include"] = f"{existing}; {extra}" if existing else extra

    return parsed


class ToolTip:
    def __init__(self, widget: tk.Widget, text: str, wraplength: int = 320):
        self.widget = widget
        self.text = text
        self.wraplength = wraplength
        self.tip_window: tk.Toplevel | None = None

        self.widget.bind("<Enter>", self._show, add="+")
        self.widget.bind("<Leave>", self._hide, add="+")
        self.widget.bind("<ButtonPress>", self._hide, add="+")

    def _show(self, _event=None) -> None:
        if self.tip_window is not None or not self.text:
            return

        x = self.widget.winfo_rootx() + 16
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8

        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)
        self.tip_window.wm_geometry(f"+{x}+{y}")

        label = tk.Label(
            self.tip_window,
            text=self.text,
            justify=tk.LEFT,
            background="#fffbe6",
            foreground="#333333",
            relief=tk.SOLID,
            borderwidth=1,
            padx=8,
            pady=5,
            wraplength=self.wraplength,
        )
        label.pack()

    def _hide(self, _event=None) -> None:
        if self.tip_window is not None:
            self.tip_window.destroy()
            self.tip_window = None


class ImprovePickQAGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Improve Pick - Targeted ss_wr_desc QA")
        self.root.geometry("1240x760")

        self.status_var = tk.StringVar(value="Loading data...")
        self.step_var = tk.StringVar(value="")
        self.progress_var = tk.StringVar(value="Done 0/0 (0%)")
        self.scenario_var = tk.StringVar(value="gui_mvp_approved")
        self.show_unsaved_only_var = tk.BooleanVar(value=False)
        self.low_rating_jump_ignore_default_five_var = tk.BooleanVar(value=True)
        self.awaiting_download_faiss_var = tk.BooleanVar(value=False)
        self.candidate_panel_state_var = tk.StringVar(value="Candidate panel: locked until Update QA CSV")
        self.constraints_status_var = tk.StringVar(value="Constraints gate: idle")
        self.constraints_summary_var = tk.StringVar(value="No constraint test run yet")
        self.constraints_step_label_var = tk.StringVar(value="Selected small step: none")
        self.constraints_k_var = tk.StringVar(value=str(CONSTRAINTS_GATE_DEFAULT_K))
        self.constraints_objective_core_var = tk.StringVar(value="")
        self.constraints_must_include_var = tk.StringVar(value="")
        self.constraints_must_not_include_var = tk.StringVar(value="")
        self.constraints_numerical_domain_var = tk.StringVar(value="")
        self.constraints_reject_rule_fail_gate_var = tk.StringVar(value="")
        self.notes_var = tk.StringVar(value="")
        self.job_state_var = tk.StringVar(value="Job state: idle")
        self.job_step_var = tk.StringVar(value="Current step status: ready")
        self.job_error_var = tk.StringVar(value="")

        self.curriculum_df = pd.DataFrame()
        self.curriculum_by_id: dict[str, dict[str, object]] = {}
        self.step_labels_by_id: dict[str, str] = {}
        self.step_label_to_id: dict[str, str] = {}
        self.sorted_step_ids: list[str] = []
        self.saved_step_ids: set[str] = set()

        self.index = None
        self.metadata: list[dict[str, object]] = []
        self.embedder: QueryEmbedder | None = None
        self.scorer: InstructionQualityScorer | None = None
        self.deleted_videos: set[str] = set()
        self.fallback_lookup: dict[str, dict[str, str]] = {}
        self.video_lookup: dict[str, dict[str, str]] = {}

        self.latest_results: list[dict[str, object]] = []
        self.latest_enriched_results: list[dict[str, object]] = []
        self.latest_alignment_results: list[dict[str, object]] = []
        self.latest_final_results: list[dict[str, object]] = []
        self.latest_query_text = ""
        self.semantic_preview_results: list[dict[str, object]] = []
        self.semantic_preview_status_var = tk.StringVar(value="Semantic preview: idle")
        self.semantic_preview_after_id: str | None = None
        self.semantic_preview_request_id = 0

        self.result_title_labels: list[ttk.Label] = []
        self.result_channel_labels: list[ttk.Label] = []
        self.result_score_labels: list[ttk.Label] = []
        self.result_open_buttons: list[ttk.Button] = []
        self.rating_vars: list[tk.StringVar] = []
        self.rating_dropdowns: list[tk.OptionMenu] = []
        self.candidate_rank_vars: list[tk.StringVar] = []
        self.candidate_rank_dropdowns: list[tk.OptionMenu] = []
        self.candidate_knockout_buttons: list[ttk.Button] = []
        self._prev_candidate_ranks: list[int] = []

        self.precomputed_df: pd.DataFrame = pd.DataFrame()
        self.wildcard_df: pd.DataFrame = pd.DataFrame()
        self.precomputed_results: list[dict[str, object]] = []
        self.precomputed_panel_state_var = tk.StringVar(value="Current picks source: precomputed base")
        self.precomputed_title_labels: list[ttk.Label] = []
        self.precomputed_channel_labels: list[ttk.Label] = []
        self.precomputed_score_labels: list[ttk.Label] = []
        self.precomputed_open_buttons: list[ttk.Button] = []
        self.precomputed_delete_buttons: list[ttk.Button] = []
        self.precomputed_knockout_buttons: list[ttk.Button] = []
        self.precomputed_rating_vars: list[tk.StringVar] = []
        self.precomputed_rating_dropdowns: list[tk.OptionMenu] = []
        self.precomputed_rank_vars: list[tk.StringVar] = []
        self.precomputed_rank_dropdowns: list[tk.OptionMenu] = []
        self._prev_precomputed_ranks: list[int] = []
        self.candidate_delete_buttons: list[ttk.Button] = []
        self.semantic_preview_title_labels: list[ttk.Label] = []
        self.semantic_preview_channel_labels: list[ttk.Label] = []
        self.semantic_preview_score_labels: list[ttk.Label] = []
        self.saved_candidate_steps: set[str] = set()
        self.candidate_display_unlocked_steps: set[str] = set()
        self.promoted_step_ids: set[str] = set()
        self.promoted_status_var = tk.StringVar(value="")
        self.constraints_results: list[dict[str, object]] = []
        self.constraints_title_labels: list[ttk.Label] = []
        self.constraints_gate_labels: list[ttk.Label] = []
        self.constraints_reason_labels: list[ttk.Label] = []
        self.constraints_open_buttons: list[ttk.Button] = []
        self.constraints_score_labels: list[ttk.Label] = []
        self.alignment_tree: ttk.Treeview | None = None
        self.stage4_survivors_tree: ttk.Treeview | None = None
        self.stage4_final_title_labels: list[ttk.Label] = []
        self.stage4_final_stage3_labels: list[ttk.Label] = []
        self.stage4_final_instruction_labels: list[ttk.Label] = []
        self.stage4_final_score_labels: list[ttk.Label] = []
        self.stage4_final_open_buttons: list[ttk.Button] = []
        self.command_buttons: list[ttk.Button] = []
        self.command_tooltips: list[ToolTip] = []
        self.cancel_job_btn: ttk.Button | None = None
        self.retry_job_btn: ttk.Button | None = None
        self.job_status_label: ttk.Label | None = None
        self.job_step_label: ttk.Label | None = None
        self.job_error_label: ttk.Label | None = None

        # Dup proximity review state
        self.dup_review_mode = False
        self.dup_threshold_pct_var = tk.StringVar(value=str(DUP_REVIEW_DEFAULT_TOP_PCT))
        self.dup_score_display_var = tk.StringVar(value="")
        self.dup_scores: dict[str, dict] = {}
        self.dup_flagged_steps: set[str] = set()
        self.step_global_num: dict[str, int] = {}
        self.global_num_to_step_id: dict[int, str] = {}
        self.dup_neighbour_text: scrolledtext.ScrolledText | None = None
        self.dup_review_btn: ttk.Button | None = None
        self.dup_jump_btn: ttk.Button | None = None
        self.dup_flag_btn: ttk.Button | None = None

        self.active_job_state = JOB_STATE_IDLE
        self.active_job_name = ""
        self.active_job_thread: threading.Thread | None = None
        self.active_process: subprocess.Popen[str] | None = None
        self.cancel_requested = False
        self.log_lock = threading.Lock()
        self.last_failed_subprocess_spec: tuple[str, list[str], bool] | None = None

        self._build_ui()
        # Defer heavy loading until after mainloop starts so the window appears immediately.
        self.root.after(100, self._load_initial_data)

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root)
        container.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        self.main_canvas = tk.Canvas(container, highlightthickness=0)
        self.main_canvas.grid(row=0, column=0, sticky="nsew")

        self.main_scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.main_canvas.yview)
        self.main_scrollbar.grid(row=0, column=1, sticky="ns")
        self.main_canvas.configure(yscrollcommand=self.main_scrollbar.set)

        outer = ttk.Frame(self.main_canvas, padding=8)
        self._outer_canvas_window = self.main_canvas.create_window((0, 0), window=outer, anchor="nw")

        def _on_outer_configure(_event) -> None:
            self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))

        def _on_canvas_configure(event) -> None:
            self.main_canvas.itemconfigure(self._outer_canvas_window, width=event.width)

        outer.bind("<Configure>", _on_outer_configure)
        self.main_canvas.bind("<Configure>", _on_canvas_configure)

        # Mouse wheel support for Windows to make vertical scrolling easier.
        self.main_canvas.bind_all("<MouseWheel>", lambda event: self.main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units"))

        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(6, weight=1)

        title = ttk.Label(
            outer,
            text="Improve Pick - Manual Candidate QA",
            font=("Segoe UI", 13, "bold"),
        )
        title.grid(row=0, column=0, sticky="w", pady=(0, 4))

        selector_frame = ttk.LabelFrame(outer, text="Small Step Selection", padding=8)
        selector_frame.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        selector_frame.columnconfigure(1, weight=1)

        ttk.Label(selector_frame, text="Small step:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.step_combo = ttk.Combobox(selector_frame, textvariable=self.step_var, state="readonly")
        self.step_combo.grid(row=0, column=1, sticky="ew")
        self.step_combo.bind("<<ComboboxSelected>>", self._on_step_selected)

        ttk.Label(selector_frame, text="Scenario label:").grid(row=0, column=2, sticky="w", padx=(12, 8))
        self.scenario_entry = ttk.Entry(selector_frame, textvariable=self.scenario_var, width=24)
        self.scenario_entry.grid(row=0, column=3, sticky="w")

        ttk.Label(selector_frame, textvariable=self.progress_var, foreground="#1f7a1f").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.jump_unsaved_btn = ttk.Button(
            selector_frame,
            text="Jump to Next Unsaved",
            command=self._jump_to_next_unsaved,
        )
        self.jump_unsaved_btn.grid(row=1, column=1, sticky="w", pady=(4, 0))

        self.next_small_step_btn = ttk.Button(
            selector_frame,
            text="Next Small Step",
            command=self._jump_to_next_small_step,
        )
        self.next_small_step_btn.grid(row=1, column=2, sticky="w", padx=(12, 0), pady=(4, 0))

        self.jump_low_candidate_btn = ttk.Button(
            selector_frame,
            text=f"Jump to Next Candidate <= {LOW_CANDIDATE_RATING_THRESHOLD}",
            command=self._jump_to_next_low_candidate_rating,
        )
        self.jump_low_candidate_btn.grid(row=1, column=3, sticky="w", padx=(12, 0), pady=(4, 0))

        self.jump_ignore_default_five_check = ttk.Checkbutton(
            selector_frame,
            text="Jump <=7 ignores default 5",
            variable=self.low_rating_jump_ignore_default_five_var,
            command=self._on_jump_filter_changed,
        )
        self.jump_ignore_default_five_check.grid(row=1, column=4, sticky="w", padx=(12, 0), pady=(4, 0))

        if SHOW_SHOW_UNSAVED_ONLY_CONTROL:
            self.show_unsaved_check = ttk.Checkbutton(
                selector_frame,
                text="Show unsaved only",
                variable=self.show_unsaved_only_var,
                command=self._on_show_unsaved_only_changed,
            )
            self.show_unsaved_check.grid(row=1, column=4, sticky="w", padx=(12, 0), pady=(4, 0))

        # Row 4: Dup Review Mode controls
        self.dup_review_btn = ttk.Button(
            selector_frame,
            text="High-Dup Review: OFF",
            command=self._toggle_dup_review_mode,
        )
        self.dup_review_btn.grid(row=4, column=0, sticky="w", pady=(4, 0))

        ttk.Label(selector_frame, text="Hotspot top %:").grid(row=4, column=1, sticky="e", padx=(0, 4), pady=(4, 0))
        self.dup_threshold_spin = tk.Spinbox(
            selector_frame,
            from_=1,
            to=50,
            width=4,
            textvariable=self.dup_threshold_pct_var,
            increment=1,
        )
        self.dup_threshold_spin.grid(row=4, column=2, sticky="w", pady=(4, 0))

        self.dup_jump_btn = ttk.Button(
            selector_frame,
            text="Next High-Dup Step",
            command=self._jump_to_next_dup_hotspot,
        )
        self.dup_jump_btn.grid(row=4, column=3, sticky="w", padx=(12, 0), pady=(4, 0))

        self.dup_flag_btn = ttk.Button(
            selector_frame,
            text="Mark Step Redundant",
            command=self._flag_current_step_redundant,
        )
        self.dup_flag_btn.grid(row=4, column=4, sticky="w", padx=(12, 0), pady=(4, 0))

        # Row 5: per-step dup score display
        ttk.Label(
            selector_frame,
            textvariable=self.dup_score_display_var,
            foreground="#994400",
        ).grid(row=5, column=0, columnspan=5, sticky="w", pady=(2, 0))

        text_frame = ttk.LabelFrame(outer, text="Query Text", padding=8)
        text_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 4))
        text_frame.columnconfigure(0, weight=1)
        text_frame.columnconfigure(1, weight=1)

        baseline_frame = ttk.Frame(text_frame)
        baseline_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        baseline_frame.columnconfigure(0, weight=1)
        baseline_frame.rowconfigure(1, weight=1)
        ttk.Label(baseline_frame, text="Current ss_wr_desc", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        self.baseline_text = scrolledtext.ScrolledText(baseline_frame, wrap=tk.WORD, height=9)
        self.baseline_text.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        self.baseline_text.config(state=tk.DISABLED)

        candidate_frame = ttk.Frame(text_frame)
        candidate_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        candidate_frame.columnconfigure(0, weight=1)
        candidate_frame.columnconfigure(1, weight=0)
        candidate_frame.rowconfigure(1, weight=1)
        ttk.Label(candidate_frame, text="Candidate wording (candidate_ss_wr_desc)", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        self.promoted_status_label = ttk.Label(candidate_frame, textvariable=self.promoted_status_var, foreground="green", font=("Segoe UI", 9, "bold"))
        self.promoted_status_label.grid(row=0, column=1, sticky="e", padx=(8, 0))
        self.candidate_text = scrolledtext.ScrolledText(candidate_frame, wrap=tk.WORD, height=9)
        self.candidate_text.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(4, 0))
        self.candidate_text.bind("<<Modified>>", self._on_candidate_text_modified)

        if SHOW_LIVE_SEMANTIC_PREVIEW:
            semantic_preview_frame = ttk.LabelFrame(candidate_frame, text="Live Semantic Preview (No Instruction Scoring)", padding=6)
            semantic_preview_frame.grid(row=2, column=0, sticky="nsew", pady=(4, 0))
            semantic_preview_frame.columnconfigure(1, weight=1)
            candidate_frame.rowconfigure(2, weight=1)

            preview_headers = ["Rank", "Title", "Channel", "Semantic"]
            for col, header in enumerate(preview_headers):
                ttk.Label(semantic_preview_frame, text=header, font=("Segoe UI", 9, "bold")).grid(row=0, column=col, sticky="w", padx=3, pady=(0, 4))

            for i in range(SEMANTIC_PREVIEW_K):
                row_num = i + 1
                ttk.Label(semantic_preview_frame, text=f"{row_num}").grid(row=row_num, column=0, sticky="w", padx=3, pady=1)

                title_label = ttk.Label(semantic_preview_frame, text="", width=44)
                title_label.grid(row=row_num, column=1, sticky="w", padx=3, pady=1)
                self.semantic_preview_title_labels.append(title_label)

                channel_label = ttk.Label(semantic_preview_frame, text="", width=20)
                channel_label.grid(row=row_num, column=2, sticky="w", padx=3, pady=1)
                self.semantic_preview_channel_labels.append(channel_label)

                score_label = ttk.Label(semantic_preview_frame, text="", width=10)
                score_label.grid(row=row_num, column=3, sticky="w", padx=3, pady=1)
                self.semantic_preview_score_labels.append(score_label)

            ttk.Label(candidate_frame, textvariable=self.semantic_preview_status_var, foreground="#555555").grid(row=3, column=0, sticky="w", pady=(2, 0))

        control_frame = ttk.Frame(outer)
        control_frame.grid(row=3, column=0, sticky="ew", pady=(0, 4))
        self.search_btn = ttk.Button(control_frame, text="Search Top 3", command=self._run_search)
        self.search_btn.grid(row=0, column=0, padx=(0, 8))
        self.save_btn = ttk.Button(control_frame, text="Save Approved Candidate", command=self._save_candidate, state=tk.DISABLED)
        # Hidden intentionally: workflow now uses qa.csv via Update QA CSV.
        self.update_qa_btn = ttk.Button(control_frame, text="Update QA CSV", command=self._update_qa_csv)
        self.update_qa_btn.grid(row=0, column=1, padx=(0, 8))

        self.mark_candidate_done_btn = ttk.Button(
            control_frame,
            text="Mark Candidate Reviewed (set shown ratings=10)",
            command=self._mark_candidate_reviewed,
        )
        self.mark_candidate_done_btn.grid(row=0, column=2, padx=(0, 8))

        if SHOW_AWAITING_DOWNLOAD_CONTROL:
            self.awaiting_download_check = ttk.Checkbutton(
                control_frame,
                text="Set 'Awaiting download/faiss rebuild' on Update QA CSV",
                variable=self.awaiting_download_faiss_var,
            )
            self.awaiting_download_check.grid(row=0, column=2, padx=(0, 8), sticky="w")

        self.status_label = ttk.Label(control_frame, textvariable=self.status_var, foreground="blue")
        self.status_label.grid(row=0, column=4, sticky="w")

        self.promote_canonical_btn = ttk.Button(
            control_frame,
            text="⭐ Promote to Canonical",
            command=self._promote_to_canonical,
        )
        self.promote_canonical_btn.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Label(
            control_frame,
            text="Writes candidate text → qa/ss_desc_validated_overrides.csv (read by precompute)",
            foreground="#555555",
        ).grid(row=1, column=2, columnspan=3, sticky="w", pady=(4, 0))

        command_frame = ttk.LabelFrame(outer, text="QA Command Center", padding=8)
        command_frame.grid(row=4, column=0, sticky="ew", pady=(0, 4))
        for col in range(7):
            command_frame.columnconfigure(col, weight=1)

        apply_delete_btn = ttk.Button(command_frame, text="Apply Delete Queue", command=self._command_apply_delete_queue)
        apply_delete_btn.grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 4))
        self.command_buttons.append(apply_delete_btn)
        self._attach_tooltip(apply_delete_btn, "Runs delete_content.py on videos_to_delete.csv in soft-delete mode only. Local files and metadata are removed immediately, but this button does not perform the full FAISS rebuild.")

        if SHOW_FULL_REBUILD_CONTROL:
            full_rebuild_btn = ttk.Button(command_frame, text="Full Rebuild FAISS", command=self._command_full_rebuild_faiss)
            full_rebuild_btn.grid(row=0, column=1, sticky="w", padx=(0, 8), pady=(0, 4))
            self.command_buttons.append(full_rebuild_btn)
            self._attach_tooltip(full_rebuild_btn, "Runs chunk, embedding, and a full FAISS rebuild from local data. Use this when you want to physically purge deleted vectors and fully realign FAISS with current local assets.")

        sync_btn = ttk.Button(command_frame, text="Sync New Downloads", command=self._command_sync_new_downloads)
        sync_btn.grid(row=0, column=2, sticky="w", padx=(0, 8), pady=(0, 4))
        self.command_buttons.append(sync_btn)
        self._attach_tooltip(sync_btn, "Runs the incremental chunk/embed/index pipeline so newly downloaded material becomes searchable without a full rebuild.")

        if SHOW_APPROVE_UPDATE_CONTROL:
            finalize_btn = ttk.Button(command_frame, text="Approve + Update QA CSV", command=self._command_finalize_current_step)
            finalize_btn.grid(row=0, column=3, sticky="w", padx=(0, 8), pady=(0, 4))
            self.command_buttons.append(finalize_btn)
            self._attach_tooltip(finalize_btn, "Writes the current candidate wording, ratings, and visible picks into qa/qa.csv for the selected small step.")

        cand_override_btn = ttk.Button(
            command_frame,
            text="Apply Cand MR",
            command=self._command_apply_manual_override,
        )
        cand_override_btn.grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(0, 4))
        self.command_buttons.append(cand_override_btn)
        self._attach_tooltip(cand_override_btn, "Uses Candidate panel MR values and writes qa/manual_precomputed_overrides.csv for this step.")

        curr_override_btn = ttk.Button(
            command_frame,
            text="Apply Curr MR",
            command=self._command_apply_precomputed_manual_override,
        )
        curr_override_btn.grid(row=1, column=1, sticky="w", padx=(0, 8), pady=(0, 4))
        self.command_buttons.append(curr_override_btn)
        self._attach_tooltip(curr_override_btn, "Uses Precomputed panel MR values and writes qa/manual_precomputed_overrides.csv for this step.")

        if SHOW_CLEAR_OVERRIDE_CONTROL:
            clear_override_btn = ttk.Button(command_frame, text="Clear Override", command=self._command_clear_manual_override)
            clear_override_btn.grid(row=1, column=2, sticky="w", padx=(0, 8), pady=(0, 4))
            self.command_buttons.append(clear_override_btn)
            self._attach_tooltip(clear_override_btn, "Removes any manual precomputed override rows for the selected small step and falls back to the normal precomputed results.")

        publish_qa_ref_btn = ttk.Button(
            command_frame,
            text="Publish QA Reference CSV",
            command=self._command_publish_qa_reference_csv,
        )
        publish_qa_ref_btn.grid(row=0, column=4, sticky="w", padx=(0, 8), pady=(0, 4))
        self.command_buttons.append(publish_qa_ref_btn)
        self._attach_tooltip(
            publish_qa_ref_btn,
            "Publishes precomputed_recommendations_flat_qa.csv from precomputed + manual overrides + wildcards. Atomic write; flipper_lite reads this file.",
        )

        health_btn = ttk.Button(command_frame, text="Health Check", command=self._command_health_check)
        health_btn.grid(row=1, column=3, sticky="w", padx=(0, 8), pady=(0, 4))
        self.command_buttons.append(health_btn)
        self._attach_tooltip(health_btn, "Checks whether the key QA files and FAISS assets exist and whether retrieval assets are loaded in this GUI session.")

        open_log_btn = ttk.Button(command_frame, text="Open Log", command=self._command_open_log)
        open_log_btn.grid(row=1, column=4, sticky="w", pady=(0, 4))
        self.command_buttons.append(open_log_btn)
        self._attach_tooltip(open_log_btn, "Opens the QA command log file that records command starts, completions, failures, cancels, and health checks.")

        self.cancel_job_btn = ttk.Button(
            command_frame,
            text="Cancel Active Job",
            command=self._command_cancel_active_job,
            state=tk.DISABLED,
        )
        self.cancel_job_btn.grid(row=1, column=5, sticky="w", padx=(0, 8), pady=(0, 4))
        self._attach_tooltip(self.cancel_job_btn, "Requests cancellation of the currently running subprocess-backed QA command.")

        self.retry_job_btn = ttk.Button(
            command_frame,
            text="Retry Last Failed Job",
            command=self._command_retry_last_failed,
            state=tk.DISABLED,
        )
        self.retry_job_btn.grid(row=1, column=6, sticky="w", padx=(0, 8), pady=(0, 4))
        self._attach_tooltip(self.retry_job_btn, "Re-runs the last subprocess-backed QA command that ended in failure.")

        self.job_status_label = ttk.Label(command_frame, textvariable=self.job_state_var, foreground="#1f4d7a")
        self.job_status_label.grid(row=2, column=0, columnspan=7, sticky="w", pady=(4, 0))

        self.job_step_label = ttk.Label(command_frame, textvariable=self.job_step_var, foreground="#444444")
        self.job_step_label.grid(row=3, column=0, columnspan=7, sticky="w")

        self.job_error_label = ttk.Label(command_frame, textvariable=self.job_error_var, foreground="#aa2c2c")
        self.job_error_label.grid(row=4, column=0, columnspan=7, sticky="w")

        notes_frame = ttk.LabelFrame(outer, text="Notes (optional)", padding=6)
        notes_frame.grid(row=5, column=0, sticky="ew", pady=(0, 4))
        notes_frame.columnconfigure(1, weight=1)
        ttk.Label(notes_frame, text="QA note (~15 words):").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.notes_entry = ttk.Entry(notes_frame, textvariable=self.notes_var)
        self.notes_entry.grid(row=0, column=1, sticky="ew")

        rating_options = [str(i) for i in range(1, 11)]

        results_notebook = ttk.Notebook(outer)
        results_notebook.grid(row=6, column=0, sticky="nsew")

        qa_results_tab = ttk.Frame(results_notebook, padding=6)
        qa_results_tab.columnconfigure(0, weight=1)
        qa_results_tab.columnconfigure(1, weight=1)
        qa_results_tab.rowconfigure(0, weight=1)
        results_notebook.add(qa_results_tab, text="Stage 1 QA Results")

        constraints_tab = ttk.Frame(results_notebook, padding=6)
        constraints_tab.columnconfigure(0, weight=1)
        constraints_tab.rowconfigure(2, weight=1)
        results_notebook.add(constraints_tab, text="Stage 2 Constraints Gate")

        alignment_tab = None
        if SHOW_ALIGNMENT_TAB:
            alignment_tab = ttk.Frame(results_notebook, padding=6)
            alignment_tab.columnconfigure(0, weight=1)
            alignment_tab.rowconfigure(1, weight=1)
            results_notebook.add(alignment_tab, text="Stage 3 Alignment")

        stage4_tab = None
        if SHOW_STAGE4_TAB:
            stage4_tab = ttk.Frame(results_notebook, padding=6)
            stage4_tab.columnconfigure(0, weight=1)
            stage4_tab.rowconfigure(1, weight=1)
            stage4_tab.rowconfigure(3, weight=1)
            results_notebook.add(stage4_tab, text="Stage 4 Pedagogy + Final Ranking")

        precomp_frame = ttk.LabelFrame(qa_results_tab, text="Precomputed Picks (Current)", padding=6)
        precomp_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        precomp_frame.columnconfigure(1, weight=1)
        candidate_results_frame = ttk.LabelFrame(qa_results_tab, text="Candidate Search Results", padding=6)
        candidate_results_frame.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        candidate_results_frame.columnconfigure(1, weight=1)

        ttk.Label(
            candidate_results_frame,
            textvariable=self.candidate_panel_state_var,
            foreground="#555555",
        ).grid(row=0, column=0, columnspan=9, sticky="w", padx=4, pady=(0, 4))

        ttk.Label(
            precomp_frame,
            textvariable=self.precomputed_panel_state_var,
            foreground="#555555",
        ).grid(row=0, column=0, columnspan=9, sticky="w", padx=4, pady=(0, 4))

        precomp_headers = ["#", "Title", "Ch", "Sc", "MR", "O", "D", "X", "Rt"]
        candidate_headers = ["#", "Title", "Ch", "Sc", "MR", "O", "D", "X", "Rt"]
        for col, header in enumerate(precomp_headers):
            ttk.Label(precomp_frame, text=header, font=("Segoe UI", 10, "bold")).grid(row=1, column=col, sticky="w", padx=4, pady=(0, 4))
        for col, header in enumerate(candidate_headers):
            ttk.Label(candidate_results_frame, text=header, font=("Segoe UI", 10, "bold")).grid(row=1, column=col, sticky="w", padx=4, pady=(0, 4))

        # Precomputed (current) panel rows — always TOP_K = 3
        for i in range(TOP_K):
            row_num = i + 1
            ttk.Label(precomp_frame, text=f"{row_num}").grid(row=row_num + 1, column=0, sticky="w", padx=4, pady=2)

            p_title = ttk.Label(precomp_frame, text="", width=58)
            p_title.grid(row=row_num + 1, column=1, sticky="w", padx=4, pady=2)
            self.precomputed_title_labels.append(p_title)

            p_channel = ttk.Label(precomp_frame, text="", width=12)
            p_channel.grid(row=row_num + 1, column=2, sticky="w", padx=4, pady=2)
            self.precomputed_channel_labels.append(p_channel)

            p_score = ttk.Label(precomp_frame, text="", width=6)
            p_score.grid(row=row_num + 1, column=3, sticky="w", padx=4, pady=2)
            self.precomputed_score_labels.append(p_score)

            p_rank_var = tk.StringVar(value=str(row_num))
            self.precomputed_rank_vars.append(p_rank_var)
            p_rank_menu = tk.OptionMenu(
                precomp_frame,
                p_rank_var,
                *[str(rank_option) for rank_option in range(1, TOP_K + 1)],
                command=lambda _v, idx=i: self._on_precomputed_rank_change(idx),
            )
            p_rank_menu.grid(row=row_num + 1, column=4, sticky="w", padx=4, pady=2)
            p_rank_menu.config(width=2)
            self.precomputed_rank_dropdowns.append(p_rank_menu)

            p_open = ttk.Button(precomp_frame, text="O", command=lambda idx=i: self._open_precomputed_video(idx), state=tk.DISABLED)
            p_open.grid(row=row_num + 1, column=5, sticky="w", padx=4, pady=2)
            self.precomputed_open_buttons.append(p_open)

            p_delete = ttk.Button(
                precomp_frame,
                text="Add",
                command=lambda idx=i: self._append_result_to_videos_to_delete("current", idx),
                state=tk.DISABLED,
            )
            p_delete.grid(row=row_num + 1, column=6, sticky="w", padx=4, pady=2)
            self.precomputed_delete_buttons.append(p_delete)

            p_knockout = ttk.Button(
                precomp_frame,
                text="Excl",
                command=lambda idx=i: self._toggle_precomputed_knockout(idx),
                state=tk.DISABLED,
            )
            p_knockout.grid(row=row_num + 1, column=7, sticky="w", padx=4, pady=2)
            self.precomputed_knockout_buttons.append(p_knockout)

            p_rating_var = tk.StringVar(value="5")
            self.precomputed_rating_vars.append(p_rating_var)
            p_menu = tk.OptionMenu(precomp_frame, p_rating_var, *rating_options, command=lambda _v, idx=i: self._on_precomputed_rating_change(idx))
            p_menu.grid(row=row_num + 1, column=8, sticky="w", padx=4, pady=2)
            p_menu.config(width=2)
            self.precomputed_rating_dropdowns.append(p_menu)
            self._apply_precomputed_rating_color(i)

        # Candidate panel rows — CANDIDATE_DISPLAY_K = 10 (up to 10 search results shown)
        for i in range(CANDIDATE_DISPLAY_K):
            row_num = i + 1
            ttk.Label(candidate_results_frame, text=f"{row_num}").grid(row=row_num + 1, column=0, sticky="w", padx=4, pady=2)

            c_title = ttk.Label(candidate_results_frame, text="", width=58)
            c_title.grid(row=row_num + 1, column=1, sticky="w", padx=4, pady=2)
            self.result_title_labels.append(c_title)

            c_channel = ttk.Label(candidate_results_frame, text="", width=12)
            c_channel.grid(row=row_num + 1, column=2, sticky="w", padx=4, pady=2)
            self.result_channel_labels.append(c_channel)

            c_score = ttk.Label(candidate_results_frame, text="", width=6)
            c_score.grid(row=row_num + 1, column=3, sticky="w", padx=4, pady=2)
            self.result_score_labels.append(c_score)

            c_rank_var = tk.StringVar(value=str(row_num))
            self.candidate_rank_vars.append(c_rank_var)
            c_rank_menu = tk.OptionMenu(
                candidate_results_frame,
                c_rank_var,
                *[str(rank_option) for rank_option in range(1, CANDIDATE_DISPLAY_K + 1)],
                command=lambda _v, idx=i: self._on_candidate_rank_change(idx),
            )
            c_rank_menu.grid(row=row_num + 1, column=4, sticky="w", padx=4, pady=2)
            c_rank_menu.config(width=2)
            self.candidate_rank_dropdowns.append(c_rank_menu)

            c_open = ttk.Button(candidate_results_frame, text="O", command=lambda idx=i: self._open_video(idx), state=tk.DISABLED)
            c_open.grid(row=row_num + 1, column=5, sticky="w", padx=4, pady=2)
            self.result_open_buttons.append(c_open)

            c_delete = ttk.Button(
                candidate_results_frame,
                text="Add",
                command=lambda idx=i: self._append_result_to_videos_to_delete("candidate", idx),
                state=tk.DISABLED,
            )
            c_delete.grid(row=row_num + 1, column=6, sticky="w", padx=4, pady=2)
            self.candidate_delete_buttons.append(c_delete)

            c_knockout = ttk.Button(
                candidate_results_frame,
                text="Excl",
                command=lambda idx=i: self._toggle_candidate_knockout(idx),
                state=tk.DISABLED,
            )
            c_knockout.grid(row=row_num + 1, column=7, sticky="w", padx=4, pady=2)
            self.candidate_knockout_buttons.append(c_knockout)

            c_rating_var = tk.StringVar(value="5")
            self.rating_vars.append(c_rating_var)
            # tk.OptionMenu allows per-widget background color updates.
            c_menu = tk.OptionMenu(candidate_results_frame, c_rating_var, *rating_options, command=lambda _v, idx=i: self._on_rating_change(idx))
            c_menu.grid(row=row_num + 1, column=8, sticky="w", padx=4, pady=2)
            c_menu.config(width=2)
            self.rating_dropdowns.append(c_menu)
            self._apply_rating_color(i)

        constraints_controls = ttk.LabelFrame(constraints_tab, text="Stage 2 Constraints Gate", padding=6)
        constraints_controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        constraints_controls.columnconfigure(1, weight=1)

        ttk.Label(constraints_controls, textvariable=self.constraints_step_label_var).grid(
            row=0,
            column=0,
            columnspan=5,
            sticky="w",
            pady=(0, 6),
        )

        ttk.Label(constraints_controls, text="objective_core (target objective terms for retrieval context):").grid(
            row=1,
            column=0,
            sticky="nw",
            padx=(0, 8),
        )
        self.constraints_objective_core_entry = ttk.Entry(
            constraints_controls,
            textvariable=self.constraints_objective_core_var,
        )
        self.constraints_objective_core_entry.grid(row=1, column=1, columnspan=4, sticky="ew")

        ttk.Label(constraints_controls, text="must_include (comma/semicolon-separated terms, any match passes include rule):").grid(
            row=2,
            column=0,
            sticky="nw",
            padx=(0, 8),
            pady=(6, 0),
        )
        self.constraints_must_include_entry = ttk.Entry(
            constraints_controls,
            textvariable=self.constraints_must_include_var,
        )
        self.constraints_must_include_entry.grid(row=2, column=1, columnspan=4, sticky="ew", pady=(6, 0))

        ttk.Label(constraints_controls, text="must_not_include (comma/semicolon-separated blocked terms):").grid(
            row=3,
            column=0,
            sticky="nw",
            padx=(0, 8),
            pady=(6, 0),
        )
        self.constraints_must_not_include_entry = ttk.Entry(
            constraints_controls,
            textvariable=self.constraints_must_not_include_var,
        )
        self.constraints_must_not_include_entry.grid(row=3, column=1, columnspan=4, sticky="ew", pady=(6, 0))

        ttk.Label(constraints_controls, text="numerical/domain (e.g. up to 20):").grid(
            row=4,
            column=0,
            sticky="nw",
            padx=(0, 8),
            pady=(6, 0),
        )
        self.constraints_numerical_domain_entry = ttk.Entry(
            constraints_controls,
            textvariable=self.constraints_numerical_domain_var,
        )
        self.constraints_numerical_domain_entry.grid(row=4, column=1, columnspan=4, sticky="ew", pady=(6, 0))

        ttk.Label(constraints_controls, text="reject_rule_fail_gate (e.g. divisible by 10):").grid(
            row=5,
            column=0,
            sticky="nw",
            padx=(0, 8),
            pady=(6, 0),
        )
        self.constraints_reject_rule_fail_gate_entry = ttk.Entry(
            constraints_controls,
            textvariable=self.constraints_reject_rule_fail_gate_var,
        )
        self.constraints_reject_rule_fail_gate_entry.grid(row=5, column=1, columnspan=4, sticky="ew", pady=(6, 0))

        ttk.Label(constraints_controls, text="FAISS shortlist k:").grid(row=6, column=0, sticky="w", padx=(0, 6), pady=(8, 0))
        self.constraints_k_spin = tk.Spinbox(
            constraints_controls,
            from_=5,
            to=CONSTRAINTS_GATE_MAX_K,
            width=6,
            textvariable=self.constraints_k_var,
            increment=1,
        )
        self.constraints_k_spin.grid(row=6, column=1, sticky="w", pady=(8, 0))

        self.constraints_save_btn = ttk.Button(
            constraints_controls,
            text="Save Constraints",
            command=self._save_constraints_text,
        )
        self.constraints_save_btn.grid(row=6, column=2, sticky="w", padx=(8, 0), pady=(8, 0))

        self.constraints_run_btn = ttk.Button(
            constraints_controls,
            text="Run Constraints Gate",
            command=self._run_constraints_gate_test,
            state=tk.DISABLED,
        )
        self.constraints_run_btn.grid(row=6, column=3, sticky="w", padx=(12, 0), pady=(8, 0))

        ttk.Label(constraints_controls, textvariable=self.constraints_status_var, foreground="blue").grid(
            row=7,
            column=0,
            columnspan=5,
            sticky="w",
            pady=(8, 0),
        )

        summary_frame = ttk.LabelFrame(constraints_tab, text="Gate Summary", padding=6)
        summary_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(summary_frame, textvariable=self.constraints_summary_var, foreground="#555555").grid(row=0, column=0, sticky="w")

        constraints_results_frame = ttk.LabelFrame(constraints_tab, text="FAISS -> Gate Outcome", padding=6)
        constraints_results_frame.grid(row=2, column=0, sticky="nsew")
        constraints_results_frame.columnconfigure(1, weight=1)

        constraints_headers = ["Rank", "Title (video_id)", "Semantic", "Gate", "Reason", "Open"]
        for col, header in enumerate(constraints_headers):
            ttk.Label(constraints_results_frame, text=header, font=("Segoe UI", 10, "bold")).grid(
                row=0,
                column=col,
                sticky="w",
                padx=4,
                pady=(0, 4),
            )

        for i in range(10):
            row_num = i + 1
            ttk.Label(constraints_results_frame, text=f"{row_num}").grid(row=row_num, column=0, sticky="w", padx=4, pady=2)

            title_label = ttk.Label(constraints_results_frame, text="", width=56)
            title_label.grid(row=row_num, column=1, sticky="w", padx=4, pady=2)
            self.constraints_title_labels.append(title_label)

            semantic_label = ttk.Label(constraints_results_frame, text="", width=10)
            semantic_label.grid(row=row_num, column=2, sticky="w", padx=4, pady=2)
            self.constraints_score_labels.append(semantic_label)

            gate_label = ttk.Label(constraints_results_frame, text="", width=8)
            gate_label.grid(row=row_num, column=3, sticky="w", padx=4, pady=2)
            self.constraints_gate_labels.append(gate_label)

            reason_label = ttk.Label(constraints_results_frame, text="", width=58)
            reason_label.grid(row=row_num, column=4, sticky="w", padx=4, pady=2)
            self.constraints_reason_labels.append(reason_label)

            open_btn = ttk.Button(
                constraints_results_frame,
                text="Open",
                command=lambda idx=i: self._open_constraints_video(idx),
                state=tk.DISABLED,
            )
            open_btn.grid(row=row_num, column=5, sticky="w", padx=4, pady=2)
            self.constraints_open_buttons.append(open_btn)

        if SHOW_ALIGNMENT_TAB and alignment_tab is not None:
            ttk.Label(
                alignment_tab,
                text="Stage 1 candidate picks filtered by Stage 2 constraints gate (PASS only).",
                foreground="#555555",
            ).grid(row=0, column=0, sticky="w", pady=(0, 6))

            alignment_results_frame = ttk.LabelFrame(alignment_tab, text="Stage 3 Alignment Scoring Input Set", padding=6)
            alignment_results_frame.grid(row=1, column=0, sticky="nsew")
            alignment_results_frame.columnconfigure(0, weight=1)
            alignment_results_frame.rowconfigure(0, weight=1)

            self.alignment_tree = ttk.Treeview(
                alignment_results_frame,
                columns=("rank", "title", "channel", "gate", "alignment", "combined"),
                show="headings",
                height=8,
            )
            self.alignment_tree.grid(row=0, column=0, sticky="nsew")
            self.alignment_tree.heading("rank", text="Rank")
            self.alignment_tree.heading("title", text="Title (video_id)")
            self.alignment_tree.heading("channel", text="Channel")
            self.alignment_tree.heading("gate", text="Stage 2 Gate")
            self.alignment_tree.heading("alignment", text="Stage 3 Alignment")
            self.alignment_tree.heading("combined", text="Combined")
            self.alignment_tree.column("rank", width=60, anchor="w")
            self.alignment_tree.column("title", width=520, anchor="w")
            self.alignment_tree.column("channel", width=180, anchor="w")
            self.alignment_tree.column("gate", width=100, anchor="w")
            self.alignment_tree.column("alignment", width=110, anchor="w")
            self.alignment_tree.column("combined", width=110, anchor="w")
            self.alignment_tree.bind("<Double-1>", self._open_selected_alignment_video)

            alignment_scroll = ttk.Scrollbar(alignment_results_frame, orient="vertical", command=self.alignment_tree.yview)
            alignment_scroll.grid(row=0, column=1, sticky="ns")
            self.alignment_tree.configure(yscrollcommand=alignment_scroll.set)

            ttk.Label(
                alignment_results_frame,
                text="All Stage 2 PASS survivors are scored here. Double-click a row to open the video.",
                foreground="#555555",
            ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        if SHOW_STAGE4_TAB and stage4_tab is not None:
            ttk.Label(
                stage4_tab,
                text="Stage 4 uses instruction (pedagogy) to rerank survivors from Stages 1-3.",
                foreground="#555555",
            ).grid(row=0, column=0, sticky="w", pady=(0, 6))

            stage4_survivors_frame = ttk.LabelFrame(stage4_tab, text="Input Survivors (Stages 1-3)", padding=6)
            stage4_survivors_frame.grid(row=1, column=0, sticky="nsew")
            stage4_survivors_frame.columnconfigure(0, weight=1)
            stage4_survivors_frame.rowconfigure(0, weight=1)

            self.stage4_survivors_tree = ttk.Treeview(
                stage4_survivors_frame,
                columns=("rank", "title", "stage3", "instruction"),
                show="headings",
                height=8,
            )
            self.stage4_survivors_tree.grid(row=0, column=0, sticky="nsew")

            self.stage4_survivors_tree.heading("rank", text="Rank")
            self.stage4_survivors_tree.heading("title", text="Title (video_id)")
            self.stage4_survivors_tree.heading("stage3", text="Stage 3 Alignment")
            self.stage4_survivors_tree.heading("instruction", text="Stage 4 Instruction")

            self.stage4_survivors_tree.column("rank", width=60, anchor="w")
            self.stage4_survivors_tree.column("title", width=640, anchor="w")
            self.stage4_survivors_tree.column("stage3", width=100, anchor="w")
            self.stage4_survivors_tree.column("instruction", width=100, anchor="w")

            survivors_scroll = ttk.Scrollbar(stage4_survivors_frame, orient="vertical", command=self.stage4_survivors_tree.yview)
            survivors_scroll.grid(row=0, column=1, sticky="ns")
            self.stage4_survivors_tree.configure(yscrollcommand=survivors_scroll.set)

            stage4_final_frame = ttk.LabelFrame(stage4_tab, text="Final Ranking Top 3 (After Stage 4)", padding=6)
            stage4_final_frame.grid(row=3, column=0, sticky="nsew", pady=(8, 0))
            stage4_final_frame.columnconfigure(1, weight=1)

            final_headers = ["Rank", "Title (video_id)", "Stage 3 Alignment", "Stage 4 Instruction", "Stage 5 Final", "Open"]
            for col, header in enumerate(final_headers):
                ttk.Label(stage4_final_frame, text=header, font=("Segoe UI", 10, "bold")).grid(
                    row=0,
                    column=col,
                    sticky="w",
                    padx=4,
                    pady=(0, 4),
                )

            for i in range(TOP_K):
                row_num = i + 1
                ttk.Label(stage4_final_frame, text=f"{row_num}").grid(row=row_num, column=0, sticky="w", padx=4, pady=2)

                final_title = ttk.Label(stage4_final_frame, text="", width=56)
                final_title.grid(row=row_num, column=1, sticky="w", padx=4, pady=2)
                self.stage4_final_title_labels.append(final_title)

                final_stage3 = ttk.Label(stage4_final_frame, text="", width=10)
                final_stage3.grid(row=row_num, column=2, sticky="w", padx=4, pady=2)
                self.stage4_final_stage3_labels.append(final_stage3)

                final_instruction = ttk.Label(stage4_final_frame, text="", width=10)
                final_instruction.grid(row=row_num, column=3, sticky="w", padx=4, pady=2)
                self.stage4_final_instruction_labels.append(final_instruction)

                final_score = ttk.Label(stage4_final_frame, text="", width=10)
                final_score.grid(row=row_num, column=4, sticky="w", padx=4, pady=2)
                self.stage4_final_score_labels.append(final_score)

                final_open = ttk.Button(
                    stage4_final_frame,
                    text="Open",
                    command=lambda idx=i: self._open_stage4_final_video(idx),
                    state=tk.DISABLED,
                )
                final_open.grid(row=row_num, column=5, sticky="w", padx=4, pady=2)
                self.stage4_final_open_buttons.append(final_open)

            self.stage4_save_btn = ttk.Button(
                stage4_tab,
                text="Save Final Ranking to QA CSV",
                command=self._update_qa_csv,
            )
            self.stage4_save_btn.grid(row=2, column=0, sticky="w", pady=(8, 0))

        # Adjacent steps tab — always visible regardless of SHOW_* flags
        dup_neighbours_tab = ttk.Frame(results_notebook, padding=6)
        dup_neighbours_tab.columnconfigure(0, weight=1)
        dup_neighbours_tab.rowconfigure(1, weight=1)
        results_notebook.add(dup_neighbours_tab, text="Adjacent Steps")
        ttk.Label(
            dup_neighbours_tab,
            text=(
                f"Adjacent steps (±{DUP_NEIGHBOUR_RADIUS}) in global curriculum order. "
                "Helps decide if the current step semantically overlaps neighbours. "
                "Use 'Mark Step Redundant' above to mark steps for removal."
            ),
            foreground="#555555",
            wraplength=900,
            justify=tk.LEFT,
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.dup_neighbour_text = scrolledtext.ScrolledText(
            dup_neighbours_tab,
            wrap=tk.WORD,
            height=18,
            state=tk.DISABLED,
            font=("Consolas", 9),
        )
        self.dup_neighbour_text.grid(row=1, column=0, sticky="nsew")

        self._refresh_command_controls()

    def _attach_tooltip(self, widget: tk.Widget, text: str) -> None:
        tooltip = ToolTip(widget, text)
        self.command_tooltips.append(tooltip)

    def _python_cmd_prefix(self) -> list[str]:
        exe_path = Path(sys.executable)
        exe_name = exe_path.name.lower()
        if exe_name == "pythonw.exe":
            candidate = exe_path.with_name("python.exe")
            if candidate.exists():
                return [str(candidate)]
        return [str(exe_path)]

    def _append_command_log(self, message: str) -> None:
        QA_COMMAND_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        stamped = f"[{datetime.now().isoformat(timespec='seconds')}] {message}\n"
        with self.log_lock:
            with QA_COMMAND_LOG_PATH.open("a", encoding="utf-8") as handle:
                handle.write(stamped)

    def _set_job_state(self, state: str, step_text: str = "", error_text: str = "") -> None:
        self.active_job_state = state
        if state == JOB_STATE_RUNNING:
            self.job_state_var.set(f"Job state: running ({self.active_job_name or 'job'})")
        else:
            self.job_state_var.set(f"Job state: {state}")
        if step_text:
            self.job_step_var.set(f"Current step status: {step_text}")
        if error_text:
            self.job_error_var.set(error_text)
        elif state != JOB_STATE_FAILED:
            self.job_error_var.set("")
        self._refresh_command_controls()

    def _refresh_command_controls(self) -> None:
        running = self.active_job_state == JOB_STATE_RUNNING
        for btn in self.command_buttons:
            btn.config(state=tk.DISABLED if running else tk.NORMAL)
        if self.cancel_job_btn is not None:
            self.cancel_job_btn.config(state=tk.NORMAL if running else tk.DISABLED)
        if self.retry_job_btn is not None:
            self.retry_job_btn.config(
                state=tk.NORMAL if (not running and self.last_failed_subprocess_spec is not None) else tk.DISABLED
            )

    def _start_subprocess_job(self, job_name: str, command: list[str], reload_assets: bool) -> None:
        if self.active_job_state == JOB_STATE_RUNNING:
            messagebox.showwarning("Job running", "Another QA command is already running.")
            return

        self.active_job_name = job_name
        self.cancel_requested = False
        self._set_job_state(JOB_STATE_RUNNING, step_text=f"Starting {job_name}...")
        self._append_command_log(f"START {job_name}: {' '.join(command)}")

        worker = threading.Thread(
            target=self._subprocess_job_worker,
            args=(job_name, command, reload_assets),
            daemon=True,
        )
        self.active_job_thread = worker
        worker.start()

    def _subprocess_job_worker(self, job_name: str, command: list[str], reload_assets: bool) -> None:
        process: subprocess.Popen | None = None
        output_lines: list[str] = []
        was_cancelled = False
        try:
            child_env = dict(os.environ)
            child_env["PYTHONUTF8"] = "1"
            child_env["PYTHONIOENCODING"] = "utf-8"
            process = subprocess.Popen(
                command,
                cwd=str(project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=child_env,
                bufsize=1,
            )
            self.active_process = process

            while True:
                if self.cancel_requested and process.poll() is None:
                    was_cancelled = True
                    process.terminate()

                if process.stdout is None:
                    break

                line = process.stdout.readline()
                if line:
                    output_lines.append(line.decode("utf-8", errors="replace"))
                elif process.poll() is not None:
                    break
                else:
                    time.sleep(0.05)

            return_code = process.wait()
            captured_output = "".join(output_lines).strip()
            if captured_output:
                self._append_command_log(captured_output)

            if was_cancelled:
                self.root.after(0, self._on_subprocess_job_cancelled, job_name)
                return

            if return_code in WINDOWS_CTRL_C_EXIT_CODES:
                interruption_message = (
                    f"{job_name} was interrupted (exit code {return_code}, Windows 0xC000013A). "
                    "This usually means the process received an external stop signal."
                )
                self.root.after(0, self._on_subprocess_job_error, job_name, interruption_message, command, reload_assets)
                return

            if return_code != 0:
                raise RuntimeError(f"{job_name} failed with exit code {return_code}. See log for details.")

            self.root.after(0, self._on_subprocess_job_success, job_name, reload_assets)
        except Exception as exc:
            self.root.after(0, self._on_subprocess_job_error, job_name, str(exc), command, reload_assets)
        finally:
            self.active_process = None

    def _on_subprocess_job_success(self, job_name: str, reload_assets: bool) -> None:
        self._append_command_log(f"DONE {job_name}")
        self._set_job_state(JOB_STATE_DONE, step_text=f"Completed {job_name}")
        self.status_var.set(f"{job_name} completed.")
        self.last_failed_subprocess_spec = None
        if reload_assets:
            if job_name == "Apply Delete Queue":
                self.status_var.set(f"{job_name} completed. Soft delete finished; refreshing deleted-video state...")
                self._refresh_after_soft_delete()
            else:
                self.status_var.set(f"{job_name} completed. Reloading retrieval assets...")
                worker = threading.Thread(target=self._load_heavy_assets, daemon=True)
                worker.start()

    def _on_subprocess_job_error(
        self,
        job_name: str,
        error_message: str,
        command: list[str],
        reload_assets: bool,
    ) -> None:
        self._append_command_log(f"FAIL {job_name}: {error_message}")
        self.last_failed_subprocess_spec = (job_name, list(command), reload_assets)
        self._set_job_state(JOB_STATE_FAILED, step_text=f"Failed {job_name}", error_text=error_message)
        self.status_var.set(f"{job_name} failed")
        messagebox.showerror("QA Command Error", error_message)

    def _on_subprocess_job_cancelled(self, job_name: str) -> None:
        self._append_command_log(f"CANCELLED {job_name}")
        self._set_job_state(JOB_STATE_CANCELLED, step_text=f"Cancelled {job_name}")
        self.status_var.set(f"{job_name} cancelled")

    def _command_apply_delete_queue(self) -> None:
        if not VIDEOS_TO_DELETE_PATH.exists():
            messagebox.showwarning("Missing delete queue", f"Delete queue file not found:\n{VIDEOS_TO_DELETE_PATH}")
            return

        try:
            delete_df = pd.read_csv(VIDEOS_TO_DELETE_PATH)
        except Exception as exc:
            messagebox.showerror("Delete queue error", str(exc))
            return

        if delete_df.empty:
            messagebox.showinfo("Delete queue", "Delete queue is empty. Nothing to apply.")
            return

        if not messagebox.askyesno(
            "Confirm delete queue",
            "Apply queued deletions now? This performs soft delete only: local assets and metadata are removed now, deleted-video tracking is updated, and full FAISS rebuild remains a separate step.",
        ):
            return

        command = self._python_cmd_prefix() + [
            "delete_content.py",
            "--batch",
            str(VIDEOS_TO_DELETE_PATH),
            "--yes",
        ]
        self._start_subprocess_job("Apply Delete Queue", command, reload_assets=True)

    def _command_full_rebuild_faiss(self) -> None:
        if not messagebox.askyesno(
            "Confirm full rebuild",
            "Run full chunk/embed/index rebuild now? This can take significant time.",
        ):
            return

        command = self._python_cmd_prefix() + [
            "data_pipeline/run_pipeline.py",
            "--index-only",
            "--rebuild-index",
        ]
        self._start_subprocess_job("Full Rebuild FAISS", command, reload_assets=True)

    def _command_sync_new_downloads(self) -> None:
        command = self._python_cmd_prefix() + [
            "data_pipeline/run_pipeline.py",
            "--index-only",
        ]
        self._start_subprocess_job("Sync New Downloads", command, reload_assets=True)

    def _command_finalize_current_step(self) -> None:
        if self.active_job_state == JOB_STATE_RUNNING:
            messagebox.showwarning("Job running", "Another QA command is already running.")
            return
        self._set_job_state(JOB_STATE_RUNNING, step_text="Updating qa.csv for selected step")
        self._append_command_log("START Approve + Update QA CSV")
        try:
            self._update_qa_csv()
            self._set_job_state(JOB_STATE_DONE, step_text="Updated qa.csv for selected step")
            self._append_command_log("DONE Approve + Update QA CSV")
        except Exception as exc:
            error_text = str(exc)
            self._set_job_state(JOB_STATE_FAILED, step_text="Approve/finalize failed", error_text=error_text)
            self._append_command_log(f"FAIL Approve + Update QA CSV: {error_text}")

    def _reload_wildcards_df(self) -> None:
        self.wildcard_df = _read_wildcard_rows(WILDCARD_OVERRIDE_PATH)

    def _get_wildcard_for_step(self, small_step_id: str) -> dict[str, str]:
        if self.wildcard_df.empty or not small_step_id:
            return {}
        matches = self.wildcard_df[self.wildcard_df["small_step_id"] == small_step_id]
        if matches.empty:
            return {}
        row = matches.iloc[-1]
        video_id = clean_text(row.get("video_id"))
        title = clean_text(row.get("title"))
        channel = clean_text(row.get("channel"))

        # Fallback: infer video_id from precomputed rows when wildcard CSV omits video_id.
        if not video_id and not self.precomputed_df.empty:
            step_rows = self.precomputed_df[self.precomputed_df["small_step_id"] == small_step_id].copy()
            if "rank" in step_rows.columns:
                step_rows = step_rows.sort_values("rank")

            if title:
                title_mask = (
                    step_rows.get("title", pd.Series(dtype=str)).map(clean_text) == title
                ) | (
                    step_rows.get("video_title", pd.Series(dtype=str)).map(clean_text) == title
                )
                title_matches = step_rows[title_mask]
                if not title_matches.empty:
                    video_id = clean_text(title_matches.iloc[0].get("video_id"))

            if not video_id and channel:
                channel_mask = step_rows.get("channel", pd.Series(dtype=str)).map(clean_text) == channel
                channel_matches = step_rows[channel_mask]
                if len(channel_matches) == 1:
                    video_id = clean_text(channel_matches.iloc[0].get("video_id"))

        return {
            "video_id": video_id,
            "title": title,
            "channel": channel,
        }

    def _get_precomputed_base_results_for_step(self, small_step_id: str) -> list[dict[str, object]]:
        if self.precomputed_df.empty or not small_step_id:
            return []

        step_rows = self.precomputed_df[self.precomputed_df["small_step_id"] == small_step_id]
        if "rank" in step_rows.columns:
            step_rows = step_rows.sort_values("rank")
        picks = step_rows.head(TOP_K).reset_index(drop=True)

        rows: list[dict[str, object]] = []
        for i in range(len(picks)):
            r = picks.iloc[i]
            rows.append(
                {
                    "video_id": clean_text(r.get("video_id")),
                    "title": clean_text(r.get("title") or r.get("video_title")),
                    "channel": clean_text(r.get("channel")),
                    "combined_score": float(r.get("combined_score") or 0.0),
                    "semantic_score": clean_text(r.get("semantic_score")),
                    "instruction_score": clean_text(r.get("instruction_score")),
                    "alignment_score": clean_text(r.get("alignment_score")),
                }
            )
        return rows

    def _apply_wildcard_to_results(
        self,
        small_step_id: str,
        base_results: list[dict[str, object]],
    ) -> tuple[list[dict[str, object]], bool]:
        wildcard = self._get_wildcard_for_step(small_step_id)
        if not wildcard:
            return base_results[:TOP_K], False

        wildcard_video_id = clean_text(wildcard.get("video_id"))
        wildcard_title = clean_text(wildcard.get("title"))
        wildcard_channel = clean_text(wildcard.get("channel"))

        wildcard_row = {
            "video_id": wildcard_video_id,
            "title": wildcard_title,
            "channel": wildcard_channel,
            "combined_score": 100,
            "semantic_score": 100,
            "instruction_score": 100,
            "alignment_score": "",
        }

        demoted = [
            item for item in base_results
            if clean_text(item.get("video_id")) != wildcard_video_id
        ]
        return [wildcard_row, *demoted[: TOP_K - 1]], True

    def _build_effective_precomputed_results_for_step(self, small_step_id: str) -> tuple[list[dict[str, object]], str]:
        manual_override_rows = self._read_manual_override_for_step(small_step_id)
        if manual_override_rows:
            base_rows = manual_override_rows
            source = "manual override"
        else:
            base_rows = self._get_precomputed_base_results_for_step(small_step_id)
            source = "precomputed base"

        effective_rows, wildcard_applied = self._apply_wildcard_to_results(small_step_id, base_rows)
        if wildcard_applied and source == "manual override":
            source = "manual override + wildcard rank-1"
        elif wildcard_applied:
            source = "precomputed base + wildcard rank-1"

        return effective_rows, source

    def _build_publish_rows_for_step(self, step_df: pd.DataFrame, effective_results: list[dict[str, object]]) -> pd.DataFrame:
        if step_df.empty or not effective_results:
            return pd.DataFrame(columns=step_df.columns)

        template = step_df.iloc[0].to_dict()
        new_rows: list[dict[str, object]] = []
        for rank_idx, result in enumerate(effective_results[:TOP_K], start=1):
            row = dict(template)
            if "rank" in row:
                row["rank"] = rank_idx
            if "recommendation_num" in row:
                row["recommendation_num"] = rank_idx
            if "video_id" in row:
                row["video_id"] = clean_text(result.get("video_id"))
            if "title" in row:
                row["title"] = clean_text(result.get("title"))
            if "video_title" in row:
                row["video_title"] = clean_text(result.get("title"))
            if "channel" in row:
                row["channel"] = clean_text(result.get("channel"))
            if "combined_score" in row:
                row["combined_score"] = clean_text(result.get("combined_score"))
            if "semantic_score" in row:
                row["semantic_score"] = clean_text(result.get("semantic_score"))
            if "instruction_score" in row:
                row["instruction_score"] = clean_text(result.get("instruction_score"))
            if "alignment_score" in row:
                row["alignment_score"] = clean_text(result.get("alignment_score"))
            new_rows.append(row)

        return pd.DataFrame(new_rows, columns=step_df.columns)

    def _build_published_precomputed_df(self) -> tuple[pd.DataFrame, dict[str, int]]:
        base_df = self.precomputed_df.copy()
        if base_df.empty:
            raise ValueError("Cannot publish QA reference CSV because precomputed_recommendations_flat.csv is empty.")

        if "small_step_id" not in base_df.columns:
            raise ValueError("precomputed dataframe is missing required column: small_step_id")

        if "rank" not in base_df.columns:
            raise ValueError("precomputed dataframe is missing required column: rank")

        base_df["small_step_id"] = base_df["small_step_id"].map(clean_text)
        rank_numeric = pd.to_numeric(base_df["rank"], errors="coerce")

        overrides_df = self._load_manual_precomputed_overrides_df()
        manual_steps = set(
            overrides_df[
                (overrides_df["status"].str.lower() != "inactive")
                & (overrides_df["small_step_id"].str.len() > 0)
            ]["small_step_id"].tolist()
        )
        wildcard_steps = set(self.wildcard_df["small_step_id"].tolist()) if not self.wildcard_df.empty else set()
        target_steps = sorted(manual_steps | wildcard_steps)

        if not target_steps:
            return base_df, {
                "steps_touched": 0,
                "wildcard_steps": 0,
                "manual_steps": 0,
                "skipped_steps": 0,
            }

        keep_mask = ~(
            base_df["small_step_id"].isin(target_steps)
            & rank_numeric.notna()
            & (rank_numeric <= TOP_K)
        )
        output_df = base_df[keep_mask].copy()

        replacement_frames: list[pd.DataFrame] = []
        wildcard_count = 0
        manual_count = 0
        skipped_count = 0

        for small_step_id in target_steps:
            step_df = base_df[base_df["small_step_id"] == small_step_id].copy()
            if step_df.empty:
                skipped_count += 1
                continue

            effective_rows, source_label = self._build_effective_precomputed_results_for_step(small_step_id)
            if not effective_rows:
                skipped_count += 1
                continue

            if "wildcard" in source_label:
                wildcard_count += 1
            if "manual override" in source_label:
                manual_count += 1

            replacement_frames.append(self._build_publish_rows_for_step(step_df, effective_rows))

        if replacement_frames:
            output_df = pd.concat([output_df, *replacement_frames], ignore_index=True)

        output_df = output_df.sort_values(["small_step_id", "rank"], kind="stable")
        return output_df, {
            "steps_touched": len(replacement_frames),
            "wildcard_steps": wildcard_count,
            "manual_steps": manual_count,
            "skipped_steps": skipped_count,
        }

    def _command_publish_qa_reference_csv(self) -> None:
        if self.active_job_state == JOB_STATE_RUNNING:
            messagebox.showwarning("Job running", "Another QA command is already running.")
            return

        try:
            precomputed_path = project_root / "precomputed_recommendations_flat.csv"
            if precomputed_path.exists():
                precomp_df = pd.read_csv(precomputed_path)
                for col in ["small_step_id", "video_id", "title", "video_title", "channel"]:
                    if col in precomp_df.columns:
                        precomp_df[col] = precomp_df[col].map(clean_text)
                self.precomputed_df = precomp_df

            self._reload_wildcards_df()
            published_df, stats = self._build_published_precomputed_df()

            # Validation guard: enforce contiguous top ranks for each touched step.
            if "rank" in published_df.columns and "small_step_id" in published_df.columns:
                touched_steps = set(self.wildcard_df["small_step_id"].tolist())
                overrides_df = self._load_manual_precomputed_overrides_df()
                active_override_steps = set(
                    overrides_df[
                        (overrides_df["status"].str.lower() != "inactive")
                        & (overrides_df["small_step_id"].str.len() > 0)
                    ]["small_step_id"].tolist()
                )
                touched_steps |= active_override_steps
                for step_id in touched_steps:
                    step_rows = published_df[published_df["small_step_id"] == step_id].copy()
                    if step_rows.empty:
                        continue
                    step_rows["rank"] = pd.to_numeric(step_rows["rank"], errors="coerce")
                    top_rows = step_rows[step_rows["rank"].notna() & (step_rows["rank"] <= TOP_K)].sort_values("rank")
                    if top_rows.empty:
                        continue
                    expected = list(range(1, len(top_rows) + 1))
                    actual = [int(value) for value in top_rows["rank"].tolist()]
                    if actual != expected:
                        raise ValueError(f"Publish validation failed for {step_id}: expected top ranks {expected}, found {actual}")

            _atomic_write_csv(published_df, QA_REFERENCE_OUTPUT_PATH)
            self._append_command_log(
                "QA REFERENCE PUBLISHED "
                f"rows={len(published_df)} steps={stats['steps_touched']} "
                f"wildcards={stats['wildcard_steps']} manual={stats['manual_steps']} skipped={stats['skipped_steps']}"
            )
            self.status_var.set(
                f"Published QA reference CSV: steps={stats['steps_touched']}, wildcards={stats['wildcard_steps']}, manual={stats['manual_steps']}"
            )
            self._refresh_dup_review_state()
            messagebox.showinfo(
                "QA reference published",
                f"Published:\n{QA_REFERENCE_OUTPUT_PATH}\n\n"
                f"Rows: {len(published_df)}\n"
                f"Steps touched: {stats['steps_touched']}\n"
                f"Wildcard steps: {stats['wildcard_steps']}\n"
                f"Manual-override steps: {stats['manual_steps']}\n"
                f"Skipped steps: {stats['skipped_steps']}",
            )
        except Exception as exc:
            messagebox.showerror("Publish QA reference failed", str(exc))

    def _load_manual_precomputed_overrides_df(self) -> pd.DataFrame:
        columns = [
            "updated_at",
            "small_step_id",
            "rank",
            "video_id",
            "video_title",
            "channel",
            "combined_score",
            "source",
            "status",
            "notes",
        ]
        if MANUAL_PRECOMP_OVERRIDE_PATH.exists():
            overrides_df = pd.read_csv(MANUAL_PRECOMP_OVERRIDE_PATH)
        else:
            overrides_df = pd.DataFrame(columns=columns)

        for col in columns:
            if col not in overrides_df.columns:
                overrides_df[col] = ""

        overrides_df = overrides_df[columns].copy()
        overrides_df["small_step_id"] = overrides_df["small_step_id"].map(clean_text)
        overrides_df["video_id"] = overrides_df["video_id"].map(clean_text)
        overrides_df["video_title"] = overrides_df["video_title"].map(clean_text)
        overrides_df["channel"] = overrides_df["channel"].map(clean_text)
        overrides_df["source"] = overrides_df["source"].map(clean_text)
        overrides_df["status"] = overrides_df["status"].map(clean_text)
        overrides_df["notes"] = overrides_df["notes"].map(clean_text)
        overrides_df["rank"] = pd.to_numeric(overrides_df["rank"], errors="coerce").fillna(0).astype(int)
        return overrides_df

    def _read_manual_override_for_step(self, small_step_id: str) -> list[dict[str, object]]:
        if not small_step_id:
            return []
        overrides_df = self._load_manual_precomputed_overrides_df()
        step_df = overrides_df[
            (overrides_df["small_step_id"] == small_step_id)
            & (overrides_df["status"].str.lower() != "inactive")
        ].copy()
        if step_df.empty:
            return []
        step_df = step_df.sort_values(["rank", "updated_at"], kind="stable")

        rows: list[dict[str, object]] = []
        for _, override_row in step_df.head(TOP_K).iterrows():
            try:
                combined = float(clean_text(override_row.get("combined_score")) or 0.0)
            except ValueError:
                combined = 0.0
            rows.append(
                {
                    "video_id": clean_text(override_row.get("video_id")),
                    "title": clean_text(override_row.get("video_title")),
                    "channel": clean_text(override_row.get("channel")),
                    "combined_score": combined,
                    "semantic_score": "",
                    "instruction_score": "",
                    "alignment_score": "",
                }
            )
        return rows

    def _write_manual_precomputed_override_rows(
        self,
        small_step_id: str,
        ranked_results: list[dict[str, object]],
        source_note: str,
    ) -> int:
        rows: list[dict[str, object]] = []
        for idx, result in enumerate(ranked_results[:TOP_K], start=1):
            video_id = clean_text(result.get("video_id"))
            title = clean_text(result.get("title"))
            if not video_id and not title:
                continue
            rows.append(
                {
                    "updated_at": datetime.now().isoformat(timespec="seconds"),
                    "small_step_id": small_step_id,
                    "rank": idx,
                    "video_id": video_id,
                    "video_title": title,
                    "channel": clean_text(result.get("channel")),
                    "combined_score": clean_text(result.get("combined_score")),
                    "source": "qa_manual_override",
                    "status": "active",
                    "notes": source_note,
                }
            )

        if not rows:
            return 0

        overrides_df = self._load_manual_precomputed_overrides_df()
        overrides_df = overrides_df[overrides_df["small_step_id"] != small_step_id].copy()
        overrides_df = pd.concat([overrides_df, pd.DataFrame(rows)], ignore_index=True)

        MANUAL_PRECOMP_OVERRIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
        overrides_df.to_csv(MANUAL_PRECOMP_OVERRIDE_PATH, index=False)
        self._append_command_log(f"MANUAL OVERRIDE applied for {small_step_id}")
        self.status_var.set(f"Applied manual precomputed override with manual ranks for {small_step_id}")
        self._populate_precomputed(small_step_id)
        return len(rows)

    def _command_apply_manual_override(self) -> None:
        small_step_id = self._selected_small_step_id()
        if not small_step_id:
            messagebox.showwarning("Missing small step", "Select a small step first.")
            return

        if not self.latest_results:
            messagebox.showwarning("No candidate picks", "Run Search Top 3 first; then apply manual override.")
            return

        try:
            ranked_results = self._get_manual_ranked_candidate_results()
        except ValueError as exc:
            messagebox.showwarning("Manual rank invalid", str(exc))
            return

        if not ranked_results:
            messagebox.showwarning("No candidate picks", "No candidate rows available to apply.")
            return

        self.latest_results = ranked_results
        self.latest_final_results = list(ranked_results)
        self._render_candidate_search_results(self.latest_results)

        written_count = self._write_manual_precomputed_override_rows(
            small_step_id=small_step_id,
            ranked_results=ranked_results,
            source_note="applied_from_candidate_panel",
        )
        if written_count == 0:
            messagebox.showwarning("No override rows", "Current candidate panel has no rows to override.")
            return

        wildcard_active = bool(self._get_wildcard_for_step(small_step_id))
        wildcard_note = "\n\nWildcard is active for this step and remains pinned at rank 1 in current display/published QA reference."
        self._refresh_dup_review_state()
        messagebox.showinfo(
            "Manual override applied",
            f"Saved {written_count} candidate manual-rank row(s) to:\n{MANUAL_PRECOMP_OVERRIDE_PATH}"
            f"{wildcard_note if wildcard_active else ''}",
        )

    def _command_apply_precomputed_manual_override(self) -> None:
        small_step_id = self._selected_small_step_id()
        if not small_step_id:
            messagebox.showwarning("Missing small step", "Select a small step first.")
            return

        if not self.precomputed_results:
            messagebox.showwarning("No current picks", "No precomputed rows are available to re-rank.")
            return

        try:
            ranked_results = self._get_manual_ranked_precomputed_results()
        except ValueError as exc:
            messagebox.showwarning("Manual rank invalid", str(exc))
            return

        if not ranked_results:
            messagebox.showwarning("No current picks", "No precomputed rows are available to apply.")
            return

        written_count = self._write_manual_precomputed_override_rows(
            small_step_id=small_step_id,
            ranked_results=ranked_results,
            source_note="applied_from_precomputed_panel",
        )
        if written_count == 0:
            messagebox.showwarning("No override rows", "Current precomputed panel has no rows to override.")
            return

        wildcard_active = bool(self._get_wildcard_for_step(small_step_id))
        wildcard_note = "\n\nWildcard is active for this step and remains pinned at rank 1 in current display/published QA reference."
        self._refresh_dup_review_state()
        messagebox.showinfo(
            "Manual override applied",
            f"Saved {written_count} precomputed manual-rank row(s) to:\n{MANUAL_PRECOMP_OVERRIDE_PATH}"
            f"{wildcard_note if wildcard_active else ''}",
        )

    def _command_clear_manual_override(self) -> None:
        small_step_id = self._selected_small_step_id()
        if not small_step_id:
            messagebox.showwarning("Missing small step", "Select a small step first.")
            return
        overrides_df = self._load_manual_precomputed_overrides_df()
        before = len(overrides_df)
        overrides_df = overrides_df[overrides_df["small_step_id"] != small_step_id].copy()
        removed = before - len(overrides_df)
        MANUAL_PRECOMP_OVERRIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
        overrides_df.to_csv(MANUAL_PRECOMP_OVERRIDE_PATH, index=False)
        self._append_command_log(f"MANUAL OVERRIDE cleared for {small_step_id}; rows_removed={removed}")
        self.status_var.set(f"Cleared manual override for {small_step_id}")
        self._populate_precomputed(small_step_id)
        self._refresh_dup_review_state()

    def _command_cancel_active_job(self) -> None:
        if self.active_job_state != JOB_STATE_RUNNING:
            return
        self.cancel_requested = True
        self.job_step_var.set("Current step status: cancellation requested")
        self._append_command_log(f"CANCEL REQUESTED for {self.active_job_name}")

    def _command_retry_last_failed(self) -> None:
        if self.active_job_state == JOB_STATE_RUNNING:
            return
        if self.last_failed_subprocess_spec is None:
            messagebox.showinfo("Retry", "No failed subprocess command to retry.")
            return
        job_name, command, reload_assets = self.last_failed_subprocess_spec
        self._start_subprocess_job(job_name, command, reload_assets)

    def _command_health_check(self) -> None:
        checks: list[str] = []
        checks.append(f"qa.csv: {'ok' if QA_TRACKING_PATH.exists() else 'missing'}")
        checks.append(f"videos_to_delete.csv: {'ok' if VIDEOS_TO_DELETE_PATH.exists() else 'missing'}")
        checks.append(f"manual_precomputed_overrides.csv: {'ok' if MANUAL_PRECOMP_OVERRIDE_PATH.exists() else 'missing'}")
        checks.append(f"wildcards.csv: {'ok' if WILDCARD_OVERRIDE_PATH.exists() else 'missing'}")
        checks.append(f"precomputed_recommendations_flat_qa.csv: {'ok' if QA_REFERENCE_OUTPUT_PATH.exists() else 'missing'}")
        checks.append(f"step_video_knockouts.csv: {'ok' if STEP_KNOCKOUT_PATH.exists() else 'missing'}")

        faiss_bin = project_root / "data" / "faiss_index" / "faiss_index.bin"
        faiss_meta = project_root / "data" / "faiss_index" / "faiss_index_metadata.json"
        checks.append(f"faiss index: {'ok' if faiss_bin.exists() else 'missing'}")
        checks.append(f"faiss metadata: {'ok' if faiss_meta.exists() else 'missing'}")
        checks.append(f"retrieval assets loaded: {'yes' if (self.index is not None and self.embedder is not None) else 'no'}")

        pending_delete_count = 0
        if VIDEOS_TO_DELETE_PATH.exists():
            try:
                delete_df = pd.read_csv(VIDEOS_TO_DELETE_PATH)
                pending_delete_count = len(delete_df)
            except Exception:
                pending_delete_count = 0
        checks.append(f"delete queue rows: {pending_delete_count}")

        message = "\n".join(checks)
        self.status_var.set("Health check complete")
        self._append_command_log(f"HEALTH CHECK\n{message}")
        messagebox.showinfo("QA Health Check", message)

    def _command_open_log(self) -> None:
        QA_COMMAND_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not QA_COMMAND_LOG_PATH.exists():
            QA_COMMAND_LOG_PATH.write_text("", encoding="utf-8")
        webbrowser.open(str(QA_COMMAND_LOG_PATH))

    def _set_candidate_panel_state(self, text: str) -> None:
        self.candidate_panel_state_var.set(text)

    def _set_constraints_text(self, value: str) -> None:
        parsed = parse_constraints_text_block(value)

        objective_core = ""
        numerical_domain = clean_text(parsed.get("numeric_bounds"))
        reject_rule_fail_gate = clean_text(parsed.get("reject_rule"))

        for line in clean_text(value).splitlines():
            line_text = line.strip()
            if not line_text:
                continue

            if ":" in line_text:
                key, raw_val = line_text.split(":", 1)
            elif "=" in line_text:
                key, raw_val = line_text.split("=", 1)
            else:
                continue

            key_norm = key.strip().lower().replace("-", "_").replace(" ", "_").replace("/", "_")
            value_norm = raw_val.strip()
            if key_norm == "objective_core":
                objective_core = value_norm
            elif key_norm in {"numerical_domain", "numeric_domain", "numerical_domain_bounds"}:
                numerical_domain = value_norm
            elif key_norm in {"reject_rule_fail_gate", "fail_gate"}:
                reject_rule_fail_gate = value_norm

        self.constraints_objective_core_var.set(objective_core)
        self.constraints_must_include_var.set(clean_text(parsed.get("must_include")))
        self.constraints_must_not_include_var.set(clean_text(parsed.get("must_not_include")))
        self.constraints_numerical_domain_var.set(numerical_domain)
        self.constraints_reject_rule_fail_gate_var.set(reject_rule_fail_gate)

    def _get_constraints_text(self) -> str:
        lines: list[str] = []

        objective_core = self.constraints_objective_core_var.get().strip()
        must_include = self.constraints_must_include_var.get().strip()
        must_not_include = self.constraints_must_not_include_var.get().strip()
        numerical_domain = self.constraints_numerical_domain_var.get().strip()
        reject_rule_fail_gate = self.constraints_reject_rule_fail_gate_var.get().strip()

        if objective_core:
            lines.append(f"objective_core: {objective_core}")
        if must_include:
            lines.append(f"must_include: {must_include}")
        if must_not_include:
            lines.append(f"must_not_include: {must_not_include}")
        if numerical_domain:
            lines.append(f"numerical/domain: {numerical_domain}")
        if reject_rule_fail_gate:
            lines.append(f"reject_rule_fail_gate: {reject_rule_fail_gate}")

        return "\n".join(lines)

    def _load_constraints_text_for_step(self, small_step_id: str) -> None:
        if not small_step_id:
            self._set_constraints_text("")
            self.constraints_step_label_var.set("Selected small step: none")
            return

        qa_row = self._get_qa_row_for_step(small_step_id)
        constraints_text = clean_text(qa_row.get("constraints_text")) if qa_row else ""
        self._set_constraints_text(constraints_text)

        row = self.curriculum_by_id.get(small_step_id, {})
        topic = clean_text(row.get("topic"))
        small_step_name = clean_text(row.get("small_step_name"))
        self.constraints_step_label_var.set(f"Selected small step: {small_step_id} | {topic} | {small_step_name}")

    def _save_constraints_text(self) -> None:
        small_step_id = self._selected_small_step_id()
        row = self.curriculum_by_id.get(small_step_id)
        if row is None:
            messagebox.showwarning("Missing small step", "Select a small step first.")
            return

        constraints_text = self._get_constraints_text()

        qa_row = self._build_or_get_qa_row_template(row)
        qa_row["constraints_text"] = constraints_text
        qa_row["updated_at"] = datetime.now().isoformat(timespec="seconds")

        try:
            self._upsert_qa_row(qa_row)
        except Exception as exc:
            messagebox.showerror("Constraints Save Error", str(exc))
            return

        self.constraints_summary_var.set("Constraints fields saved to qa/qa.csv")
        self.status_var.set("Saved constraints text to qa/qa.csv")

    def _clear_constraints_results(self) -> None:
        self.constraints_results = []
        for i in range(len(self.constraints_title_labels)):
            self.constraints_title_labels[i].config(text="")
            self.constraints_score_labels[i].config(text="")
            self.constraints_gate_labels[i].config(text="")
            self.constraints_reason_labels[i].config(text="")
            self.constraints_open_buttons[i].config(state=tk.DISABLED)

    def _clear_alignment_results(self) -> None:
        self.latest_alignment_results = []
        if self.alignment_tree is not None:
            for item in self.alignment_tree.get_children():
                self.alignment_tree.delete(item)

    def _render_alignment_results(self, results: list[dict[str, object]]) -> None:
        self._clear_alignment_results()
        self.latest_alignment_results = list(results)

        if self.alignment_tree is None:
            return

        for i, result in enumerate(self.latest_alignment_results, start=1):
            video_id = clean_text(result.get("video_id"))
            title = clean_text(result.get("title"))
            channel = clean_text(result.get("channel"))
            gate_text = "PASS" if bool(result.get("gate_pass", True)) else "FAIL"

            try:
                alignment_score = f"{float(result.get('alignment_score', 0.0)):.1f}"
            except (TypeError, ValueError):
                alignment_score = ""

            try:
                combined_score = f"{float(result.get('combined_score', 0.0)):.4f}"
            except (TypeError, ValueError):
                combined_score = ""

            self.alignment_tree.insert(
                "",
                tk.END,
                iid=str(i - 1),
                values=(
                    i,
                    f"{title} ({video_id})" if video_id else title,
                    channel,
                    gate_text,
                    alignment_score,
                    combined_score,
                ),
            )

    def _open_alignment_video(self, index_num: int) -> None:
        if index_num < 0 or index_num >= len(self.latest_alignment_results):
            return
        video_id = clean_text(self.latest_alignment_results[index_num].get("video_id"))
        if not video_id:
            return
        webbrowser.open(f"https://www.youtube.com/watch?v={video_id}")

    def _open_selected_alignment_video(self, _event=None) -> None:
        if self.alignment_tree is None:
            return
        selection = self.alignment_tree.selection()
        if not selection:
            return
        try:
            index_num = int(selection[0])
        except ValueError:
            return
        self._open_alignment_video(index_num)

    def _compute_stage3_score(self, result: dict[str, object]) -> float:
        return shared_compute_stage3_score(result)

    def _compute_stage4_final_score(self, stage3_score: float, instruction_score_raw: float) -> float:
        return shared_compute_stage4_final_score(stage3_score, instruction_score_raw)

    def _clear_stage4_results(self) -> None:
        self.latest_final_results = []
        if self.stage4_survivors_tree is not None:
            for item in self.stage4_survivors_tree.get_children():
                self.stage4_survivors_tree.delete(item)

        for i in range(min(TOP_K, len(self.stage4_final_title_labels))):
            self.stage4_final_title_labels[i].config(text="")
            self.stage4_final_stage3_labels[i].config(text="")
            self.stage4_final_instruction_labels[i].config(text="")
            self.stage4_final_score_labels[i].config(text="")
            self.stage4_final_open_buttons[i].config(state=tk.DISABLED)

    def _render_stage4_results(self, survivors: list[dict[str, object]]) -> None:
        self._clear_stage4_results()

        enriched_survivors: list[dict[str, object]] = []
        for result in survivors:
            stage3_score = self._compute_stage3_score(result)
            instruction_score = float(result.get("instruction_score", 0.0))
            final_score = self._compute_stage4_final_score(stage3_score, instruction_score)
            enriched_survivors.append(
                {
                    **result,
                    "stage3_score": stage3_score,
                    "final_score": final_score,
                }
            )

        final_top3 = sorted(enriched_survivors, key=lambda item: float(item.get("final_score", 0.0)), reverse=True)[:CANDIDATE_DISPLAY_K]
        self.latest_final_results = final_top3

        if self.stage4_survivors_tree is not None:
            for idx, survivor in enumerate(enriched_survivors, start=1):
                title = clean_text(survivor.get("title"))
                video_id = clean_text(survivor.get("video_id"))
                self.stage4_survivors_tree.insert(
                    "",
                    tk.END,
                    values=(
                        idx,
                        f"{title} ({video_id})" if video_id else title,
                        f"{float(survivor.get('stage3_score', 0.0)):.4f}",
                        f"{float(survivor.get('instruction_score', 0.0)):.1f}",
                    ),
                )

        if not self.stage4_final_title_labels:
            return

        for i in range(min(TOP_K, len(self.stage4_final_title_labels))):
            if i < len(final_top3):
                final_row = final_top3[i]
                title = clean_text(final_row.get("title"))
                video_id = clean_text(final_row.get("video_id"))
                self.stage4_final_title_labels[i].config(text=f"{title} ({video_id})" if video_id else title)
                self.stage4_final_stage3_labels[i].config(text=f"{float(final_row.get('stage3_score', 0.0)):.4f}")
                self.stage4_final_instruction_labels[i].config(text=f"{float(final_row.get('instruction_score', 0.0)):.1f}")
                self.stage4_final_score_labels[i].config(text=f"{float(final_row.get('final_score', 0.0)):.4f}")
                self.stage4_final_open_buttons[i].config(state=tk.NORMAL if video_id else tk.DISABLED)

    def _open_stage4_final_video(self, index_num: int) -> None:
        if index_num < 0 or index_num >= len(self.latest_final_results):
            return
        video_id = clean_text(self.latest_final_results[index_num].get("video_id"))
        if not video_id:
            return
        webbrowser.open(f"https://www.youtube.com/watch?v={video_id}")

    def _evaluate_constraints_for_text(self, gate_row: dict[str, object], text: str) -> tuple[bool, str]:
        haystack = text.lower()
        reasons: list[str] = []

        must_include_terms = split_constraint_terms(gate_row.get("must_include"))
        if must_include_terms and not any(term in haystack for term in must_include_terms):
            reasons.append("missing required signal")

        must_not_terms = split_constraint_terms(gate_row.get("must_not_include"))
        triggered = [term for term in must_not_terms if term in haystack]
        if triggered:
            reasons.append(f"blocked term: {triggered[0]}")

        upper_bound = parse_upper_bound(gate_row.get("numeric_bounds") or gate_row.get("reject_rule"))
        if upper_bound is not None:
            numeric_hits = [int(m) for m in re.findall(r"\b\d+\b", haystack)]
            above_bound = [value for value in numeric_hits if value > upper_bound]
            if above_bound:
                reasons.append(f"number above {upper_bound}")

        reject_rule = clean_text(gate_row.get("reject_rule")).lower()
        if "divisable by 10" in reject_rule or "divisible by 10" in reject_rule:
            numeric_hits = [int(m) for m in re.findall(r"\b\d+\b", haystack)]
            if any(value % 10 == 0 for value in numeric_hits if value > 0):
                reasons.append("contains multiple of 10")

        passed = len(reasons) == 0
        return passed, "PASS" if passed else "; ".join(reasons)

    def _get_constraints_shortlist_k(self) -> int:
        try:
            shortlist_k = int(self.constraints_k_var.get().strip())
        except ValueError:
            shortlist_k = CONSTRAINTS_GATE_DEFAULT_K
        shortlist_k = max(5, min(CONSTRAINTS_GATE_MAX_K, shortlist_k))
        self.constraints_k_var.set(str(shortlist_k))
        return shortlist_k

    def _build_stage2_shortlist(
        self,
        query_text: str,
        gate_row: dict[str, object],
        shortlist_k: int,
    ) -> list[dict[str, Any]]:
        return shared_build_stage2_shortlist(
            query_text=query_text,
            embedder=self.embedder,
            index=self.index,
            metadata=self.metadata,
            shortlist_k=shortlist_k,
            deleted_videos=self.deleted_videos,
            video_lookup=self.video_lookup,
            fallback_lookup=self.fallback_lookup,
            gate_evaluator=lambda gate_eval_text: self._evaluate_constraints_for_text(gate_row, gate_eval_text),
        )

    async def _score_stage2_survivors_async(
        self,
        survivors: list[dict[str, Any]],
        age: str,
        topic: str,
        small_step_name: str,
        small_step_desc: str,
    ) -> list[dict[str, Any]]:
        return await shared_score_stage2_survivors_async(
            survivors=survivors,
            scorer=self.scorer,
            age=age,
            topic=topic,
            small_step_name=small_step_name,
            small_step_desc=small_step_desc,
        )

    def _run_constraints_gate_test(self) -> None:
        step_id = self._selected_small_step_id()
        if not step_id:
            messagebox.showwarning("Missing small step", "Select a small step first.")
            return

        if self.embedder is None or self.index is None:
            messagebox.showwarning("Not ready", "Retrieval assets are still loading or failed.")
            return

        curriculum_row = self.curriculum_by_id.get(step_id, {})
        topic = clean_text(curriculum_row.get("topic"))
        small_step_name = clean_text(curriculum_row.get("small_step_name"))
        candidate_desc = self.candidate_text.get("1.0", tk.END).strip()
        ss_wr_desc = candidate_desc or clean_text(curriculum_row.get("ss_wr_desc"))
        gate_row = parse_constraints_text_block(self._get_constraints_text())

        shortlist_k = self._get_constraints_shortlist_k()

        self.constraints_run_btn.config(state=tk.DISABLED)
        self.constraints_status_var.set("Constraints gate: running FAISS shortlist and hard-rule gate...")
        self._clear_constraints_results()

        worker = threading.Thread(
            target=self._constraints_gate_worker,
            args=(gate_row, topic, small_step_name, ss_wr_desc, shortlist_k),
            daemon=True,
        )
        worker.start()

    def _constraints_gate_worker(
        self,
        gate_row: dict[str, object],
        topic: str,
        small_step_name: str,
        ss_wr_desc: str,
        shortlist_k: int,
    ) -> None:
        try:
            query_text = build_query_text(topic=topic, small_step_name=small_step_name, ss_desc_validated=ss_wr_desc)
            ranked_results = self._build_stage2_shortlist(query_text, gate_row, shortlist_k)
            self.root.after(0, self._on_constraints_gate_success, ranked_results)
        except Exception as exc:
            self.root.after(0, self._on_constraints_gate_error, str(exc))

    def _on_constraints_gate_success(self, results: list[dict[str, object]]) -> None:
        self.constraints_run_btn.config(state=tk.NORMAL)
        self.constraints_results = results

        display_count = len(self.constraints_title_labels)
        for i in range(display_count):
            if i < len(results):
                result = results[i]
                video_id = clean_text(result.get("video_id"))
                title = clean_text(result.get("title"))
                self.constraints_title_labels[i].config(text=f"{title} ({video_id})")
                self.constraints_score_labels[i].config(text=f"{float(result.get('semantic_score', 0.0)):.4f}")

                if bool(result.get("gate_pass")):
                    self.constraints_gate_labels[i].config(text="PASS", foreground="#1f7a1f")
                else:
                    self.constraints_gate_labels[i].config(text="FAIL", foreground="#aa2c2c")

                self.constraints_reason_labels[i].config(text=clean_text(result.get("gate_reason")))
                self.constraints_open_buttons[i].config(state=tk.NORMAL if video_id else tk.DISABLED)
            else:
                self.constraints_title_labels[i].config(text="")
                self.constraints_score_labels[i].config(text="")
                self.constraints_gate_labels[i].config(text="", foreground="black")
                self.constraints_reason_labels[i].config(text="")
                self.constraints_open_buttons[i].config(state=tk.DISABLED)

        total = len(results)
        passed = sum(1 for r in results if bool(r.get("gate_pass")))
        failed = total - passed
        self.constraints_status_var.set(f"Constraints gate: complete ({total} FAISS videos evaluated)")
        self.constraints_summary_var.set(f"Pass={passed} | Fail={failed} | Rule set from constraints text in qa/qa.csv")

        # Re-apply current gate rules to the main search results so Stage 3/4 stay in sync.
        if self.latest_enriched_results:
            current_gate_row = parse_constraints_text_block(self._get_constraints_text())
            has_rules = any(clean_text(v) for v in current_gate_row.values())
            for result in self.latest_enriched_results:
                if has_rules:
                    eval_text = clean_text(result.get("gate_eval_text")) or clean_text(result.get("title", ""))
                    gate_pass, gate_reason = self._evaluate_constraints_for_text(current_gate_row, eval_text)
                    result["gate_pass"] = gate_pass
                    result["gate_reason"] = gate_reason
                else:
                    result["gate_pass"] = True
                    result["gate_reason"] = "PASS (no constraints)"
            alignment_input = [r for r in self.latest_enriched_results if bool(r.get("gate_pass"))]
            alignment_input = self._apply_step_knockout_filter(alignment_input, self._selected_small_step_id())
            self._render_stage4_results(alignment_input)
            if self.latest_final_results:
                self.latest_results = self.latest_final_results
            else:
                self.latest_results = []
            self._render_candidate_search_results(self.latest_results)
            self._render_alignment_results(alignment_input)

    def _on_constraints_gate_error(self, error_message: str) -> None:
        self.constraints_run_btn.config(state=tk.NORMAL)
        self.constraints_status_var.set("Constraints gate: failed")
        messagebox.showerror("Constraints Gate Error", error_message)

    def _refresh_after_soft_delete(self) -> None:
        try:
            self.deleted_videos = DeletionTracker().get_deleted_video_ids()
            self.video_lookup = load_video_lookup()
            self._reload_wildcards_df()

            precomputed_path = project_root / "precomputed_recommendations_flat.csv"
            if precomputed_path.exists():
                precomp_df = pd.read_csv(precomputed_path)
                for col in ["small_step_id", "video_id", "title", "video_title", "channel"]:
                    if col in precomp_df.columns:
                        precomp_df[col] = precomp_df[col].map(clean_text)
                self.precomputed_df = precomp_df

            selected_step_id = self._selected_small_step_id()
            if selected_step_id:
                self._populate_precomputed(selected_step_id)

            self._refresh_dup_review_state()

            if self.active_job_state == JOB_STATE_RUNNING:
                self._set_job_state(JOB_STATE_DONE, step_text="Deleted-video state refreshed")
            self.status_var.set("Ready (soft delete applied; run Full Rebuild FAISS to physically purge deleted vectors)")
        except Exception as exc:
            if self.active_job_state == JOB_STATE_RUNNING:
                self._set_job_state(JOB_STATE_FAILED, step_text="Deleted-video refresh failed", error_text=str(exc))
            self.status_var.set("Failed to refresh deleted-video state")
            messagebox.showerror("Delete Queue Refresh Error", str(exc))

    def _open_constraints_video(self, index_num: int) -> None:
        if index_num < 0 or index_num >= len(self.constraints_results):
            return
        video_id = clean_text(self.constraints_results[index_num].get("video_id"))
        if not video_id:
            return
        webbrowser.open(f"https://www.youtube.com/watch?v={video_id}")

    def _load_initial_data(self) -> None:
        """Entry point called after mainloop starts. Curriculum loads on main thread (fast);
        heavy FAISS/embedder assets load in a background thread."""
        try:
            self.status_var.set("Loading curriculum...")
            self.root.update_idletasks()
            curriculum_raw = pd.read_csv(CURRICULUM_PATH)
            self.curriculum_df = curriculum_to_long_df(curriculum_raw).copy()

            required_cols = ["small_step_id", "topic", "small_step_name", "ss_wr_desc", "age"]
            for col in required_cols:
                if col not in self.curriculum_df.columns:
                    raise ValueError(f"Curriculum is missing required column: {col}")

            self.curriculum_df["small_step_id"] = self.curriculum_df["small_step_id"].map(clean_text)
            self.curriculum_df["topic"] = self.curriculum_df["topic"].map(clean_text)
            self.curriculum_df["small_step_name"] = self.curriculum_df["small_step_name"].map(clean_text)
            self.curriculum_df["ss_wr_desc"] = self.curriculum_df["ss_wr_desc"].map(clean_text)
            self.curriculum_df["age"] = self.curriculum_df["age"].map(clean_text)

            self.curriculum_df = self.curriculum_df[self.curriculum_df["small_step_id"].str.len() > 0].copy()

            precomputed_path = project_root / "precomputed_recommendations_flat.csv"
            if precomputed_path.exists():
                precomp_df = pd.read_csv(precomputed_path)
                for col in ["small_step_id", "video_id", "title", "video_title", "channel"]:
                    if col in precomp_df.columns:
                        precomp_df[col] = precomp_df[col].map(clean_text)
                self.precomputed_df = precomp_df

            self._reload_wildcards_df()

            self.curriculum_by_id = {
                row["small_step_id"]: row
                for _, row in self.curriculum_df.drop_duplicates(subset=["small_step_id"], keep="first").iterrows()
            }

            self.sorted_step_ids = sorted(
                self.curriculum_by_id.keys(),
                key=lambda sid: int(self.curriculum_by_id[sid].get("small_step_num", 0)),
            )
            self.saved_step_ids = self._load_saved_step_ids_from_qa()
            # Load promoted steps from canonical overrides
            override_map = load_validated_override_map(CANONICAL_OVERRIDE_PATH)
            self.promoted_step_ids = set(override_map.keys())
            self._refresh_step_combo_labels()

            # Build global step number lookup and compute dup proximity scores
            self._build_step_global_num_lookup()
            self.dup_scores = self._compute_dup_scores()
            self.dup_flagged_steps = self._load_dup_flagged_steps()
            self._refresh_dup_review_state()

            if self.step_var.get():
                self._on_step_selected(None)
                selected_step_id = self._selected_small_step_id()
                if selected_step_id:
                    self._populate_precomputed(selected_step_id)

            self.status_var.set("Loading retrieval assets (FAISS / embedder)...")
            self.search_btn.config(state=tk.DISABLED)
            self.root.update_idletasks()

            worker = threading.Thread(target=self._load_heavy_assets, daemon=True)
            worker.start()

        except Exception as exc:
            self.status_var.set("Failed to initialize curriculum")
            messagebox.showerror("Initialization Error", str(exc))

    def _load_heavy_assets(self) -> None:
        """Background thread: load FAISS index, embedder, scorer."""
        try:
            index, metadata = load_faiss_index()
            fallback_lookup = build_faiss_video_lookup(metadata)
            video_lookup = load_video_lookup()
            deleted_videos = DeletionTracker().get_deleted_video_ids()
            embedder = QueryEmbedder()
            scorer = InstructionQualityScorer()

            self.root.after(0, self._on_heavy_assets_ready, index, metadata, fallback_lookup, video_lookup, deleted_videos, embedder, scorer)
        except Exception as exc:
            self.root.after(0, self._on_heavy_assets_error, str(exc))

    def _on_heavy_assets_ready(
        self,
        index,
        metadata: list[dict[str, object]],
        fallback_lookup: dict[str, dict[str, str]],
        video_lookup: dict[str, dict[str, str]],
        deleted_videos: set[str],
        embedder,
        scorer,
    ) -> None:
        self.index = index
        self.metadata = metadata
        self.fallback_lookup = fallback_lookup
        self.video_lookup = video_lookup
        self.deleted_videos = deleted_videos
        self.embedder = embedder
        self.scorer = scorer
        self.search_btn.config(state=tk.NORMAL)
        self.constraints_run_btn.config(state=tk.NORMAL)
        self.status_var.set("Ready")
        self.constraints_status_var.set("Constraints gate: ready")
        self._schedule_semantic_preview()
        if self.active_job_state == JOB_STATE_RUNNING:
            self._set_job_state(JOB_STATE_DONE, step_text="Retrieval assets reloaded")

    def _on_heavy_assets_error(self, error_message: str) -> None:
        self.status_var.set("Failed to load retrieval assets")
        self.constraints_status_var.set("Constraints gate: retrieval assets failed to load")
        if self.active_job_state == JOB_STATE_RUNNING:
            self._set_job_state(JOB_STATE_FAILED, step_text="Retrieval asset reload failed", error_text=error_message)
        messagebox.showerror("Initialization Error", error_message)

    def _selected_small_step_id(self) -> str:
        label = self.step_var.get().strip()
        if not label:
            return ""

        mapped = self.step_label_to_id.get(label)
        if mapped:
            return mapped

        # Backward compatibility for plain labels without marker prefix.
        if label.startswith("✓ ") or label.startswith("• "):
            label = label[2:].strip()
        return label.split(" | ", 1)[0].strip()

    def _step_sort_key(self, small_step_id: str) -> tuple[int, str]:
        row = self.curriculum_by_id.get(small_step_id, {})
        raw_num = clean_text(row.get("small_step_num"))
        try:
            step_num = int(raw_num)
        except ValueError:
            step_num = 10**9
        return (step_num, small_step_id)

    def _refresh_dup_review_state(self) -> None:
        """Recompute dup-review metrics and refresh related UI state."""
        self._build_step_global_num_lookup()
        self.dup_scores = self._compute_dup_scores()
        current_step_id = self._selected_small_step_id()
        self._refresh_step_combo_labels(preserve_step_id=current_step_id)
        self._update_dup_score_display()
        self._populate_dup_neighbours(current_step_id)

    def _load_saved_step_ids_from_qa(self) -> set[str]:
        if not QA_TRACKING_PATH.exists():
            return set()

        try:
            qa_df = self._load_qa_df()
        except Exception:
            return set()

        if qa_df.empty:
            return set()

        persisted_mask = qa_df["candidate_ss_wr_desc"].map(clean_text).str.len() > 0
        for rank in range(1, CANDIDATE_DISPLAY_K + 1):
            persisted_mask = (
                persisted_mask
                | (qa_df[f"candidate_{rank}_video_id"].map(clean_text).str.len() > 0)
                | (qa_df[f"candidate_{rank}_video_title"].map(clean_text).str.len() > 0)
                | (qa_df[f"candidate_{rank}_combined_score"].map(clean_text).str.len() > 0)
            )

        return set(qa_df.loc[persisted_mask, "small_step_id"].map(clean_text).tolist())

    def _refresh_step_combo_labels(self, preserve_step_id: str = "") -> None:
        self.step_labels_by_id = {}
        self.step_label_to_id = {}

        visible_step_ids = self.sorted_step_ids
        if self.show_unsaved_only_var.get():
            visible_step_ids = [sid for sid in self.sorted_step_ids if sid not in self.saved_step_ids]

        # In dup review mode, sort the visible list by H_i descending (top-N% first, rest in normal order).
        if self.dup_review_mode and self.dup_scores:
            try:
                pct = max(1, min(100, int(self.dup_threshold_pct_var.get())))
            except ValueError:
                pct = DUP_REVIEW_DEFAULT_TOP_PCT
            n_top = max(1, int(len(visible_step_ids) * pct / 100))
            scored = sorted(visible_step_ids, key=lambda sid: -self.dup_scores.get(sid, {}).get("H", 0.0))
            top_set = set(scored[:n_top])
            top_first = scored[:n_top]
            rest_in_order = [sid for sid in visible_step_ids if sid not in top_set]
            visible_step_ids = top_first + rest_in_order

        labels: list[str] = []
        for small_step_id in visible_step_ids:
            if small_step_id in self.dup_flagged_steps:
                marker = "✗"
            elif small_step_id in self.promoted_step_ids:
                marker = "⭐"
            elif small_step_id in self.saved_step_ids:
                marker = "✓"
            else:
                marker = "•"
            label = f"{marker} {small_step_id}"
            self.step_labels_by_id[small_step_id] = label
            self.step_label_to_id[label] = small_step_id
            labels.append(label)

        self.step_combo["values"] = labels

        selected_step_id = preserve_step_id or self._selected_small_step_id()
        if selected_step_id and selected_step_id in self.step_labels_by_id:
            self.step_var.set(self.step_labels_by_id[selected_step_id])
        elif labels:
            self.step_var.set(labels[0])
        else:
            self.step_var.set("")

        # Exclude redundant-flagged steps from progress workload accounting.
        effective_step_ids = [sid for sid in self.sorted_step_ids if sid not in self.dup_flagged_steps]
        total_steps = len(effective_step_ids)
        done_steps = len([sid for sid in self.saved_step_ids if sid not in self.dup_flagged_steps])
        percent = int((done_steps / total_steps) * 100) if total_steps else 100
        flagged_steps = len(self.dup_flagged_steps)
        self.progress_var.set(
            f"Done {done_steps}/{total_steps} ({percent}%) | redundant excluded {flagged_steps}"
        )

        has_unsaved = any(sid not in self.saved_step_ids for sid in effective_step_ids)
        self.jump_unsaved_btn.config(state=tk.NORMAL if has_unsaved else tk.DISABLED)

        self._refresh_low_candidate_jump_button_state()
        self._update_dup_score_display()

    def _on_jump_filter_changed(self) -> None:
        self._refresh_low_candidate_jump_button_state()

    def _refresh_low_candidate_jump_button_state(self) -> None:
        low_candidate_step_ids = self._load_low_candidate_rating_step_ids()
        self.jump_low_candidate_btn.config(state=tk.NORMAL if low_candidate_step_ids else tk.DISABLED)

    def _load_low_candidate_rating_step_ids(self) -> set[str]:
        """Return step ids where any persisted candidate rating is <= threshold.

        Empty candidate slots are ignored so template/default values do not count.
        """
        if not QA_TRACKING_PATH.exists():
            return set()

        try:
            qa_df = self._load_qa_df()
        except Exception:
            return set()

        if qa_df.empty:
            return set()

        ignore_default_five = bool(self.low_rating_jump_ignore_default_five_var.get())
        low_step_ids: set[str] = set()
        for _, qa_row in qa_df.iterrows():
            small_step_id = clean_text(qa_row.get("small_step_id"))
            if not small_step_id:
                continue

            for rank in range(1, CANDIDATE_DISPLAY_K + 1):
                video_id = clean_text(qa_row.get(f"candidate_{rank}_video_id"))
                video_title = clean_text(qa_row.get(f"candidate_{rank}_video_title"))
                if not video_id and not video_title:
                    # Ignore empty candidate slots.
                    continue

                rating_text = clean_text(qa_row.get(f"candidate_{rank}_rating_1_10"))
                if not rating_text:
                    continue

                try:
                    rating_value = int(rating_text)
                except ValueError:
                    continue

                if ignore_default_five and rating_value == 5:
                    # Optional workflow: treat untouched/default ratings as neutral.
                    continue

                if rating_value <= LOW_CANDIDATE_RATING_THRESHOLD:
                    low_step_ids.add(small_step_id)
                    break

        return low_step_ids

    def _set_selected_step_by_id(self, small_step_id: str) -> bool:
        label = self.step_labels_by_id.get(small_step_id)
        if not label:
            return False
        self.step_var.set(label)
        self._on_step_selected(None)
        return True

    def _jump_to_next_unsaved(self) -> None:
        if not self.sorted_step_ids:
            return

        unsaved_step_ids = [
            sid
            for sid in self.sorted_step_ids
            if sid not in self.saved_step_ids and sid not in self.dup_flagged_steps
        ]
        if not unsaved_step_ids:
            messagebox.showinfo(
                "All complete",
                "All non-redundant small steps are marked as saved in qa.csv.",
            )
            return

        current_step_id = self._selected_small_step_id()
        if current_step_id in self.sorted_step_ids:
            current_idx = self.sorted_step_ids.index(current_step_id)
        else:
            current_idx = -1

        next_step_id = ""
        for offset in range(1, len(self.sorted_step_ids) + 1):
            candidate_idx = (current_idx + offset) % len(self.sorted_step_ids)
            candidate_step_id = self.sorted_step_ids[candidate_idx]
            if candidate_step_id not in self.saved_step_ids and candidate_step_id not in self.dup_flagged_steps:
                next_step_id = candidate_step_id
                break

        if not next_step_id:
            next_step_id = unsaved_step_ids[0]

        if not self._set_selected_step_by_id(next_step_id):
            # If filtered list hides the target, disable filter and try again.
            self.show_unsaved_only_var.set(False)
            self._refresh_step_combo_labels(preserve_step_id=next_step_id)
            self._set_selected_step_by_id(next_step_id)

    def _jump_to_next_small_step(self) -> None:
        values = list(self.step_combo["values"])
        if not values:
            return

        current_label = self.step_var.get().strip()
        if current_label not in values:
            self.step_var.set(values[0])
            self._on_step_selected(None)
            return

        current_idx = values.index(current_label)
        if current_idx >= len(values) - 1:
            return

        self.step_var.set(values[current_idx + 1])
        self._on_step_selected(None)

    def _jump_to_next_low_candidate_rating(self) -> None:
        if not self.sorted_step_ids:
            return

        low_step_ids = self._load_low_candidate_rating_step_ids()
        if not low_step_ids:
            messagebox.showinfo(
                "No low candidate ratings",
                f"No small steps found with any candidate rating <= {LOW_CANDIDATE_RATING_THRESHOLD}.",
            )
            return

        current_step_id = self._selected_small_step_id()
        if current_step_id in self.sorted_step_ids:
            current_idx = self.sorted_step_ids.index(current_step_id)
        else:
            current_idx = -1

        next_step_id = ""
        for offset in range(1, len(self.sorted_step_ids) + 1):
            candidate_idx = (current_idx + offset) % len(self.sorted_step_ids)
            candidate_step_id = self.sorted_step_ids[candidate_idx]
            if candidate_step_id in low_step_ids:
                next_step_id = candidate_step_id
                break

        if not next_step_id:
            for step_id in self.sorted_step_ids:
                if step_id in low_step_ids:
                    next_step_id = step_id
                    break

        if not next_step_id:
            messagebox.showinfo(
                "No low candidate ratings",
                f"No small steps found with any candidate rating <= {LOW_CANDIDATE_RATING_THRESHOLD}.",
            )
            return

        if not self._set_selected_step_by_id(next_step_id):
            # If filtered list hides the target, disable filter and try again.
            self.show_unsaved_only_var.set(False)
            self._refresh_step_combo_labels(preserve_step_id=next_step_id)
            self._set_selected_step_by_id(next_step_id)

    def _mark_candidate_reviewed(self) -> None:
        small_step_id = self._selected_small_step_id()
        if not small_step_id:
            messagebox.showwarning("Missing small step", "Select a small step first.")
            return

        updated_count = 0
        for i in range(CANDIDATE_DISPLAY_K):
            result = self.latest_results[i] if i < len(self.latest_results) else {}
            has_result = bool(clean_text(result.get("video_id")) or clean_text(result.get("title")))
            if not has_result:
                continue
            self.rating_vars[i].set("10")
            self._apply_rating_color(i)
            updated_count += 1

        if updated_count == 0:
            messagebox.showinfo(
                "No candidate results",
                "No candidate rows are currently shown. Load persisted picks or run Search Top 3 first.",
            )
            return

        self.status_var.set(
            f"Marked {updated_count} shown candidate rating(s) as 10. Click Update QA CSV to persist for jump filtering."
        )

    def _on_show_unsaved_only_changed(self) -> None:
        current_step_id = self._selected_small_step_id()
        self._refresh_step_combo_labels(preserve_step_id=current_step_id)
        if self.step_var.get():
            self._on_step_selected(None)

    def _get_saved_candidate_text(self, small_step_id: str) -> str:
        if not small_step_id:
            return ""

        override_map = load_validated_override_map(CANONICAL_OVERRIDE_PATH)
        override_text = clean_text(override_map.get(small_step_id, ""))
        if override_text:
            return override_text

        if APPROVED_CANDIDATES_PATH.exists():
            try:
                approved_df = pd.read_csv(APPROVED_CANDIDATES_PATH)
            except Exception:
                approved_df = pd.DataFrame()

            required_cols = {"small_step_id", "candidate_ss_wr_desc"}
            if not approved_df.empty and required_cols.issubset(approved_df.columns):
                approved_df["small_step_id"] = approved_df["small_step_id"].map(clean_text)
                approved_df["candidate_ss_wr_desc"] = approved_df["candidate_ss_wr_desc"].map(clean_text)
                step_rows = approved_df[approved_df["small_step_id"] == small_step_id]
                if not step_rows.empty:
                    saved_candidate = clean_text(step_rows.iloc[-1].get("candidate_ss_wr_desc"))
                    if saved_candidate:
                        return saved_candidate

        qa_row = self._get_qa_row_for_step(small_step_id)
        if qa_row is None:
            return ""
        return clean_text(qa_row.get("candidate_ss_wr_desc"))

    def _on_step_selected(self, _event) -> None:
        small_step_id = self._selected_small_step_id()
        row = self.curriculum_by_id.get(small_step_id)
        if row is None:
            return

        # Default to unchecked when navigating between small steps.
        self.awaiting_download_faiss_var.set(False)

        baseline = clean_text(row.get("ss_wr_desc"))
        override_map = load_validated_override_map(CANONICAL_OVERRIDE_PATH)
        ss_desc_validated, _ = resolve_validated_desc(
            small_step_id=small_step_id,
            baseline_ss_wr_desc=baseline,
            override_map=override_map,
        )
        candidate_default = self._get_saved_candidate_text(small_step_id) or baseline
        self._set_text(self.baseline_text, ss_desc_validated)
        self._set_text(self.candidate_text, candidate_default)
        self._clear_results()
        self._clear_semantic_preview()
        self._populate_precomputed(small_step_id)
        if self._populate_candidate_from_qa(small_step_id):
            self.candidate_display_unlocked_steps.add(small_step_id)
        else:
            self.candidate_display_unlocked_steps.discard(small_step_id)
            self._set_candidate_panel_state("Candidate panel: locked until Update QA CSV")
        # Update promoted status indicator
        if small_step_id in self.promoted_step_ids:
            self.promoted_status_var.set("✓ Promoted to canonical")
        else:
            self.promoted_status_var.set("")
        self.status_var.set("Ready")
        self._load_constraints_text_for_step(small_step_id)
        self.constraints_status_var.set("Constraints gate: ready")
        self._schedule_semantic_preview()
        self._update_dup_score_display()
        self._populate_dup_neighbours(small_step_id)

    def _set_text(self, widget: scrolledtext.ScrolledText, content: str) -> None:
        widget.config(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, content)
        if widget is self.candidate_text:
            self.candidate_text.edit_modified(False)
        if widget is self.baseline_text:
            widget.config(state=tk.DISABLED)

    def _clear_semantic_preview(self) -> None:
        self.semantic_preview_results = []
        for i in range(len(self.semantic_preview_title_labels)):
            self.semantic_preview_title_labels[i].config(text="")
            self.semantic_preview_channel_labels[i].config(text="")
            self.semantic_preview_score_labels[i].config(text="")
        self.semantic_preview_status_var.set("Semantic preview: idle")

    def _on_candidate_text_modified(self, _event) -> None:
        if not self.candidate_text.edit_modified():
            return
        self.candidate_text.edit_modified(False)
        step_id = self._selected_small_step_id()
        if step_id:
            # Edited candidate text invalidates any previously unlocked persisted candidate view.
            self.saved_candidate_steps.discard(step_id)
            self.candidate_display_unlocked_steps.discard(step_id)
        self._clear_results()
        self._set_candidate_panel_state("Candidate panel: candidate edited, click Update QA CSV to persist")
        self._schedule_semantic_preview()

    def _schedule_semantic_preview(self) -> None:
        if not SHOW_LIVE_SEMANTIC_PREVIEW:
            return
        if self.semantic_preview_after_id is not None:
            self.root.after_cancel(self.semantic_preview_after_id)
            self.semantic_preview_after_id = None

        self.semantic_preview_after_id = self.root.after(
            SEMANTIC_PREVIEW_DEBOUNCE_MS,
            self._run_semantic_preview,
        )

    def _run_semantic_preview(self) -> None:
        if not SHOW_LIVE_SEMANTIC_PREVIEW:
            return
        self.semantic_preview_after_id = None
        small_step_id = self._selected_small_step_id()
        row = self.curriculum_by_id.get(small_step_id)
        if row is None:
            self._clear_semantic_preview()
            return

        if self.embedder is None or self.index is None:
            self.semantic_preview_status_var.set("Semantic preview: waiting for retrieval assets")
            return

        candidate = self.candidate_text.get("1.0", tk.END).strip()
        if not candidate:
            self._clear_semantic_preview()
            return

        self.semantic_preview_request_id += 1
        request_id = self.semantic_preview_request_id
        self.semantic_preview_status_var.set("Semantic preview: searching...")

        worker = threading.Thread(
            target=self._semantic_preview_worker,
            args=(request_id, row, candidate),
            daemon=True,
        )
        worker.start()

    def _semantic_preview_worker(self, request_id: int, row: dict[str, object], candidate: str) -> None:
        try:
            query_text = build_query_text(
                topic=clean_text(row.get("topic")),
                small_step_name=clean_text(row.get("small_step_name")),
                ss_desc_validated=candidate,
            )

            embedding = self.embedder.embed_query(query_text).reshape(1, -1)
            distances, indices = self.index.search(embedding, SEMANTIC_PREVIEW_CHUNKS)

            video_chunks: dict[str, list[dict[str, object]]] = {}
            for dist, idx in zip(distances[0], indices[0]):
                if idx == -1 or idx >= len(self.metadata):
                    continue

                video_meta = self.metadata[int(idx)]
                video_id = clean_text(video_meta.get("video_id"))
                if not video_id or video_id in self.deleted_videos:
                    continue

                cosine_sim = calculate_cosine_similarity(float(dist))
                if video_id not in video_chunks:
                    video_chunks[video_id] = []
                video_chunks[video_id].append(
                    {
                        "cosine_similarity": cosine_sim,
                        "video_meta": video_meta,
                    }
                )

            video_stats: list[dict[str, object]] = []
            for video_id, chunks in video_chunks.items():
                sims = [float(c["cosine_similarity"]) for c in chunks]
                good_chunks = [sim for sim in sims if sim >= 0.6]
                median_sim = sorted(sims)[len(sims) // 2]
                ranking_score = median_sim + (len(good_chunks) * 0.02)
                best_meta = chunks[0]["video_meta"]

                title = clean_text(best_meta.get("video_title") or best_meta.get("title"))
                meta = self.video_lookup.get(video_id) or self.fallback_lookup.get(video_id) or {}
                video_stats.append(
                    {
                        "video_id": video_id,
                        "title": title,
                        "channel": clean_text(meta.get("channel") or best_meta.get("channel")),
                        "semantic_score": median_sim,
                        "ranking_score": ranking_score,
                    }
                )

            top_results = sorted(video_stats, key=lambda x: float(x["ranking_score"]), reverse=True)[:SEMANTIC_PREVIEW_K]
            self.root.after(0, self._on_semantic_preview_success, request_id, top_results)
        except Exception as exc:
            self.root.after(0, self._on_semantic_preview_error, request_id, str(exc))

    def _on_semantic_preview_success(self, request_id: int, results: list[dict[str, object]]) -> None:
        if request_id != self.semantic_preview_request_id:
            return

        self.semantic_preview_results = results
        for i in range(SEMANTIC_PREVIEW_K):
            if i < len(results):
                result = results[i]
                self.semantic_preview_title_labels[i].config(text=f"{result['title']} ({result['video_id']})")
                self.semantic_preview_channel_labels[i].config(text=clean_text(result.get("channel")))
                self.semantic_preview_score_labels[i].config(text=f"{float(result['semantic_score']):.4f}")
            else:
                self.semantic_preview_title_labels[i].config(text="")
                self.semantic_preview_channel_labels[i].config(text="")
                self.semantic_preview_score_labels[i].config(text="")

        self.semantic_preview_status_var.set(f"Semantic preview: {len(results)} result(s)")

    def _on_semantic_preview_error(self, request_id: int, error_message: str) -> None:
        if request_id != self.semantic_preview_request_id:
            return
        self.semantic_preview_status_var.set(f"Semantic preview error: {error_message}")

    def _clear_results(self) -> None:
        self.latest_results = []
        self.latest_enriched_results = []
        self.latest_alignment_results = []
        self.latest_final_results = []
        self.latest_query_text = ""

        self._clear_candidate_result_widgets(reset_ratings=True, reset_notes=True)
        self._clear_alignment_results()
        self._clear_stage4_results()
        self._set_candidate_panel_state("Candidate panel: locked until Update QA CSV")
        self.save_btn.config(state=tk.DISABLED)

    def _clear_candidate_result_widgets(self, reset_ratings: bool, reset_notes: bool = True) -> None:
        for i in range(CANDIDATE_DISPLAY_K):
            self.result_title_labels[i].config(text="")
            self.result_channel_labels[i].config(text="")
            self.result_score_labels[i].config(text="")
            self.result_open_buttons[i].config(state=tk.DISABLED)
            self.candidate_delete_buttons[i].config(state=tk.DISABLED)
            self.candidate_knockout_buttons[i].config(state=tk.DISABLED, text="Excl")
            self.candidate_rank_vars[i].set(str(i + 1))
            self.candidate_rank_dropdowns[i].config(state=tk.DISABLED)
            if reset_ratings:
                self.rating_vars[i].set("5")
                self._apply_rating_color(i)
        self._prev_candidate_ranks = list(range(1, CANDIDATE_DISPLAY_K + 1))
        if reset_notes:
            self.notes_var.set("")

    def _render_candidate_search_results(self, results: list[dict[str, object]]) -> None:
        self._clear_candidate_result_widgets(reset_ratings=True, reset_notes=True)

        for i in range(CANDIDATE_DISPLAY_K):
            if i >= len(results):
                continue

            result = results[i]
            video_id = clean_text(result.get("video_id"))
            title = clean_text(result.get("title"))
            channel = clean_text(result.get("channel"))

            score_text = ""
            try:
                score_text = f"{float(result.get('combined_score', 0.0)):.4f}"
            except (TypeError, ValueError):
                score_text = ""

            title_text = ""
            if title and video_id:
                title_text = f"{title} ({video_id})"
            elif title:
                title_text = title
            elif video_id:
                title_text = f"({video_id})"

            self.result_title_labels[i].config(text=title_text)
            self.result_channel_labels[i].config(text=channel)
            self.result_score_labels[i].config(text=score_text)
            self.result_open_buttons[i].config(state=tk.NORMAL if video_id else tk.DISABLED)
            self.candidate_delete_buttons[i].config(state=tk.NORMAL if video_id else tk.DISABLED)
            self.rating_vars[i].set("5")
            self._apply_rating_color(i)

        self._sync_candidate_controls_for_current_step()

    def _run_search(self) -> None:
        small_step_id = self._selected_small_step_id()
        if not small_step_id:
            messagebox.showwarning("Missing small step", "Select a small step first.")
            return

        if self.embedder is None or self.scorer is None or self.index is None:
            messagebox.showwarning("Not ready", "Retrieval assets are still loading or failed.")
            return

        row = self.curriculum_by_id.get(small_step_id)
        if row is None:
            messagebox.showwarning("Missing row", "Unable to find selected small step in curriculum.")
            return

        candidate = self.candidate_text.get("1.0", tk.END).strip()
        if not candidate:
            messagebox.showwarning("Missing candidate", "Enter candidate wording before searching.")
            return

        # Any new search requires Update QA CSV before persisted candidate picks are shown again.
        self.saved_candidate_steps.discard(small_step_id)
        self.candidate_display_unlocked_steps.discard(small_step_id)
        self._clear_candidate_result_widgets(reset_ratings=True, reset_notes=True)
        self._set_candidate_panel_state("Candidate panel: search is transient until Update QA CSV")

        self.search_btn.config(state=tk.DISABLED)
        self.save_btn.config(state=tk.DISABLED)
        self.status_var.set("Searching top 3 recommendations...")

        constraints_text = self._get_constraints_text()

        worker = threading.Thread(
            target=self._search_worker,
            args=(row, candidate, constraints_text),
            daemon=True,
        )
        worker.start()

    def _search_worker(self, row: dict[str, object], candidate: str, constraints_text: str) -> None:
        try:
            query_text = build_query_text(
                topic=clean_text(row.get("topic")),
                small_step_name=clean_text(row.get("small_step_name")),
                ss_desc_validated=candidate,
            )
            gate_rules = parse_constraints_text_block(constraints_text)
            shortlist_k = self._get_constraints_shortlist_k()
            stage2_results = self._build_stage2_shortlist(query_text, gate_rules, shortlist_k)
            stage2_survivors = [result for result in stage2_results if bool(result.get("gate_pass"))]
            step_id = clean_text(row.get("small_step_id"))
            stage2_survivors = self._apply_step_knockout_filter(stage2_survivors, step_id)
            scored_survivors = asyncio.run(
                self._score_stage2_survivors_async(
                    survivors=stage2_survivors,
                    age=clean_text(row.get("age")),
                    topic=clean_text(row.get("topic")),
                    small_step_name=clean_text(row.get("small_step_name")),
                    small_step_desc=candidate,
                )
            )
            self.root.after(0, self._on_search_success, stage2_results, scored_survivors, query_text)
        except Exception as exc:
            self.root.after(0, self._on_search_error, str(exc))

    def _on_search_success(
        self,
        stage2_results: list[dict[str, object]],
        alignment_input: list[dict[str, object]],
        query_text: str,
    ) -> None:
        self.constraints_results = stage2_results
        self.latest_enriched_results = alignment_input
        self.latest_results = alignment_input
        self.latest_alignment_results = list(alignment_input)
        self.latest_query_text = query_text

        self._render_stage4_results(alignment_input)
        if self.latest_final_results:
            # Candidate panel and downstream QA save should use final ranking after stage 4.
            self.latest_results = self.latest_final_results

        self._render_candidate_search_results(self.latest_results)
        self._render_alignment_results(alignment_input)
        self._set_candidate_panel_state("Candidate panel: showing current Search Top 3 results (not yet persisted)")

        self.search_btn.config(state=tk.NORMAL)
        self.save_btn.config(state=tk.NORMAL if alignment_input else tk.DISABLED)

        if stage2_results:
            passed_count = sum(1 for result in stage2_results if bool(result.get("gate_pass", True)))
            self.status_var.set(
                f"Search complete. Evaluated {len(stage2_results)} Stage 2 candidates; {passed_count} pass constraints gate and were scored in Stages 3-4."
            )
        else:
            self.status_var.set("Search complete. No recommendations found.")

    def _populate_candidate_from_qa(self, small_step_id: str) -> bool:
        self._clear_candidate_result_widgets(reset_ratings=True, reset_notes=False)
        qa_row = self._get_qa_row_for_step(small_step_id)
        if qa_row is None:
            self.notes_var.set("")
            self._set_candidate_panel_state("Candidate panel: no persisted candidate picks found in qa.csv")
            return False

        # Load notes from qa_row
        notes = clean_text(qa_row.get("notes", ""))
        self.notes_var.set(notes)

        displayed_results: list[dict[str, object]] = []
        has_persisted_picks = False
        for i in range(CANDIDATE_DISPLAY_K):
            rank = i + 1
            video_id = clean_text(qa_row.get(f"candidate_{rank}_video_id"))
            title = clean_text(qa_row.get(f"candidate_{rank}_video_title"))
            channel = clean_text(qa_row.get(f"candidate_{rank}_channel"))

            score_text = ""
            try:
                score_value = float(qa_row.get(f"candidate_{rank}_combined_score"))
                score_text = f"{score_value:.4f}"
            except (TypeError, ValueError):
                score_value = ""

            title_text = ""
            if title and video_id:
                title_text = f"{title} ({video_id})"
            elif title:
                title_text = title
            elif video_id:
                title_text = f"({video_id})"

            self.result_title_labels[i].config(text=title_text)
            self.result_channel_labels[i].config(text=channel)
            self.result_score_labels[i].config(text=score_text)
            self.result_open_buttons[i].config(state=tk.NORMAL if video_id else tk.DISABLED)
            self.candidate_delete_buttons[i].config(state=tk.NORMAL if video_id else tk.DISABLED)
            self.rating_vars[i].set(str(self._safe_parse_rating(qa_row.get(f"candidate_{rank}_rating_1_10"), default=5)))
            self._apply_rating_color(i)

            if video_id or title:
                has_persisted_picks = True

            displayed_results.append(
                {
                    "video_id": video_id,
                    "title": title,
                    "channel": channel,
                    "combined_score": score_value,
                }
            )

        if not has_persisted_picks:
            # Keep notes visible even when candidate picks are empty.
            self._clear_candidate_result_widgets(reset_ratings=True, reset_notes=False)
            self.latest_results = []
            self._clear_stage4_results()
            self._set_candidate_panel_state("Candidate panel: no persisted candidate picks found in qa.csv")
            self.save_btn.config(state=tk.DISABLED)
            return False

        self.latest_results = displayed_results
        self.latest_final_results = displayed_results
        self._sync_candidate_controls_for_current_step()
        self._set_candidate_panel_state("Candidate panel: showing persisted candidate picks from qa.csv")
        self.save_btn.config(state=tk.DISABLED)
        return True

    def _on_search_error(self, error_message: str) -> None:
        self.search_btn.config(state=tk.NORMAL)
        self.save_btn.config(state=tk.DISABLED)
        self.status_var.set("Search failed")
        messagebox.showerror("Search Error", error_message)

    def _open_video(self, index_num: int) -> None:
        if index_num < 0 or index_num >= len(self.latest_results):
            return

        video_id = clean_text(self.latest_results[index_num].get("video_id"))
        if not video_id:
            return

        webbrowser.open(f"https://www.youtube.com/watch?v={video_id}")

    def _on_rating_change(self, index_num: int) -> None:
        self._apply_rating_color(index_num)

    def _on_candidate_rank_change(self, index_num: int) -> None:
        if index_num < 0 or index_num >= CANDIDATE_DISPLAY_K:
            return
        if index_num >= len(self.latest_results):
            return
        new_rank = int(self.candidate_rank_vars[index_num].get().strip())
        n_active = len(self.latest_results)
        # Ensure tracking list is long enough
        while len(self._prev_candidate_ranks) < CANDIDATE_DISPLAY_K:
            self._prev_candidate_ranks.append(len(self._prev_candidate_ranks) + 1)
        old_rank = self._prev_candidate_ranks[index_num]
        if new_rank != old_rank:
            # Shift other active rows: insert-style cascade
            for j in range(n_active):
                if j == index_num:
                    continue
                r = self._prev_candidate_ranks[j]
                if old_rank < new_rank and old_rank < r <= new_rank:
                    # moved down: rows in (old, new] shift up by -1
                    self._prev_candidate_ranks[j] = r - 1
                    self.candidate_rank_vars[j].set(str(r - 1))
                elif new_rank < old_rank and new_rank <= r < old_rank:
                    # moved up: rows in [new, old) shift down by +1
                    self._prev_candidate_ranks[j] = r + 1
                    self.candidate_rank_vars[j].set(str(r + 1))
            self._prev_candidate_ranks[index_num] = new_rank
        self.status_var.set(f"Candidate row {index_num + 1} manual rank set to {new_rank}")

    def _on_precomputed_rank_change(self, index_num: int) -> None:
        if index_num < 0 or index_num >= TOP_K:
            return
        if index_num >= len(self.precomputed_results):
            return
        new_rank = int(self.precomputed_rank_vars[index_num].get().strip())
        n_active = len(self.precomputed_results)
        # Ensure tracking list is long enough
        while len(self._prev_precomputed_ranks) < TOP_K:
            self._prev_precomputed_ranks.append(len(self._prev_precomputed_ranks) + 1)
        old_rank = self._prev_precomputed_ranks[index_num]
        if new_rank != old_rank:
            for j in range(n_active):
                if j == index_num:
                    continue
                r = self._prev_precomputed_ranks[j]
                if old_rank < new_rank and old_rank < r <= new_rank:
                    self._prev_precomputed_ranks[j] = r - 1
                    self.precomputed_rank_vars[j].set(str(r - 1))
                elif new_rank < old_rank and new_rank <= r < old_rank:
                    self._prev_precomputed_ranks[j] = r + 1
                    self.precomputed_rank_vars[j].set(str(r + 1))
            self._prev_precomputed_ranks[index_num] = new_rank
        self.status_var.set(f"Current row {index_num + 1} manual rank set to {new_rank}")

    def _load_step_knockout_df(self) -> pd.DataFrame:
        columns = ["updated_at", "small_step_id", "video_id", "status", "source", "notes"]
        if STEP_KNOCKOUT_PATH.exists():
            knockout_df = pd.read_csv(STEP_KNOCKOUT_PATH)
        else:
            knockout_df = pd.DataFrame(columns=columns)

        for col in columns:
            if col not in knockout_df.columns:
                knockout_df[col] = ""

        knockout_df = knockout_df[columns].copy()
        knockout_df["small_step_id"] = knockout_df["small_step_id"].map(clean_text)
        knockout_df["video_id"] = knockout_df["video_id"].map(clean_text)
        knockout_df["status"] = knockout_df["status"].map(clean_text)
        knockout_df["source"] = knockout_df["source"].map(clean_text)
        knockout_df["notes"] = knockout_df["notes"].map(clean_text)
        return knockout_df

    def _get_step_knocked_out_video_ids(self, small_step_id: str) -> set[str]:
        if not small_step_id:
            return set()
        knockout_df = self._load_step_knockout_df()
        step_df = knockout_df[
            (knockout_df["small_step_id"] == small_step_id)
            & (knockout_df["status"].str.lower() != "inactive")
        ]
        return {video_id for video_id in step_df["video_id"].tolist() if video_id}

    def _apply_step_knockout_filter(self, results: list[dict[str, object]], small_step_id: str) -> list[dict[str, object]]:
        knocked_out_ids = self._get_step_knocked_out_video_ids(small_step_id)
        if not knocked_out_ids:
            return list(results)
        filtered: list[dict[str, object]] = []
        for result in results:
            video_id = clean_text(result.get("video_id"))
            if video_id and video_id in knocked_out_ids:
                continue
            filtered.append(result)
        return filtered

    def _sync_candidate_controls_for_current_step(self) -> None:
        small_step_id = self._selected_small_step_id()
        knocked_out_ids = self._get_step_knocked_out_video_ids(small_step_id)

        for i in range(CANDIDATE_DISPLAY_K):
            default_rank = str(i + 1)
            if i >= len(self.latest_results):
                self.candidate_rank_vars[i].set(default_rank)
                self.candidate_rank_dropdowns[i].config(state=tk.DISABLED)
                self.candidate_knockout_buttons[i].config(state=tk.DISABLED, text="Excl")
                continue

            video_id = clean_text(self.latest_results[i].get("video_id"))
            if not self.candidate_rank_vars[i].get().strip():
                self.candidate_rank_vars[i].set(default_rank)
            self.candidate_rank_dropdowns[i].config(state=tk.NORMAL)
            knockout_text = "Undo" if video_id and video_id in knocked_out_ids else "Excl"
            self.candidate_knockout_buttons[i].config(
                state=tk.NORMAL if video_id else tk.DISABLED,
                text=knockout_text,
            )

    def _sync_precomputed_controls_for_current_step(self) -> None:
        small_step_id = self._selected_small_step_id()
        knocked_out_ids = self._get_step_knocked_out_video_ids(small_step_id)

        for i in range(TOP_K):
            default_rank = str(i + 1)
            if i >= len(self.precomputed_results):
                self.precomputed_rank_vars[i].set(default_rank)
                self.precomputed_rank_dropdowns[i].config(state=tk.DISABLED)
                self.precomputed_knockout_buttons[i].config(state=tk.DISABLED, text="Excl")
                continue
            if not self.precomputed_rank_vars[i].get().strip():
                self.precomputed_rank_vars[i].set(default_rank)
            self.precomputed_rank_dropdowns[i].config(state=tk.NORMAL)
            video_id = clean_text(self.precomputed_results[i].get("video_id"))
            knockout_text = "Undo" if video_id and video_id in knocked_out_ids else "Excl"
            self.precomputed_knockout_buttons[i].config(
                state=tk.NORMAL if video_id else tk.DISABLED,
                text=knockout_text,
            )

    def _get_manual_ranked_candidate_results(self) -> list[dict[str, object]]:
        results = self.latest_results[:CANDIDATE_DISPLAY_K]
        if not results:
            return []

        available_rows = min(CANDIDATE_DISPLAY_K, len(results))
        seen_ranks: set[int] = set()
        row_pairs: list[tuple[int, dict[str, object]]] = []

        for idx in range(available_rows):
            raw_rank = self.candidate_rank_vars[idx].get().strip()
            try:
                parsed_rank = int(raw_rank)
            except ValueError as exc:
                raise ValueError(f"Row {idx + 1} has invalid manual rank '{raw_rank or '?'}'.") from exc

            if parsed_rank < 1 or parsed_rank > available_rows:
                raise ValueError(f"Row {idx + 1} rank must be between 1 and {available_rows}.")
            if parsed_rank in seen_ranks:
                raise ValueError("Manual ranks must be unique (no duplicates).")

            seen_ranks.add(parsed_rank)
            row_pairs.append((parsed_rank, results[idx]))

        expected = set(range(1, available_rows + 1))
        if seen_ranks != expected:
            raise ValueError(f"Manual ranks must cover exactly 1..{available_rows}.")

        row_pairs.sort(key=lambda pair: pair[0])
        return [item for _, item in row_pairs]

    def _get_manual_ranked_precomputed_results(self) -> list[dict[str, object]]:
        results = self.precomputed_results[:TOP_K]
        if not results:
            return []

        available_rows = min(TOP_K, len(results))
        seen_ranks: set[int] = set()
        row_pairs: list[tuple[int, dict[str, object]]] = []

        for idx in range(available_rows):
            raw_rank = self.precomputed_rank_vars[idx].get().strip()
            try:
                parsed_rank = int(raw_rank)
            except ValueError as exc:
                raise ValueError(f"Row {idx + 1} has invalid manual rank '{raw_rank or '?'}'.") from exc

            if parsed_rank < 1 or parsed_rank > available_rows:
                raise ValueError(f"Row {idx + 1} rank must be between 1 and {available_rows}.")
            if parsed_rank in seen_ranks:
                raise ValueError("Manual ranks must be unique (no duplicates).")

            seen_ranks.add(parsed_rank)
            row_pairs.append((parsed_rank, results[idx]))

        expected = set(range(1, available_rows + 1))
        if seen_ranks != expected:
            raise ValueError(f"Manual ranks must cover exactly 1..{available_rows}.")

        row_pairs.sort(key=lambda pair: pair[0])
        return [item for _, item in row_pairs]

    def _toggle_candidate_knockout(self, index_num: int) -> None:
        small_step_id = self._selected_small_step_id()
        if not small_step_id:
            messagebox.showwarning("Missing small step", "Select a small step first.")
            return
        if index_num < 0 or index_num >= len(self.latest_results):
            return

        video_id = clean_text(self.latest_results[index_num].get("video_id"))
        title = clean_text(self.latest_results[index_num].get("title"))
        if not video_id:
            messagebox.showwarning("Missing video", "Selected candidate row has no video_id.")
            return

        knockout_df = self._load_step_knockout_df()
        mask = (knockout_df["small_step_id"] == small_step_id) & (knockout_df["video_id"] == video_id)
        is_active = False
        if mask.any():
            first_idx = knockout_df.index[mask][0]
            current_status = clean_text(knockout_df.at[first_idx, "status"]).lower()
            is_active = current_status != "inactive"

        new_status = "inactive" if is_active else "active"
        now = datetime.now().isoformat(timespec="seconds")
        if mask.any():
            first_idx = knockout_df.index[mask][0]
            knockout_df.at[first_idx, "updated_at"] = now
            knockout_df.at[first_idx, "status"] = new_status
            knockout_df.at[first_idx, "source"] = "gui_candidate_knockout"
            knockout_df.at[first_idx, "notes"] = "toggled_from_candidate_panel"
            duplicate_indices = knockout_df.index[mask][1:]
            if len(duplicate_indices) > 0:
                knockout_df = knockout_df.drop(index=duplicate_indices)
        else:
            new_row = {
                "updated_at": now,
                "small_step_id": small_step_id,
                "video_id": video_id,
                "status": new_status,
                "source": "gui_candidate_knockout",
                "notes": "added_from_candidate_panel",
            }
            knockout_df = pd.concat([knockout_df, pd.DataFrame([new_row])], ignore_index=True)

        STEP_KNOCKOUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        knockout_df.to_csv(STEP_KNOCKOUT_PATH, index=False)
        self._sync_candidate_controls_for_current_step()

        if new_status == "active":
            self.status_var.set(f"Excluded {video_id} for this step; rerun Search Top 3 to backfill.")
            messagebox.showinfo("Candidate excluded", f"Excluded from future Search Top 3 for this step:\n{title} ({video_id})")
        else:
            self.status_var.set(f"Restored {video_id} for this step.")
            messagebox.showinfo("Candidate restored", f"Restored for future Search Top 3 for this step:\n{title} ({video_id})")

    def _toggle_precomputed_knockout(self, index_num: int) -> None:
        small_step_id = self._selected_small_step_id()
        if not small_step_id:
            messagebox.showwarning("Missing small step", "Select a small step first.")
            return
        if index_num < 0 or index_num >= len(self.precomputed_results):
            return

        video_id = clean_text(self.precomputed_results[index_num].get("video_id"))
        title = clean_text(self.precomputed_results[index_num].get("title"))
        if not video_id:
            messagebox.showwarning("Missing video", "Selected current row has no video_id.")
            return

        knockout_df = self._load_step_knockout_df()
        mask = (knockout_df["small_step_id"] == small_step_id) & (knockout_df["video_id"] == video_id)
        is_active = False
        if mask.any():
            first_idx = knockout_df.index[mask][0]
            current_status = clean_text(knockout_df.at[first_idx, "status"]).lower()
            is_active = current_status != "inactive"

        new_status = "inactive" if is_active else "active"
        now = datetime.now().isoformat(timespec="seconds")
        if mask.any():
            first_idx = knockout_df.index[mask][0]
            knockout_df.at[first_idx, "updated_at"] = now
            knockout_df.at[first_idx, "status"] = new_status
            knockout_df.at[first_idx, "source"] = "gui_current_knockout"
            knockout_df.at[first_idx, "notes"] = "toggled_from_current_panel"
            duplicate_indices = knockout_df.index[mask][1:]
            if len(duplicate_indices) > 0:
                knockout_df = knockout_df.drop(index=duplicate_indices)
        else:
            new_row = {
                "updated_at": now,
                "small_step_id": small_step_id,
                "video_id": video_id,
                "status": new_status,
                "source": "gui_current_knockout",
                "notes": "added_from_current_panel",
            }
            knockout_df = pd.concat([knockout_df, pd.DataFrame([new_row])], ignore_index=True)

        STEP_KNOCKOUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        knockout_df.to_csv(STEP_KNOCKOUT_PATH, index=False)
        self._sync_precomputed_controls_for_current_step()
        self._sync_candidate_controls_for_current_step()

        if new_status == "active":
            self.status_var.set(f"Excluded {video_id} for this step; rerun Search Top 3 to backfill.")
            messagebox.showinfo("Current pick excluded", f"Excluded from future Search Top 3 for this step:\n{title} ({video_id})")
        else:
            self.status_var.set(f"Restored {video_id} for this step.")
            messagebox.showinfo("Current pick restored", f"Restored for future Search Top 3 for this step:\n{title} ({video_id})")

    def _apply_rating_color(self, index_num: int) -> None:
        rating_str = self.rating_vars[index_num].get().strip() or "5"
        try:
            rating = int(rating_str)
        except ValueError:
            rating = 5
            self.rating_vars[index_num].set("5")

        bg = rating_to_color(rating)
        fg = text_color_for_bg(bg)

        menu_btn = self.rating_dropdowns[index_num]
        menu_btn.config(bg=bg, fg=fg, activebackground=bg, activeforeground=fg, highlightthickness=1)
        menu_btn["menu"].config(bg="white", fg="black")

    def _populate_precomputed(self, small_step_id: str) -> None:
        self.precomputed_results, source_label = self._build_effective_precomputed_results_for_step(small_step_id)
        self.precomputed_panel_state_var.set(f"Current picks source: {source_label}")
        if "manual override" in source_label:
            self.status_var.set("Manual precomputed override is active for this step")

        for i in range(len(self.precomputed_results), TOP_K):
            self.precomputed_title_labels[i].config(text="")
            self.precomputed_channel_labels[i].config(text="")
            self.precomputed_score_labels[i].config(text="")
            self.precomputed_open_buttons[i].config(state=tk.DISABLED)
            self.precomputed_delete_buttons[i].config(state=tk.DISABLED)
            self.precomputed_rank_vars[i].set(str(i + 1))
            self.precomputed_rank_dropdowns[i].config(state=tk.DISABLED)
            self.precomputed_rating_vars[i].set("5")
            self._apply_precomputed_rating_color(i)

        for i in range(min(TOP_K, len(self.precomputed_results))):
            result = self.precomputed_results[i]
            video_id = clean_text(result.get("video_id"))
            title = clean_text(result.get("title"))
            channel = clean_text(result.get("channel"))
            try:
                combined_score = float(result.get("combined_score") or 0.0)
            except (TypeError, ValueError):
                combined_score = 0.0
            self.precomputed_title_labels[i].config(text=f"{title} ({video_id})")
            self.precomputed_channel_labels[i].config(text=channel)
            self.precomputed_score_labels[i].config(text=f"{combined_score:.4f}")
            self.precomputed_open_buttons[i].config(state=tk.NORMAL if video_id else tk.DISABLED)
            self.precomputed_delete_buttons[i].config(state=tk.NORMAL if video_id else tk.DISABLED)
            self.precomputed_rank_vars[i].set(str(i + 1))
            self.precomputed_rank_dropdowns[i].config(state=tk.NORMAL)
            self.precomputed_rating_vars[i].set("5")
            self._apply_precomputed_rating_color(i)

        self._prev_precomputed_ranks = list(range(1, TOP_K + 1))
        self._sync_precomputed_controls_for_current_step()
        self._restore_saved_ratings(
            small_step_id=small_step_id,
            source="current",
            results=self.precomputed_results,
            rating_vars=self.precomputed_rating_vars,
            apply_color_fn=self._apply_precomputed_rating_color,
        )

    def _open_precomputed_video(self, index_num: int) -> None:
        if index_num < 0 or index_num >= len(self.precomputed_results):
            return
        video_id = clean_text(self.precomputed_results[index_num].get("video_id"))
        if not video_id:
            return
        webbrowser.open(f"https://www.youtube.com/watch?v={video_id}")

    def _on_precomputed_rating_change(self, index_num: int) -> None:
        self._apply_precomputed_rating_color(index_num)

    def _apply_precomputed_rating_color(self, index_num: int) -> None:
        rating_str = self.precomputed_rating_vars[index_num].get().strip() or "5"
        try:
            rating = int(rating_str)
        except ValueError:
            rating = 5
            self.precomputed_rating_vars[index_num].set("5")
        bg = rating_to_color(rating)
        fg = text_color_for_bg(bg)
        menu_btn = self.precomputed_rating_dropdowns[index_num]
        menu_btn.config(bg=bg, fg=fg, activebackground=bg, activeforeground=fg, highlightthickness=1)
        menu_btn["menu"].config(bg="white", fg="black")

    def _safe_parse_rating(self, raw_value: object, default: int = 5) -> int:
        try:
            parsed = int(str(raw_value).strip())
        except (TypeError, ValueError):
            return default
        return max(1, min(10, parsed))

    def _load_qa_df(self) -> pd.DataFrame:
        if QA_TRACKING_PATH.exists():
            qa_df = pd.read_csv(QA_TRACKING_PATH)
        else:
            qa_df = pd.DataFrame(columns=QA_COLUMNS)

        # Legacy schema migration: one row per (small_step_id, source, rank)
        if "source" in qa_df.columns and "rank" in qa_df.columns:
            qa_df = self._migrate_legacy_qa_df(qa_df)

        for col in QA_COLUMNS:
            if col not in qa_df.columns:
                qa_df[col] = ""

        qa_df = qa_df[QA_COLUMNS].copy()
        qa_df["small_step_id"] = qa_df["small_step_id"].map(clean_text)

        text_columns = [col for col in QA_COLUMNS if col not in {"updated_at"}]
        for col in text_columns:
            if col != "small_step_id":
                qa_df[col] = qa_df[col].map(clean_text)

        qa_df = qa_df[qa_df["small_step_id"].str.len() > 0].copy()
        qa_df = qa_df.drop_duplicates(subset=["small_step_id"], keep="last")
        return qa_df.sort_values(["small_step_id"], kind="stable")

    def _migrate_legacy_qa_df(self, legacy_df: pd.DataFrame) -> pd.DataFrame:
        migrated_rows: list[dict[str, object]] = []

        legacy = legacy_df.copy()
        for col in [
            "small_step_id",
            "topic",
            "small_step_name",
            "source",
            "video_id",
            "video_title",
            "channel",
            "candidate_ss_wr_desc",
            "awaiting download and faiss update",
        ]:
            if col not in legacy.columns:
                legacy[col] = ""

        legacy["small_step_id"] = legacy["small_step_id"].map(clean_text)
        legacy["source"] = legacy["source"].map(clean_text)
        legacy["rank"] = pd.to_numeric(legacy.get("rank"), errors="coerce")

        for small_step_id in sorted(legacy["small_step_id"].unique()):
            if not small_step_id:
                continue

            step_rows = legacy[legacy["small_step_id"] == small_step_id].copy()
            if step_rows.empty:
                continue

            base_row = {col: "" for col in QA_COLUMNS}
            latest_row = step_rows.iloc[-1]
            curriculum_row = self.curriculum_by_id.get(small_step_id, {})

            base_row["updated_at"] = clean_text(latest_row.get("updated_at")) or datetime.now().isoformat(timespec="seconds")
            base_row["small_step_id"] = small_step_id
            base_row["topic"] = clean_text(latest_row.get("topic")) or clean_text(curriculum_row.get("topic"))
            base_row["small_step_name"] = clean_text(latest_row.get("small_step_name")) or clean_text(curriculum_row.get("small_step_name"))
            base_row["baseline_ss_wr_desc"] = clean_text(curriculum_row.get("ss_wr_desc"))
            base_row["candidate_ss_wr_desc"] = clean_text(
                step_rows[step_rows["source"] == "candidate"].tail(1).iloc[0].get("candidate_ss_wr_desc")
            ) if not step_rows[step_rows["source"] == "candidate"].empty else ""

            awaiting_series = step_rows["awaiting download and faiss update"].map(clean_text)
            awaiting_values = awaiting_series[awaiting_series.str.len() > 0]
            base_row["awaiting download and faiss update"] = awaiting_values.iloc[-1] if not awaiting_values.empty else ""

            for source in ("current", "candidate"):
                source_rows = step_rows[step_rows["source"] == source]
                for rank in range(1, TOP_K + 1):
                    slot = source_rows[source_rows["rank"] == rank]
                    if slot.empty:
                        continue
                    pick = slot.iloc[-1]
                    prefix = f"{source}_{rank}"
                    base_row[f"{prefix}_video_id"] = clean_text(pick.get("video_id"))
                    base_row[f"{prefix}_video_title"] = clean_text(pick.get("video_title"))
                    base_row[f"{prefix}_channel"] = clean_text(pick.get("channel"))
                    base_row[f"{prefix}_rating_1_10"] = str(self._safe_parse_rating(pick.get("rating"), default=5))
                    base_row[f"{prefix}_combined_score"] = clean_text(pick.get("combined_score"))

            migrated_rows.append(base_row)

        return pd.DataFrame(migrated_rows, columns=QA_COLUMNS)

    def _empty_qa_row(self, row: dict[str, object]) -> dict[str, object]:
        qa_row = {col: "" for col in QA_COLUMNS}
        qa_row["updated_at"] = datetime.now().isoformat(timespec="seconds")
        qa_row["small_step_id"] = clean_text(row.get("small_step_id"))
        qa_row["topic"] = clean_text(row.get("topic"))
        qa_row["small_step_name"] = clean_text(row.get("small_step_name"))
        qa_row["baseline_ss_wr_desc"] = clean_text(row.get("ss_wr_desc"))
        return qa_row

    def _get_qa_row_for_step(self, small_step_id: str) -> dict[str, object] | None:
        if not small_step_id:
            return None
        qa_df = self._load_qa_df()
        step_rows = qa_df[qa_df["small_step_id"] == small_step_id]
        if step_rows.empty:
            return None
        return step_rows.iloc[-1].to_dict()

    def _build_or_get_qa_row_template(self, row: dict[str, object]) -> dict[str, object]:
        small_step_id = clean_text(row.get("small_step_id"))
        existing = self._get_qa_row_for_step(small_step_id)
        if existing is None:
            return self._empty_qa_row(row)

        qa_row = {col: clean_text(existing.get(col)) for col in QA_COLUMNS}
        qa_row["updated_at"] = datetime.now().isoformat(timespec="seconds")
        qa_row["small_step_id"] = small_step_id
        qa_row["topic"] = clean_text(row.get("topic"))
        qa_row["small_step_name"] = clean_text(row.get("small_step_name"))
        qa_row["baseline_ss_wr_desc"] = clean_text(row.get("ss_wr_desc"))
        return qa_row

    def _ensure_qa_template_exists(self) -> None:
        if QA_TRACKING_PATH.exists():
            return

        QA_TRACKING_PATH.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=QA_COLUMNS).to_csv(QA_TRACKING_PATH, index=False)

    def _restore_saved_ratings(
        self,
        small_step_id: str,
        source: str,
        results: list[dict[str, object]],
        rating_vars: list[tk.StringVar],
        apply_color_fn,
    ) -> None:
        if not small_step_id:
            return

        qa_row = self._get_qa_row_for_step(small_step_id)
        if qa_row is None:
            return

        for i in range(len(rating_vars)):
            rank = i + 1
            qa_video_id = clean_text(qa_row.get(f"{source}_{rank}_video_id"))
            result_video_id = ""
            if i < len(results):
                result_video_id = clean_text(results[i].get("video_id"))

            # Only restore when empty/template row or matching video id.
            if qa_video_id and result_video_id and qa_video_id != result_video_id:
                continue

            rating_vars[i].set(str(self._safe_parse_rating(qa_row.get(f"{source}_{rank}_rating_1_10"), default=5)))
            apply_color_fn(i)

    def _build_qa_row(
        self,
        row: dict[str, object],
        candidate_text: str,
        candidate_ratings: list[int],
        precomputed_ratings: list[int],
        awaiting_download_faiss_text: str,
    ) -> dict[str, object]:
        qa_row = self._build_or_get_qa_row_template(row)
        qa_row["updated_at"] = datetime.now().isoformat(timespec="seconds")
        qa_row["candidate_ss_wr_desc"] = candidate_text
        # constraints_text is intentionally NOT written here; it is managed
        # exclusively by _save_constraints_text so constraints stay per-step.
        qa_row["awaiting download and faiss update"] = awaiting_download_faiss_text
        notes_text = self.notes_entry.get().strip()
        if not notes_text:
            notes_text = self.notes_var.get().strip()
        qa_row["notes"] = notes_text

        def fill_slots(source: str, results: list[dict[str, object]], ratings: list[int]) -> None:
            limit = TOP_K if source == "current" else CANDIDATE_DISPLAY_K
            for idx in range(limit):
                rank = idx + 1
                prefix = f"{source}_{rank}"
                result = results[idx] if idx < len(results) else {}
                qa_row[f"{prefix}_video_id"] = clean_text(result.get("video_id"))
                qa_row[f"{prefix}_video_title"] = clean_text(result.get("title"))
                qa_row[f"{prefix}_channel"] = clean_text(result.get("channel"))
                qa_row[f"{prefix}_rating_1_10"] = str(ratings[idx] if idx < len(ratings) else 5)

                combined_score = clean_text(result.get("combined_score"))
                semantic_score = clean_text(result.get("semantic_score"))
                instruction_score = clean_text(result.get("instruction_score"))
                alignment_score = clean_text(result.get("alignment_score"))

                qa_row[f"{prefix}_combined_score"] = combined_score
                qa_row[f"{prefix}_semantic_score"] = semantic_score
                qa_row[f"{prefix}_instruction_score"] = instruction_score
                qa_row[f"{prefix}_alignment_score"] = alignment_score

        fill_slots("current", self.precomputed_results, precomputed_ratings)
        fill_slots("candidate", self.latest_results, candidate_ratings)
        return qa_row

    def _upsert_qa_row(self, qa_row: dict[str, object]) -> None:
        self._ensure_qa_template_exists()
        qa_df = self._load_qa_df()
        new_df = pd.DataFrame([{col: qa_row.get(col, "") for col in QA_COLUMNS}], columns=QA_COLUMNS)

        merged = pd.concat([qa_df, new_df], ignore_index=True)
        merged = merged.drop_duplicates(subset=["small_step_id"], keep="last")
        merged = merged.sort_values(["small_step_id"], kind="stable")
        merged.to_csv(QA_TRACKING_PATH, index=False)

    def _update_qa_csv(self) -> None:
        small_step_id = self._selected_small_step_id()
        row = self.curriculum_by_id.get(small_step_id)
        if row is None:
            messagebox.showwarning("Missing small step", "Select a small step first.")
            return

        candidate_text = self.candidate_text.get("1.0", tk.END).strip()
        awaiting_download_faiss_text = "Awaiting download/faiss rebuild" if self.awaiting_download_faiss_var.get() else ""

        candidate_ratings = [self._safe_parse_rating(var.get(), default=5) for var in self.rating_vars]
        precomputed_ratings = [self._safe_parse_rating(var.get(), default=5) for var in self.precomputed_rating_vars]

        qa_row = self._build_qa_row(
            row=row,
            candidate_text=candidate_text,
            candidate_ratings=candidate_ratings,
            precomputed_ratings=precomputed_ratings,
            awaiting_download_faiss_text=awaiting_download_faiss_text,
        )

        try:
            self._upsert_qa_row(qa_row)
            if candidate_text:
                self._save_approved_candidate_mapping(row=row, candidate=candidate_text)
        except Exception as exc:
            messagebox.showerror("QA Save Error", str(exc))
            return

        self.saved_step_ids = self._load_saved_step_ids_from_qa()
        self._refresh_step_combo_labels(preserve_step_id=small_step_id)
        self.awaiting_download_faiss_var.set(False)
        small_step_id = self._selected_small_step_id()
        if not small_step_id:
            self.status_var.set("Updated qa/qa.csv. Current step is filtered out by Show unsaved only.")
            messagebox.showinfo("QA Updated", f"Saved QA row to:\n{QA_TRACKING_PATH}")
            return

        if self._populate_candidate_from_qa(small_step_id):
            self.candidate_display_unlocked_steps.add(small_step_id)
            self.status_var.set("Updated qa/qa.csv and loaded persisted candidate picks.")
        else:
            self.candidate_display_unlocked_steps.discard(small_step_id)
            self._clear_candidate_result_widgets(reset_ratings=False, reset_notes=False)
            self._set_candidate_panel_state("Candidate panel: Update QA CSV ran, but no persisted candidate picks were found")
            self.status_var.set("Updated qa/qa.csv. Candidate panel remains blank because no candidate picks are stored yet.")

        messagebox.showinfo("QA Updated", f"Saved QA row to:\n{QA_TRACKING_PATH}")

    def _promote_to_canonical(self) -> None:
        """Write the current candidate text to the canonical ss_desc_validated_overrides.csv."""
        small_step_id = self._selected_small_step_id()
        row = self.curriculum_by_id.get(small_step_id)
        if row is None:
            messagebox.showwarning("No small step", "Select a small step first.")
            return

        candidate_text = self.candidate_text.get("1.0", tk.END).strip()
        if not candidate_text:
            messagebox.showwarning("Empty candidate", "Enter a candidate wording before promoting.")
            return

        try:
            upsert_validated_override(
                override_path=CANONICAL_OVERRIDE_PATH,
                small_step_id=clean_text(row.get("small_step_id")),
                ss_desc_validated=candidate_text,
                source="qa_promoted",
            )
        except Exception as exc:
            messagebox.showerror("Promote Error", str(exc))
            return

        # Track promoted step and update UI
        self.promoted_step_ids.add(small_step_id)
        self.promoted_status_var.set("✓ Promoted to canonical")
        self.status_var.set(f"Promoted to canonical: {clean_text(row.get('small_step_id'))}")
        self._refresh_step_combo_labels(preserve_step_id=small_step_id)
        messagebox.showinfo(
            "Promoted",
            f"Candidate written to canonical overrides:\n{CANONICAL_OVERRIDE_PATH}\n\n"
            f"Run precompute_curriculum_recommendations.py to rebuild recommendations.",
        )

    def _append_result_to_videos_to_delete(self, source: str, index_num: int) -> None:
        results = self.precomputed_results if source == "current" else self.latest_results
        if index_num < 0 or index_num >= len(results):
            return

        result = results[index_num]
        video_id = clean_text(result.get("video_id"))
        video_title = clean_text(result.get("title") or result.get("video_title"))
        channel = clean_text(result.get("channel"))
        if not video_id:
            messagebox.showwarning("Missing video", "No video_id found for this row.")
            return

        VIDEOS_TO_DELETE_PATH.parent.mkdir(parents=True, exist_ok=True)
        if VIDEOS_TO_DELETE_PATH.exists():
            delete_df = pd.read_csv(VIDEOS_TO_DELETE_PATH)
        else:
            delete_df = pd.DataFrame(columns=["video_id", "video_title", "channel"])

        if "video_id" not in delete_df.columns:
            first_col = delete_df.columns[0] if len(delete_df.columns) > 0 else None
            if first_col:
                delete_df = delete_df.rename(columns={first_col: "video_id"})
            else:
                delete_df["video_id"] = ""

        for required_col in ("video_title", "channel"):
            if required_col not in delete_df.columns:
                delete_df[required_col] = ""

        delete_df["video_id"] = delete_df["video_id"].map(clean_text)
        if (delete_df["video_id"] == video_id).any():
            self.status_var.set(f"{video_id} is already in videos_to_delete.csv")
            return

        delete_df = pd.concat(
            [
                delete_df,
                pd.DataFrame(
                    [
                        {
                            "video_id": video_id,
                            "video_title": video_title,
                            "channel": channel,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
        delete_df.to_csv(VIDEOS_TO_DELETE_PATH, index=False)
        self.status_var.set(f"Appended {video_id} to videos_to_delete.csv")

    def _clear_for_new_step_selection(self) -> None:
        """Clear UI when loading a new step, preserving notes from qa.csv."""
        self._clear_candidate_result_widgets(reset_ratings=True, reset_notes=True)

    def _save_candidate(self) -> None:
        small_step_id = self._selected_small_step_id()
        row = self.curriculum_by_id.get(small_step_id)

        if row is None:
            messagebox.showwarning("Missing small step", "Select a small step first.")
            return

        candidate = self.candidate_text.get("1.0", tk.END).strip()
        if not candidate:
            messagebox.showwarning("Missing candidate", "Candidate wording is empty.")
            return

        if not self.latest_results:
            messagebox.showwarning("No results", "Run Search Top 3 before saving.")
            return

        scenario_label = clean_text(self.scenario_var.get()) or "gui_mvp_approved"

        ratings: list[int] = []
        for i in range(CANDIDATE_DISPLAY_K):
            try:
                ratings.append(int(self.rating_vars[i].get().strip()))
            except ValueError:
                ratings.append(5)

        try:
            upsert_validated_override(
                override_path=CANONICAL_OVERRIDE_PATH,
                small_step_id=clean_text(row.get("small_step_id")),
                ss_desc_validated=candidate,
                source="gui_save_candidate",
            )
            self._save_approved_candidate_mapping(row=row, candidate=candidate)
            self._upsert_targeted_override(row=row, candidate=candidate, scenario_label=scenario_label, ratings=ratings)
            self.saved_candidate_steps.add(small_step_id)
            self.candidate_display_unlocked_steps.discard(small_step_id)
            self._set_candidate_panel_state("Candidate panel: candidate saved, click Update QA CSV to show persisted picks")
            self.status_var.set("Saved approved candidate and override row.")
            messagebox.showinfo(
                "Saved",
                f"Saved to:\n{CANONICAL_OVERRIDE_PATH}\n{APPROVED_CANDIDATES_PATH}\n{TARGET_OVERRIDES_PATH}",
            )
        except Exception as exc:
            messagebox.showerror("Save Error", str(exc))

    def _save_approved_candidate_mapping(self, row: dict[str, object], candidate: str) -> None:
        APPROVED_CANDIDATES_PATH.parent.mkdir(parents=True, exist_ok=True)

        now = datetime.now().isoformat(timespec="seconds")

        base_columns = ["updated_at", "small_step_id", "candidate_ss_wr_desc"]
        record = {
            "updated_at": now,
            "small_step_id": clean_text(row.get("small_step_id")),
            "candidate_ss_wr_desc": candidate,
        }

        if APPROVED_CANDIDATES_PATH.exists():
            approved_df = pd.read_csv(APPROVED_CANDIDATES_PATH)
        else:
            approved_df = pd.DataFrame(columns=base_columns)

        for col in base_columns:
            if col not in approved_df.columns:
                approved_df[col] = ""

        approved_df["small_step_id"] = approved_df["small_step_id"].map(clean_text)
        merged = pd.concat([approved_df[base_columns], pd.DataFrame([record], columns=base_columns)], ignore_index=True)
        merged = merged.drop_duplicates(subset=["small_step_id"], keep="last")
        merged = merged.sort_values(["small_step_id"], kind="stable")
        merged.to_csv(APPROVED_CANDIDATES_PATH, index=False)

    def _upsert_targeted_override(
        self,
        row: dict[str, object],
        candidate: str,
        scenario_label: str,
        ratings: list[int],
    ) -> None:
        TARGET_OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)

        base_columns = ["small_step_id", "scenario_label", "candidate_ss_wr_desc", "status", "notes"]
        if TARGET_OVERRIDES_PATH.exists():
            overrides_df = pd.read_csv(TARGET_OVERRIDES_PATH)
        else:
            overrides_df = pd.DataFrame(columns=base_columns)

        for col in base_columns:
            if col not in overrides_df.columns:
                overrides_df[col] = ""

        overrides_df["small_step_id"] = overrides_df["small_step_id"].map(clean_text)
        overrides_df["scenario_label"] = overrides_df["scenario_label"].map(clean_text)

        top_video_ids = [clean_text(result.get("video_id")) for result in self.latest_results]
        top_ids_joined = " | ".join([vid for vid in top_video_ids if vid])
        notes = (
            "saved_from_gui_mvp"
            f";ratings={','.join(str(x) for x in ratings)}"
            f";top3={top_ids_joined}"
        )

        new_row = {
            "small_step_id": clean_text(row.get("small_step_id")),
            "scenario_label": scenario_label,
            "candidate_ss_wr_desc": candidate,
            "status": "active",
            "notes": notes,
        }

        mask = (
            (overrides_df["small_step_id"] == new_row["small_step_id"])
            & (overrides_df["scenario_label"] == new_row["scenario_label"])
        )

        if mask.any():
            first_index = overrides_df.index[mask][0]
            for col, value in new_row.items():
                overrides_df.at[first_index, col] = value
            duplicate_indices = overrides_df.index[mask][1:]
            if len(duplicate_indices) > 0:
                overrides_df = overrides_df.drop(index=duplicate_indices)
        else:
            overrides_df = pd.concat([overrides_df, pd.DataFrame([new_row])], ignore_index=True)

        overrides_df.to_csv(TARGET_OVERRIDES_PATH, index=False)


    # ------------------------------------------------------------------ #
    # Dup proximity scoring helpers                                        #
    # ------------------------------------------------------------------ #

def _build_step_global_num_lookup(self) -> None:
    """Build step_id -> small_step_num_global and reverse lookup from precomputed_df."""
    self.step_global_num = {}
    self.global_num_to_step_id = {}
    if self.precomputed_df.empty:
        return
    seen: set[str] = set()
    for _, row in self.precomputed_df.iterrows():
        sid = clean_text(row.get("small_step_id", ""))
        if not sid or sid in seen:
            continue
        seen.add(sid)
        try:
            g = int(row["small_step_num_global"])
        except (ValueError, TypeError, KeyError):
            continue
        self.step_global_num[sid] = g
        self.global_num_to_step_id[g] = sid


def _compute_dup_scores(self) -> dict[str, dict]:
    """Compute per-step proximity duplicate H_i scores.

    Returns dict small_step_id -> {H, A, B, C, n_links, nearest_d}.
    Only steps with at least one duplicate link within the same year/age/term
    context receive a score; the rest are absent from the dict.
    """
    import numpy as np
    from collections import defaultdict

    if self.precomputed_df.empty:
        return {}

    df = self.precomputed_df.copy()
    df["small_step_num_global"] = pd.to_numeric(df["small_step_num_global"], errors="coerce")

    W = DUP_REVIEW_W
    k = DUP_REVIEW_K_SHRINK

    # Build video -> list of step appearances (deduplicated per video/step pair)
    video_appearances: dict[str, list] = defaultdict(list)
    seen_pairs: set[tuple] = set()
    for _, row in df.iterrows():
        vid = clean_text(row.get("video_id", ""))
        sid = clean_text(row.get("small_step_id", ""))
        if not vid or not sid or (vid, sid) in seen_pairs:
            continue
        seen_pairs.add((vid, sid))
        g_raw = row["small_step_num_global"]
        if pd.isna(g_raw):
            continue
        video_appearances[vid].append({
            "sid": sid,
            "g": int(g_raw),
            "year": clean_text(row.get("year", "")),
            "age": clean_text(row.get("age", "")),
            "term": clean_text(row.get("term", "")),
        })

    # Collect distances per step from duplicate links within same year/age/term
    step_links: dict[str, list[int]] = defaultdict(list)
    for vid, appearances in video_appearances.items():
        if len(appearances) < 2:
            continue
        for a in appearances:
            for b in appearances:
                if b["sid"] == a["sid"]:
                    continue
                if a["year"] == b["year"] and a["age"] == b["age"] and a["term"] == b["term"]:
                    step_links[a["sid"]].append(abs(a["g"] - b["g"]))

    if not step_links:
        return {}

    # Compute A (absolute proximity pressure) and C (very-near proportion) per step
    step_scores: dict[str, dict] = {}
    step_A: dict[str, float] = {}
    for sid, links in step_links.items():
        n = len(links)
        mean_pen = sum(max(0.0, 1.0 - d / W) for d in links) / n
        S = n / (n + k)
        A = S * mean_pen
        C = sum(1 for d in links if d <= 3) / n
        step_scores[sid] = {
            "A": round(A, 4),
            "C": round(C, 4),
            "n_links": n,
            "nearest_d": min(links),
            "H": 0.0,
            "B": 0.0,
        }
        step_A[sid] = A

    # Build context groups for B_i (z-score within year/age/term/topic)
    step_ctx: dict[str, tuple] = {}
    for _, row in df.drop_duplicates(subset=["small_step_id"]).iterrows():
        sid = clean_text(row.get("small_step_id", ""))
        if sid:
            step_ctx[sid] = (
                clean_text(row.get("year", "")),
                clean_text(row.get("age", "")),
                clean_text(row.get("term", "")),
                clean_text(row.get("topic", "")),
            )

    ctx4_groups: dict[tuple, list] = defaultdict(list)
    ctx3_groups: dict[tuple, list] = defaultdict(list)
    for sid in step_scores:
        ctx = step_ctx.get(sid, ("", "", "", ""))
        ctx4_groups[ctx].append(sid)
        ctx3_groups[ctx[:3]].append(sid)

    for sid, scores in step_scores.items():
        ctx = step_ctx.get(sid, ("", "", "", ""))
        group = ctx4_groups[ctx]
        if len(group) < 4:
            group = ctx3_groups[ctx[:3]]
        group_A = [step_A[g] for g in group if g in step_A]
        if len(group_A) >= 3:
            mu = float(np.mean(group_A))
            sigma = float(np.std(group_A))
            B = max(0.0, (scores["A"] - mu) / sigma) if sigma > 0 else 0.0
        else:
            B = 0.0
        scores["B"] = round(B, 4)
        B_scaled = min(B, 4.0) / 4.0
        scores["H"] = round(0.5 * scores["A"] + 0.3 * B_scaled + 0.2 * scores["C"], 4)

    return step_scores


def _load_dup_flagged_steps(self) -> set[str]:
    if not DUP_FLAGGED_PATH.exists():
        return set()
    try:
        df = pd.read_csv(DUP_FLAGGED_PATH)
        if "small_step_id" not in df.columns:
            return set()
        return set(df["small_step_id"].map(clean_text).dropna().tolist())
    except Exception:
        return set()


def _save_dup_flagged_steps(self) -> None:
    df = pd.DataFrame({"small_step_id": sorted(self.dup_flagged_steps)})
    _atomic_write_csv(df, DUP_FLAGGED_PATH)


def _flag_current_step_redundant(self) -> None:
    sid = self._selected_small_step_id()
    if not sid:
        return
    if sid in self.dup_flagged_steps:
        self.dup_flagged_steps.discard(sid)
        if self.dup_flag_btn is not None:
            self.dup_flag_btn.config(text="Mark Step Redundant")
        self.status_var.set(f"Marked keep: {sid}")
    else:
        self.dup_flagged_steps.add(sid)
        if self.dup_flag_btn is not None:
            self.dup_flag_btn.config(text="Mark Step Keep")
        self.status_var.set(f"Marked redundant: {sid}")
    self._save_dup_flagged_steps()
    current = self._selected_small_step_id()
    self._refresh_step_combo_labels(preserve_step_id=current)
    self._update_dup_score_display()


def _toggle_dup_review_mode(self) -> None:
    self.dup_review_mode = not self.dup_review_mode
    if self.dup_review_btn is not None:
        self.dup_review_btn.config(text=f"High-Dup Review: {'ON' if self.dup_review_mode else 'OFF'}")
    current = self._selected_small_step_id()
    self._refresh_step_combo_labels(preserve_step_id=current)
    self.status_var.set(
        "Dup Review ON — combo sorted by dup score (highest first)"
        if self.dup_review_mode
        else "Dup Review OFF — normal curriculum order restored"
    )


def _jump_to_next_dup_hotspot(self) -> None:
    if not self.dup_scores:
        messagebox.showinfo("No dup scores", "Dup scores have not been computed yet (precomputed CSV may not be loaded).")
        return
    try:
        pct = max(1, min(100, int(self.dup_threshold_pct_var.get())))
    except ValueError:
        pct = DUP_REVIEW_DEFAULT_TOP_PCT

    scored = sorted(self.sorted_step_ids, key=lambda sid: -self.dup_scores.get(sid, {}).get("H", 0.0))
    n_top = max(1, int(len(scored) * pct / 100))
    top_ids = scored[:n_top]
    candidate_ids = [sid for sid in top_ids if sid not in self.dup_flagged_steps]

    if not candidate_ids:
        messagebox.showinfo(
            "All hotspots reviewed",
            f"All top-{pct}% high-dup steps are marked redundant. Raise the threshold or mark some as keep.",
        )
        return

    current = self._selected_small_step_id()
    try:
        cur_idx = candidate_ids.index(current)
        next_idx = (cur_idx + 1) % len(candidate_ids)
    except ValueError:
        next_idx = 0

    target = candidate_ids[next_idx]
    if not self._set_selected_step_by_id(target):
        self.show_unsaved_only_var.set(False)
        self._refresh_step_combo_labels(preserve_step_id=target)
        self._set_selected_step_by_id(target)

    s = self.dup_scores.get(target, {})
    self.status_var.set(
        f"High-dup step {next_idx + 1}/{len(candidate_ids)}: H={s.get('H', 0):.3f}  "
        f"n={s.get('n_links', 0)}  nearest_d={s.get('nearest_d', '?')}"
    )


def _update_dup_score_display(self) -> None:
    sid = self._selected_small_step_id()
    if not sid or not self.dup_scores:
        self.dup_score_display_var.set("")
        return
    s = self.dup_scores.get(sid)
    if s is None:
        self.dup_score_display_var.set("High-dup: no proximal duplicates in same term")
        if self.dup_flag_btn is not None:
            self.dup_flag_btn.config(text="Mark Step Redundant")
        return
    flagged = "  [FLAGGED REDUNDANT]" if sid in self.dup_flagged_steps else ""
    self.dup_score_display_var.set(
        f"High-dup score: H={s['H']:.3f}  A={s['A']:.3f}  C={s['C']:.3f}"
        f"  n={s['n_links']}  nearest_d={s['nearest_d']}{flagged}"
    )
    if self.dup_flag_btn is not None:
        self.dup_flag_btn.config(text="Mark Step Keep" if sid in self.dup_flagged_steps else "Mark Step Redundant")


def _populate_dup_neighbours(self, small_step_id: str) -> None:
    """Fill the Dup Neighbours text panel with adjacent steps and their ss_wr_desc."""
    if self.dup_neighbour_text is None:
        return
    self.dup_neighbour_text.config(state=tk.NORMAL)
    self.dup_neighbour_text.delete("1.0", tk.END)

    if not small_step_id:
        self.dup_neighbour_text.config(state=tk.DISABLED)
        return

    g = self.step_global_num.get(small_step_id)
    if g is None:
        self.dup_neighbour_text.insert(tk.END, "(No global step number found — precomputed CSV may not cover this step.)")
        self.dup_neighbour_text.config(state=tk.DISABLED)
        return

    sep_major = "═" * 72
    sep_minor = "─" * 72
    lines: list[str] = []

    for offset in range(-DUP_NEIGHBOUR_RADIUS, DUP_NEIGHBOUR_RADIUS + 1):
        target_g = g + offset
        target_sid = self.global_num_to_step_id.get(target_g)
        is_current = offset == 0

        if target_sid:
            row = self.curriculum_by_id.get(target_sid, {})
            topic = clean_text(row.get("topic"))
            name = clean_text(row.get("small_step_name"))
            ss_desc = clean_text(row.get("ss_wr_desc"))
            s = self.dup_scores.get(target_sid)
            dup_info = (
                f"H={s['H']:.3f}  n={s['n_links']}  nearest_d={s['nearest_d']}"
                if s else "no proximal dups"
            )
            flagged_marker = "  [FLAGGED]" if target_sid in self.dup_flagged_steps else ""
            direction = "" if is_current else ("↑" if offset < 0 else "↓")

            lines.append(sep_major if is_current else sep_minor)
            if is_current:
                lines.append(f">>> [G={target_g}] {topic} | {name}   ← CURRENT  [{dup_info}]{flagged_marker}")
            else:
                lines.append(f"{direction}   [G={target_g}] {topic} | {name}   [{dup_info}]{flagged_marker}")

            if ss_desc:
                # Soft-wrap at ~88 chars with 2-space indent
                words = ss_desc.split()
                current_line = "  "
                for word in words:
                    if len(current_line) + len(word) + 1 > 88:
                        lines.append(current_line)
                        current_line = "  " + word
                    else:
                        current_line += (" " if current_line.strip() else "") + word
                if current_line.strip():
                    lines.append(current_line)
        else:
            lines.append(sep_minor)
            lines.append(f"[G={target_g}] (no step at this position in precomputed data)")

        lines.append("")

    self.dup_neighbour_text.insert(tk.END, "\n".join(lines))
    # Scroll to current step (approximate: each entry is ~5 lines, current is at radius offset)
    approx_line = DUP_NEIGHBOUR_RADIUS * 6 + 1
    self.dup_neighbour_text.see(f"{approx_line}.0")
    self.dup_neighbour_text.config(state=tk.DISABLED)


# Bind the above functions as methods of ImprovePickQAGUI
ImprovePickQAGUI._build_step_global_num_lookup = _build_step_global_num_lookup
ImprovePickQAGUI._compute_dup_scores = _compute_dup_scores
ImprovePickQAGUI._load_dup_flagged_steps = _load_dup_flagged_steps
ImprovePickQAGUI._save_dup_flagged_steps = _save_dup_flagged_steps
ImprovePickQAGUI._flag_current_step_redundant = _flag_current_step_redundant
ImprovePickQAGUI._toggle_dup_review_mode = _toggle_dup_review_mode
ImprovePickQAGUI._jump_to_next_dup_hotspot = _jump_to_next_dup_hotspot
ImprovePickQAGUI._update_dup_score_display = _update_dup_score_display
ImprovePickQAGUI._populate_dup_neighbours = _populate_dup_neighbours


def main() -> None:
    root = tk.Tk()
    app = ImprovePickQAGUI(root)
    _ = app
    root.mainloop()


if __name__ == "__main__":
    main()
