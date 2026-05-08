"""Merge extracted Y7-Y10 Summer ss_wr_desc backfill into canonical small-steps CSV.

Default behavior is safe and conservative:
- Writes preview + manual review outputs
- Fills empty canonical ss_wr_desc only
- Never overwrites non-empty values unless --overwrite-non-empty is set
- Never applies updates unless --apply is set
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path
import difflib
import re
from typing import Dict, List, Optional, Tuple

import pandas as pd

import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))
from shared.curriculum_schema import build_small_step_key as _build_small_step_key


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def normalize_term(value: object) -> str:
    token = clean_text(value).lower()
    mapping = {
        "aut": "Autumn",
        "autumn": "Autumn",
        "spr": "Spring",
        "spring": "Spring",
        "sum": "Summer",
        "summer": "Summer",
    }
    return mapping.get(token, clean_text(value).title())


def normalize_difficulty(value: object) -> str:
    token = clean_text(value).lower()
    mapping = {
        "f": "Foundation",
        "foundation": "Foundation",
        "h": "Higher",
        "higher": "Higher",
        "": "",
    }
    return mapping.get(token, clean_text(value).title())


YEAR_TO_AGE: dict[str, str] = {
    "year 7": "11-12",
    "year 8": "12-13",
    "year 9": "13-14",
    "year 10": "14-15",
}


def _constructed_key(row: pd.Series) -> str:
    """Build a small_step_key from extracted fields, using sub_topic as topic so
    slugification strips any punctuation differences vs canonical topic strings."""
    year = clean_text(row.get("year"))
    age = YEAR_TO_AGE.get(year.lower(), "")
    term = normalize_term(row.get("term"))
    difficulty = normalize_difficulty(row.get("difficulty"))
    # sub_topic (e.g. "Speed distance and time") matches canonical topic after slugify
    topic = clean_text(row.get("sub_topic")) or clean_text(row.get("topic"))
    step_num = clean_text(row.get("small_step_num_in_topic"))
    step_name = clean_text(row.get("small_step_name"))
    return _build_small_step_key(year, age, term, difficulty, topic, step_num, step_name)

def normalize_compare_text(value: object) -> str:
    text = clean_text(value).lower()
    text = re.sub(r"\s*[-–—]\s*", "-", text)
    text = re.sub(r"[^a-z0-9\-\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_step_name_for_match(value: object) -> str:
    """Normalize step names while removing known legacy prefix artifacts.

    Examples handled:
    - '1 Multiples' -> 'Multiples'
    - '"" Angles around a point' -> 'Angles around a point'
    - '""0 Parallel and perpendicular lines' -> 'Parallel and perpendicular lines'
    """
    text = clean_text(value)
    text = re.sub(r'^\s*""\s*', '', text)
    text = re.sub(r'^\s*"\s*', '', text)
    text = re.sub(r'^\s*\d+\s*', '', text)
    return normalize_compare_text(text)


def parse_year_number(value: object) -> Optional[int]:
    text = clean_text(value)
    match = re.search(r"(\d+)", text)
    if not match:
        return None
    return int(match.group(1))


def in_scope_y7_y10_summer(row: pd.Series) -> bool:
    year_num = parse_year_number(row.get("year"))
    term = normalize_term(row.get("term"))
    return year_num is not None and 7 <= year_num <= 10 and term == "Summer"


def canonical_required_columns() -> List[str]:
    return [
        "small_step_id",
        "small_step_key",
        "year",
        "term",
        "difficulty",
        "topic",
        "small_step_num_in_topic",
        "small_step_name",
        "ss_wr_desc",
    ]


def backfill_required_columns() -> List[str]:
    return [
        "year",
        "term",
        "difficulty",
        "topic",
        "small_step_num_in_topic",
        "small_step_name",
        "ss_wr_desc_extracted",
        "source_pdf_name",
    ]


def validate_columns(df: pd.DataFrame, required: List[str], label: str) -> None:
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def build_meta_key(year: object, term: object, difficulty: object, topic: object, step_num: object) -> Tuple[str, str, str, str, str]:
    return (
        clean_text(year),
        normalize_term(term),
        normalize_difficulty(difficulty),
        normalize_compare_text(topic),
        clean_text(step_num),
    )


def build_block_meta_key(year: object, term: object, difficulty: object, block: object, step_num: object) -> Tuple[str, str, str, str, str]:
    block_text = clean_text(block)
    try:
        if block_text:
            block_text = str(int(float(block_text)))
    except ValueError:
        pass
    return (
        clean_text(year),
        normalize_term(term),
        normalize_difficulty(difficulty),
        block_text,
        clean_text(step_num),
    )


def build_step_meta_key(year: object, term: object, difficulty: object, step_num: object) -> Tuple[str, str, str, str]:
    return (
        clean_text(year),
        normalize_term(term),
        normalize_difficulty(difficulty),
        clean_text(step_num),
    )


def _backfill_topic_for_matching(row: pd.Series) -> str:
    # Extractor's "topic" can be broad (e.g. "Time"); "sub_topic" maps better to canonical "topic".
    return clean_text(row.get("sub_topic")) or clean_text(row.get("topic"))


def best_fuzzy_match(candidates: pd.DataFrame, step_name: str, threshold: float = 0.9) -> Optional[pd.Series]:
    target = normalize_step_name_for_match(step_name)
    if not target:
        return None

    best_row = None
    best_score = 0.0
    ties = 0

    for _, row in candidates.iterrows():
        candidate_name = normalize_step_name_for_match(row.get("small_step_name"))
        score = difflib.SequenceMatcher(None, target, candidate_name).ratio()
        if score > best_score:
            best_score = score
            best_row = row
            ties = 1
        elif score == best_score:
            ties += 1

    if best_row is None or best_score < threshold or ties > 1:
        return None
    return best_row


def best_fuzzy_suggestion(candidates: pd.DataFrame, step_name: str) -> Tuple[Optional[pd.Series], float, int]:
    """Return the best fuzzy candidate, its score, and tie count at best score.

    Used for manual-review suggestions, not automatic matching.
    """
    target = normalize_step_name_for_match(step_name)
    if not target or candidates is None or candidates.empty:
        return None, 0.0, 0

    best_row = None
    best_score = 0.0
    ties = 0

    for _, row in candidates.iterrows():
        candidate_name = normalize_step_name_for_match(row.get("small_step_name"))
        score = difflib.SequenceMatcher(None, target, candidate_name).ratio()
        if score > best_score:
            best_score = score
            best_row = row
            ties = 1
        elif score == best_score:
            ties += 1

    return best_row, best_score, ties


def choose_best_backfill_rows(match_df: pd.DataFrame) -> pd.DataFrame:
    if match_df.empty:
        return match_df

    confidence_rank = {"high": 3, "medium": 2, "low": 1, "": 0}
    ranked = match_df.copy()
    ranked["_confidence_rank"] = ranked["extraction_confidence"].map(lambda x: confidence_rank.get(clean_text(x).lower(), 0))
    ranked["_desc_len"] = ranked["ss_wr_desc_extracted"].map(lambda v: len(clean_text(v)))
    ranked["_source_pdf"] = ranked["source_pdf_name"].map(clean_text)

    ranked = ranked.sort_values(
        ["small_step_id", "_confidence_rank", "_desc_len", "_source_pdf"],
        ascending=[True, False, False, True],
        kind="stable",
    )

    return ranked.drop_duplicates(subset=["small_step_id"], keep="first")


def merge_backfill(
    canonical_path: Path,
    backfill_path: Path,
    preview_path: Path,
    manual_review_path: Path,
    match_report_path: Optional[Path],
    apply_changes: bool,
    backup_path: Optional[Path],
    overwrite_non_empty: bool,
) -> None:
    canonical_df = pd.read_csv(canonical_path)
    backfill_df = pd.read_csv(backfill_path)

    validate_columns(canonical_df, canonical_required_columns(), "Canonical CSV")
    validate_columns(backfill_df, backfill_required_columns(), "Backfill CSV")

    canonical_df["term"] = canonical_df["term"].map(normalize_term)
    canonical_df["difficulty"] = canonical_df["difficulty"].map(normalize_difficulty)

    backfill_df["term"] = backfill_df["term"].map(normalize_term)
    backfill_df["difficulty"] = backfill_df["difficulty"].map(normalize_difficulty)

    canonical_scope_df = canonical_df[canonical_df.apply(in_scope_y7_y10_summer, axis=1)].copy()
    backfill_scope_df = backfill_df[backfill_df.apply(in_scope_y7_y10_summer, axis=1)].copy()

    canonical_by_id = canonical_scope_df.set_index("small_step_id", drop=False)
    canonical_by_key = canonical_scope_df.set_index("small_step_key", drop=False)

    meta_groups: Dict[Tuple[str, str, str, str, str], pd.DataFrame] = {}
    block_groups: Dict[Tuple[str, str, str, str, str], pd.DataFrame] = {}
    step_groups: Dict[Tuple[str, str, str, str], pd.DataFrame] = {}
    for _, row in canonical_scope_df.iterrows():
        key = build_meta_key(
            row.get("year"),
            row.get("term"),
            row.get("difficulty"),
            row.get("topic"),
            row.get("small_step_num_in_topic"),
        )
        if key not in meta_groups:
            meta_groups[key] = canonical_scope_df.iloc[0:0].copy()
        meta_groups[key] = pd.concat([meta_groups[key], row.to_frame().T], ignore_index=True)

        block_key = build_block_meta_key(
            row.get("year"),
            row.get("term"),
            row.get("difficulty"),
            row.get("block"),
            row.get("small_step_num_in_topic"),
        )
        if block_key not in block_groups:
            block_groups[block_key] = canonical_scope_df.iloc[0:0].copy()
        block_groups[block_key] = pd.concat([block_groups[block_key], row.to_frame().T], ignore_index=True)

        step_key = build_step_meta_key(
            row.get("year"),
            row.get("term"),
            row.get("difficulty"),
            row.get("small_step_num_in_topic"),
        )
        if step_key not in step_groups:
            step_groups[step_key] = canonical_scope_df.iloc[0:0].copy()
        step_groups[step_key] = pd.concat([step_groups[step_key], row.to_frame().T], ignore_index=True)

    match_rows = []
    manual_rows = []

    for idx, row in backfill_scope_df.iterrows():
        extracted_desc = clean_text(row.get("ss_wr_desc_extracted"))
        if not extracted_desc:
            manual_rows.append(
                {
                    "backfill_index": idx,
                    "reason": "empty_extracted_desc",
                    "source_pdf_name": clean_text(row.get("source_pdf_name")),
                    "year": clean_text(row.get("year")),
                    "term": clean_text(row.get("term")),
                    "difficulty": clean_text(row.get("difficulty")),
                    "topic": clean_text(row.get("topic")),
                    "small_step_num_in_topic": clean_text(row.get("small_step_num_in_topic")),
                    "small_step_name": clean_text(row.get("small_step_name")),
                    "ss_wr_desc_extracted": extracted_desc,
                }
            )
            continue

        matched_row = None
        match_method = ""
        manual_reason = "no_unique_match"
        meta_candidate_count = 0
        block_candidate_count = 0

        backfill_small_step_id = clean_text(row.get("small_step_id"))
        if backfill_small_step_id and backfill_small_step_id in canonical_by_id.index:
            matched_row = canonical_by_id.loc[backfill_small_step_id]
            if isinstance(matched_row, pd.DataFrame):
                matched_row = None
            else:
                match_method = "id_exact"

        if matched_row is None:
            backfill_small_step_key = clean_text(row.get("small_step_key"))
            if backfill_small_step_key and backfill_small_step_key in canonical_by_key.index:
                candidate = canonical_by_key.loc[backfill_small_step_key]
                if isinstance(candidate, pd.DataFrame):
                    matched_row = None
                else:
                    matched_row = candidate
                    match_method = "key_exact"

        if matched_row is None:
            constructed = _constructed_key(row)
            if constructed and constructed in canonical_by_key.index:
                candidate = canonical_by_key.loc[constructed]
                if isinstance(candidate, pd.DataFrame):
                    matched_row = None
                else:
                    matched_row = candidate
                    match_method = "constructed_key_exact"

        if matched_row is None:
            key = build_meta_key(
                row.get("year"),
                row.get("term"),
                row.get("difficulty"),
                _backfill_topic_for_matching(row),
                row.get("small_step_num_in_topic"),
            )
            candidates = meta_groups.get(key)
            if candidates is not None and not candidates.empty:
                meta_candidate_count = len(candidates)
                exact_name = normalize_step_name_for_match(row.get("small_step_name"))
                exact_candidates = candidates[
                    candidates["small_step_name"].map(normalize_step_name_for_match) == exact_name
                ]
                if len(exact_candidates) == 1:
                    matched_row = exact_candidates.iloc[0]
                    match_method = "metadata_name_exact"
                elif len(exact_candidates) > 1:
                    manual_reason = "metadata_multiple_exact_name_candidates"
                else:
                    fuzzy = best_fuzzy_match(candidates, clean_text(row.get("small_step_name")))
                    if fuzzy is not None:
                        matched_row = fuzzy
                        match_method = "metadata_name_fuzzy"
                    elif len(candidates) == 1:
                        # Safe fallback: metadata narrowed to a single canonical row,
                        # so accept it even if name text differs.
                        matched_row = candidates.iloc[0]
                        match_method = "metadata_singleton"
                    else:
                        manual_reason = "metadata_candidates_no_unique_name_match"
            else:
                manual_reason = "no_topic_metadata_candidates"

        if matched_row is None:
            # Block-agnostic fallback when block metadata is missing or unreliable.
            step_key = build_step_meta_key(
                row.get("year"),
                row.get("term"),
                row.get("difficulty"),
                row.get("small_step_num_in_topic"),
            )
            step_candidates = step_groups.get(step_key)
            if step_candidates is not None and not step_candidates.empty:
                if len(step_candidates) == 1:
                    matched_row = step_candidates.iloc[0]
                    match_method = "step_singleton"
                else:
                    exact_name = normalize_step_name_for_match(row.get("small_step_name"))
                    exact_candidates = step_candidates[
                        step_candidates["small_step_name"].map(normalize_step_name_for_match) == exact_name
                    ]
                    if len(exact_candidates) == 1:
                        matched_row = exact_candidates.iloc[0]
                        match_method = "step_name_exact"
                    elif len(exact_candidates) == 0:
                        fuzzy = best_fuzzy_match(step_candidates, clean_text(row.get("small_step_name")), threshold=0.95)
                        if fuzzy is not None:
                            matched_row = fuzzy
                            match_method = "step_name_fuzzy"

        if matched_row is None:
            block_key = build_block_meta_key(
                row.get("year"),
                row.get("term"),
                row.get("difficulty"),
                row.get("block"),
                row.get("small_step_num_in_topic"),
            )
            block_candidates = block_groups.get(block_key)
            if block_candidates is not None and not block_candidates.empty:
                block_candidate_count = len(block_candidates)
                if block_candidate_count == 1:
                    matched_row = block_candidates.iloc[0]
                    match_method = "block_singleton"
                else:
                    exact_name = normalize_step_name_for_match(row.get("small_step_name"))
                    exact_candidates = block_candidates[
                        block_candidates["small_step_name"].map(normalize_step_name_for_match) == exact_name
                    ]
                    if len(exact_candidates) == 1:
                        matched_row = exact_candidates.iloc[0]
                        match_method = "block_step_name_exact"
                    elif len(exact_candidates) > 1:
                        manual_reason = "block_multiple_exact_name_candidates"
                    else:
                        fuzzy = best_fuzzy_match(block_candidates, clean_text(row.get("small_step_name")))
                        if fuzzy is not None:
                            matched_row = fuzzy
                            match_method = "block_step_name_fuzzy"
                        else:
                            manual_reason = "block_candidates_no_unique_name_match"

        if matched_row is None:
            suggestion_id = ""
            suggestion_key = ""
            suggestion_method = ""
            suggestion_score = ""
            source_name_norm = normalize_step_name_for_match(row.get("small_step_name"))

            def _name_score(candidate_row: pd.Series) -> float:
                target_norm = normalize_step_name_for_match(candidate_row.get("small_step_name"))
                if not source_name_norm or not target_norm:
                    return 0.0
                return difflib.SequenceMatcher(None, source_name_norm, target_norm).ratio()

            # Strong deterministic suggestion: exactly one candidate by block+step metadata.
            if block_candidate_count == 1 and block_candidates is not None and not block_candidates.empty:
                suggested = block_candidates.iloc[0]
                score = _name_score(suggested)
                if score >= 0.8:
                    suggestion_id = clean_text(suggested.get("small_step_id"))
                    suggestion_key = clean_text(suggested.get("small_step_key"))
                    suggestion_method = "block_single_candidate"
                    suggestion_score = f"{score:.3f}"
            # Next best deterministic suggestion: exactly one candidate by topic metadata.
            elif meta_candidate_count == 1 and candidates is not None and not candidates.empty:
                suggested = candidates.iloc[0]
                score = _name_score(suggested)
                if score >= 0.8:
                    suggestion_id = clean_text(suggested.get("small_step_id"))
                    suggestion_key = clean_text(suggested.get("small_step_key"))
                    suggestion_method = "meta_single_candidate"
                    suggestion_score = f"{score:.3f}"
            else:
                pool = None
                pool_method = ""
                if block_candidates is not None and not block_candidates.empty:
                    pool = block_candidates
                    pool_method = "block_fuzzy_top"
                elif candidates is not None and not candidates.empty:
                    pool = candidates
                    pool_method = "meta_fuzzy_top"

                if pool is not None:
                    suggested, score, ties = best_fuzzy_suggestion(pool, clean_text(row.get("small_step_name")))
                    if suggested is not None and ties == 1 and score >= 0.8:
                        suggestion_id = clean_text(suggested.get("small_step_id"))
                        suggestion_key = clean_text(suggested.get("small_step_key"))
                        suggestion_method = pool_method
                        suggestion_score = f"{score:.3f}"

            manual_rows.append(
                {
                    "backfill_index": idx,
                    "reason": manual_reason,
                    "source_pdf_name": clean_text(row.get("source_pdf_name")),
                    "year": clean_text(row.get("year")),
                    "term": clean_text(row.get("term")),
                    "difficulty": clean_text(row.get("difficulty")),
                    "topic": clean_text(row.get("topic")),
                    "sub_topic": clean_text(row.get("sub_topic")),
                    "block": clean_text(row.get("block")),
                    "small_step_num_in_topic": clean_text(row.get("small_step_num_in_topic")),
                    "small_step_name": clean_text(row.get("small_step_name")),
                    "meta_candidate_count": meta_candidate_count,
                    "block_candidate_count": block_candidate_count,
                    "suggested_canonical_small_step_id": suggestion_id,
                    "suggested_canonical_small_step_key": suggestion_key,
                    "suggestion_method": suggestion_method,
                    "suggestion_score": suggestion_score,
                    "ss_wr_desc_extracted": extracted_desc,
                }
            )
            continue

        match_rows.append(
            {
                "backfill_index": idx,
                "small_step_id": clean_text(matched_row.get("small_step_id")),
                "small_step_key": clean_text(matched_row.get("small_step_key")),
                "match_method": match_method,
                "extraction_confidence": clean_text(row.get("extraction_confidence")),
                "source_pdf_name": clean_text(row.get("source_pdf_name")),
                "year": clean_text(row.get("year")),
                "term": clean_text(row.get("term")),
                "difficulty": clean_text(row.get("difficulty")),
                "topic": clean_text(row.get("topic")),
                "small_step_num_in_topic": clean_text(row.get("small_step_num_in_topic")),
                "small_step_name": clean_text(row.get("small_step_name")),
                "ss_wr_desc_extracted": extracted_desc,
            }
        )

    match_df = pd.DataFrame(match_rows)
    manual_df = pd.DataFrame(manual_rows)

    if not match_df.empty:
        match_df = choose_best_backfill_rows(match_df)

    updates_by_id = {}
    for _, row in match_df.iterrows():
        updates_by_id[clean_text(row.get("small_step_id"))] = row

    preview_rows = []
    updated_count = 0

    updated_df = canonical_df.copy()
    for idx, row in updated_df.iterrows():
        step_id = clean_text(row.get("small_step_id"))
        in_scope = in_scope_y7_y10_summer(row)
        old_desc = clean_text(row.get("ss_wr_desc"))

        if not in_scope or step_id not in updates_by_id:
            continue

        update_row = updates_by_id[step_id]
        new_desc = clean_text(update_row.get("ss_wr_desc_extracted"))

        if not new_desc:
            change_type = "skipped_empty_new"
            apply_value = old_desc
        elif old_desc and not overwrite_non_empty:
            change_type = "skipped_non_empty_existing"
            apply_value = old_desc
        elif old_desc == new_desc:
            change_type = "no_change"
            apply_value = old_desc
        else:
            apply_value = new_desc
            change_type = "updated_non_empty" if old_desc else "filled_empty"
            if apply_changes:
                updated_df.at[idx, "ss_wr_desc"] = apply_value
                updated_count += 1

        preview_rows.append(
            {
                "small_step_id": step_id,
                "small_step_key": clean_text(row.get("small_step_key")),
                "year": clean_text(row.get("year")),
                "term": clean_text(row.get("term")),
                "difficulty": clean_text(row.get("difficulty")),
                "topic": clean_text(row.get("topic")),
                "small_step_num_in_topic": clean_text(row.get("small_step_num_in_topic")),
                "small_step_name": clean_text(row.get("small_step_name")),
                "ss_wr_desc_before": old_desc,
                "ss_wr_desc_after": apply_value,
                "ss_wr_desc_extracted": new_desc,
                "change_type": change_type,
                "match_method": clean_text(update_row.get("match_method")),
                "extraction_confidence": clean_text(update_row.get("extraction_confidence")),
                "source_pdf_name": clean_text(update_row.get("source_pdf_name")),
            }
        )

    preview_df = pd.DataFrame(preview_rows)

    preview_df.to_csv(preview_path, index=False, encoding="utf-8", quoting=csv.QUOTE_MINIMAL)
    manual_df.to_csv(manual_review_path, index=False, encoding="utf-8", quoting=csv.QUOTE_MINIMAL)

    if match_report_path:
        match_df.to_csv(match_report_path, index=False, encoding="utf-8", quoting=csv.QUOTE_MINIMAL)

    if apply_changes:
        if backup_path is None:
            backup_name = f"{canonical_path.stem}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}{canonical_path.suffix}"
            backup_path = canonical_path.parent / backup_name
        canonical_df.to_csv(backup_path, index=False, encoding="utf-8", quoting=csv.QUOTE_MINIMAL)
        updated_df.to_csv(canonical_path, index=False, encoding="utf-8", quoting=csv.QUOTE_MINIMAL)

    print(f"Canonical rows total: {len(canonical_df)}")
    print(f"Canonical in-scope rows (Y7-Y10 Summer): {len(canonical_scope_df)}")
    print(f"Backfill in-scope rows: {len(backfill_scope_df)}")
    print(f"Matched rows: {len(match_df)}")
    print(f"Manual-review rows: {len(manual_df)}")
    print(f"Preview rows: {len(preview_df)}")

    if apply_changes:
        print(f"Applied updates: {updated_count}")
        print(f"Backup written: {backup_path}")
        print(f"Canonical updated: {canonical_path}")
    else:
        print("Apply mode disabled; no canonical file changes made")

    print(f"Preview file: {preview_path}")
    print(f"Manual review file: {manual_review_path}")
    if match_report_path:
        print(f"Match report file: {match_report_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge extracted ss_wr_desc backfill into canonical curriculum")
    parser.add_argument("--canonical", required=True, help="Path to canonical curriculum_08052026_small_steps.csv")
    parser.add_argument("--backfill", required=True, help="Path to extracted flat backfill CSV")
    parser.add_argument("--preview", required=True, help="Path to write update preview CSV")
    parser.add_argument("--manual-review", required=True, help="Path to write manual review queue CSV")
    parser.add_argument("--match-report", help="Optional path for match report CSV")
    parser.add_argument("--apply", action="store_true", help="Apply updates to canonical CSV")
    parser.add_argument("--backup", help="Optional backup path when using --apply")
    parser.add_argument(
        "--overwrite-non-empty",
        action="store_true",
        help="Allow overwriting non-empty canonical ss_wr_desc values",
    )

    args = parser.parse_args()

    merge_backfill(
        canonical_path=Path(args.canonical),
        backfill_path=Path(args.backfill),
        preview_path=Path(args.preview),
        manual_review_path=Path(args.manual_review),
        match_report_path=Path(args.match_report) if args.match_report else None,
        apply_changes=args.apply,
        backup_path=Path(args.backup) if args.backup else None,
        overwrite_non_empty=args.overwrite_non_empty,
    )


if __name__ == "__main__":
    main()
