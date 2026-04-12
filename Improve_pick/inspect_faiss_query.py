"""Inspect raw FAISS chunk hits and grouped semantic ranks for a single query."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
import sys

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import faiss

from precompute_curriculum_recommendations import calculate_cosine_similarity, load_faiss_index
from query_embedder import QueryEmbedder


def configure_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def clean_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def parse_target_ids(raw_value: str) -> list[str]:
    if not raw_value:
        return []
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def load_metadata() -> list[dict[str, object]]:
    _, metadata = load_faiss_index()
    return metadata


def search_chunks(index: faiss.Index, metadata: list[dict[str, object]], query_text: str, top_chunks: int) -> list[dict[str, object]]:
    embedder = QueryEmbedder()
    query_embedding = embedder.embed_query(query_text)
    distances, indices = index.search(query_embedding, top_chunks)

    rows: list[dict[str, object]] = []
    for rank, (distance, idx) in enumerate(zip(distances[0], indices[0]), start=1):
        if idx == -1 or idx >= len(metadata):
            continue
        item = metadata[int(idx)]
        rows.append(
            {
                "chunk_rank": rank,
                "metadata_index": int(idx),
                "l2_distance": float(distance),
                "cosine_similarity": float(calculate_cosine_similarity(float(distance))),
                "video_id": clean_text(item.get("video_id")),
                "title": clean_text(item.get("title")),
                "chunk_index": item.get("chunk_index"),
                "text": clean_text(item.get("text")),
            }
        )
    return rows


def group_video_ranks(chunk_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    video_chunks: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in chunk_rows:
        video_chunks[row["video_id"]].append(row)

    grouped_rows: list[dict[str, object]] = []
    for video_id, rows in video_chunks.items():
        similarities = [float(row["cosine_similarity"]) for row in rows]
        good_chunk_count = sum(1 for similarity in similarities if similarity >= 0.6)
        median_similarity = sorted(similarities)[len(similarities) // 2]
        ranking_score = median_similarity + (good_chunk_count * 0.02)
        first_row = rows[0]

        grouped_rows.append(
            {
                "video_id": video_id,
                "title": first_row["title"],
                "semantic_rank": 0,
                "first_chunk_rank": int(first_row["chunk_rank"]),
                "chunk_hits": len(rows),
                "median_similarity": median_similarity,
                "ranking_score": ranking_score,
                "best_similarity": max(similarities),
            }
        )

    grouped_rows.sort(key=lambda item: float(item["ranking_score"]), reverse=True)
    for rank, row in enumerate(grouped_rows, start=1):
        row["semantic_rank"] = rank
    return grouped_rows


def print_chunk_rows(chunk_rows: list[dict[str, object]], limit: int) -> None:
    print("\nRAW CHUNK HITS")
    for row in chunk_rows[:limit]:
        sample = row["text"][:180].replace("\n", " ")
        print(
            json.dumps(
                {
                    "chunk_rank": row["chunk_rank"],
                    "video_id": row["video_id"],
                    "title": row["title"],
                    "chunk_index": row["chunk_index"],
                    "l2_distance": round(float(row["l2_distance"]), 6),
                    "cosine_similarity": round(float(row["cosine_similarity"]), 6),
                    "sample": sample,
                },
                ensure_ascii=False,
            )
        )


def print_grouped_rows(grouped_rows: list[dict[str, object]], limit: int) -> None:
    print("\nGROUPED VIDEO RANKS")
    for row in grouped_rows[:limit]:
        print(
            json.dumps(
                {
                    "semantic_rank": row["semantic_rank"],
                    "video_id": row["video_id"],
                    "title": row["title"],
                    "first_chunk_rank": row["first_chunk_rank"],
                    "chunk_hits": row["chunk_hits"],
                    "best_similarity": round(float(row["best_similarity"]), 6),
                    "median_similarity": round(float(row["median_similarity"]), 6),
                    "ranking_score": round(float(row["ranking_score"]), 6),
                },
                ensure_ascii=False,
            )
        )


def print_target_summary(target_ids: list[str], chunk_rows: list[dict[str, object]], grouped_rows: list[dict[str, object]]) -> None:
    if not target_ids:
        return

    chunk_first_hits: dict[str, dict[str, object]] = {}
    for row in chunk_rows:
        video_id = clean_text(row["video_id"])
        if video_id in target_ids and video_id not in chunk_first_hits:
            chunk_first_hits[video_id] = row

    grouped_lookup = {clean_text(row["video_id"]): row for row in grouped_rows}

    print("\nTARGET VIDEO SUMMARY")
    for video_id in target_ids:
        chunk_row = chunk_first_hits.get(video_id)
        grouped_row = grouped_lookup.get(video_id)
        summary = {
            "video_id": video_id,
            "chunk_rank": chunk_row["chunk_rank"] if chunk_row else None,
            "semantic_rank": grouped_row["semantic_rank"] if grouped_row else None,
            "title": grouped_row["title"] if grouped_row else (chunk_row["title"] if chunk_row else ""),
            "ranking_score": round(float(grouped_row["ranking_score"]), 6) if grouped_row else None,
        }
        print(json.dumps(summary, ensure_ascii=False))


def main() -> None:
    configure_stdout()

    parser = argparse.ArgumentParser(description="Inspect raw FAISS chunk hits and grouped semantic ranks")
    parser.add_argument("query", help="Query text to embed and search")
    parser.add_argument("--top-chunks", type=int, default=50, help="Number of raw chunk hits to inspect")
    parser.add_argument("--show-chunks", type=int, default=25, help="Number of raw chunk hits to print")
    parser.add_argument("--show-videos", type=int, default=15, help="Number of grouped videos to print")
    parser.add_argument(
        "--target-ids",
        default="",
        help="Comma-separated video IDs to track through the chunk and grouped rankings",
    )
    args = parser.parse_args()

    index, metadata = load_faiss_index()
    chunk_rows = search_chunks(index, metadata, args.query, args.top_chunks)
    grouped_rows = group_video_ranks(chunk_rows)
    target_ids = parse_target_ids(args.target_ids)

    print(json.dumps({"query": args.query, "top_chunks": args.top_chunks, "unique_videos": len(grouped_rows)}, ensure_ascii=False))
    print_chunk_rows(chunk_rows, args.show_chunks)
    print_grouped_rows(grouped_rows, args.show_videos)
    print_target_summary(target_ids, chunk_rows, grouped_rows)


if __name__ == "__main__":
    main()