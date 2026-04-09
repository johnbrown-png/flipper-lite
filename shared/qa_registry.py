"""Helpers for QA exception and target registry files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


DEFAULT_EXCEPTION_REGISTRY_PATH = Path('qa/recommendation_exception_registry.csv')


def _clean_text(value: object) -> str:
    if value is None:
        return ''
    text = str(value).strip()
    if text.lower() == 'nan':
        return ''
    return text


def load_exception_registry(path: str | Path = DEFAULT_EXCEPTION_REGISTRY_PATH) -> pd.DataFrame:
    """Load the QA exception registry if it exists."""
    registry_path = Path(path)
    if not registry_path.exists():
        return pd.DataFrame(columns=['small_step_id', 'exception_type', 'status'])

    registry_df = pd.read_csv(registry_path)
    registry_df.columns = [str(column).strip() for column in registry_df.columns]

    if 'small_step_id' not in registry_df.columns:
        raise ValueError(f'Exception registry is missing required column: small_step_id ({registry_path})')

    if 'exception_type' not in registry_df.columns:
        registry_df['exception_type'] = ''
    if 'status' not in registry_df.columns:
        registry_df['status'] = 'active'

    registry_df['small_step_id'] = registry_df['small_step_id'].map(_clean_text)
    registry_df['exception_type'] = registry_df['exception_type'].map(_clean_text)
    registry_df['status'] = registry_df['status'].map(_clean_text).str.lower()

    return registry_df[registry_df['small_step_id'].str.len() > 0].copy()


def get_allowed_incomplete_recommendation_ids(
    path: str | Path = DEFAULT_EXCEPTION_REGISTRY_PATH,
) -> set[str]:
    """Return small_step_id values allowed to have fewer than the target recommendation count."""
    registry_df = load_exception_registry(path)
    if registry_df.empty:
        return set()

    allowed_rows = registry_df[
        (registry_df['exception_type'].str.lower() == 'incomplete_recommendations')
        & (registry_df['status'].isin({'active', 'accepted', 'allow'}))
    ]
    return set(allowed_rows['small_step_id'])