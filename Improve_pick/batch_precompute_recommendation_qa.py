"""Run targeted QA experiments for selected curriculum small steps."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from pathlib import Path
import sys

import pandas as pd

# Ensure imports work when script is launched from Improve_pick/
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from precompute_curriculum_recommendations import load_faiss_index, search_and_score_async
from query_embedder import QueryEmbedder
from data_pipeline.deletion_tracker import DeletionTracker
from data_pipeline.instruction_quality_scorer import InstructionQualityScorer
from shared.curriculum_schema import curriculum_to_long_df, enrich_precomputed_with_curriculum
from shared.qa_registry import DEFAULT_EXCEPTION_REGISTRY_PATH, get_allowed_incomplete_recommendation_ids


DEFAULT_TARGETS_PATH = project_root / 'qa' / 'targeted_ss_wr_desc_overrides.csv'
DEFAULT_OUTPUT_DIR = project_root / 'qa' / 'outputs'


def clean_text(value: object) -> str:
    if value is None:
        return ''
    text = str(value).strip()
    return '' if text.lower() == 'nan' else text


def is_active_target(value: object) -> bool:
    status = clean_text(value).lower()
    return status in {'', 'active', 'true', '1', 'yes'}


def build_query_text(topic: str, small_step_name: str, ss_wr_desc: str) -> str:
    query_text = f'{topic}: {small_step_name}'
    if ss_wr_desc:
        query_text += f' - {ss_wr_desc}'
    return query_text


def load_video_lookup() -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    video_inventory_path = project_root / 'video_inventory.csv'
    if not video_inventory_path.exists():
        return lookup

    inventory_df = pd.read_csv(video_inventory_path)
    for _, row in inventory_df.iterrows():
        video_id = clean_text(row.get('video_id'))
        if not video_id:
            continue
        lookup[video_id] = {
            'channel': clean_text(row.get('channel')),
            'duration_formatted': clean_text(row.get('duration_formatted')),
        }
    return lookup


def format_duration_hms(seconds: object) -> str:
    if seconds is None or seconds == '':
        return ''
    try:
        total_seconds = int(float(seconds))
    except (TypeError, ValueError):
        return ''
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f'{hours:02d}:{minutes:02d}:{secs:02d}'


def build_faiss_video_lookup(metadata: list[dict[str, object]]) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for item in metadata:
        video_id = clean_text(item.get('video_id'))
        if not video_id or video_id in lookup:
            continue
        lookup[video_id] = {
            'channel': clean_text(item.get('channel')),
            'duration_formatted': format_duration_hms(item.get('duration')),
        }
    return lookup


def load_targets(path: str | Path) -> pd.DataFrame:
    targets_path = Path(path)
    if not targets_path.exists():
        raise FileNotFoundError(f'Target file not found: {targets_path}')

    targets_df = pd.read_csv(targets_path)
    if 'small_step_id' not in targets_df.columns:
        raise ValueError(f'Target file is missing required column: small_step_id ({targets_path})')

    for column in ['scenario_label', 'candidate_ss_wr_desc', 'status', 'notes']:
        if column not in targets_df.columns:
            targets_df[column] = ''

    targets_df['small_step_id'] = targets_df['small_step_id'].map(clean_text)
    targets_df['scenario_label'] = targets_df['scenario_label'].map(clean_text)
    targets_df['candidate_ss_wr_desc'] = targets_df['candidate_ss_wr_desc'].map(clean_text)
    targets_df['status'] = targets_df['status'].map(clean_text)
    targets_df['notes'] = targets_df['notes'].map(clean_text)

    targets_df = targets_df[targets_df['small_step_id'].str.len() > 0].copy()
    targets_df = targets_df[targets_df['status'].map(is_active_target)].copy()
    return targets_df


def build_detailed_rows(
    row: pd.Series,
    scenario_label: str,
    candidate_ss_wr_desc: str,
    baseline_rows: pd.DataFrame,
    candidate_results: list[dict[str, object]],
    video_lookup: dict[str, dict[str, str]],
    fallback_lookup: dict[str, dict[str, str]],
) -> list[dict[str, object]]:
    detailed_rows: list[dict[str, object]] = []

    baseline_rows = baseline_rows.sort_values('recommendation_num', kind='stable')
    for _, baseline in baseline_rows.iterrows():
        detailed_rows.append({
            'small_step_id': row['small_step_id'],
            'small_step_key': row['small_step_key'],
            'small_step_num_global': row['small_step_num'],
            'small_step_num_in_topic': row['small_step_num_in_topic'],
            'year': row['year'],
            'age': row['age'],
            'term': row['term'],
            'difficulty': row['difficulty'],
            'topic': row['topic'],
            'small_step_name': row['small_step_name'],
            'baseline_ss_wr_desc': row['ss_wr_desc'],
            'candidate_ss_wr_desc': candidate_ss_wr_desc,
            'scenario_label': scenario_label,
            'result_set': 'baseline',
            'recommendation_num': int(baseline.get('recommendation_num', baseline.get('rank', 0))),
            'video_id': clean_text(baseline.get('video_id')),
            'title': clean_text(baseline.get('title', baseline.get('video_title'))),
            'channel': clean_text(baseline.get('channel')),
            'duration_formatted': clean_text(baseline.get('duration_formatted', baseline.get('duration'))),
            'semantic_score': baseline.get('semantic_score'),
            'instruction_score': baseline.get('instruction_score'),
            'combined_score': baseline.get('combined_score'),
            'instruction_justification': clean_text(baseline.get('instruction_justification')),
        })

    for rank, result in enumerate(candidate_results, 1):
        video_id = clean_text(result.get('video_id'))
        video_meta = video_lookup.get(video_id, {})
        if not video_meta:
            video_meta = fallback_lookup.get(video_id, {})
        detailed_rows.append({
            'small_step_id': row['small_step_id'],
            'small_step_key': row['small_step_key'],
            'small_step_num_global': row['small_step_num'],
            'small_step_num_in_topic': row['small_step_num_in_topic'],
            'year': row['year'],
            'age': row['age'],
            'term': row['term'],
            'difficulty': row['difficulty'],
            'topic': row['topic'],
            'small_step_name': row['small_step_name'],
            'baseline_ss_wr_desc': row['ss_wr_desc'],
            'candidate_ss_wr_desc': candidate_ss_wr_desc,
            'scenario_label': scenario_label,
            'result_set': 'candidate',
            'recommendation_num': rank,
            'video_id': video_id,
            'title': clean_text(result.get('title')),
            'channel': clean_text(video_meta.get('channel')),
            'duration_formatted': clean_text(video_meta.get('duration_formatted')),
            'semantic_score': round(float(result.get('semantic_score', 0.0)), 4),
            'instruction_score': round(float(result.get('instruction_score', 0.0)), 2),
            'combined_score': round(float(result.get('combined_score', 0.0)), 4),
            'instruction_justification': clean_text(result.get('instruction_justification')),
        })

    return detailed_rows


def build_summary_row(
    row: pd.Series,
    scenario_label: str,
    candidate_ss_wr_desc: str,
    baseline_rows: pd.DataFrame,
    candidate_results: list[dict[str, object]],
    notes: str,
    allowed_incomplete_ids: set[str],
) -> dict[str, object]:
    baseline_rows = baseline_rows.sort_values('recommendation_num', kind='stable')
    baseline_video_ids = [clean_text(video_id) for video_id in baseline_rows['video_id'].tolist() if clean_text(video_id)]
    candidate_video_ids = [clean_text(result.get('video_id')) for result in candidate_results if clean_text(result.get('video_id'))]
    overlap_ids = sorted(set(baseline_video_ids) & set(candidate_video_ids))

    baseline_top = baseline_rows.iloc[0] if not baseline_rows.empty else None
    candidate_top = candidate_results[0] if candidate_results else None

    return {
        'small_step_id': row['small_step_id'],
        'small_step_key': row['small_step_key'],
        'small_step_num_global': row['small_step_num'],
        'small_step_num_in_topic': row['small_step_num_in_topic'],
        'year': row['year'],
        'age': row['age'],
        'term': row['term'],
        'difficulty': row['difficulty'],
        'topic': row['topic'],
        'small_step_name': row['small_step_name'],
        'scenario_label': scenario_label,
        'baseline_ss_wr_desc': row['ss_wr_desc'],
        'candidate_ss_wr_desc': candidate_ss_wr_desc,
        'is_registered_exception': row['small_step_id'] in allowed_incomplete_ids,
        'baseline_count': len(baseline_rows),
        'candidate_count': len(candidate_results),
        'overlap_video_count': len(overlap_ids),
        'overlap_video_ids': ' | '.join(overlap_ids),
        'baseline_top_video_id': clean_text(baseline_top.get('video_id')) if baseline_top is not None else '',
        'baseline_top_title': clean_text(baseline_top.get('title', baseline_top.get('video_title'))) if baseline_top is not None else '',
        'baseline_top_score': baseline_top.get('combined_score') if baseline_top is not None else None,
        'candidate_top_video_id': clean_text(candidate_top.get('video_id')) if candidate_top is not None else '',
        'candidate_top_title': clean_text(candidate_top.get('title')) if candidate_top is not None else '',
        'candidate_top_score': round(float(candidate_top.get('combined_score', 0.0)), 4) if candidate_top is not None else None,
        'top_video_changed': (
            clean_text(baseline_top.get('video_id')) != clean_text(candidate_top.get('video_id'))
            if baseline_top is not None and candidate_top is not None
            else False
        ),
        'notes': notes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='Run targeted QA experiments for selected curriculum steps')
    parser.add_argument(
        '--curriculum',
        default=str(project_root / 'Curriculum' / 'Maths' / 'curriculum_22032026_small_steps.csv'),
        help='Path to long curriculum CSV or legacy curriculum CSV',
    )
    parser.add_argument(
        '--precomputed',
        default=str(project_root / 'precomputed_recommendations_flat.csv'),
        help='Path to precomputed recommendations CSV',
    )
    parser.add_argument(
        '--targets',
        default=str(DEFAULT_TARGETS_PATH),
        help='Path to target override CSV',
    )
    parser.add_argument(
        '--output-dir',
        default=str(DEFAULT_OUTPUT_DIR),
        help='Directory for detailed and summary CSV outputs',
    )
    parser.add_argument(
        '--top-k',
        type=int,
        default=3,
        help='Number of candidate recommendations to generate per target',
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=0,
        help='Optional limit on number of active target rows to process',
    )
    parser.add_argument(
        '--exception-registry',
        default=str(DEFAULT_EXCEPTION_REGISTRY_PATH),
        help='Path to QA exception registry CSV',
    )
    args = parser.parse_args()

    curriculum_df = curriculum_to_long_df(pd.read_csv(args.curriculum))
    precomputed_df = enrich_precomputed_with_curriculum(pd.read_csv(args.precomputed), curriculum_df)
    targets_df = load_targets(args.targets)

    if args.limit > 0:
        targets_df = targets_df.head(args.limit).copy()

    if targets_df.empty:
        raise SystemExit('No active target rows found in target override CSV.')

    curriculum_columns = [
        'small_step_id',
        'small_step_key',
        'small_step_num',
        'small_step_num_in_topic',
        'year',
        'age',
        'term',
        'difficulty',
        'topic',
        'small_step_name',
        'ss_wr_desc',
    ]
    target_steps = targets_df.merge(
        curriculum_df[curriculum_columns],
        on='small_step_id',
        how='left',
        validate='many_to_one',
    )

    unresolved_ids = sorted(target_steps[target_steps['small_step_name'].isna()]['small_step_id'].unique().tolist())
    if unresolved_ids:
        sample = ', '.join(unresolved_ids[:5])
        raise SystemExit(f'{len(unresolved_ids)} target small_step_id values were not found in curriculum. Sample: {sample}')

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print('Loading FAISS index...')
    index, metadata = load_faiss_index()
    fallback_lookup = build_faiss_video_lookup(metadata)
    print('Loading video inventory...')
    video_lookup = load_video_lookup()
    print('Loading deleted video registry...')
    deleted_videos = DeletionTracker().get_deleted_video_ids()
    print('Initializing embedder and scorer...')
    embedder = QueryEmbedder()
    scorer = InstructionQualityScorer()

    allowed_incomplete_ids = get_allowed_incomplete_recommendation_ids(args.exception_registry)

    detailed_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []

    total = len(target_steps)
    print(f'Processing {total} targeted QA scenarios...')

    for index_num, (_, row) in enumerate(target_steps.iterrows(), 1):
        scenario_label = clean_text(row.get('scenario_label')) or 'candidate'
        candidate_ss_wr_desc = clean_text(row.get('candidate_ss_wr_desc')) or clean_text(row.get('ss_wr_desc'))
        notes = clean_text(row.get('notes'))
        baseline_rows = precomputed_df[precomputed_df['small_step_id'] == row['small_step_id']].copy()
        query_text = build_query_text(
            topic=clean_text(row.get('topic')),
            small_step_name=clean_text(row.get('small_step_name')),
            ss_wr_desc=candidate_ss_wr_desc,
        )

        candidate_results = asyncio.run(
            search_and_score_async(
                query_text=query_text,
                age=clean_text(row.get('age')),
                topic=clean_text(row.get('topic')),
                small_step=clean_text(row.get('small_step_name')),
                small_step_desc=candidate_ss_wr_desc,
                index=index,
                metadata=metadata,
                embedder=embedder,
                scorer=scorer,
                deleted_videos=deleted_videos,
                k=args.top_k,
            )
        )

        detailed_rows.extend(
            build_detailed_rows(
                row=row,
                scenario_label=scenario_label,
                candidate_ss_wr_desc=candidate_ss_wr_desc,
                baseline_rows=baseline_rows,
                candidate_results=candidate_results,
                video_lookup=video_lookup,
                fallback_lookup=fallback_lookup,
            )
        )
        summary_rows.append(
            build_summary_row(
                row=row,
                scenario_label=scenario_label,
                candidate_ss_wr_desc=candidate_ss_wr_desc,
                baseline_rows=baseline_rows,
                candidate_results=candidate_results,
                notes=notes,
                allowed_incomplete_ids=allowed_incomplete_ids,
            )
        )

        print(f'  Processed {index_num}/{total}: {row["small_step_id"]}')

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    summary_path = output_dir / f'targeted_precompute_qa_summary_{timestamp}.csv'
    detail_path = output_dir / f'targeted_precompute_qa_detailed_{timestamp}.csv'

    pd.DataFrame(summary_rows).to_csv(summary_path, index=False)
    pd.DataFrame(detailed_rows).to_csv(detail_path, index=False)

    print('Targeted QA run complete.')
    print(f'Summary output: {summary_path}')
    print(f'Detailed output: {detail_path}')


if __name__ == '__main__':
    main()
