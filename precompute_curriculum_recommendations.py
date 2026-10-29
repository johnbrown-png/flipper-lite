"""
Pre-compute all curriculum recommendations for Flipper Lite.
Runs the full FAISS + LLM system once per curriculum small step and saves results to CSV.
"""

import pandas as pd
import numpy as np
import faiss
import json
import hashlib
from pathlib import Path
from query_embedder import QueryEmbedder
from data_pipeline.instruction_quality_scorer import InstructionQualityScorer
from data_pipeline.deletion_tracker import DeletionTracker
import sys
import asyncio
import argparse

from shared.curriculum_schema import curriculum_to_long_df, build_recommendation_id
from shared.pick_engine import (
    build_query_text,
    calculate_cosine_similarity as shared_calculate_cosine_similarity,
    estimate_precompute_calls,
    load_validated_override_map,
    resolve_validated_desc,
    run_pick_pipeline_async,
)

# Add search_app to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


FAISS_PRE_AGGREGATION_CHUNKS = 20
SEMANTIC_WEIGHT = 0.55
ALIGNMENT_WEIGHT = 0.20
INSTRUCTION_WEIGHT = 0.25
CANONICAL_OVERRIDE_PATH = Path("qa/ss_desc_validated_overrides.csv")


def load_faiss_index():
    """Load FAISS index and metadata"""
    index_path = Path('data/faiss_index/faiss_index.bin')
    metadata_path = Path('data/faiss_index/faiss_index_metadata.json')
    
    index = faiss.read_index(str(index_path))
    with open(metadata_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        metadata = data['metadata']
    
    return index, metadata


def calculate_cosine_similarity(l2_distance):
    """
    Convert L2 distance to cosine similarity
    For normalized vectors: cosine_similarity = 1 - (L2_distance^2 / 2)
    """
    return shared_calculate_cosine_similarity(l2_distance)


def format_duration_hms(seconds: object) -> str:
    """Convert seconds to HH:MM:SS; returns empty string if unavailable."""
    if seconds is None or seconds == '':
        return ''
    try:
        total_seconds = int(float(seconds))
    except (TypeError, ValueError):
        return ''

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def apply_channel_diversity_cap(results: list, target_k: int = 3, quality_threshold_margin: float = 0.05):
    """
    Post-ranking channel diversity filter with fallback.
    Pass 1: Select unique channels only (up to target_k).
    Pass 2: If fewer than target_k items, allow duplicates if within quality threshold margin.
    Returns: (filtered_results, metrics_dict)
    """
    if not results or target_k <= 0:
        return results[:target_k], {"seen_channels": 0, "had_duplicates": False, "fallback_triggered": False, "num_unique_channels": 0}
    
    # Pass 1: Unique channels only
    unique_results = []
    seen_channels = set()
    duplicate_removed = False
    
    for result in results:
        channel = result.get('channel', '').strip()
        if not channel or channel not in seen_channels:
            unique_results.append(result)
            if channel:
                seen_channels.add(channel)
        else:
            duplicate_removed = True
    
    if len(unique_results) >= target_k:
        return unique_results[:target_k], {
            "seen_channels": len(seen_channels),
            "had_duplicates": duplicate_removed,
            "fallback_triggered": False,
            "num_unique_channels": len(seen_channels),
        }
    
    # Pass 2: Fallback - allow duplicates if score within threshold
    fallback_triggered = False
    current_best_score = unique_results[-1].get('combined_score', 0.0) if unique_results else 0.0
    threshold_score = current_best_score - quality_threshold_margin
    
    for result in results[len(unique_results):]:
        if len(unique_results) >= target_k:
            break
        score = result.get('combined_score', 0.0)
        if score >= threshold_score:
            unique_results.append(result)
            fallback_triggered = True
    
    return unique_results[:target_k], {
        "seen_channels": len(seen_channels),
        "had_duplicates": duplicate_removed,
        "fallback_triggered": fallback_triggered,
        "num_unique_channels": len(set(r.get('channel', '').strip() for r in unique_results if r.get('channel', '').strip())),
    }


async def search_and_score_async(query_text, age, topic, small_step, small_step_desc, 
                                  index, metadata, embedder, scorer, deleted_videos, k=5):
    """
    Perform semantic search and instruction quality scoring.
    Returns top video recommendations with scores.
    """
    # Fetch extra candidates to allow channel diversity filtering
    fetch_k = max(k + 5, int(k * 1.5))
    
    pipeline = await run_pick_pipeline_async(
        query_text=query_text,
        age=age,
        topic=topic,
        small_step_name=small_step,
        small_step_desc=small_step_desc,
        embedder=embedder,
        index=index,
        metadata=metadata,
        scorer=scorer,
        deleted_videos=deleted_videos,
        video_lookup={},
        fallback_lookup={},
        shortlist_k=FAISS_PRE_AGGREGATION_CHUNKS,
        top_k=fetch_k,
        gate_evaluator=None,
    )
    return pipeline["final_topk"]


def generate_query_embeddings(embedder, query_texts, batch_size=100):
    """Generate query embeddings in batches with per-query fallback on batch failure."""
    if not query_texts:
        return []

    effective_batch_size = max(1, int(batch_size))
    all_embeddings = []
    total = len(query_texts)

    for start in range(0, total, effective_batch_size):
        batch_queries = query_texts[start:start + effective_batch_size]
        try:
            batch_embeddings = embedder.embed_batch(batch_queries)
            if batch_embeddings.shape[0] != len(batch_queries):
                raise RuntimeError("Batch embedding count mismatch")
            all_embeddings.extend(batch_embeddings)
        except Exception as e:
            print(
                f"  ⚠ Batch embedding failed for queries {start + 1}-{start + len(batch_queries)}: {e}. "
                "Falling back to single-query embedding for this batch."
            )
            for query_text in batch_queries:
                all_embeddings.append(embedder.embed_query(query_text).reshape(-1))

    return all_embeddings


def build_run_signature(curriculum_csv_path: str, top_k: int) -> str:
    """Build a stable signature for resume compatibility checks."""
    signature_payload = {
        "curriculum_csv_path": str(Path(curriculum_csv_path).resolve()),
        "top_k": int(top_k),
        "shortlist_k": int(FAISS_PRE_AGGREGATION_CHUNKS),
        "semantic_weight": float(SEMANTIC_WEIGHT),
        "alignment_weight": float(ALIGNMENT_WEIGHT),
        "instruction_weight": float(INSTRUCTION_WEIGHT),
        "override_path": str(CANONICAL_OVERRIDE_PATH),
    }
    serialized = json.dumps(signature_payload, sort_keys=True)
    return hashlib.sha1(serialized.encode("utf-8")).hexdigest()


def load_resume_state(
    output_csv_path: str,
    run_signature: str,
    top_k: int,
    allow_legacy_resume: bool,
):
    """Load resumable state from existing output CSV, validating signature compatibility."""
    output_path = Path(output_csv_path)
    if not output_path.exists():
        return set(), 0

    existing_df = pd.read_csv(output_path)
    if existing_df.empty:
        return set(), 0

    filtered_df = existing_df
    if 'run_signature' in existing_df.columns:
        filtered_df = existing_df[existing_df['run_signature'].astype(str) == run_signature].copy()
        if filtered_df.empty:
            raise RuntimeError(
                "Existing output CSV was generated with different runtime settings. "
                "Use --no-resume to rebuild or write to a new --output path."
            )
    elif not allow_legacy_resume:
        raise RuntimeError(
            "Existing output CSV has no run_signature column. "
            "Use --allow_legacy_resume to accept legacy rows or --no-resume to rebuild."
        )

    if 'small_step_id' not in filtered_df.columns:
        return set(), len(filtered_df)

    step_counts = (
        filtered_df.assign(small_step_id=filtered_df['small_step_id'].astype(str))
        .groupby('small_step_id')
        .size()
    )
    completed_steps = {
        step_id
        for step_id, count in step_counts.items()
        if step_id and step_id.lower() != 'nan' and int(count) >= int(top_k)
    }
    return completed_steps, len(filtered_df)


async def precompute_all_recommendations_async(
    curriculum_csv_path,
    output_csv_path,
    top_k=3,
    estimate_scored_survivors=10,
    checkpoint_interval=10,
    resume=True,
    allow_legacy_resume=False,
    embedding_batch_size=100,
    min_step_num=None,
    enforce_channel_diversity=True,
):
    """
    Pre-compute recommendations for every curriculum small step.
    
    Args:
        curriculum_csv_path: Path to curriculum CSV  
        output_csv_path: Where to save precomputed recommendations
        top_k: Number of video recommendations per small step (default: 3)
    """
    print("Loading curriculum...")
    curriculum_df = curriculum_to_long_df(pd.read_csv(curriculum_csv_path))
    
    print("Loading FAISS index...")
    index, metadata = load_faiss_index()

    faiss_video_lookup = {}
    for item in metadata:
        if not isinstance(item, dict):
            continue
        video_id = item.get('video_id')
        if not video_id or video_id in faiss_video_lookup:
            continue
        faiss_video_lookup[video_id] = {
            'channel': str(item.get('channel', '') or ''),
            'duration_formatted': format_duration_hms(item.get('duration')),
        }
    
    print("Loading video inventory for channel and duration data...")
    video_inventory_path = Path('video_inventory/video_inventory.csv')
    video_lookup = {}
    if video_inventory_path.exists():
        inventory_df = pd.read_csv(video_inventory_path)
        for _, row in inventory_df.iterrows():
            video_lookup[row['video_id']] = {
                'channel': row.get('channel', ''),
                'duration_formatted': row.get('duration_formatted', '')
            }
        print(f"Loaded metadata for {len(video_lookup)} videos")
    else:
        print("⚠ Warning: video_inventory.csv not found. Channel and duration will be empty.")
    
    print("Loading deleted videos...")
    deletion_tracker = DeletionTracker()
    deleted_videos = deletion_tracker.get_deleted_video_ids()
    print(f"Found {len(deleted_videos)} deleted videos to filter out")
    
    print("Initializing embedder and scorer...")
    embedder = QueryEmbedder()
    scorer = InstructionQualityScorer()

    validated_override_map = load_validated_override_map(CANONICAL_OVERRIDE_PATH)
    print(f"Loaded {len(validated_override_map)} canonical ss_desc_validated override(s)")
    
    run_signature = build_run_signature(curriculum_csv_path, top_k)

    output_path = Path(output_csv_path)
    completed_small_step_ids = set()
    existing_rows_count = 0
    output_has_rows = False
    if resume:
        completed_small_step_ids, existing_rows_count = load_resume_state(
            output_csv_path=output_csv_path,
            run_signature=run_signature,
            top_k=top_k,
            allow_legacy_resume=allow_legacy_resume,
        )
        output_has_rows = output_path.exists() and existing_rows_count > 0
        if completed_small_step_ids:
            print(f"Resume detected {len(completed_small_step_ids)} completed small step(s) from prior run")
    else:
        if output_path.exists():
            output_path.unlink()

    pending_rows = []
    written_rows = existing_rows_count
    total_steps = len(curriculum_df)
    candidate_steps = total_steps - len(completed_small_step_ids)

    pending_step_contexts = []
    for _, row in curriculum_df.iterrows():
        small_step_id = str(row.get('small_step_id', '')).strip()
        if small_step_id in completed_small_step_ids:
            continue
        
        # Filter by min_step_num if specified
        if min_step_num is not None:
            try:
                step_num = int(row.get('small_step_num', 0))
                if step_num < min_step_num:
                    continue
            except (ValueError, TypeError):
                pass

        topic = row.get('topic', '')
        small_step = str(row.get('small_step_name', '')).strip()
        baseline_desc = str(row.get('ss_wr_desc', '')).strip()
        ss_desc_validated, ss_desc_source = resolve_validated_desc(
            small_step_id=small_step_id,
            baseline_ss_wr_desc=baseline_desc,
            override_map=validated_override_map,
        )
        query_text = build_query_text(topic=topic, small_step_name=small_step, ss_desc_validated=ss_desc_validated)
        pending_step_contexts.append(
            {
                'row': row,
                'small_step_id': small_step_id,
                'baseline_desc': baseline_desc,
                'ss_desc_validated': ss_desc_validated,
                'ss_desc_source': ss_desc_source,
                'query_text': query_text,
            }
        )

    if pending_step_contexts:
        print(
            f"Generating {len(pending_step_contexts)} query embeddings in batches of {max(1, int(embedding_batch_size))}..."
        )
        batched_embeddings = generate_query_embeddings(
            embedder=embedder,
            query_texts=[ctx['query_text'] for ctx in pending_step_contexts],
            batch_size=embedding_batch_size,
        )
        if len(batched_embeddings) != len(pending_step_contexts):
            raise RuntimeError(
                "Embedding generation count mismatch. "
                f"Expected {len(pending_step_contexts)}, received {len(batched_embeddings)}"
            )
        for idx, embedding in enumerate(batched_embeddings):
            pending_step_contexts[idx]['query_embedding'] = embedding

    def flush_checkpoint(reason: str):
        nonlocal pending_rows, written_rows, output_has_rows
        if not pending_rows:
            return

        checkpoint_df = pd.DataFrame(pending_rows)
        mode = 'a' if output_has_rows else 'w'
        checkpoint_df.to_csv(output_path, mode=mode, header=not output_has_rows, index=False)
        output_has_rows = True
        written_rows += len(checkpoint_df)
        pending_rows = []
        scorer.flush_runtime_cache()
        print(f"  💾 Checkpoint ({reason}): wrote {written_rows} total row(s)")
    
    print(f"\nProcessing {total_steps} small steps across {curriculum_df['topic'].nunique()} topics...")
    print(f"Small steps pending this run: {candidate_steps}")
    call_estimate = estimate_precompute_calls(total_steps, estimate_scored_survivors)
    print("Estimated API call volume for this run:")
    print(f"  Embedding calls:   {call_estimate['embedding_calls']}")
    print(f"  Alignment calls:   {call_estimate['alignment_calls']} (estimate)")
    print(f"  Instruction calls: {call_estimate['instruction_calls']} (estimate)")
    print(f"  Total LLM calls:   {call_estimate['total_llm_calls']} (estimate)")
    
    processed = 0
    skipped_completed = len(completed_small_step_ids)
    
    # Metrics tracking for channel diversity
    metrics = {
        "total_steps": 0,
        "top1_changed": 0,
        "dup_channels_in_top3": 0,
        "unique_channels_in_top3": 0,
        "fallback_triggered": 0,
        "candidates_examined": 0,
    }
    
    for context in pending_step_contexts:
        row = context['row']
        year = row.get('year', '')
        age = row.get('age', '')
        term = row.get('term', '')
        difficulty = row.get('difficulty', '')
        topic = row.get('topic', '')
        step_num_in_topic = int(row.get('small_step_num_in_topic', 0))
        step_num_global = int(row.get('small_step_num', 0))
        small_step_id = context['small_step_id']
        small_step_key = row.get('small_step_key', '')
        small_step = str(row.get('small_step_name', '')).strip()
        baseline_desc = context['baseline_desc']
        ss_desc_validated = context['ss_desc_validated']
        ss_desc_source = context['ss_desc_source']
        query_text = context['query_text']
        query_embedding = context['query_embedding']

        try:
            pipeline = await run_pick_pipeline_async(
                query_text=query_text,
                age=age,
                topic=topic,
                small_step_name=small_step,
                small_step_desc=ss_desc_validated,
                embedder=embedder,
                query_embedding=query_embedding,
                index=index,
                metadata=metadata,
                scorer=scorer,
                deleted_videos=deleted_videos,
                video_lookup=video_lookup,
                fallback_lookup=faiss_video_lookup,
                shortlist_k=FAISS_PRE_AGGREGATION_CHUNKS,
                top_k=int(top_k * 1.5) + 5,
                gate_evaluator=None,
            )
            raw_results = pipeline["final_topk"]
            
            # Apply channel diversity cap after scoring
            if enforce_channel_diversity and raw_results:
                results, div_metrics = apply_channel_diversity_cap(raw_results, target_k=top_k)
                metrics["total_steps"] += 1
                metrics["fallback_triggered"] += 1 if div_metrics["fallback_triggered"] else 0
                metrics["candidates_examined"] += len(raw_results)
                
                # Track top-1 changes
                if div_metrics["had_duplicates"] and results and raw_results and results[0]['video_id'] != raw_results[0]['video_id']:
                    metrics["top1_changed"] += 1
                
                # Count duplicate channels in final results
                channels_in_final = [r.get('channel', '').strip() for r in results]
                if len(channels_in_final) != len(set(channels_in_final)):
                    metrics["dup_channels_in_top3"] += 1
                metrics["unique_channels_in_top3"] += div_metrics["num_unique_channels"]
            else:
                results = raw_results[:top_k]

            for rank, video_result in enumerate(results, 1):
                video_id = video_result['video_id']

                video_meta = video_lookup.get(video_id, {})
                fallback_meta = faiss_video_lookup.get(video_id, {})
                channel = video_meta.get('channel', '') or fallback_meta.get('channel', '')
                duration = video_meta.get('duration_formatted', '') or fallback_meta.get('duration_formatted', '')

                pending_rows.append({
                    'year': year,
                    'age': age,
                    'term': term,
                    'difficulty': difficulty,
                    'topic': topic,
                    'small_step_num': step_num_in_topic,
                    'small_step_num_in_topic': step_num_in_topic,
                    'small_step_num_global': step_num_global,
                    'small_step': small_step,
                    'small_step_name': small_step,
                    'small_step_desc': baseline_desc,
                    'ss_wr_desc': baseline_desc,
                    'ss_desc_validated': ss_desc_validated,
                    'ss_desc_validated_source': ss_desc_source,
                    'small_step_id': small_step_id,
                    'small_step_key': small_step_key,
                    'rank': rank,
                    'recommendation_num': rank,
                    'recommendation_id': build_recommendation_id(small_step_id, rank),
                    'video_id': video_id,
                    'title': video_result['title'],
                    'video_title': video_result['title'],
                    'channel': channel,
                    'duration': duration,
                    'duration_formatted': duration,
                    'semantic_score': round(video_result['semantic_score'], 4),
                    'alignment_score': round(video_result.get('alignment_score', 0.0), 2),
                    'instruction_score': round(video_result['instruction_score'], 2),
                    'combined_score': round(video_result['combined_score'], 4),
                    'alignment_justification': video_result.get('alignment_justification', ''),
                    'instruction_justification': video_result['instruction_justification'],
                    'run_signature': run_signature,
                })

            processed += 1
            if processed % 10 == 0:
                print(f"  Processed {processed}/{candidate_steps} pending small steps...")

            if processed % max(1, int(checkpoint_interval)) == 0:
                flush_checkpoint(reason=f"every {checkpoint_interval} steps")

        except Exception as e:
            print(f"  ⚠ Error processing {topic} - Step {step_num_in_topic}: {e}")
            continue
    
    flush_checkpoint(reason="final")
    scorer.flush_runtime_cache()

    # Print channel diversity metrics
    if enforce_channel_diversity and metrics["total_steps"] > 0:
        print(f"\n📊 Channel Diversity Metrics:")
        print(f"  Steps processed: {metrics['total_steps']}")
        print(f"  Top-1 changed: {metrics['top1_changed']} ({metrics['top1_changed']/metrics['total_steps']*100:.1f}%)")
        print(f"  Steps with dup channels in final top-3: {metrics['dup_channels_in_top3']} ({metrics['dup_channels_in_top3']/metrics['total_steps']*100:.1f}%)")
        if metrics["total_steps"] > 0:
            avg_unique = metrics['unique_channels_in_top3'] / metrics['total_steps']
            print(f"  Avg unique channels per step: {avg_unique:.2f} out of 3")
        print(f"  Fallback to duplicates triggered: {metrics['fallback_triggered']} steps")
        print(f"  Avg candidates examined per step: {metrics['candidates_examined'] / metrics['total_steps']:.1f}")

    print(f"\nSaving precomputed recommendations to {output_csv_path}...")
    print(f"  Resume-skipped small steps: {skipped_completed}")
    print(f"\n✅ Complete! Precomputed {written_rows} total video recommendations in output.")
    print(f"   Output: {output_csv_path}")
    csv_path = Path(output_csv_path)
    if csv_path.exists():
        size_mb = csv_path.stat().st_size / 1024 / 1024
        print(f"   CSV size: {size_mb:.2f} MB")
        try:
            results_df = pd.read_csv(csv_path, on_bad_lines='skip', engine='python')

            if len(results_df) > 0 and 'video_id' in results_df.columns:
                non_empty = results_df[results_df['video_id'].fillna('').astype(str).str.len() > 0]
                print(f"   Recommendations with videos: {len(non_empty)}/{len(results_df)} ({len(non_empty)/len(results_df)*100:.1f}%)")
            else:
                print(f"   ⚠ Warning: No recommendations generated or video_id column missing")
        except Exception as e:
            print(f"   ⚠ Verification skipped (CSV read error): {str(e)[:100]}")


def precompute_all_recommendations(
    curriculum_csv_path,
    output_csv_path,
    top_k=3,
    estimate_scored_survivors=10,
    checkpoint_interval=10,
    resume=True,
    allow_legacy_resume=False,
    embedding_batch_size=100,
    enforce_channel_diversity=True,
    min_step_num=None,
):
    return asyncio.run(
        precompute_all_recommendations_async(
            curriculum_csv_path=curriculum_csv_path,
            output_csv_path=output_csv_path,
            top_k=top_k,
            estimate_scored_survivors=estimate_scored_survivors,
            checkpoint_interval=checkpoint_interval,
            resume=resume,
            allow_legacy_resume=allow_legacy_resume,
            embedding_batch_size=embedding_batch_size,
            enforce_channel_diversity=enforce_channel_diversity,
            min_step_num=min_step_num,
        )
    )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Pre-compute curriculum recommendations for Flipper Lite')
    parser.add_argument('--curriculum', default='Curriculum/Maths/curriculum_08052026_small_steps.csv', help='Path to curriculum CSV file (default: curriculum_08052026_small_steps.csv)')
    parser.add_argument('--output', default='precomputed_recommendations_flat.csv', help='Path to output CSV file (default: precomputed_recommendations_flat.csv)')
    parser.add_argument('--top_k', type=int, default=3, help='Number of top video recommendations per small step (default: 3)')
    parser.add_argument('--estimate_scored_survivors', type=int, default=10, help='Expected Stage 2 survivors scored per step for API-call estimate (default: 10)')
    parser.add_argument('--checkpoint_interval', type=int, default=10, help='Checkpoint CSV write interval in processed small steps (default: 10)')
    parser.add_argument('--embedding_batch_size', type=int, default=100, help='Batch size for query embedding API calls during precompute (default: 100)')
    parser.add_argument('--resume', dest='resume', action='store_true', default=True, help='Resume from existing output CSV when signatures are compatible (default: on)')
    parser.add_argument('--no-resume', dest='resume', action='store_false', help='Disable resume and rebuild output from scratch')
    parser.add_argument('--allow_legacy_resume', action='store_true', help='Allow resume from legacy output CSVs without run_signature column')
    parser.add_argument('--enforce_channel_diversity', dest='enforce_channel_diversity', action='store_true', default=True, help='Enforce max 1 video per channel in top-k results (default: on)')
    parser.add_argument('--no-enforce_channel_diversity', dest='enforce_channel_diversity', action='store_false', help='Disable channel diversity enforcement')
    parser.add_argument('--min_step_num', type=int, default=None, help='Only process small steps with step_num >= min_step_num (e.g., 623 to resume from step 623)')
    args = parser.parse_args()

    precompute_all_recommendations(
        curriculum_csv_path=args.curriculum,
        output_csv_path=args.output,
        top_k=args.top_k,
        estimate_scored_survivors=args.estimate_scored_survivors,
        checkpoint_interval=args.checkpoint_interval,
        resume=args.resume,
        allow_legacy_resume=args.allow_legacy_resume,
        embedding_batch_size=args.embedding_batch_size,
        enforce_channel_diversity=args.enforce_channel_diversity,
        min_step_num=args.min_step_num,
    )
