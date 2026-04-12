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

from precompute_curriculum_recommendations import load_faiss_index, search_and_score_async
from query_embedder import QueryEmbedder
from data_pipeline.deletion_tracker import DeletionTracker
from data_pipeline.instruction_quality_scorer import InstructionQualityScorer
from shared.curriculum_schema import curriculum_to_long_df


CURRICULUM_PATH = project_root / "Curriculum" / "Maths" / "curriculum_22032026_small_steps.csv"
TARGET_OVERRIDES_PATH = project_root / "qa" / "targeted_ss_wr_desc_overrides.csv"
APPROVED_CANDIDATES_PATH = project_root / "qa" / "approved_ss_wr_desc_candidates.csv"
TOP_K = 3


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

        self.result_title_labels: list[ttk.Label] = []
        self.result_channel_labels: list[ttk.Label] = []
        self.result_score_labels: list[ttk.Label] = []
        self.result_open_buttons: list[ttk.Button] = []
        self.rating_vars: list[tk.StringVar] = []
        self.rating_dropdowns: list[tk.OptionMenu] = []

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

        control_frame = ttk.Frame(outer)
        control_frame.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        self.search_btn = ttk.Button(control_frame, text="Search Top 3", command=self._run_search)
        self.search_btn.grid(row=0, column=0, padx=(0, 8))
        self.save_btn = ttk.Button(control_frame, text="Save Approved Candidate", command=self._save_candidate, state=tk.DISABLED)
        self.save_btn.grid(row=0, column=1, padx=(0, 8))

        self.status_label = ttk.Label(control_frame, textvariable=self.status_var, foreground="blue")
        self.status_label.grid(row=0, column=2, sticky="w")

        results_frame = ttk.LabelFrame(outer, text="Top 3 Results", padding=10)
        results_frame.grid(row=4, column=0, sticky="nsew")
        results_frame.columnconfigure(1, weight=1)
        for row_num in range(TOP_K + 1):
            results_frame.rowconfigure(row_num, weight=0)

        headers = ["Rank", "Video", "Channel", "Combined", "Open", "Rating (1-10)"]
        for col, header in enumerate(headers):
            ttk.Label(results_frame, text=header, font=("Segoe UI", 10, "bold")).grid(row=0, column=col, sticky="w", padx=4, pady=(0, 6))

        rating_options = [str(i) for i in range(1, 11)]

        for i in range(TOP_K):
            row_num = i + 1
            ttk.Label(results_frame, text=f"{row_num}").grid(row=row_num, column=0, sticky="w", padx=4, pady=4)

            title_label = ttk.Label(results_frame, text="", width=70)
            title_label.grid(row=row_num, column=1, sticky="w", padx=4, pady=4)
            self.result_title_labels.append(title_label)

            channel_label = ttk.Label(results_frame, text="", width=28)
            channel_label.grid(row=row_num, column=2, sticky="w", padx=4, pady=4)
            self.result_channel_labels.append(channel_label)

            score_label = ttk.Label(results_frame, text="", width=12)
            score_label.grid(row=row_num, column=3, sticky="w", padx=4, pady=4)
            self.result_score_labels.append(score_label)

            open_btn = ttk.Button(results_frame, text="Open", command=lambda idx=i: self._open_video(idx), state=tk.DISABLED)
            open_btn.grid(row=row_num, column=4, sticky="w", padx=4, pady=4)
            self.result_open_buttons.append(open_btn)

            rating_var = tk.StringVar(value="5")
            self.rating_vars.append(rating_var)

            # tk.OptionMenu allows per-widget background color updates.
            rating_menu = tk.OptionMenu(results_frame, rating_var, *rating_options, command=lambda _value, idx=i: self._on_rating_change(idx))
            rating_menu.grid(row=row_num, column=5, sticky="w", padx=4, pady=4)
            rating_menu.config(width=5)
            self.rating_dropdowns.append(rating_menu)
            self._apply_rating_color(i)

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

            self.curriculum_by_id = {
                row["small_step_id"]: row
                for _, row in self.curriculum_df.drop_duplicates(subset=["small_step_id"], keep="first").iterrows()
            }

            self.sorted_step_ids = sorted(self.curriculum_by_id.keys())
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
        self.status_var.set("Ready")

    def _set_text(self, widget: scrolledtext.ScrolledText, content: str) -> None:
        widget.config(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, content)
        if widget is self.baseline_text:
            widget.config(state=tk.DISABLED)

    def _clear_results(self) -> None:
        self.latest_results = []
        self.latest_query_text = ""

        for i in range(TOP_K):
            self.result_title_labels[i].config(text="")
            self.result_channel_labels[i].config(text="")
            self.result_score_labels[i].config(text="")
            self.result_open_buttons[i].config(state=tk.DISABLED)
            self.rating_vars[i].set("5")
            self._apply_rating_color(i)

        self.save_btn.config(state=tk.DISABLED)

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

        for i in range(TOP_K):
            if i < len(results):
                result = results[i]
                title_text = f"{result['title']} ({result['video_id']})"
                self.result_title_labels[i].config(text=title_text)
                self.result_channel_labels[i].config(text=result.get("channel", ""))
                self.result_score_labels[i].config(text=f"{result['combined_score']:.4f}")
                self.result_open_buttons[i].config(state=tk.NORMAL)
            else:
                self.result_title_labels[i].config(text="")
                self.result_channel_labels[i].config(text="")
                self.result_score_labels[i].config(text="")
                self.result_open_buttons[i].config(state=tk.DISABLED)

            self.rating_vars[i].set("5")
            self._apply_rating_color(i)

        self.search_btn.config(state=tk.NORMAL)
        self.save_btn.config(state=tk.NORMAL if results else tk.DISABLED)

        if results:
            self.status_var.set(f"Search complete. Found {len(results)} recommendation(s).")
        else:
            self.status_var.set("Search complete. No recommendations found.")

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
            self._save_approved_candidates_log(row=row, candidate=candidate, ratings=ratings)
            self._upsert_targeted_override(row=row, candidate=candidate, scenario_label=scenario_label, ratings=ratings)
            self.status_var.set("Saved approved candidate and override row.")
            messagebox.showinfo(
                "Saved",
                f"Saved to:\n{APPROVED_CANDIDATES_PATH}\n{TARGET_OVERRIDES_PATH}",
            )
        except Exception as exc:
            messagebox.showerror("Save Error", str(exc))

    def _save_approved_candidates_log(self, row: dict[str, object], candidate: str, ratings: list[int]) -> None:
        APPROVED_CANDIDATES_PATH.parent.mkdir(parents=True, exist_ok=True)

        now = datetime.now().isoformat(timespec="seconds")

        result_rows: dict[int, dict[str, str]] = {}
        top3_video_ids = []
        for idx in range(TOP_K):
            result = self.latest_results[idx] if idx < len(self.latest_results) else {}
            video_id = clean_text(result.get("video_id"))
            title = clean_text(result.get("title"))
            channel = clean_text(result.get("channel"))
            top3_video_ids.append(video_id)
            result_rows[idx + 1] = {
                "video_id": video_id,
                "title": title,
                "channel": channel,
            }

        record = {
            "approved_at": now,
            "small_step_id": clean_text(row.get("small_step_id")),
            "topic": clean_text(row.get("topic")),
            "small_step_name": clean_text(row.get("small_step_name")),
            "baseline_ss_wr_desc": clean_text(row.get("ss_wr_desc")),
            "candidate_ss_wr_desc": candidate,
            "query_text_used": self.latest_query_text,
            "candidate_top3_video_ids": " | ".join([v for v in top3_video_ids if v]),
            "rank1_video_id": result_rows[1]["video_id"],
            "rank1_video_title": result_rows[1]["title"],
            "rank1_video_channel": result_rows[1]["channel"],
            "rank1_rating": ratings[0] if len(ratings) > 0 else "",
            "rank2_video_id": result_rows[2]["video_id"],
            "rank2_video_title": result_rows[2]["title"],
            "rank2_video_channel": result_rows[2]["channel"],
            "rank2_rating": ratings[1] if len(ratings) > 1 else "",
            "rank3_video_id": result_rows[3]["video_id"],
            "rank3_video_title": result_rows[3]["title"],
            "rank3_video_channel": result_rows[3]["channel"],
            "rank3_rating": ratings[2] if len(ratings) > 2 else "",
        }

        if APPROVED_CANDIDATES_PATH.exists():
            existing_df = pd.read_csv(APPROVED_CANDIDATES_PATH)
            updated_df = pd.concat([existing_df, pd.DataFrame([record])], ignore_index=True)
        else:
            updated_df = pd.DataFrame([record])

        updated_df.to_csv(APPROVED_CANDIDATES_PATH, index=False)

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
