"""Shared retrieval and ranking engine used by GUI and batch precompute."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd


@dataclass(frozen=True)
class PickWeights:
    semantic: float = 0.55
    alignment: float = 0.20
    instruction: float = 0.25


DEFAULT_WEIGHTS = PickWeights()


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def build_query_text(topic: str, small_step_name: str, ss_desc_validated: str) -> str:
    query_text = f"{topic}: {small_step_name}"
    if ss_desc_validated:
        query_text += f" - {ss_desc_validated}"
    return query_text


def calculate_cosine_similarity(l2_distance: float) -> float:
    """Convert L2 distance to cosine similarity for normalized vectors."""
    return 1 - (l2_distance ** 2 / 2)


def compute_stage3_score(result: dict[str, object], weights: PickWeights = DEFAULT_WEIGHTS) -> float:
    semantic = float(result.get("semantic_score", 0.0))
    alignment = float(result.get("alignment_score", 0.0)) / 100.0

    components = [(semantic, weights.semantic)]
    if alignment > 0:
        components.append((alignment, weights.alignment))

    total_weight = sum(weight for _, weight in components)
    if total_weight <= 0:
        return semantic
    return sum(value * weight for value, weight in components) / total_weight


def compute_stage4_final_score(
    stage3_score: float,
    instruction_score_raw: float,
    weights: PickWeights = DEFAULT_WEIGHTS,
) -> float:
    instruction = max(0.0, float(instruction_score_raw)) / 100.0
    components = [(stage3_score, weights.semantic + weights.alignment)]
    if instruction > 0:
        components.append((instruction, weights.instruction))

    total_weight = sum(weight for _, weight in components)
    if total_weight <= 0:
        return stage3_score
    return sum(value * weight for value, weight in components) / total_weight


def build_stage2_shortlist(
    *,
    query_text: str,
    embedder,
    index,
    metadata: list[dict[str, object]],
    shortlist_k: int,
    deleted_videos: set[str],
    video_lookup: dict[str, dict[str, str]],
    fallback_lookup: dict[str, dict[str, str]],
    gate_evaluator: Callable[[str], tuple[bool, str]] | None = None,
) -> list[dict[str, Any]]:
    embedding = embedder.embed_query(query_text).reshape(1, -1)
    distances, indices = index.search(embedding, shortlist_k)

    video_chunks: dict[str, list[dict[str, object]]] = {}
    for dist, idx in zip(distances[0], indices[0]):
        if idx == -1 or idx >= len(metadata):
            continue

        video_meta = metadata[int(idx)]
        video_id = clean_text(video_meta.get("video_id"))
        if not video_id or video_id in deleted_videos:
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

        meta = video_lookup.get(video_id) or fallback_lookup.get(video_id) or {}
        gate_eval_text = f"{title} {evidence_text}".strip()

        if gate_evaluator is None:
            gate_pass, gate_reason = True, "PASS"
        else:
            gate_pass, gate_reason = gate_evaluator(gate_eval_text)

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


async def score_stage2_survivors_async(
    *,
    survivors: list[dict[str, Any]],
    scorer,
    age: str,
    topic: str,
    small_step_name: str,
    small_step_desc: str,
    weights: PickWeights = DEFAULT_WEIGHTS,
) -> list[dict[str, Any]]:
    if not survivors:
        return []

    video_ids = [clean_text(result.get("video_id")) for result in survivors if clean_text(result.get("video_id"))]
    if not video_ids:
        return []

    instruction_scores, alignment_scores = await asyncio.gather(
        asyncio.gather(
            *[
                scorer.score_for_curriculum_context_async(
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
                scorer.score_alignment_for_curriculum_context_async(
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
        scored_result["combined_score"] = compute_stage3_score(scored_result, weights=weights)
        scored_results.append(scored_result)

    scored_results.sort(key=lambda item: float(item.get("combined_score", 0.0)), reverse=True)
    return scored_results


async def run_pick_pipeline_async(
    *,
    query_text: str,
    age: str,
    topic: str,
    small_step_name: str,
    small_step_desc: str,
    embedder,
    index,
    metadata: list[dict[str, object]],
    scorer,
    deleted_videos: set[str],
    video_lookup: dict[str, dict[str, str]],
    fallback_lookup: dict[str, dict[str, str]],
    shortlist_k: int,
    top_k: int,
    gate_evaluator: Callable[[str], tuple[bool, str]] | None = None,
    weights: PickWeights = DEFAULT_WEIGHTS,
) -> dict[str, list[dict[str, Any]]]:
    stage2_results = build_stage2_shortlist(
        query_text=query_text,
        embedder=embedder,
        index=index,
        metadata=metadata,
        shortlist_k=shortlist_k,
        deleted_videos=deleted_videos,
        video_lookup=video_lookup,
        fallback_lookup=fallback_lookup,
        gate_evaluator=gate_evaluator,
    )

    stage2_survivors = [result for result in stage2_results if bool(result.get("gate_pass", True))]

    stage3_scored = await score_stage2_survivors_async(
        survivors=stage2_survivors,
        scorer=scorer,
        age=age,
        topic=topic,
        small_step_name=small_step_name,
        small_step_desc=small_step_desc,
        weights=weights,
    )

    enriched_survivors: list[dict[str, Any]] = []
    for result in stage3_scored:
        stage3_score = float(result.get("combined_score", 0.0))
        instruction_score = float(result.get("instruction_score", 0.0))
        final_score = compute_stage4_final_score(stage3_score, instruction_score, weights=weights)
        enriched_survivors.append(
            {
                **result,
                "stage3_score": stage3_score,
                "final_score": final_score,
                "combined_score": final_score,
            }
        )

    final_topk = sorted(enriched_survivors, key=lambda item: float(item.get("final_score", 0.0)), reverse=True)[:top_k]
    return {
        "stage2_results": stage2_results,
        "stage3_survivors": stage3_scored,
        "final_topk": final_topk,
    }


def load_validated_override_map(override_path: Path) -> dict[str, str]:
    if not override_path.exists():
        return {}

    df = pd.read_csv(override_path)
    required_cols = {"small_step_id", "ss_desc_validated"}
    if not required_cols.issubset(set(df.columns)):
        return {}

    df["small_step_id"] = df["small_step_id"].map(clean_text)
    df["ss_desc_validated"] = df["ss_desc_validated"].map(clean_text)
    df = df[df["small_step_id"].str.len() > 0].copy()
    df = df.drop_duplicates(subset=["small_step_id"], keep="last")

    return {
        row["small_step_id"]: row["ss_desc_validated"]
        for _, row in df.iterrows()
        if row["ss_desc_validated"]
    }


def resolve_validated_desc(
    *,
    small_step_id: str,
    baseline_ss_wr_desc: str,
    override_map: dict[str, str],
) -> tuple[str, str]:
    override_value = clean_text(override_map.get(clean_text(small_step_id)))
    if override_value:
        return override_value, "override"
    return clean_text(baseline_ss_wr_desc), "baseline"


def upsert_validated_override(
    *,
    override_path: Path,
    small_step_id: str,
    ss_desc_validated: str,
    source: str,
) -> None:
    override_path.parent.mkdir(parents=True, exist_ok=True)

    columns = ["updated_at", "small_step_id", "ss_desc_validated", "source"]
    if override_path.exists():
        df = pd.read_csv(override_path)
    else:
        df = pd.DataFrame(columns=columns)

    for col in columns:
        if col not in df.columns:
            df[col] = ""

    df["small_step_id"] = df["small_step_id"].map(clean_text)
    row = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "small_step_id": clean_text(small_step_id),
        "ss_desc_validated": clean_text(ss_desc_validated),
        "source": clean_text(source),
    }

    merged = pd.concat([df[columns], pd.DataFrame([row], columns=columns)], ignore_index=True)
    merged = merged[merged["small_step_id"].str.len() > 0].copy()
    merged = merged.drop_duplicates(subset=["small_step_id"], keep="last")
    merged = merged.sort_values(["small_step_id"], kind="stable")
    merged.to_csv(override_path, index=False)


def estimate_precompute_calls(total_steps: int, expected_scored_survivors_per_step: int) -> dict[str, int]:
    survivors = max(0, int(expected_scored_survivors_per_step))
    embedding_calls = max(0, int(total_steps))
    alignment_calls = embedding_calls * survivors
    instruction_calls = embedding_calls * survivors
    return {
        "embedding_calls": embedding_calls,
        "alignment_calls": alignment_calls,
        "instruction_calls": instruction_calls,
        "total_llm_calls": alignment_calls + instruction_calls,
    }
