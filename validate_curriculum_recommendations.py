"""Validate curriculum and recommendation schema alignment."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from shared.curriculum_schema import curriculum_to_long_df, enrich_precomputed_with_curriculum
from shared.qa_registry import DEFAULT_EXCEPTION_REGISTRY_PATH, get_allowed_incomplete_recommendation_ids


def validate_sequences(curriculum_df: pd.DataFrame) -> list[str]:
    errors: list[str] = []

    expected_global = list(range(1, len(curriculum_df) + 1))
    actual_global = curriculum_df['small_step_num'].tolist()
    if actual_global != expected_global:
        errors.append('Curriculum small_step_num is not sequential across the full curriculum.')

    for topic_key, topic_df in curriculum_df.groupby(['year', 'term', 'difficulty', 'topic'], dropna=False):
        topic_df = topic_df.sort_values('small_step_num_in_topic', kind='stable')
        expected_topic = list(range(1, len(topic_df) + 1))
        actual_topic = topic_df['small_step_num_in_topic'].tolist()
        if actual_topic != expected_topic:
            errors.append(
                f"small_step_num_in_topic is not sequential for topic {topic_key}."
            )

    if curriculum_df['small_step_id'].duplicated().any():
        errors.append('Curriculum small_step_id values are not unique.')
    if curriculum_df['small_step_key'].duplicated().any():
        errors.append('Curriculum small_step_key values are not unique.')

    return errors


def validate_recommendations(
    curriculum_df: pd.DataFrame,
    precomputed_df: pd.DataFrame,
    expected_per_step: int,
    require_all_steps: bool,
    allow_incomplete_recommendations: bool,
    allowed_incomplete_ids: set[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    allowed_incomplete_ids = allowed_incomplete_ids or set()

    curriculum_ids = set(curriculum_df['small_step_id'])
    recommendation_ids = set(precomputed_df['small_step_id'])

    extra_ids = sorted(recommendation_ids - curriculum_ids)
    if extra_ids:
        errors.append(f'Recommendations contain {len(extra_ids)} small_step_id values not present in curriculum.')

    if require_all_steps:
        missing_ids = sorted((curriculum_ids - recommendation_ids) - allowed_incomplete_ids)
        if missing_ids:
            errors.append(f'Recommendations are missing {len(missing_ids)} curriculum small_step_id values.')

    counts = precomputed_df.groupby('small_step_id').size()
    if allow_incomplete_recommendations:
        invalid_counts = counts[counts > expected_per_step]
    else:
        invalid_too_many = counts[counts > expected_per_step]
        invalid_too_few = counts[
            (counts < expected_per_step) & (~counts.index.isin(allowed_incomplete_ids))
        ]
        invalid_counts = pd.concat([invalid_too_many, invalid_too_few]).sort_index()
    if not invalid_counts.empty:
        sample = ', '.join(f"{step_id}={count}" for step_id, count in invalid_counts.head(5).items())
        if allow_incomplete_recommendations:
            errors.append(
                f'Recommendation row counts exceed {expected_per_step} for some small steps. Sample: {sample}'
            )
        else:
            errors.append(
                f'Recommendation row counts are not exactly {expected_per_step} for all small steps. Sample: {sample}'
            )

    for step_id, step_df in precomputed_df.groupby('small_step_id'):
        expected_ranks = list(range(1, len(step_df) + 1))
        actual_ranks = sorted(step_df['recommendation_num'].astype(int).tolist())
        if actual_ranks != expected_ranks:
            errors.append(f'Recommendation ranks are not sequential for {step_id}.')
            break

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description='Validate curriculum and recommendation alignment')
    parser.add_argument(
        '--curriculum',
        default='Curriculum/Maths/curriculum_22032026_small_steps.csv',
        help='Path to the long curriculum CSV or a legacy curriculum CSV',
    )
    parser.add_argument(
        '--precomputed',
        default='precomputed_recommendations_flat.csv',
        help='Path to the precomputed recommendations CSV',
    )
    parser.add_argument(
        '--expected-per-step',
        type=int,
        default=3,
        help='Expected recommendation row count per small step',
    )
    parser.add_argument(
        '--allow-missing-steps',
        action='store_true',
        help='Allow curriculum steps with no matching recommendations',
    )
    parser.add_argument(
        '--allow-incomplete-recommendations',
        action='store_true',
        help='Allow groups with fewer than the expected recommendation count',
    )
    parser.add_argument(
        '--exception-registry',
        default=str(DEFAULT_EXCEPTION_REGISTRY_PATH),
        help='Path to QA exception registry CSV for accepted short groups',
    )
    parser.add_argument(
        '--ignore-exception-registry',
        action='store_true',
        help='Ignore the exception registry and validate all short groups strictly',
    )
    args = parser.parse_args()

    curriculum_path = Path(args.curriculum)
    precomputed_path = Path(args.precomputed)
    allowed_incomplete_ids: set[str] = set()
    if not args.ignore_exception_registry and not args.allow_incomplete_recommendations:
        allowed_incomplete_ids = get_allowed_incomplete_recommendation_ids(args.exception_registry)

    curriculum_df = curriculum_to_long_df(pd.read_csv(curriculum_path))
    precomputed_df = enrich_precomputed_with_curriculum(pd.read_csv(precomputed_path), curriculum_df)

    errors = []
    errors.extend(validate_sequences(curriculum_df))
    errors.extend(
        validate_recommendations(
            curriculum_df=curriculum_df,
            precomputed_df=precomputed_df,
            expected_per_step=args.expected_per_step,
            require_all_steps=not args.allow_missing_steps,
            allow_incomplete_recommendations=args.allow_incomplete_recommendations,
            allowed_incomplete_ids=allowed_incomplete_ids,
        )
    )

    if errors:
        print('Validation failed:')
        for error in errors:
            print(f'- {error}')
        raise SystemExit(1)

    print('Validation passed.')
    print(f'Curriculum small steps: {len(curriculum_df)}')
    print(f'Recommendation rows: {len(precomputed_df)}')
    if allowed_incomplete_ids:
        print(f'Accepted incomplete groups from registry: {len(allowed_incomplete_ids)}')


if __name__ == '__main__':
    main()