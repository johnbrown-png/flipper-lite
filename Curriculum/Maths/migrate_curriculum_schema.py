"""Add compatibility identifiers to curriculum and recommendation CSVs."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from shared.curriculum_schema import (
    add_identifier_columns_to_wide_curriculum,
    curriculum_to_long_df,
    enrich_precomputed_with_curriculum,
)


def reorder_columns(original_columns: list[str], df: pd.DataFrame) -> pd.DataFrame:
    """Keep existing columns first and append any additive columns to the end."""
    additive_columns = [column for column in df.columns if column not in original_columns]
    return df[original_columns + additive_columns]


def migrate_schema(
    curriculum_path: Path,
    precomputed_path: Path,
    long_curriculum_output_path: Path,
) -> None:
    curriculum_df = pd.read_csv(curriculum_path)
    original_curriculum_columns = curriculum_df.columns.tolist()

    migrated_wide_curriculum = add_identifier_columns_to_wide_curriculum(curriculum_df)
    migrated_wide_curriculum = reorder_columns(original_curriculum_columns, migrated_wide_curriculum)
    migrated_wide_curriculum.to_csv(curriculum_path, index=False)

    curriculum_long_df = curriculum_to_long_df(curriculum_df)
    curriculum_long_df.to_csv(long_curriculum_output_path, index=False)

    precomputed_df = pd.read_csv(precomputed_path)
    original_precomputed_columns = precomputed_df.columns.tolist()
    migrated_precomputed = enrich_precomputed_with_curriculum(precomputed_df, curriculum_long_df)
    migrated_precomputed = reorder_columns(original_precomputed_columns, migrated_precomputed)
    migrated_precomputed.to_csv(precomputed_path, index=False)

    print(f"Updated wide curriculum: {curriculum_path}")
    print(f"Wrote long curriculum: {long_curriculum_output_path}")
    print(f"Updated precomputed recommendations: {precomputed_path}")
    print(f"Canonical small steps: {len(curriculum_long_df)}")
    print(f"Recommendation rows: {len(migrated_precomputed)}")


def main() -> None:
    parser = argparse.ArgumentParser(description='Add additive migration columns for curriculum compatibility')
    parser.add_argument(
        '--curriculum',
        default='Curriculum/Maths/curriculum_22032026.csv',
        help='Path to the legacy or current curriculum CSV',
    )
    parser.add_argument(
        '--precomputed',
        default='precomputed_recommendations_flat.csv',
        help='Path to the precomputed recommendations CSV',
    )
    parser.add_argument(
        '--long-output',
        default='Curriculum/Maths/curriculum_22032026_small_steps.csv',
        help='Path for the one-row-per-small-step curriculum CSV',
    )
    args = parser.parse_args()

    migrate_schema(
        curriculum_path=Path(args.curriculum),
        precomputed_path=Path(args.precomputed),
        long_curriculum_output_path=Path(args.long_output),
    )


if __name__ == '__main__':
    main()