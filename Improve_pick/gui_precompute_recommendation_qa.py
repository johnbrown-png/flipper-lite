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
from pathlib import Path
import re
import sys
import threading
from typing import Any
import webbrowser

import pandas as pd
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

# Ensure imports work when script is launched from Improve_pick/
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from precompute_curriculum_recommendations import calculate_cosine_similarity, load_faiss_index
from query_embedder import QueryEmbedder
from data_pipeline.deletion_tracker import DeletionTracker
from data_pipeline.instruction_quality_scorer import InstructionQualityScorer
from shared.curriculum_schema import curriculum_to_long_df


CURRICULUM_PATH = project_root / "Curriculum" / "Maths" / "curriculum_22032026_small_steps.csv"
TARGET_OVERRIDES_PATH = project_root / "qa" / "targeted_ss_wr_desc_overrides.csv"
APPROVED_CANDIDATES_PATH = project_root / "qa" / "approved_ss_wr_desc_candidates.csv"
QA_TRACKING_PATH = project_root / "qa" / "qa.csv"
VIDEOS_TO_DELETE_PATH = project_root / "videos_to_delete" / "videos_to_delete.csv"
TOP_K = 3
SEMANTIC_PREVIEW_K = 5
SEMANTIC_PREVIEW_CHUNKS = 40
SEMANTIC_PREVIEW_DEBOUNCE_MS = 550
CONSTRAINTS_GATE_DEFAULT_K = 20
CONSTRAINTS_GATE_MAX_K = 80
SEMANTIC_WEIGHT = 0.55
ALIGNMENT_WEIGHT = 0.20
INSTRUCTION_WEIGHT = 0.25


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
    ]

    for source in ("current", "candidate"):
        for rank in range(1, TOP_K + 1):
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


def build_query_text(topic: str, small_step_name: str, ss_wr_desc: str) -> str:
    query_text = f"{topic}: {small_step_name}"
    if ss_wr_desc:
        query_text += f" - {ss_wr_desc}"
    return query_text


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


def load_video_lookup() -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    video_inventory_path = project_root / "video_inventory.csv"
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

        self.precomputed_df: pd.DataFrame = pd.DataFrame()
        self.precomputed_results: list[dict[str, object]] = []
        self.precomputed_title_labels: list[ttk.Label] = []
        self.precomputed_channel_labels: list[ttk.Label] = []
        self.precomputed_score_labels: list[ttk.Label] = []
        self.precomputed_open_buttons: list[ttk.Button] = []
        self.precomputed_delete_buttons: list[ttk.Button] = []
        self.precomputed_rating_vars: list[tk.StringVar] = []
        self.precomputed_rating_dropdowns: list[tk.OptionMenu] = []
        self.candidate_delete_buttons: list[ttk.Button] = []
        self.semantic_preview_title_labels: list[ttk.Label] = []
        self.semantic_preview_channel_labels: list[ttk.Label] = []
        self.semantic_preview_score_labels: list[ttk.Label] = []
        self.saved_candidate_steps: set[str] = set()
        self.candidate_display_unlocked_steps: set[str] = set()
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
        outer.rowconfigure(4, weight=1)

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
        self.show_unsaved_check = ttk.Checkbutton(
            selector_frame,
            text="Show unsaved only",
            variable=self.show_unsaved_only_var,
            command=self._on_show_unsaved_only_changed,
        )
        self.show_unsaved_check.grid(row=1, column=2, columnspan=2, sticky="w", padx=(12, 0), pady=(4, 0))

        text_frame = ttk.LabelFrame(outer, text="Query Text", padding=8)
        text_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 4))
        text_frame.columnconfigure(0, weight=1)
        text_frame.columnconfigure(1, weight=1)

        baseline_frame = ttk.Frame(text_frame)
        baseline_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        baseline_frame.columnconfigure(0, weight=1)
        baseline_frame.rowconfigure(1, weight=1)
        ttk.Label(baseline_frame, text="Current ss_wr_desc", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        self.baseline_text = scrolledtext.ScrolledText(baseline_frame, wrap=tk.WORD, height=3)
        self.baseline_text.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        self.baseline_text.config(state=tk.DISABLED)

        candidate_frame = ttk.Frame(text_frame)
        candidate_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        candidate_frame.columnconfigure(0, weight=1)
        candidate_frame.rowconfigure(1, weight=1)
        ttk.Label(candidate_frame, text="Candidate wording (candidate_ss_wr_desc)", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        self.candidate_text = scrolledtext.ScrolledText(candidate_frame, wrap=tk.WORD, height=5)
        self.candidate_text.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        self.candidate_text.bind("<<Modified>>", self._on_candidate_text_modified)

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

        self.awaiting_download_check = ttk.Checkbutton(
            control_frame,
            text="Set 'Awaiting download/faiss rebuild' on Update QA CSV",
            variable=self.awaiting_download_faiss_var,
        )
        self.awaiting_download_check.grid(row=0, column=2, padx=(0, 8), sticky="w")

        self.status_label = ttk.Label(control_frame, textvariable=self.status_var, foreground="blue")
        self.status_label.grid(row=0, column=3, sticky="w")

        rating_options = [str(i) for i in range(1, 11)]

        results_notebook = ttk.Notebook(outer)
        results_notebook.grid(row=4, column=0, sticky="nsew")

        qa_results_tab = ttk.Frame(results_notebook, padding=6)
        qa_results_tab.columnconfigure(0, weight=1)
        qa_results_tab.columnconfigure(1, weight=1)
        qa_results_tab.rowconfigure(0, weight=1)
        results_notebook.add(qa_results_tab, text="Stage 1 QA Results")

        constraints_tab = ttk.Frame(results_notebook, padding=6)
        constraints_tab.columnconfigure(0, weight=1)
        constraints_tab.rowconfigure(2, weight=1)
        results_notebook.add(constraints_tab, text="Stage 2 Constraints Gate")

        alignment_tab = ttk.Frame(results_notebook, padding=6)
        alignment_tab.columnconfigure(0, weight=1)
        alignment_tab.rowconfigure(1, weight=1)
        results_notebook.add(alignment_tab, text="Stage 3 Alignment")

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
        ).grid(row=0, column=0, columnspan=7, sticky="w", padx=4, pady=(0, 4))

        headers = ["Rank", "Title", "Channel", "Score", "Open", "Delete", "Rating"]
        for col, header in enumerate(headers):
            ttk.Label(precomp_frame, text=header, font=("Segoe UI", 10, "bold")).grid(row=0, column=col, sticky="w", padx=4, pady=(0, 4))
            ttk.Label(candidate_results_frame, text=header, font=("Segoe UI", 10, "bold")).grid(row=1, column=col, sticky="w", padx=4, pady=(0, 4))

        for i in range(TOP_K):
            row_num = i + 1
            ttk.Label(precomp_frame, text=f"{row_num}").grid(row=row_num, column=0, sticky="w", padx=4, pady=2)
            ttk.Label(candidate_results_frame, text=f"{row_num}").grid(row=row_num + 1, column=0, sticky="w", padx=4, pady=2)

            p_title = ttk.Label(precomp_frame, text="", width=44)
            p_title.grid(row=row_num, column=1, sticky="w", padx=4, pady=2)
            self.precomputed_title_labels.append(p_title)
            c_title = ttk.Label(candidate_results_frame, text="", width=44)
            c_title.grid(row=row_num + 1, column=1, sticky="w", padx=4, pady=2)
            self.result_title_labels.append(c_title)

            p_channel = ttk.Label(precomp_frame, text="", width=20)
            p_channel.grid(row=row_num, column=2, sticky="w", padx=4, pady=2)
            self.precomputed_channel_labels.append(p_channel)
            c_channel = ttk.Label(candidate_results_frame, text="", width=20)
            c_channel.grid(row=row_num + 1, column=2, sticky="w", padx=4, pady=2)
            self.result_channel_labels.append(c_channel)

            p_score = ttk.Label(precomp_frame, text="", width=10)
            p_score.grid(row=row_num, column=3, sticky="w", padx=4, pady=2)
            self.precomputed_score_labels.append(p_score)
            c_score = ttk.Label(candidate_results_frame, text="", width=10)
            c_score.grid(row=row_num + 1, column=3, sticky="w", padx=4, pady=2)
            self.result_score_labels.append(c_score)

            p_open = ttk.Button(precomp_frame, text="Open", command=lambda idx=i: self._open_precomputed_video(idx), state=tk.DISABLED)
            p_open.grid(row=row_num, column=4, sticky="w", padx=4, pady=2)
            self.precomputed_open_buttons.append(p_open)
            c_open = ttk.Button(candidate_results_frame, text="Open", command=lambda idx=i: self._open_video(idx), state=tk.DISABLED)
            c_open.grid(row=row_num + 1, column=4, sticky="w", padx=4, pady=2)
            self.result_open_buttons.append(c_open)

            p_delete = ttk.Button(
                precomp_frame,
                text="Append",
                command=lambda idx=i: self._append_result_to_videos_to_delete("current", idx),
                state=tk.DISABLED,
            )
            p_delete.grid(row=row_num, column=5, sticky="w", padx=4, pady=2)
            self.precomputed_delete_buttons.append(p_delete)

            c_delete = ttk.Button(
                candidate_results_frame,
                text="Append",
                command=lambda idx=i: self._append_result_to_videos_to_delete("candidate", idx),
                state=tk.DISABLED,
            )
            c_delete.grid(row=row_num + 1, column=5, sticky="w", padx=4, pady=2)
            self.candidate_delete_buttons.append(c_delete)

            p_rating_var = tk.StringVar(value="5")
            self.precomputed_rating_vars.append(p_rating_var)
            p_menu = tk.OptionMenu(precomp_frame, p_rating_var, *rating_options, command=lambda _v, idx=i: self._on_precomputed_rating_change(idx))
            p_menu.grid(row=row_num, column=6, sticky="w", padx=4, pady=2)
            p_menu.config(width=4)
            self.precomputed_rating_dropdowns.append(p_menu)
            self._apply_precomputed_rating_color(i)

            c_rating_var = tk.StringVar(value="5")
            self.rating_vars.append(c_rating_var)
            # tk.OptionMenu allows per-widget background color updates.
            c_menu = tk.OptionMenu(candidate_results_frame, c_rating_var, *rating_options, command=lambda _v, idx=i: self._on_rating_change(idx))
            c_menu.grid(row=row_num + 1, column=6, sticky="w", padx=4, pady=2)
            c_menu.config(width=4)
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
        semantic = float(result.get("semantic_score", 0.0))
        alignment = float(result.get("alignment_score", 0.0)) / 100.0

        components = [(semantic, SEMANTIC_WEIGHT)]
        if alignment > 0:
            components.append((alignment, ALIGNMENT_WEIGHT))

        total_weight = sum(weight for _, weight in components)
        if total_weight <= 0:
            return semantic
        return sum(value * weight for value, weight in components) / total_weight

    def _compute_stage4_final_score(self, stage3_score: float, instruction_score_raw: float) -> float:
        instruction = max(0.0, float(instruction_score_raw)) / 100.0
        components = [(stage3_score, SEMANTIC_WEIGHT + ALIGNMENT_WEIGHT)]
        if instruction > 0:
            components.append((instruction, INSTRUCTION_WEIGHT))

        total_weight = sum(weight for _, weight in components)
        if total_weight <= 0:
            return stage3_score
        return sum(value * weight for value, weight in components) / total_weight

    def _clear_stage4_results(self) -> None:
        self.latest_final_results = []
        if self.stage4_survivors_tree is not None:
            for item in self.stage4_survivors_tree.get_children():
                self.stage4_survivors_tree.delete(item)

        for i in range(TOP_K):

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

        final_top3 = sorted(enriched_survivors, key=lambda item: float(item.get("final_score", 0.0)), reverse=True)[:TOP_K]
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

        for i in range(TOP_K):
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
        embedding = self.embedder.embed_query(query_text).reshape(1, -1)
        distances, indices = self.index.search(embedding, shortlist_k)

        video_chunks: dict[str, list[dict[str, object]]] = {}
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1 or idx >= len(self.metadata):
                continue

            video_meta = self.metadata[int(idx)]
            video_id = clean_text(video_meta.get("video_id"))
            if not video_id or video_id in self.deleted_videos:
                continue

            cosine_sim = calculate_cosine_similarity(float(dist))
            video_chunks.setdefault(video_id, []).append(
                {
                    "cosine_similarity": float(cosine_sim),
                    "video_meta": video_meta,
                    "chunk_text": clean_text(video_meta.get("text")),
                }
            )

        ranked_results: list[dict[str, Any]] = []
        for video_id, chunks in video_chunks.items():
            sims = [float(chunk["cosine_similarity"]) for chunk in chunks]
            good_chunks = [sim for sim in sims if sim >= 0.6]
            median_sim = sorted(sims)[len(sims) // 2]
            ranking_score = median_sim + (len(good_chunks) * 0.02)

            sorted_chunks = sorted(chunks, key=lambda item: float(item["cosine_similarity"]), reverse=True)
            evidence_text = " ".join(clean_text(chunk.get("chunk_text")) for chunk in sorted_chunks[:3])
            best_meta = sorted_chunks[0]["video_meta"]
            title = clean_text(best_meta.get("video_title") or best_meta.get("title"))
            meta = self.video_lookup.get(video_id) or self.fallback_lookup.get(video_id) or {}
            gate_eval_text = f"{title} {evidence_text}".strip()
            gate_pass, gate_reason = self._evaluate_constraints_for_text(gate_row, gate_eval_text)

            ranked_results.append(
                {
                    "video_id": video_id,
                    "title": title,
                    "channel": clean_text(meta.get("channel") or best_meta.get("channel")),
                    "semantic_score": ranking_score,
                    "gate_pass": gate_pass,
                    "gate_reason": gate_reason,
                    "gate_eval_text": gate_eval_text,
                }
            )

        ranked_results.sort(key=lambda item: float(item["semantic_score"]), reverse=True)
        return ranked_results

    async def _score_stage2_survivors_async(
        self,
        survivors: list[dict[str, Any]],
        age: str,
        topic: str,
        small_step_name: str,
        small_step_desc: str,
    ) -> list[dict[str, Any]]:
        if not survivors:
            return []

        video_ids = [clean_text(result.get("video_id")) for result in survivors if clean_text(result.get("video_id"))]
        if not video_ids:
            return []

        instruction_scores, alignment_scores = await asyncio.gather(
            asyncio.gather(
                *[
                    self.scorer.score_for_curriculum_context_async(
                        video_id=video_id,
                        age=age,
                        topic=topic,
                        small_step=small_step_name,
                        small_step_desc=small_step_desc,
                        use_cache=True,
                    )
                    for video_id in video_ids
                ]
            ),
            asyncio.gather(
                *[
                    self.scorer.score_alignment_for_curriculum_context_async(
                        video_id=video_id,
                        age=age,
                        topic=topic,
                        small_step=small_step_name,
                        small_step_desc=small_step_desc,
                        use_cache=True,
                    )
                    for video_id in video_ids
                ]
            ),
        )

        instruction_map = {item["video_id"]: item for item in instruction_scores if item}
        alignment_map = {item["video_id"]: item for item in alignment_scores if item}

        scored_results: list[dict[str, Any]] = []
        for survivor in survivors:
            video_id = clean_text(survivor.get("video_id"))
            instruction_score_raw = instruction_map.get(video_id, {}).get("score") or 0.0
            alignment_score_raw = alignment_map.get(video_id, {}).get("score") or 0.0

            scored_result = {
                **survivor,
                "instruction_score": float(instruction_score_raw),
                "instruction_justification": clean_text(instruction_map.get(video_id, {}).get("justification")),
                "alignment_score": float(alignment_score_raw),
                "alignment_justification": clean_text(alignment_map.get(video_id, {}).get("justification")),
            }
            scored_result["combined_score"] = self._compute_stage3_score(scored_result)
            scored_results.append(scored_result)

        scored_results.sort(key=lambda item: float(item.get("combined_score", 0.0)), reverse=True)
        return scored_results

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
            query_text = build_query_text(topic=topic, small_step_name=small_step_name, ss_wr_desc=ss_wr_desc)
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

            self.curriculum_by_id = {
                row["small_step_id"]: row
                for _, row in self.curriculum_df.drop_duplicates(subset=["small_step_id"], keep="first").iterrows()
            }

            self.sorted_step_ids = sorted(
                self.curriculum_by_id.keys(),
                key=lambda sid: int(self.curriculum_by_id[sid].get("small_step_num", 0)),
            )
            self.saved_step_ids = self._load_saved_step_ids_from_qa()
            self._refresh_step_combo_labels()

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

    def _on_heavy_assets_error(self, error_message: str) -> None:
        self.status_var.set("Failed to load retrieval assets")
        self.constraints_status_var.set("Constraints gate: retrieval assets failed to load")
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
        for rank in range(1, TOP_K + 1):
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

        labels: list[str] = []
        for small_step_id in visible_step_ids:
            row = self.curriculum_by_id.get(small_step_id, {})
            marker = "✓" if small_step_id in self.saved_step_ids else "•"
            label = f"{marker} {small_step_id} | {clean_text(row.get('topic'))} | {clean_text(row.get('small_step_name'))}"
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

        total_steps = len(self.sorted_step_ids)
        done_steps = len(self.saved_step_ids)
        percent = int((done_steps / total_steps) * 100) if total_steps else 0
        self.progress_var.set(f"Done {done_steps}/{total_steps} ({percent}%)")

        has_unsaved = done_steps < total_steps
        self.jump_unsaved_btn.config(state=tk.NORMAL if has_unsaved else tk.DISABLED)

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

        unsaved_step_ids = [sid for sid in self.sorted_step_ids if sid not in self.saved_step_ids]
        if not unsaved_step_ids:
            messagebox.showinfo("All complete", "All small steps are marked as saved in qa.csv.")
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
            if candidate_step_id not in self.saved_step_ids:
                next_step_id = candidate_step_id
                break

        if not next_step_id:
            next_step_id = unsaved_step_ids[0]

        if not self._set_selected_step_by_id(next_step_id):
            # If filtered list hides the target, disable filter and try again.
            self.show_unsaved_only_var.set(False)
            self._refresh_step_combo_labels(preserve_step_id=next_step_id)
            self._set_selected_step_by_id(next_step_id)

    def _on_show_unsaved_only_changed(self) -> None:
        current_step_id = self._selected_small_step_id()
        self._refresh_step_combo_labels(preserve_step_id=current_step_id)
        if self.step_var.get():
            self._on_step_selected(None)

    def _get_saved_candidate_text(self, small_step_id: str) -> str:
        if not small_step_id:
            return ""

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

        baseline = clean_text(row.get("ss_wr_desc"))
        candidate_default = self._get_saved_candidate_text(small_step_id) or baseline
        self._set_text(self.baseline_text, baseline)
        self._set_text(self.candidate_text, candidate_default)
        self._clear_results()
        self._clear_semantic_preview()
        self._populate_precomputed(small_step_id)
        if self._populate_candidate_from_qa(small_step_id):
            self.candidate_display_unlocked_steps.add(small_step_id)
        else:
            self.candidate_display_unlocked_steps.discard(small_step_id)
            self._set_candidate_panel_state("Candidate panel: locked until Update QA CSV")
        self.status_var.set("Ready")
        self._load_constraints_text_for_step(small_step_id)
        self.constraints_status_var.set("Constraints gate: ready")
        self._schedule_semantic_preview()

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
        for i in range(SEMANTIC_PREVIEW_K):
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
        if self.semantic_preview_after_id is not None:
            self.root.after_cancel(self.semantic_preview_after_id)
            self.semantic_preview_after_id = None

        self.semantic_preview_after_id = self.root.after(
            SEMANTIC_PREVIEW_DEBOUNCE_MS,
            self._run_semantic_preview,
        )

    def _run_semantic_preview(self) -> None:
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
                ss_wr_desc=candidate,
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

        self._clear_candidate_result_widgets(reset_ratings=True)
        self._clear_alignment_results()
        self._clear_stage4_results()
        self._set_candidate_panel_state("Candidate panel: locked until Update QA CSV")
        self.save_btn.config(state=tk.DISABLED)

    def _clear_candidate_result_widgets(self, reset_ratings: bool) -> None:
        for i in range(TOP_K):
            self.result_title_labels[i].config(text="")
            self.result_channel_labels[i].config(text="")
            self.result_score_labels[i].config(text="")
            self.result_open_buttons[i].config(state=tk.DISABLED)
            self.candidate_delete_buttons[i].config(state=tk.DISABLED)
            if reset_ratings:
                self.rating_vars[i].set("5")
                self._apply_rating_color(i)

    def _render_candidate_search_results(self, results: list[dict[str, object]]) -> None:
        self._clear_candidate_result_widgets(reset_ratings=True)

        for i in range(TOP_K):
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
        self._clear_candidate_result_widgets(reset_ratings=True)
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
                ss_wr_desc=candidate,
            )
            gate_rules = parse_constraints_text_block(constraints_text)
            shortlist_k = self._get_constraints_shortlist_k()
            stage2_results = self._build_stage2_shortlist(query_text, gate_rules, shortlist_k)
            stage2_survivors = [result for result in stage2_results if bool(result.get("gate_pass"))]
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
        self._clear_candidate_result_widgets(reset_ratings=True)
        qa_row = self._get_qa_row_for_step(small_step_id)
        if qa_row is None:
            self._set_candidate_panel_state("Candidate panel: no persisted candidate picks found in qa.csv")
            return False

        displayed_results: list[dict[str, object]] = []
        has_persisted_picks = False
        for i in range(TOP_K):
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
            self._clear_candidate_result_widgets(reset_ratings=True)
            self.latest_results = []
            self._clear_stage4_results()
            self._set_candidate_panel_state("Candidate panel: no persisted candidate picks found in qa.csv")
            self.save_btn.config(state=tk.DISABLED)
            return False

        self.latest_results = displayed_results
        self.latest_final_results = displayed_results
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
        self.precomputed_results = []
        if self.precomputed_df.empty:
            return

        step_rows = self.precomputed_df[self.precomputed_df["small_step_id"] == small_step_id]
        if "rank" in step_rows.columns:
            step_rows = step_rows.sort_values("rank")
        picks = step_rows.head(TOP_K).reset_index(drop=True)

        for i in range(len(picks)):
            r = picks.iloc[i]
            video_id = clean_text(r.get("video_id"))
            title = clean_text(r.get("title") or r.get("video_title"))
            channel = clean_text(r.get("channel"))
            combined_score = float(r.get("combined_score") or 0.0)
            self.precomputed_results.append({
                "video_id": video_id,
                "title": title,
                "channel": channel,
                "combined_score": combined_score,
                "semantic_score": clean_text(r.get("semantic_score")),
                "instruction_score": clean_text(r.get("instruction_score")),
                "alignment_score": clean_text(r.get("alignment_score")),
            })
            self.precomputed_title_labels[i].config(text=f"{title} ({video_id})")
            self.precomputed_channel_labels[i].config(text=channel)
            self.precomputed_score_labels[i].config(text=f"{combined_score:.4f}")
            self.precomputed_open_buttons[i].config(state=tk.NORMAL if video_id else tk.DISABLED)
            self.precomputed_delete_buttons[i].config(state=tk.NORMAL if video_id else tk.DISABLED)
            self.precomputed_rating_vars[i].set("5")
            self._apply_precomputed_rating_color(i)

        for i in range(len(picks), TOP_K):
            self.precomputed_title_labels[i].config(text="")
            self.precomputed_channel_labels[i].config(text="")
            self.precomputed_score_labels[i].config(text="")
            self.precomputed_open_buttons[i].config(state=tk.DISABLED)
            self.precomputed_delete_buttons[i].config(state=tk.DISABLED)
            self.precomputed_rating_vars[i].set("5")
            self._apply_precomputed_rating_color(i)

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

        for i in range(TOP_K):
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

        def fill_slots(source: str, results: list[dict[str, object]], ratings: list[int]) -> None:
            for idx in range(TOP_K):
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
            self._clear_candidate_result_widgets(reset_ratings=False)
            self._set_candidate_panel_state("Candidate panel: Update QA CSV ran, but no persisted candidate picks were found")
            self.status_var.set("Updated qa/qa.csv. Candidate panel remains blank because no candidate picks are stored yet.")

        messagebox.showinfo("QA Updated", f"Saved QA row to:\n{QA_TRACKING_PATH}")

    def _append_result_to_videos_to_delete(self, source: str, index_num: int) -> None:
        results = self.precomputed_results if source == "current" else self.latest_results
        if index_num < 0 or index_num >= len(results):
            return

        video_id = clean_text(results[index_num].get("video_id"))
        if not video_id:
            messagebox.showwarning("Missing video", "No video_id found for this row.")
            return

        VIDEOS_TO_DELETE_PATH.parent.mkdir(parents=True, exist_ok=True)
        if VIDEOS_TO_DELETE_PATH.exists():
            delete_df = pd.read_csv(VIDEOS_TO_DELETE_PATH)
        else:
            delete_df = pd.DataFrame(columns=["video_id"])

        if "video_id" not in delete_df.columns:
            first_col = delete_df.columns[0] if len(delete_df.columns) > 0 else None
            if first_col:
                delete_df = delete_df.rename(columns={first_col: "video_id"})
            else:
                delete_df["video_id"] = ""

        delete_df["video_id"] = delete_df["video_id"].map(clean_text)
        if (delete_df["video_id"] == video_id).any():
            self.status_var.set(f"{video_id} is already in videos_to_delete.csv")
            return

        delete_df = pd.concat([delete_df, pd.DataFrame([{"video_id": video_id}])], ignore_index=True)
        delete_df.to_csv(VIDEOS_TO_DELETE_PATH, index=False)
        self.status_var.set(f"Appended {video_id} to videos_to_delete.csv")

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
        for i in range(TOP_K):
            try:
                ratings.append(int(self.rating_vars[i].get().strip()))
            except ValueError:
                ratings.append(5)

        try:
            self._save_approved_candidate_mapping(row=row, candidate=candidate)
            self._upsert_targeted_override(row=row, candidate=candidate, scenario_label=scenario_label, ratings=ratings)
            self.saved_candidate_steps.add(small_step_id)
            self.candidate_display_unlocked_steps.discard(small_step_id)
            self._set_candidate_panel_state("Candidate panel: candidate saved, click Update QA CSV to show persisted picks")
            self.status_var.set("Saved approved candidate and override row.")
            messagebox.showinfo(
                "Saved",
                f"Saved to:\n{APPROVED_CANDIDATES_PATH}\n{TARGET_OVERRIDES_PATH}",
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


def main() -> None:
    root = tk.Tk()
    app = ImprovePickQAGUI(root)
    _ = app
    root.mainloop()


if __name__ == "__main__":
    main()
