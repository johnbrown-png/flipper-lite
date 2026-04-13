"""Standalone GUI for targeted ss_wr_desc QA experiments.

This MVP focuses on fast manual iteration:
- choose a curriculum small step
- view current ss_wr_desc
- test a candidate wording
- inspect top-3 results with quick open links
- score each result with a color-coded 1-10 rating
- save approved candidate text and ratings to CSV outputs
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
import sys
import threading
import webbrowser

import pandas as pd
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

# Ensure imports work when script is launched from Improve_pick/
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from precompute_curriculum_recommendations import calculate_cosine_similarity, load_faiss_index, search_and_score_async
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
SEMANTIC_PREVIEW_CHUNKS = 30
SEMANTIC_PREVIEW_DEBOUNCE_MS = 550


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


class ImprovePickQAGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Improve Pick - Targeted ss_wr_desc QA")
        self.root.geometry("1300x860")

        self.status_var = tk.StringVar(value="Loading data...")
        self.step_var = tk.StringVar(value="")
        self.scenario_var = tk.StringVar(value="gui_mvp_approved")
        self.candidate_panel_state_var = tk.StringVar(value="Candidate panel: locked until Save Approved Candidate + Update QA CSV")

        self.curriculum_df = pd.DataFrame()
        self.curriculum_by_id: dict[str, dict[str, object]] = {}
        self.step_labels_by_id: dict[str, str] = {}
        self.sorted_step_ids: list[str] = []

        self.index = None
        self.metadata: list[dict[str, object]] = []
        self.embedder: QueryEmbedder | None = None
        self.scorer: InstructionQualityScorer | None = None
        self.deleted_videos: set[str] = set()
        self.fallback_lookup: dict[str, dict[str, str]] = {}
        self.video_lookup: dict[str, dict[str, str]] = {}

        self.latest_results: list[dict[str, object]] = []
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

        self._build_ui()
        # Defer heavy loading until after mainloop starts so the window appears immediately.
        self.root.after(100, self._load_initial_data)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(4, weight=1)

        title = ttk.Label(
            outer,
            text="Improve Pick - Manual Candidate QA",
            font=("Segoe UI", 16, "bold"),
        )
        title.grid(row=0, column=0, sticky="w", pady=(0, 8))

        selector_frame = ttk.LabelFrame(outer, text="Small Step Selection", padding=10)
        selector_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        selector_frame.columnconfigure(1, weight=1)

        ttk.Label(selector_frame, text="Small step:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.step_combo = ttk.Combobox(selector_frame, textvariable=self.step_var, state="readonly")
        self.step_combo.grid(row=0, column=1, sticky="ew")
        self.step_combo.bind("<<ComboboxSelected>>", self._on_step_selected)

        ttk.Label(selector_frame, text="Scenario label:").grid(row=0, column=2, sticky="w", padx=(12, 8))
        self.scenario_entry = ttk.Entry(selector_frame, textvariable=self.scenario_var, width=24)
        self.scenario_entry.grid(row=0, column=3, sticky="w")
        text_frame = ttk.LabelFrame(outer, text="Query Text", padding=10)
        text_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 8))
        text_frame.columnconfigure(0, weight=1)
        text_frame.columnconfigure(1, weight=1)

        baseline_frame = ttk.Frame(text_frame)
        baseline_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        baseline_frame.columnconfigure(0, weight=1)
        baseline_frame.rowconfigure(1, weight=1)
        ttk.Label(baseline_frame, text="Current ss_wr_desc", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        self.baseline_text = scrolledtext.ScrolledText(baseline_frame, wrap=tk.WORD, height=8)
        self.baseline_text.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        self.baseline_text.config(state=tk.DISABLED)

        candidate_frame = ttk.Frame(text_frame)
        candidate_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        candidate_frame.columnconfigure(0, weight=1)
        candidate_frame.rowconfigure(1, weight=1)
        ttk.Label(candidate_frame, text="Candidate wording (candidate_ss_wr_desc)", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        self.candidate_text = scrolledtext.ScrolledText(candidate_frame, wrap=tk.WORD, height=8)
        self.candidate_text.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        self.candidate_text.bind("<<Modified>>", self._on_candidate_text_modified)

        semantic_preview_frame = ttk.LabelFrame(candidate_frame, text="Live Semantic Preview (No Instruction Scoring)", padding=8)
        semantic_preview_frame.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
        semantic_preview_frame.columnconfigure(1, weight=1)
        candidate_frame.rowconfigure(2, weight=1)

        preview_headers = ["Rank", "Title", "Channel", "Semantic"]
        for col, header in enumerate(preview_headers):
            ttk.Label(semantic_preview_frame, text=header, font=("Segoe UI", 9, "bold")).grid(row=0, column=col, sticky="w", padx=3, pady=(0, 4))

        for i in range(SEMANTIC_PREVIEW_K):
            row_num = i + 1
            ttk.Label(semantic_preview_frame, text=f"{row_num}").grid(row=row_num, column=0, sticky="w", padx=3, pady=2)

            title_label = ttk.Label(semantic_preview_frame, text="", width=44)
            title_label.grid(row=row_num, column=1, sticky="w", padx=3, pady=2)
            self.semantic_preview_title_labels.append(title_label)

            channel_label = ttk.Label(semantic_preview_frame, text="", width=20)
            channel_label.grid(row=row_num, column=2, sticky="w", padx=3, pady=2)
            self.semantic_preview_channel_labels.append(channel_label)

            score_label = ttk.Label(semantic_preview_frame, text="", width=10)
            score_label.grid(row=row_num, column=3, sticky="w", padx=3, pady=2)
            self.semantic_preview_score_labels.append(score_label)

        ttk.Label(candidate_frame, textvariable=self.semantic_preview_status_var, foreground="#555555").grid(row=3, column=0, sticky="w", pady=(4, 0))

        control_frame = ttk.Frame(outer)
        control_frame.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        self.search_btn = ttk.Button(control_frame, text="Search Top 3", command=self._run_search)
        self.search_btn.grid(row=0, column=0, padx=(0, 8))
        self.save_btn = ttk.Button(control_frame, text="Save Approved Candidate", command=self._save_candidate, state=tk.DISABLED)
        self.save_btn.grid(row=0, column=1, padx=(0, 8))
        self.update_qa_btn = ttk.Button(control_frame, text="Update QA CSV", command=self._update_qa_csv)
        self.update_qa_btn.grid(row=0, column=2, padx=(0, 8))

        self.status_label = ttk.Label(control_frame, textvariable=self.status_var, foreground="blue")
        self.status_label.grid(row=0, column=3, sticky="w")

        rating_options = [str(i) for i in range(1, 11)]
        results_row_frame = ttk.Frame(outer)
        results_row_frame.grid(row=4, column=0, sticky="nsew")
        results_row_frame.columnconfigure(0, weight=1)
        results_row_frame.columnconfigure(1, weight=1)
        results_row_frame.rowconfigure(0, weight=1)

        precomp_frame = ttk.LabelFrame(results_row_frame, text="Precomputed Picks (Current)", padding=10)
        precomp_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        precomp_frame.columnconfigure(1, weight=1)
        candidate_results_frame = ttk.LabelFrame(results_row_frame, text="Candidate Search Results", padding=10)
        candidate_results_frame.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        candidate_results_frame.columnconfigure(1, weight=1)

        ttk.Label(
            candidate_results_frame,
            textvariable=self.candidate_panel_state_var,
            foreground="#555555",
        ).grid(row=0, column=0, columnspan=7, sticky="w", padx=4, pady=(0, 6))

        headers = ["Rank", "Title", "Channel", "Score", "Open", "Delete", "Rating"]
        for col, header in enumerate(headers):
            ttk.Label(precomp_frame, text=header, font=("Segoe UI", 10, "bold")).grid(row=0, column=col, sticky="w", padx=4, pady=(0, 6))
            ttk.Label(candidate_results_frame, text=header, font=("Segoe UI", 10, "bold")).grid(row=1, column=col, sticky="w", padx=4, pady=(0, 6))

        for i in range(TOP_K):
            row_num = i + 1
            ttk.Label(precomp_frame, text=f"{row_num}").grid(row=row_num, column=0, sticky="w", padx=4, pady=4)
            ttk.Label(candidate_results_frame, text=f"{row_num}").grid(row=row_num + 1, column=0, sticky="w", padx=4, pady=4)

            p_title = ttk.Label(precomp_frame, text="", width=44)
            p_title.grid(row=row_num, column=1, sticky="w", padx=4, pady=4)
            self.precomputed_title_labels.append(p_title)
            c_title = ttk.Label(candidate_results_frame, text="", width=44)
            c_title.grid(row=row_num + 1, column=1, sticky="w", padx=4, pady=4)
            self.result_title_labels.append(c_title)

            p_channel = ttk.Label(precomp_frame, text="", width=20)
            p_channel.grid(row=row_num, column=2, sticky="w", padx=4, pady=4)
            self.precomputed_channel_labels.append(p_channel)
            c_channel = ttk.Label(candidate_results_frame, text="", width=20)
            c_channel.grid(row=row_num + 1, column=2, sticky="w", padx=4, pady=4)
            self.result_channel_labels.append(c_channel)

            p_score = ttk.Label(precomp_frame, text="", width=10)
            p_score.grid(row=row_num, column=3, sticky="w", padx=4, pady=4)
            self.precomputed_score_labels.append(p_score)
            c_score = ttk.Label(candidate_results_frame, text="", width=10)
            c_score.grid(row=row_num + 1, column=3, sticky="w", padx=4, pady=4)
            self.result_score_labels.append(c_score)

            p_open = ttk.Button(precomp_frame, text="Open", command=lambda idx=i: self._open_precomputed_video(idx), state=tk.DISABLED)
            p_open.grid(row=row_num, column=4, sticky="w", padx=4, pady=4)
            self.precomputed_open_buttons.append(p_open)
            c_open = ttk.Button(candidate_results_frame, text="Open", command=lambda idx=i: self._open_video(idx), state=tk.DISABLED)
            c_open.grid(row=row_num + 1, column=4, sticky="w", padx=4, pady=4)
            self.result_open_buttons.append(c_open)

            p_delete = ttk.Button(
                precomp_frame,
                text="Append",
                command=lambda idx=i: self._append_result_to_videos_to_delete("current", idx),
                state=tk.DISABLED,
            )
            p_delete.grid(row=row_num, column=5, sticky="w", padx=4, pady=4)
            self.precomputed_delete_buttons.append(p_delete)

            c_delete = ttk.Button(
                candidate_results_frame,
                text="Append",
                command=lambda idx=i: self._append_result_to_videos_to_delete("candidate", idx),
                state=tk.DISABLED,
            )
            c_delete.grid(row=row_num + 1, column=5, sticky="w", padx=4, pady=4)
            self.candidate_delete_buttons.append(c_delete)

            p_rating_var = tk.StringVar(value="5")
            self.precomputed_rating_vars.append(p_rating_var)
            p_menu = tk.OptionMenu(precomp_frame, p_rating_var, *rating_options, command=lambda _v, idx=i: self._on_precomputed_rating_change(idx))
            p_menu.grid(row=row_num, column=6, sticky="w", padx=4, pady=4)
            p_menu.config(width=4)
            self.precomputed_rating_dropdowns.append(p_menu)
            self._apply_precomputed_rating_color(i)

            c_rating_var = tk.StringVar(value="5")
            self.rating_vars.append(c_rating_var)
            # tk.OptionMenu allows per-widget background color updates.
            c_menu = tk.OptionMenu(candidate_results_frame, c_rating_var, *rating_options, command=lambda _v, idx=i: self._on_rating_change(idx))
            c_menu.grid(row=row_num + 1, column=6, sticky="w", padx=4, pady=4)
            c_menu.config(width=4)
            self.rating_dropdowns.append(c_menu)
            self._apply_rating_color(i)

    def _set_candidate_panel_state(self, text: str) -> None:
        self.candidate_panel_state_var.set(text)

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
            self.step_labels_by_id = {}
            labels = []
            for small_step_id in self.sorted_step_ids:
                row = self.curriculum_by_id[small_step_id]
                label = f"{small_step_id} | {row['topic']} | {row['small_step_name']}"
                self.step_labels_by_id[small_step_id] = label
                labels.append(label)

            self.step_combo["values"] = labels
            if labels:
                self.step_var.set(labels[0])
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
        self.status_var.set("Ready")
        self._schedule_semantic_preview()

    def _on_heavy_assets_error(self, error_message: str) -> None:
        self.status_var.set("Failed to load retrieval assets")
        messagebox.showerror("Initialization Error", error_message)

    def _selected_small_step_id(self) -> str:
        label = self.step_var.get().strip()
        if not label:
            return ""
        return label.split(" | ", 1)[0].strip()

    def _on_step_selected(self, _event) -> None:
        small_step_id = self._selected_small_step_id()
        row = self.curriculum_by_id.get(small_step_id)
        if row is None:
            return

        baseline = clean_text(row.get("ss_wr_desc"))
        self._set_text(self.baseline_text, baseline)
        self._set_text(self.candidate_text, baseline)
        self._clear_results()
        self._clear_semantic_preview()
        self._populate_precomputed(small_step_id)
        if small_step_id in self.candidate_display_unlocked_steps:
            self._populate_candidate_from_qa(small_step_id)
        else:
            self._set_candidate_panel_state("Candidate panel: locked until Save Approved Candidate + Update QA CSV")
        self.status_var.set("Ready")
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
        self._set_candidate_panel_state("Candidate panel: candidate edited, Save Approved Candidate + Update QA CSV required")
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
        self.latest_query_text = ""

        self._clear_candidate_result_widgets(reset_ratings=True)
        self._set_candidate_panel_state("Candidate panel: locked until Save Approved Candidate + Update QA CSV")
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

        # Any new search requires Save + Update before candidate panel is shown again.
        self.saved_candidate_steps.discard(small_step_id)
        self.candidate_display_unlocked_steps.discard(small_step_id)
        self._clear_candidate_result_widgets(reset_ratings=True)
        self._set_candidate_panel_state("Candidate panel: search is transient until Save Approved Candidate + Update QA CSV")

        self.search_btn.config(state=tk.DISABLED)
        self.save_btn.config(state=tk.DISABLED)
        self.status_var.set("Searching top 3 recommendations...")

        worker = threading.Thread(
            target=self._search_worker,
            args=(row, candidate),
            daemon=True,
        )
        worker.start()

    def _search_worker(self, row: dict[str, object], candidate: str) -> None:
        try:
            query_text = build_query_text(
                topic=clean_text(row.get("topic")),
                small_step_name=clean_text(row.get("small_step_name")),
                ss_wr_desc=candidate,
            )

            results = asyncio.run(
                search_and_score_async(
                    query_text=query_text,
                    age=clean_text(row.get("age")),
                    topic=clean_text(row.get("topic")),
                    small_step=clean_text(row.get("small_step_name")),
                    small_step_desc=candidate,
                    index=self.index,
                    metadata=self.metadata,
                    embedder=self.embedder,
                    scorer=self.scorer,
                    deleted_videos=self.deleted_videos,
                    k=TOP_K,
                )
            )

            enriched = []
            for result in results:
                video_id = clean_text(result.get("video_id"))
                meta = self.video_lookup.get(video_id) or self.fallback_lookup.get(video_id) or {}
                enriched.append(
                    {
                        "video_id": video_id,
                        "title": clean_text(result.get("title")),
                        "channel": clean_text(meta.get("channel")),
                        "combined_score": float(result.get("combined_score", 0.0)),
                        "semantic_score": float(result.get("semantic_score", 0.0)),
                        "instruction_score": float(result.get("instruction_score", 0.0)),
                    }
                )

            self.root.after(0, self._on_search_success, enriched, query_text)
        except Exception as exc:
            self.root.after(0, self._on_search_error, str(exc))

    def _on_search_success(self, results: list[dict[str, object]], query_text: str) -> None:
        self.latest_results = results
        self.latest_query_text = query_text

        # Keep candidate panel blank until Save Approved Candidate + Update QA CSV.
        self._clear_candidate_result_widgets(reset_ratings=True)
        self._set_candidate_panel_state("Candidate panel: search complete, click Save Approved Candidate then Update QA CSV")

        self.search_btn.config(state=tk.NORMAL)
        self.save_btn.config(state=tk.NORMAL if results else tk.DISABLED)

        if results:
            self.status_var.set(
                f"Search complete. Found {len(results)} recommendation(s). "
                "Click Save Approved Candidate, then Update QA CSV to display persisted candidate picks."
            )
        else:
            self.status_var.set("Search complete. No recommendations found.")

    def _populate_candidate_from_qa(self, small_step_id: str) -> None:
        self._clear_candidate_result_widgets(reset_ratings=True)
        qa_df = self._load_qa_df()
        step_rows = qa_df[(qa_df["small_step_id"] == small_step_id) & (qa_df["source"] == "candidate")]
        if step_rows.empty:
            self._set_candidate_panel_state("Candidate panel: no persisted candidate picks found in qa.csv")
            return

        displayed_results: list[dict[str, object]] = []
        for i in range(TOP_K):
            rank = i + 1
            rank_rows = step_rows[step_rows["rank"] == rank]
            if rank_rows.empty:
                displayed_results.append({})
                continue

            qa_row = rank_rows.iloc[-1]
            video_id = clean_text(qa_row.get("video_id"))
            title = clean_text(qa_row.get("video_title"))
            channel = clean_text(qa_row.get("channel"))

            score_text = ""
            try:
                score_value = float(qa_row.get("combined_score"))
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
            self.rating_vars[i].set(str(self._safe_parse_rating(qa_row.get("rating"), default=5)))
            self._apply_rating_color(i)

            displayed_results.append(
                {
                    "video_id": video_id,
                    "title": title,
                    "channel": channel,
                    "combined_score": score_value,
                }
            )

        self.latest_results = displayed_results
        self._set_candidate_panel_state("Candidate panel: showing persisted candidate picks from qa.csv")
        self.save_btn.config(state=tk.DISABLED)

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
        columns = [
            "updated_at",
            "small_step_id",
            "topic",
            "small_step_name",
            "source",
            "rank",
            "video_id",
            "video_title",
            "channel",
            "combined_score",
            "rating",
            "candidate_ss_wr_desc",
        ]

        if QA_TRACKING_PATH.exists():
            qa_df = pd.read_csv(QA_TRACKING_PATH)
        else:
            qa_df = pd.DataFrame(columns=columns)

        for col in columns:
            if col not in qa_df.columns:
                qa_df[col] = ""

        qa_df["small_step_id"] = qa_df["small_step_id"].map(clean_text)
        qa_df["source"] = qa_df["source"].map(clean_text)
        qa_df["video_id"] = qa_df["video_id"].map(clean_text)
        qa_df["rank"] = pd.to_numeric(qa_df["rank"], errors="coerce")
        qa_df["rating"] = pd.to_numeric(qa_df["rating"], errors="coerce")
        return qa_df[columns]

    def _ensure_qa_template_exists(self) -> None:
        if QA_TRACKING_PATH.exists():
            return

        QA_TRACKING_PATH.parent.mkdir(parents=True, exist_ok=True)
        rows: list[dict[str, object]] = []
        now = datetime.now().isoformat(timespec="seconds")

        for small_step_id in self.sorted_step_ids:
            row = self.curriculum_by_id.get(small_step_id, {})
            for source in ("current", "candidate"):
                for rank in range(1, TOP_K + 1):
                    rows.append(
                        {
                            "updated_at": now,
                            "small_step_id": clean_text(small_step_id),
                            "topic": clean_text(row.get("topic")),
                            "small_step_name": clean_text(row.get("small_step_name")),
                            "source": source,
                            "rank": rank,
                            "video_id": "",
                            "video_title": "",
                            "channel": "",
                            "combined_score": "",
                            "rating": 5,
                            "candidate_ss_wr_desc": "",
                        }
                    )

        pd.DataFrame(rows).to_csv(QA_TRACKING_PATH, index=False)

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

        qa_df = self._load_qa_df()
        step_rows = qa_df[(qa_df["small_step_id"] == small_step_id) & (qa_df["source"] == source)]
        if step_rows.empty:
            return

        for i in range(TOP_K):
            rank = i + 1
            candidate_rows = step_rows[step_rows["rank"] == rank]
            if candidate_rows.empty:
                continue

            qa_row = candidate_rows.iloc[-1]
            qa_video_id = clean_text(qa_row.get("video_id"))
            result_video_id = ""
            if i < len(results):
                result_video_id = clean_text(results[i].get("video_id"))

            # Only restore when empty/template row or matching video id.
            if qa_video_id and result_video_id and qa_video_id != result_video_id:
                continue

            rating_vars[i].set(str(self._safe_parse_rating(qa_row.get("rating"), default=5)))
            apply_color_fn(i)

    def _collect_qa_rows(
        self,
        row: dict[str, object],
        candidate_text: str,
        candidate_ratings: list[int],
        precomputed_ratings: list[int],
    ) -> list[dict[str, object]]:
        now = datetime.now().isoformat(timespec="seconds")
        rows: list[dict[str, object]] = []

        def append_rows(source: str, results: list[dict[str, object]], ratings: list[int]) -> None:
            for idx in range(TOP_K):
                result = results[idx] if idx < len(results) else {}
                rows.append(
                    {
                        "updated_at": now,
                        "small_step_id": clean_text(row.get("small_step_id")),
                        "topic": clean_text(row.get("topic")),
                        "small_step_name": clean_text(row.get("small_step_name")),
                        "source": source,
                        "rank": idx + 1,
                        "video_id": clean_text(result.get("video_id")),
                        "video_title": clean_text(result.get("title")),
                        "channel": clean_text(result.get("channel")),
                        "combined_score": result.get("combined_score", ""),
                        "rating": ratings[idx] if idx < len(ratings) else 5,
                        "candidate_ss_wr_desc": candidate_text if source == "candidate" else "",
                    }
                )

        append_rows("current", self.precomputed_results, precomputed_ratings)
        append_rows("candidate", self.latest_results, candidate_ratings)
        return rows

    def _upsert_qa_rows(self, qa_rows: list[dict[str, object]]) -> None:
        self._ensure_qa_template_exists()
        qa_df = self._load_qa_df()
        new_df = pd.DataFrame(qa_rows)

        for col in qa_df.columns:
            if col not in new_df.columns:
                new_df[col] = ""

        merged = pd.concat([qa_df, new_df[qa_df.columns]], ignore_index=True)
        merged["rank"] = pd.to_numeric(merged["rank"], errors="coerce")
        merged = merged.drop_duplicates(subset=["small_step_id", "source", "rank"], keep="last")
        merged = merged.sort_values(["small_step_id", "source", "rank"], kind="stable")
        merged.to_csv(QA_TRACKING_PATH, index=False)

    def _update_qa_csv(self) -> None:
        small_step_id = self._selected_small_step_id()
        row = self.curriculum_by_id.get(small_step_id)
        if row is None:
            messagebox.showwarning("Missing small step", "Select a small step first.")
            return

        candidate_text = self.candidate_text.get("1.0", tk.END).strip()

        candidate_ratings = [self._safe_parse_rating(var.get(), default=5) for var in self.rating_vars]
        precomputed_ratings = [self._safe_parse_rating(var.get(), default=5) for var in self.precomputed_rating_vars]

        qa_rows = self._collect_qa_rows(
            row=row,
            candidate_text=candidate_text,
            candidate_ratings=candidate_ratings,
            precomputed_ratings=precomputed_ratings,
        )

        try:
            self._upsert_qa_rows(qa_rows)
        except Exception as exc:
            messagebox.showerror("QA Save Error", str(exc))
            return

        if small_step_id in self.saved_candidate_steps:
            self.candidate_display_unlocked_steps.add(small_step_id)
            self._populate_candidate_from_qa(small_step_id)
            self.status_var.set("Updated qa/qa.csv and loaded persisted candidate picks.")
        else:
            self.candidate_display_unlocked_steps.discard(small_step_id)
            self._clear_candidate_result_widgets(reset_ratings=False)
            self._set_candidate_panel_state("Candidate panel: Update QA CSV ran, but Save Approved Candidate has not been done yet")
            self.status_var.set("Updated qa/qa.csv. Candidate panel remains blank until Save Approved Candidate, then Update QA CSV.")

        messagebox.showinfo("QA Updated", f"Saved QA rows to:\n{QA_TRACKING_PATH}")

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
