"""Clean known small_step_name prefix artifacts in canonical curriculum CSV.

Scope is intentionally narrow for safety:
- Year 7-10
- Summer term

Artifact rules:
1) Remove leading quote artifacts like '"" ', '""0 ', '"1 '
2) Remove leading numeric index only when it matches small_step_num_in_topic,
   e.g. '7 Explore higher powers...' where step_num_in_topic is 7

For each changed row, recompute small_step_id and small_step_key using shared schema helpers.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import re
import shutil

import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from shared.curriculum_schema import build_small_step_id, build_small_step_key


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def parse_year_number(value: object) -> int | None:
    match = re.search(r"(\d+)", clean_text(value))
    if not match:
        return None
    return int(match.group(1))


def in_target_scope(row: pd.Series) -> bool:
    year_num = parse_year_number(row.get("year"))
    term = clean_text(row.get("term")).lower()
    return year_num is not None and 7 <= year_num <= 10 and term == "summer"


def normalize_step_name(name: object, step_num_in_topic: object) -> str:
    text = clean_text(name)

    # Remove leading quote artifacts and quote+index artifacts.
    # Examples: '"" Simplify...', '""0 Parallel...', '"1 Something...'
    text = re.sub(r'^\s*"{1,2}\s*\d*\s*', '', text)

    # Remove a leading numeric index only when it equals step_num_in_topic.
    # Example: '7 Explore...' for step_num_in_topic=7
    step_num = clean_text(step_num_in_topic)
    match = re.match(r'^(\d+)\s+(.+)$', text)
    if match and step_num and match.group(1) == step_num:
        text = match.group(2).strip()

    return text.strip()


def recompute_ids(df: pd.DataFrame, idx: int) -> None:
    row = df.loc[idx]
    df.at[idx, "small_step_id"] = build_small_step_id(
        row.get("year"),
        row.get("age"),
        row.get("term"),
        row.get("difficulty"),
        row.get("topic"),
        row.get("small_step_num_in_topic"),
        row.get("small_step_name"),
    )
    df.at[idx, "small_step_key"] = build_small_step_key(
        row.get("year"),
        row.get("age"),
        row.get("term"),
        row.get("difficulty"),
        row.get("topic"),
        row.get("small_step_num_in_topic"),
        row.get("small_step_name"),
    )


def run(canonical_path: Path, preview_path: Path | None, apply_changes: bool) -> None:
    df = pd.read_csv(canonical_path)

    changed_rows: list[dict[str, object]] = []

    for idx, row in df.iterrows():
        if not in_target_scope(row):
            continue

        old_name = clean_text(row.get("small_step_name"))
        new_name = normalize_step_name(old_name, row.get("small_step_num_in_topic"))

        if new_name and new_name != old_name:
            df.at[idx, "small_step_name"] = new_name
            recompute_ids(df, idx)
            changed_rows.append(
                {
                    "row_index": idx,
                    "small_step_num": clean_text(row.get("small_step_num")),
                    "year": clean_text(row.get("year")),
                    "term": clean_text(row.get("term")),
                    "difficulty": clean_text(row.get("difficulty")),
                    "block": clean_text(row.get("block")),
                    "small_step_num_in_topic": clean_text(row.get("small_step_num_in_topic")),
                    "old_small_step_name": old_name,
                    "new_small_step_name": new_name,
                }
            )

    changes_df = pd.DataFrame(changed_rows)

    if preview_path:
        changes_df.to_csv(preview_path, index=False)

    if apply_changes:
        backup_path = canonical_path.with_name(
            f"{canonical_path.stem}.backup_before_name_cleanup_{datetime.now().strftime('%Y%m%d_%H%M%S')}{canonical_path.suffix}"
        )
        shutil.copy2(canonical_path, backup_path)
        df.to_csv(canonical_path, index=False)
        print(f"Applied cleanup to: {canonical_path}")
        print(f"Backup created: {backup_path}")
    else:
        print("Apply mode disabled; canonical CSV unchanged")

    print(f"Rows changed: {len(changed_rows)}")
    if preview_path:
        print(f"Change preview file: {preview_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean canonical small_step_name artifacts and rebuild ids/keys")
    parser.add_argument("--canonical", required=True, help="Path to canonical curriculum CSV")
    parser.add_argument("--preview", required=False, help="Optional path to write a CSV of changed rows")
    parser.add_argument("--apply", action="store_true", help="Apply changes to canonical CSV (creates backup)")
    args = parser.parse_args()

    run(
        canonical_path=Path(args.canonical),
        preview_path=Path(args.preview) if args.preview else None,
        apply_changes=args.apply,
    )
