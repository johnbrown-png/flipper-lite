"""Prepare a filtered staging curriculum CSV for batch precompute of newly added ss_wr_desc.

Identifies Y7-Y10 Summer small steps that:
  - have a non-empty ss_wr_desc in the canonical curriculum
  - are NOT already present in precomputed_recommendations_flat.csv

Writes a filtered canonical CSV to use as --curriculum input for precompute_curriculum_recommendations.py.

Usage (run from workspace root):
    python Curriculum/Maths/pdf_extractor/prepare_precompute_staging.py

Then run precompute against the staging file:
    python precompute_curriculum_recommendations.py \
        --curriculum Curriculum/Maths/pdf_extractor/curriculum_newdesc_staging.csv \
        --output precomputed_recommendations_staging_newdesc.csv
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

# Ensure workspace root is on path
WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(WORKSPACE_ROOT))

from shared.curriculum_schema import curriculum_to_long_df  # noqa: E402

CANONICAL_CSV = WORKSPACE_ROOT / "Curriculum" / "Maths" / "curriculum_08052026_small_steps.csv"
EXISTING_FLAT_CSV = WORKSPACE_ROOT / "precomputed_recommendations_flat.csv"
STAGING_CSV = Path(__file__).parent / "curriculum_newdesc_staging.csv"


def _year_num(value: object) -> int | None:
    m = re.search(r"(\d+)", str(value or ""))
    return int(m.group(1)) if m else None


def _is_y7_y10_summer(row: pd.Series) -> bool:
    yr = _year_num(row.get("year"))
    term = str(row.get("term", "")).strip().lower()
    return yr is not None and 7 <= yr <= 10 and term in ("summer", "sum")


def main() -> None:
    print(f"Loading canonical curriculum: {CANONICAL_CSV}")
    raw_canonical = pd.read_csv(CANONICAL_CSV)
    canonical = curriculum_to_long_df(raw_canonical)
    print(f"  Canonical rows (long form): {len(canonical)}")

    # --- Scope filter: Y7-Y10 Summer with non-empty ss_wr_desc ---
    in_scope = canonical[canonical.apply(_is_y7_y10_summer, axis=1)].copy()
    with_desc = in_scope[in_scope["ss_wr_desc"].fillna("").str.strip() != ""].copy()
    print(f"  Y7-Y10 Summer rows: {len(in_scope)}")
    print(f"  With non-empty ss_wr_desc: {len(with_desc)}")

    # --- Exclude already-precomputed step IDs ---
    already_done: set[str] = set()
    if EXISTING_FLAT_CSV.exists():
        existing = pd.read_csv(EXISTING_FLAT_CSV, usecols=["small_step_id"])
        already_done = set(existing["small_step_id"].astype(str).unique())
        print(f"  Already precomputed step IDs: {len(already_done)}")
    else:
        print(f"  ⚠ No existing flat CSV found at {EXISTING_FLAT_CSV}; treating all as new")

    missing = with_desc[~with_desc["small_step_id"].astype(str).isin(already_done)].copy()
    print(f"\n  ✅ Steps requiring precompute: {len(missing)}")

    if missing.empty:
        print("Nothing to do — all in-scope steps are already precomputed.")
        return

    # --- Print summary of what will be processed ---
    print("\nBreakdown by year/term/difficulty:")
    print(
        missing.groupby(["year", "term", "difficulty"])
        .size()
        .reset_index(name="count")
        .to_string(index=False)
    )

    # --- Write staging CSV (raw canonical rows for the missing step IDs) ---
    # We filter the *raw* canonical CSV so curriculum_to_long_df inside precompute
    # processes it the same way as the full file.
    target_ids = set(missing["small_step_id"].astype(str))
    staging_rows = raw_canonical[
        raw_canonical["small_step_id"].astype(str).isin(target_ids)
    ].copy()
    staging_rows.to_csv(STAGING_CSV, index=False)
    print(f"\n✅ Staging CSV written: {STAGING_CSV}")
    print(f"   Rows in staging file: {len(staging_rows)}")
    print("\nNext step — run precompute against the staging file:")
    print(
        f"  python precompute_curriculum_recommendations.py"
        f" --curriculum \"{STAGING_CSV.relative_to(WORKSPACE_ROOT)}\""
        f" --output precomputed_recommendations_staging_newdesc.csv"
    )


if __name__ == "__main__":
    main()
