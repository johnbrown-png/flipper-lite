"""
Compare query variants for a single curriculum step using the same ranking pipeline
as precompute_curriculum_recommendations.py.

This script evaluates Manual, Original, Short, and Hybrid query strings and writes
ranked top-k results after semantic search + instruction quality scoring + combined rank.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys
from typing import Dict, List

import pandas as pd

# Ensure imports work when script is launched from Improve_pick/
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from precompute_curriculum_recommendations import load_faiss_index, search_and_score_async
from query_embedder import QueryEmbedder
from data_pipeline.deletion_tracker import DeletionTracker
from data_pipeline.instruction_quality_scorer import InstructionQualityScorer


QUERY_VARIANTS = {
    "Manual": "manual_query",
    "Original": "original_query",
    "Short": "short_query",
    "Hybrid": "hybrid_query",
}

REQUIRED_COLUMNS = ["topic", "small_step", "manual_query", "original_query", "short_query", "hybrid_query"]


def clean_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


def get_scoring_context_desc(row: pd.Series) -> str:
    """
    Keep instruction scoring context stable across comparators.

    By default this uses original_query to mirror curriculum objective context,
    with fallback to first available comparator text.
    """
    original = clean_text(row.get("original_query", ""))
    if original:
        return original

    for column in QUERY_VARIANTS.values():
        candidate = clean_text(row.get(column, ""))
        if candidate:
            return candidate

    return ""


async def run_row_comparison(
    row_id: int,
    row: pd.Series,
    *,
    top_k: int,
    index,
    metadata,
    embedder: QueryEmbedder,
    scorer: InstructionQualityScorer,
    deleted_videos: set,
) -> List[Dict]:
    topic = clean_text(row.get("topic", ""))
    small_step = clean_text(row.get("small_step", ""))
    age = clean_text(row.get("age", ""))
    year = clean_text(row.get("year", ""))
    term = clean_text(row.get("term", ""))
    difficulty = clean_text(row.get("difficulty", ""))
    notes = clean_text(row.get("notes", ""))

    scoring_context_desc = get_scoring_context_desc(row)

    records: List[Dict] = []

    for variant_name, column_name in QUERY_VARIANTS.items():
        query_text = clean_text(row.get(column_name, ""))
        if not query_text:
            continue

        ranked = await search_and_score_async(
            query_text=query_text,
            age=age,
            topic=topic,
            small_step=small_step,
            small_step_desc=scoring_context_desc,
            index=index,
            metadata=metadata,
            embedder=embedder,
            scorer=scorer,
            deleted_videos=deleted_videos,
            k=top_k,
        )

        if not ranked:
            records.append(
                {
                    "row_id": row_id,
                    "topic": topic,
                    "small_step": small_step,
                    "age": age,
                    "year": year,
                    "term": term,
                    "difficulty": difficulty,
                    "comparator_type": variant_name,
                    "input_query": query_text,
                    "scoring_context_desc": scoring_context_desc,
                    "combined_rank": "",
                    "video_id": "",
                    "title": "",
                    "semantic_score": "",
                    "instruction_score": "",
                    "combined_score": "",
                    "instruction_justification": "",
                    "notes": notes,
                }
            )
            continue

        for rank, rec in enumerate(ranked, start=1):
            records.append(
                {
                    "row_id": row_id,
                    "topic": topic,
                    "small_step": small_step,
                    "age": age,
                    "year": year,
                    "term": term,
                    "difficulty": difficulty,
                    "comparator_type": variant_name,
                    "input_query": query_text,
                    "scoring_context_desc": scoring_context_desc,
                    "combined_rank": rank,
                    "video_id": rec.get("video_id", ""),
                    "title": rec.get("title", ""),
                    "semantic_score": round(float(rec.get("semantic_score", 0.0)), 4),
                    "instruction_score": round(float(rec.get("instruction_score", 0.0)), 2),
                    "combined_score": round(float(rec.get("combined_score", 0.0)), 4),
                    "instruction_justification": rec.get("instruction_justification", ""),
                    "notes": notes,
                }
            )

    return records


def validate_input_columns(df: pd.DataFrame) -> None:
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            "Missing required columns in input CSV: " + ", ".join(missing)
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare Manual/Original/Short/Hybrid query variants with production ranking logic."
    )
    parser.add_argument(
        "--input",
        default="Improve_pick/comparator_input.csv",
        help="Input CSV with one row per topic + small_step and four comparator strings.",
    )
    parser.add_argument(
        "--output",
        default="Improve_pick/comparator_results.csv",
        help="Output CSV path for ranked comparison results.",
    )
    parser.add_argument(
        "--top_k",
        type=int,
        default=3,
        help="Top results per comparator (default: 3).",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    df = pd.read_csv(input_path)
    validate_input_columns(df)

    print(f"Loaded {len(df)} comparison row(s) from {input_path}")
    print("Loading FAISS index and metadata...")
    index, metadata = load_faiss_index()

    print("Loading deleted videos...")
    deleted_videos = DeletionTracker().get_deleted_video_ids()
    print(f"Deleted videos filtered: {len(deleted_videos)}")

    print("Initializing embedder and instruction scorer...")
    embedder = QueryEmbedder()
    scorer = InstructionQualityScorer()

    all_records: List[Dict] = []

    for i, row in df.iterrows():
        row_id = i + 1
        topic = clean_text(row.get("topic", ""))
        small_step = clean_text(row.get("small_step", ""))

        print(f"\nRow {row_id}: {topic} | {small_step}")
        row_records = asyncio.run(
            run_row_comparison(
                row_id,
                row,
                top_k=args.top_k,
                index=index,
                metadata=metadata,
                embedder=embedder,
                scorer=scorer,
                deleted_videos=deleted_videos,
            )
        )
        all_records.extend(row_records)

    out_df = pd.DataFrame(all_records)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(output_path, index=False)

    print("\nDone.")
    print(f"Saved {len(out_df)} result rows to: {output_path}")
    print("Each comparator is ranked by combined_score after semantic + instruction scoring.")


if __name__ == "__main__":
    main()
