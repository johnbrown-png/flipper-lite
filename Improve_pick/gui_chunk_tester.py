"""GUI tool for testing FAISS chunk-ceiling effects on semantic retrieval only.

Features:
- Select a small step by small_step_id
- Edit candidate wording
- Run FAISS semantic search with a user-controlled chunk ceiling (N)
- Compare ranking modes based on chunk-level cosine aggregates
- Inspect top 10-15 video aggregates with per-video statistics
"""

from __future__ import annotations

from pathlib import Path
import sys
import threading
import webbrowser

import numpy as np
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
from shared.curriculum_schema import curriculum_to_long_df


CURRICULUM_PATH = project_root / "Curriculum" / "Maths" / "curriculum_22032026_small_steps.csv"
MAX_DISPLAY_ROWS = 15
MIN_CHUNK_CEILING = 1
MAX_CHUNK_CEILING = 400
CHUNK_PRESETS = [10, 20, 30, 40, 60, 80, 120, 160]
RESULT_COUNT_CHOICES = [10, 12, 15]
GOOD_CHUNK_THRESHOLD = 0.6
GOOD_CHUNK_BONUS = 0.02


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


class ChunkTesterGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Improve Pick - Semantic Chunk Tester")
        self.root.geometry("1550x920")

        self.status_var = tk.StringVar(value="Loading data...")
        self.step_var = tk.StringVar(value="")
        self.chunk_ceiling_var = tk.StringVar(value="40")
        self.chunk_preset_var = tk.StringVar(value="40")
        self.result_count_var = tk.StringVar(value="15")
        self.rank_mode_var = tk.StringVar(value="median_plus_bonus")
        self.summary_var = tk.StringVar(value="Summary: idle")

        self.curriculum_df = pd.DataFrame()
        self.curriculum_by_id: dict[str, dict[str, object]] = {}
        self.sorted_step_ids: list[str] = []

        self.index = None
        self.metadata: list[dict[str, object]] = []
        self.embedder: QueryEmbedder | None = None
        self.deleted_videos: set[str] = set()
        self.fallback_lookup: dict[str, dict[str, str]] = {}
        self.video_lookup: dict[str, dict[str, str]] = {}

        self.latest_ranked_results: list[dict[str, object]] = []

        self.rank_labels: list[ttk.Label] = []
        self.title_labels: list[ttk.Label] = []
        self.channel_labels: list[ttk.Label] = []
        self.chunk_count_labels: list[ttk.Label] = []
        self.avg_labels: list[ttk.Label] = []
        self.std_labels: list[ttk.Label] = []
        self.median_labels: list[ttk.Label] = []
        self.bonus_labels: list[ttk.Label] = []
        self.score_labels: list[ttk.Label] = []
        self.open_buttons: list[ttk.Button] = []

        self._build_ui()
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
            text="Semantic Chunk Ceiling Tester (FAISS Only)",
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

        ttk.Label(candidate_frame, text="Candidate wording", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        self.candidate_text = scrolledtext.ScrolledText(candidate_frame, wrap=tk.WORD, height=8)
        self.candidate_text.grid(row=1, column=0, sticky="nsew", pady=(4, 0))

        controls_frame = ttk.LabelFrame(outer, text="Semantic Search Controls", padding=10)
        controls_frame.grid(row=3, column=0, sticky="ew", pady=(0, 8))

        ttk.Label(controls_frame, text="Chunk ceiling (N):").grid(row=0, column=0, sticky="w")
        self.chunk_spinbox = tk.Spinbox(
            controls_frame,
            from_=MIN_CHUNK_CEILING,
            to=MAX_CHUNK_CEILING,
            width=7,
            textvariable=self.chunk_ceiling_var,
            increment=1,
        )
        self.chunk_spinbox.grid(row=0, column=1, sticky="w", padx=(6, 8))

        ttk.Button(controls_frame, text="-5", command=lambda: self._adjust_chunk_ceiling(-5)).grid(row=0, column=2, padx=2)
        ttk.Button(controls_frame, text="-1", command=lambda: self._adjust_chunk_ceiling(-1)).grid(row=0, column=3, padx=2)
        ttk.Button(controls_frame, text="+1", command=lambda: self._adjust_chunk_ceiling(1)).grid(row=0, column=4, padx=2)
        ttk.Button(controls_frame, text="+5", command=lambda: self._adjust_chunk_ceiling(5)).grid(row=0, column=5, padx=2)

        ttk.Label(controls_frame, text="Presets:").grid(row=0, column=6, sticky="w", padx=(12, 6))
        self.chunk_preset_combo = ttk.Combobox(
            controls_frame,
            textvariable=self.chunk_preset_var,
            values=[str(v) for v in CHUNK_PRESETS],
            width=7,
            state="readonly",
        )
        self.chunk_preset_combo.grid(row=0, column=7, sticky="w")
        self.chunk_preset_combo.bind("<<ComboboxSelected>>", self._on_chunk_preset_selected)

        ttk.Label(controls_frame, text="Show rows:").grid(row=0, column=8, sticky="w", padx=(12, 6))
        self.result_count_combo = ttk.Combobox(
            controls_frame,
            textvariable=self.result_count_var,
            values=[str(v) for v in RESULT_COUNT_CHOICES],
            width=5,
            state="readonly",
        )
        self.result_count_combo.grid(row=0, column=9, sticky="w")

        ttk.Label(controls_frame, text="Rank mode:").grid(row=0, column=10, sticky="w", padx=(12, 6))
        self.rank_mode_combo = ttk.Combobox(
            controls_frame,
            textvariable=self.rank_mode_var,
            width=20,
            state="readonly",
            values=[
                "avg_cosine",
                "median_cosine",
                "median_plus_bonus",
            ],
        )
        self.rank_mode_combo.grid(row=0, column=11, sticky="w")

        self.search_btn = ttk.Button(controls_frame, text="Run Semantic Search", command=self._run_search)
        self.search_btn.grid(row=0, column=12, padx=(12, 0))

        ttk.Label(controls_frame, textvariable=self.status_var, foreground="blue").grid(row=1, column=0, columnspan=13, sticky="w", pady=(8, 0))
        ttk.Label(controls_frame, textvariable=self.summary_var, foreground="#555555").grid(row=2, column=0, columnspan=13, sticky="w", pady=(4, 0))

        results_frame = ttk.LabelFrame(outer, text="Video Aggregates", padding=10)
        results_frame.grid(row=4, column=0, sticky="nsew")
        results_frame.columnconfigure(1, weight=1)

        headers = [
            "Rank",
            "Title (video_id)",
            "Channel",
            "Chunks",
            "Avg Cos",
            "Std Cos",
            "Median",
            "Bonus",
            "Score",
            "Open",
        ]

        for col, header in enumerate(headers):
            ttk.Label(results_frame, text=header, font=("Segoe UI", 10, "bold")).grid(row=0, column=col, sticky="w", padx=4, pady=(0, 6))

        for i in range(MAX_DISPLAY_ROWS):
            row_num = i + 1

            rank_lbl = ttk.Label(results_frame, text="")
            rank_lbl.grid(row=row_num, column=0, sticky="w", padx=4, pady=3)
            self.rank_labels.append(rank_lbl)

            title_lbl = ttk.Label(results_frame, text="", width=56)
            title_lbl.grid(row=row_num, column=1, sticky="w", padx=4, pady=3)
            self.title_labels.append(title_lbl)

            channel_lbl = ttk.Label(results_frame, text="", width=20)
            channel_lbl.grid(row=row_num, column=2, sticky="w", padx=4, pady=3)
            self.channel_labels.append(channel_lbl)

            chunks_lbl = ttk.Label(results_frame, text="", width=8)
            chunks_lbl.grid(row=row_num, column=3, sticky="w", padx=4, pady=3)
            self.chunk_count_labels.append(chunks_lbl)

            avg_lbl = ttk.Label(results_frame, text="", width=8)
            avg_lbl.grid(row=row_num, column=4, sticky="w", padx=4, pady=3)
            self.avg_labels.append(avg_lbl)

            std_lbl = ttk.Label(results_frame, text="", width=8)
            std_lbl.grid(row=row_num, column=5, sticky="w", padx=4, pady=3)
            self.std_labels.append(std_lbl)

            median_lbl = ttk.Label(results_frame, text="", width=8)
            median_lbl.grid(row=row_num, column=6, sticky="w", padx=4, pady=3)
            self.median_labels.append(median_lbl)

            bonus_lbl = ttk.Label(results_frame, text="", width=8)
            bonus_lbl.grid(row=row_num, column=7, sticky="w", padx=4, pady=3)
            self.bonus_labels.append(bonus_lbl)

            score_lbl = ttk.Label(results_frame, text="", width=8)
            score_lbl.grid(row=row_num, column=8, sticky="w", padx=4, pady=3)
            self.score_labels.append(score_lbl)

            open_btn = ttk.Button(results_frame, text="Open", command=lambda idx=i: self._open_video(idx), state=tk.DISABLED)
            open_btn.grid(row=row_num, column=9, sticky="w", padx=4, pady=3)
            self.open_buttons.append(open_btn)

    def _selected_small_step_id(self) -> str:
        label = self.step_var.get().strip()
        if not label:
            return ""
        return label.split(" | ", 1)[0].strip()

    def _set_text(self, widget: scrolledtext.ScrolledText, content: str, read_only: bool = False) -> None:
        widget.config(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, content)
        if read_only:
            widget.config(state=tk.DISABLED)

    def _clear_results(self) -> None:
        self.latest_ranked_results = []
        for i in range(MAX_DISPLAY_ROWS):
            self.rank_labels[i].config(text="")
            self.title_labels[i].config(text="")
            self.channel_labels[i].config(text="")
            self.chunk_count_labels[i].config(text="")
            self.avg_labels[i].config(text="")
            self.std_labels[i].config(text="")
            self.median_labels[i].config(text="")
            self.bonus_labels[i].config(text="")
            self.score_labels[i].config(text="")
            self.open_buttons[i].config(state=tk.DISABLED)

    def _load_initial_data(self) -> None:
        try:
            self.status_var.set("Loading curriculum...")
            self.root.update_idletasks()

            curriculum_raw = pd.read_csv(CURRICULUM_PATH)
            self.curriculum_df = curriculum_to_long_df(curriculum_raw).copy()

            required_cols = ["small_step_id", "topic", "small_step_name", "ss_wr_desc"]
            for col in required_cols:
                if col not in self.curriculum_df.columns:
                    raise ValueError(f"Curriculum is missing required column: {col}")

            self.curriculum_df["small_step_id"] = self.curriculum_df["small_step_id"].map(clean_text)
            self.curriculum_df["topic"] = self.curriculum_df["topic"].map(clean_text)
            self.curriculum_df["small_step_name"] = self.curriculum_df["small_step_name"].map(clean_text)
            self.curriculum_df["ss_wr_desc"] = self.curriculum_df["ss_wr_desc"].map(clean_text)

            self.curriculum_df = self.curriculum_df[self.curriculum_df["small_step_id"].str.len() > 0].copy()

            self.curriculum_by_id = {
                row["small_step_id"]: row
                for _, row in self.curriculum_df.drop_duplicates(subset=["small_step_id"], keep="first").iterrows()
            }

            self.sorted_step_ids = sorted(
                self.curriculum_by_id.keys(),
                key=lambda sid: int(self.curriculum_by_id[sid].get("small_step_num", 0)),
            )

            labels = []
            for small_step_id in self.sorted_step_ids:
                row = self.curriculum_by_id[small_step_id]
                labels.append(f"{small_step_id} | {row['topic']} | {row['small_step_name']}")

            self.step_combo["values"] = labels
            if labels:
                self.step_var.set(labels[0])
                self._on_step_selected(None)

            self.status_var.set("Loading FAISS and embedder...")
            self.search_btn.config(state=tk.DISABLED)
            self.root.update_idletasks()

            worker = threading.Thread(target=self._load_heavy_assets, daemon=True)
            worker.start()

        except Exception as exc:
            self.status_var.set("Failed to initialize")
            messagebox.showerror("Initialization Error", str(exc))

    def _load_heavy_assets(self) -> None:
        try:
            index, metadata = load_faiss_index()
            fallback_lookup = build_faiss_video_lookup(metadata)
            video_lookup = load_video_lookup()
            deleted_videos = DeletionTracker().get_deleted_video_ids()
            embedder = QueryEmbedder()
            self.root.after(0, self._on_heavy_assets_ready, index, metadata, fallback_lookup, video_lookup, deleted_videos, embedder)
        except Exception as exc:
            self.root.after(0, self._on_heavy_assets_error, str(exc))

    def _on_heavy_assets_ready(
        self,
        index,
        metadata: list[dict[str, object]],
        fallback_lookup: dict[str, dict[str, str]],
        video_lookup: dict[str, dict[str, str]],
        deleted_videos: set[str],
        embedder: QueryEmbedder,
    ) -> None:
        self.index = index
        self.metadata = metadata
        self.fallback_lookup = fallback_lookup
        self.video_lookup = video_lookup
        self.deleted_videos = deleted_videos
        self.embedder = embedder
        self.search_btn.config(state=tk.NORMAL)
        self.status_var.set("Ready")

    def _on_heavy_assets_error(self, error_message: str) -> None:
        self.status_var.set("Failed to load FAISS/embedder")
        messagebox.showerror("Initialization Error", error_message)

    def _on_step_selected(self, _event) -> None:
        small_step_id = self._selected_small_step_id()
        row = self.curriculum_by_id.get(small_step_id)
        if row is None:
            return

        baseline = clean_text(row.get("ss_wr_desc"))
        self._set_text(self.baseline_text, baseline, read_only=True)
        self._set_text(self.candidate_text, baseline, read_only=False)
        self.summary_var.set("Summary: idle")
        self._clear_results()

    def _on_chunk_preset_selected(self, _event) -> None:
        self.chunk_ceiling_var.set(self.chunk_preset_var.get())

    def _adjust_chunk_ceiling(self, delta: int) -> None:
        current = self._get_chunk_ceiling(show_error=False)
        if current is None:
            current = 40
        new_value = max(MIN_CHUNK_CEILING, min(MAX_CHUNK_CEILING, current + delta))
        self.chunk_ceiling_var.set(str(new_value))

    def _get_chunk_ceiling(self, show_error: bool = True) -> int | None:
        raw = self.chunk_ceiling_var.get().strip()
        try:
            value = int(raw)
        except ValueError:
            if show_error:
                messagebox.showwarning("Invalid chunk ceiling", "Chunk ceiling must be an integer.")
            return None

        if value < MIN_CHUNK_CEILING or value > MAX_CHUNK_CEILING:
            if show_error:
                messagebox.showwarning(
                    "Invalid chunk ceiling",
                    f"Chunk ceiling must be between {MIN_CHUNK_CEILING} and {MAX_CHUNK_CEILING}.",
                )
            return None

        return value

    def _get_result_count(self) -> int | None:
        raw = self.result_count_var.get().strip()
        try:
            value = int(raw)
        except ValueError:
            messagebox.showwarning("Invalid row count", "Show rows must be an integer.")
            return None

        if value < 1 or value > MAX_DISPLAY_ROWS:
            messagebox.showwarning("Invalid row count", f"Show rows must be 1-{MAX_DISPLAY_ROWS}.")
            return None

        return value

    def _run_search(self) -> None:
        small_step_id = self._selected_small_step_id()
        if not small_step_id:
            messagebox.showwarning("Missing small step", "Select a small step first.")
            return

        if self.embedder is None or self.index is None:
            messagebox.showwarning("Not ready", "FAISS/index is still loading or failed.")
            return

        row = self.curriculum_by_id.get(small_step_id)
        if row is None:
            messagebox.showwarning("Missing row", "Unable to find selected small step in curriculum.")
            return

        candidate = self.candidate_text.get("1.0", tk.END).strip()
        if not candidate:
            messagebox.showwarning("Missing candidate", "Candidate wording is empty.")
            return

        chunk_ceiling = self._get_chunk_ceiling(show_error=True)
        if chunk_ceiling is None:
            return

        result_count = self._get_result_count()
        if result_count is None:
            return

        rank_mode = self.rank_mode_var.get().strip()
        if rank_mode not in {"avg_cosine", "median_cosine", "median_plus_bonus"}:
            messagebox.showwarning("Invalid rank mode", "Choose a valid rank mode.")
            return

        query_text = build_query_text(
            topic=clean_text(row.get("topic")),
            small_step_name=clean_text(row.get("small_step_name")),
            ss_wr_desc=candidate,
        )

        self.search_btn.config(state=tk.DISABLED)
        self.status_var.set("Running FAISS semantic search...")
        self.summary_var.set("Summary: working...")
        self._clear_results()

        worker = threading.Thread(
            target=self._search_worker,
            args=(query_text, chunk_ceiling, result_count, rank_mode),
            daemon=True,
        )
        worker.start()

    def _search_worker(self, query_text: str, chunk_ceiling: int, result_count: int, rank_mode: str) -> None:
        try:
            embedding = self.embedder.embed_query(query_text)
            distances, indices = self.index.search(embedding, chunk_ceiling)

            video_chunks: dict[str, list[dict[str, object]]] = {}
            seen_chunks = 0
            usable_chunks = 0

            for dist, idx in zip(distances[0], indices[0]):
                seen_chunks += 1
                if idx == -1 or idx >= len(self.metadata):
                    continue

                video_meta = self.metadata[int(idx)]
                video_id = clean_text(video_meta.get("video_id"))
                if not video_id or video_id in self.deleted_videos:
                    continue

                cosine_sim = float(calculate_cosine_similarity(float(dist)))
                usable_chunks += 1

                if video_id not in video_chunks:
                    video_chunks[video_id] = []

                video_chunks[video_id].append(
                    {
                        "cosine_similarity": cosine_sim,
                        "video_meta": video_meta,
                    }
                )

            aggregates: list[dict[str, object]] = []
            for video_id, chunks in video_chunks.items():
                sims = [float(c["cosine_similarity"]) for c in chunks]
                if not sims:
                    continue

                avg_cosine = float(np.mean(sims))
                std_cosine = float(np.std(sims))
                median_cosine = float(np.median(sims))
                good_chunk_count = sum(1 for s in sims if s >= GOOD_CHUNK_THRESHOLD)
                bonus = GOOD_CHUNK_BONUS * good_chunk_count

                if rank_mode == "avg_cosine":
                    final_score = avg_cosine
                elif rank_mode == "median_cosine":
                    final_score = median_cosine
                else:
                    final_score = median_cosine + bonus

                meta = chunks[0]["video_meta"]
                title = clean_text(meta.get("video_title") or meta.get("title"))
                fallback = self.video_lookup.get(video_id) or self.fallback_lookup.get(video_id) or {}
                channel = clean_text(fallback.get("channel") or meta.get("channel"))

                aggregates.append(
                    {
                        "video_id": video_id,
                        "title": title,
                        "channel": channel,
                        "chunk_count": len(sims),
                        "avg_cosine": avg_cosine,
                        "std_cosine": std_cosine,
                        "median_cosine": median_cosine,
                        "good_chunk_count": good_chunk_count,
                        "bonus": bonus,
                        "score": final_score,
                    }
                )

            ranked = sorted(aggregates, key=lambda x: float(x["score"]), reverse=True)
            displayed = ranked[:result_count]

            summary = {
                "requested_chunks": chunk_ceiling,
                "seen_chunks": seen_chunks,
                "usable_chunks": usable_chunks,
                "unique_videos": len(video_chunks),
                "displayed": len(displayed),
                "rank_mode": rank_mode,
            }

            self.root.after(0, self._on_search_success, displayed, summary)
        except Exception as exc:
            self.root.after(0, self._on_search_error, str(exc))

    def _on_search_success(self, results: list[dict[str, object]], summary: dict[str, object]) -> None:
        self.search_btn.config(state=tk.NORMAL)
        self.latest_ranked_results = results

        for i in range(MAX_DISPLAY_ROWS):
            if i >= len(results):
                self.rank_labels[i].config(text="")
                self.title_labels[i].config(text="")
                self.channel_labels[i].config(text="")
                self.chunk_count_labels[i].config(text="")
                self.avg_labels[i].config(text="")
                self.std_labels[i].config(text="")
                self.median_labels[i].config(text="")
                self.bonus_labels[i].config(text="")
                self.score_labels[i].config(text="")
                self.open_buttons[i].config(state=tk.DISABLED)
                continue

            result = results[i]
            title_text = clean_text(result.get("title"))
            video_id = clean_text(result.get("video_id"))
            if title_text and video_id:
                title_text = f"{title_text} ({video_id})"
            elif video_id:
                title_text = f"({video_id})"

            self.rank_labels[i].config(text=str(i + 1))
            self.title_labels[i].config(text=title_text)
            self.channel_labels[i].config(text=clean_text(result.get("channel")))
            self.chunk_count_labels[i].config(text=str(int(result.get("chunk_count", 0))))
            self.avg_labels[i].config(text=f"{float(result.get('avg_cosine', 0.0)):.4f}")
            self.std_labels[i].config(text=f"{float(result.get('std_cosine', 0.0)):.4f}")
            self.median_labels[i].config(text=f"{float(result.get('median_cosine', 0.0)):.4f}")
            self.bonus_labels[i].config(text=f"{float(result.get('bonus', 0.0)):.4f}")
            self.score_labels[i].config(text=f"{float(result.get('score', 0.0)):.4f}")
            self.open_buttons[i].config(state=tk.NORMAL if video_id else tk.DISABLED)

        self.status_var.set("Semantic search complete")
        self.summary_var.set(
            "Summary: "
            f"chunk_ceiling={summary['requested_chunks']}, "
            f"usable_chunks={summary['usable_chunks']}/{summary['seen_chunks']}, "
            f"unique_videos={summary['unique_videos']}, "
            f"displayed={summary['displayed']}, "
            f"rank_mode={summary['rank_mode']}"
        )

    def _on_search_error(self, error_message: str) -> None:
        self.search_btn.config(state=tk.NORMAL)
        self.status_var.set("Search failed")
        self.summary_var.set("Summary: error")
        messagebox.showerror("Search Error", error_message)

    def _open_video(self, index_num: int) -> None:
        if index_num < 0 or index_num >= len(self.latest_ranked_results):
            return

        video_id = clean_text(self.latest_ranked_results[index_num].get("video_id"))
        if not video_id:
            return

        webbrowser.open(f"https://www.youtube.com/watch?v={video_id}")


def main() -> None:
    root = tk.Tk()
    _app = ChunkTesterGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
