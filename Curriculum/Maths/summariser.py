"""
Flat-schema curriculum summariser for generating ss_desc from ss_wr_desc.

Workflow:
1) Generate candidate summaries from missing_ss_desc.csv (LLM calls).
2) Merge candidates into canonical curriculum CSV by small_step_id with safeguards.

Safeguards:
- Never overwrite non-empty canonical ss_desc.
- Skip rows where canonical ss_wr_desc is blank.
- Skip empty candidate summaries.
"""

from __future__ import annotations

import argparse
import csv
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI


DEFAULT_MISSING_PATH = Path("Curriculum/Maths/missing_ss_desc/missing_ss_desc.csv")
DEFAULT_CANONICAL_PATH = Path("Curriculum/Maths/curriculum_08052026_small_steps.csv")
DEFAULT_CANDIDATES_PATH = Path("Curriculum/Maths/missing_ss_desc/ss_desc_candidates_generated.csv")
DEFAULT_MERGE_REPORT_PATH = Path("Curriculum/Maths/missing_ss_desc/ss_desc_merge_report.csv")
DEFAULT_MERGED_OUTPUT_PATH = Path("Curriculum/Maths/curriculum_08052026_small_steps.with_ss_desc_generated.csv")


@dataclass
class GenerateStats:
    total_in_missing: int
    eligible_rows: int
    attempted: int
    succeeded: int
    failed: int
    skipped_existing_candidate: int
    skipped_blank_wr_desc: int


def clean_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


def ensure_columns(df: pd.DataFrame, required: List[str], label: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{label} is missing required column(s): {missing}")


def make_prompt(ss_wr_desc: str) -> str:
    word_count = len(ss_wr_desc.split())
    return f"""Task: Condense this UK maths curriculum small-step description from ~150 words to ~50 words.

Context:
- The output becomes ss_desc in a curriculum dataset.
- It must stay aligned to the exact intended learning objective.
- It should remain retrieval-friendly for educational video matching.

Requirements:
- Preserve the core objective and key mathematical language.
- Remove filler, duplication, and long pedagogical framing.
- Keep it concise, plain, and teacher-readable.
- Avoid adding new concepts that are not present.
- Target 45-60 words.

Original text ({word_count} words):
{ss_wr_desc}

Return only the shortened text.
"""


def build_client(api_key: str | None) -> OpenAI:
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not clean_text(key):
        raise RuntimeError("OPENAI_API_KEY not found. Add it to environment or .env file.")
    return OpenAI(api_key=key)


def summarise_one(
    client: OpenAI,
    model: str,
    ss_wr_desc: str,
    temperature: float,
    max_tokens: int,
) -> Tuple[str, int]:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are an expert curriculum editor producing concise, objective-faithful summaries.",
            },
            {"role": "user", "content": make_prompt(ss_wr_desc)},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    text = clean_text(response.choices[0].message.content)
    tokens = int(response.usage.total_tokens) if response.usage else 0
    return text, tokens


def load_candidates_map(candidates_path: Path) -> Dict[str, str]:
    if not candidates_path.exists():
        return {}
    df = pd.read_csv(candidates_path)
    ensure_columns(df, ["small_step_id", "candidate_ss_desc"], "Candidates CSV")
    mapped: Dict[str, str] = {}
    for _, row in df.iterrows():
        sid = clean_text(row.get("small_step_id"))
        desc = clean_text(row.get("candidate_ss_desc"))
        if sid and desc:
            mapped[sid] = desc
    return mapped


def generate_candidates(
    missing_path: Path,
    candidates_path: Path,
    api_key: str | None,
    model: str,
    temperature: float,
    max_tokens: int,
    limit: int | None,
    resume: bool,
) -> GenerateStats:
    missing_df = pd.read_csv(missing_path)
    ensure_columns(
        missing_df,
        ["small_step_id", "small_step_name", "ss_wr_desc", "ss_desc"],
        "Missing ss_desc CSV",
    )

    existing_candidates = load_candidates_map(candidates_path) if resume else {}
    client = build_client(api_key)

    rows_out: List[Dict[str, object]] = []
    if candidates_path.exists() and resume:
        existing_df = pd.read_csv(candidates_path)
        rows_out = existing_df.to_dict(orient="records")

    attempted = 0
    succeeded = 0
    failed = 0
    skipped_existing = 0
    skipped_blank_wr = 0
    eligible = 0

    for _, row in missing_df.iterrows():
        sid = clean_text(row.get("small_step_id"))
        step_name = clean_text(row.get("small_step_name"))
        ss_wr_desc = clean_text(row.get("ss_wr_desc"))
        ss_desc = clean_text(row.get("ss_desc"))

        if not sid:
            continue
        if ss_desc:
            continue
        if not ss_wr_desc:
            skipped_blank_wr += 1
            continue

        eligible += 1
        if sid in existing_candidates:
            skipped_existing += 1
            continue

        if limit is not None and attempted >= limit:
            break

        attempted += 1
        print(f"[{attempted}] Summarising: {sid}")

        try:
            candidate, tokens = summarise_one(
                client=client,
                model=model,
                ss_wr_desc=ss_wr_desc,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if not candidate:
                raise RuntimeError("Model returned empty summary")

            rows_out.append(
                {
                    "updated_at": datetime.now().isoformat(timespec="seconds"),
                    "small_step_id": sid,
                    "small_step_name": step_name,
                    "source_ss_wr_desc": ss_wr_desc,
                    "candidate_ss_desc": candidate,
                    "source_word_count": len(ss_wr_desc.split()),
                    "candidate_word_count": len(candidate.split()),
                    "model": model,
                    "tokens_used": tokens,
                }
            )
            existing_candidates[sid] = candidate
            succeeded += 1
        except Exception as exc:
            failed += 1
            rows_out.append(
                {
                    "updated_at": datetime.now().isoformat(timespec="seconds"),
                    "small_step_id": sid,
                    "small_step_name": step_name,
                    "source_ss_wr_desc": ss_wr_desc,
                    "candidate_ss_desc": "",
                    "source_word_count": len(ss_wr_desc.split()),
                    "candidate_word_count": 0,
                    "model": model,
                    "tokens_used": 0,
                    "error": str(exc),
                }
            )

        if attempted % 20 == 0:
            pd.DataFrame(rows_out).to_csv(candidates_path, index=False, encoding="utf-8-sig")
            print(f"Progress saved at {attempted} attempted rows")

    pd.DataFrame(rows_out).to_csv(candidates_path, index=False, encoding="utf-8-sig")

    return GenerateStats(
        total_in_missing=len(missing_df),
        eligible_rows=eligible,
        attempted=attempted,
        succeeded=succeeded,
        failed=failed,
        skipped_existing_candidate=skipped_existing,
        skipped_blank_wr_desc=skipped_blank_wr,
    )


def merge_candidates(
    canonical_path: Path,
    candidates_path: Path,
    merge_report_path: Path,
    merged_output_path: Path,
    inplace: bool,
) -> Dict[str, int]:
    canonical_df = pd.read_csv(canonical_path)
    candidates_df = pd.read_csv(candidates_path)

    ensure_columns(
        canonical_df,
        ["small_step_id", "ss_wr_desc", "ss_desc"],
        "Canonical curriculum CSV",
    )
    ensure_columns(
        candidates_df,
        ["small_step_id", "candidate_ss_desc"],
        "Candidates CSV",
    )

    canonical_df["small_step_id"] = canonical_df["small_step_id"].map(clean_text)
    canonical_df["ss_wr_desc"] = canonical_df["ss_wr_desc"].map(clean_text)
    canonical_df["ss_desc"] = canonical_df["ss_desc"].map(clean_text)

    candidates_df["small_step_id"] = candidates_df["small_step_id"].map(clean_text)
    candidates_df["candidate_ss_desc"] = candidates_df["candidate_ss_desc"].map(clean_text)
    candidates_df = candidates_df[candidates_df["small_step_id"] != ""].copy()

    # Keep latest candidate per small_step_id.
    if "updated_at" in candidates_df.columns:
        candidates_df = candidates_df.sort_values("updated_at").drop_duplicates(
            subset=["small_step_id"],
            keep="last",
        )
    else:
        candidates_df = candidates_df.drop_duplicates(subset=["small_step_id"], keep="last")

    candidate_map: Dict[str, str] = {
        clean_text(r["small_step_id"]): clean_text(r["candidate_ss_desc"])
        for _, r in candidates_df.iterrows()
    }

    report_rows: List[Dict[str, object]] = []
    updated = 0
    skipped_nonblank_ss_desc = 0
    skipped_blank_wr_desc = 0
    skipped_empty_candidate = 0
    unmatched = 0

    canonical_ids = set(canonical_df["small_step_id"])

    for sid, candidate in candidate_map.items():
        if sid not in canonical_ids:
            unmatched += 1
            report_rows.append(
                {
                    "small_step_id": sid,
                    "action": "unmatched_id",
                    "reason": "small_step_id not found in canonical",
                }
            )
            continue

        idx = canonical_df.index[canonical_df["small_step_id"] == sid][0]
        existing = clean_text(canonical_df.at[idx, "ss_desc"])
        wr_desc = clean_text(canonical_df.at[idx, "ss_wr_desc"])

        if existing:
            skipped_nonblank_ss_desc += 1
            report_rows.append(
                {
                    "small_step_id": sid,
                    "action": "skipped",
                    "reason": "canonical ss_desc already non-empty",
                    "existing_ss_desc": existing,
                }
            )
            continue

        if not wr_desc:
            skipped_blank_wr_desc += 1
            report_rows.append(
                {
                    "small_step_id": sid,
                    "action": "skipped",
                    "reason": "canonical ss_wr_desc is blank",
                }
            )
            continue

        if not candidate:
            skipped_empty_candidate += 1
            report_rows.append(
                {
                    "small_step_id": sid,
                    "action": "skipped",
                    "reason": "candidate_ss_desc is empty",
                }
            )
            continue

        canonical_df.at[idx, "ss_desc"] = candidate
        updated += 1
        report_rows.append(
            {
                "small_step_id": sid,
                "action": "updated",
                "reason": "ss_desc filled from candidate",
                "new_ss_desc": candidate,
            }
        )

    write_target = canonical_path if inplace else merged_output_path
    canonical_df.to_csv(write_target, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)
    pd.DataFrame(report_rows).to_csv(
        merge_report_path,
        index=False,
        encoding="utf-8-sig",
        quoting=csv.QUOTE_MINIMAL,
    )

    return {
        "updated": updated,
        "skipped_nonblank_ss_desc": skipped_nonblank_ss_desc,
        "skipped_blank_wr_desc": skipped_blank_wr_desc,
        "skipped_empty_candidate": skipped_empty_candidate,
        "unmatched_ids": unmatched,
        "written_to": 1,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate and safely merge flat-schema ss_desc summaries from ss_wr_desc."
    )
    parser.add_argument("--mode", choices=["generate", "merge", "all"], default="all")
    parser.add_argument("--missing", type=Path, default=DEFAULT_MISSING_PATH)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL_PATH)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES_PATH)
    parser.add_argument("--merge-report", type=Path, default=DEFAULT_MERGE_REPORT_PATH)
    parser.add_argument("--merged-output", type=Path, default=DEFAULT_MERGED_OUTPUT_PATH)
    parser.add_argument("--inplace", action="store_true", help="Write merge result to canonical CSV in place")

    parser.add_argument("--api-key", default=None)
    parser.add_argument("--model", default="gpt-4o")
    parser.add_argument("--temperature", type=float, default=0.3)
    parser.add_argument("--max-tokens", type=int, default=180)
    parser.add_argument("--limit", type=int, default=None, help="Limit number of LLM attempts (for controlled runs)")
    parser.add_argument("--no-resume", action="store_true", help="Do not resume from existing candidates file")

    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()

    for p in [args.missing, args.canonical]:
        if not p.exists():
            raise FileNotFoundError(f"Required file not found: {p}")

    if args.mode in {"generate", "all"}:
        print("Starting candidate generation...")
        stats = generate_candidates(
            missing_path=args.missing,
            candidates_path=args.candidates,
            api_key=args.api_key,
            model=args.model,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            limit=args.limit,
            resume=not args.no_resume,
        )
        print("Generation complete")
        print(
            {
                "total_in_missing": stats.total_in_missing,
                "eligible_rows": stats.eligible_rows,
                "attempted": stats.attempted,
                "succeeded": stats.succeeded,
                "failed": stats.failed,
                "skipped_existing_candidate": stats.skipped_existing_candidate,
                "skipped_blank_wr_desc": stats.skipped_blank_wr_desc,
                "candidates_file": str(args.candidates),
            }
        )

    if args.mode in {"merge", "all"}:
        if not args.candidates.exists():
            raise FileNotFoundError(f"Candidates file not found: {args.candidates}")
        print("Starting safe merge into canonical curriculum...")
        merge_stats = merge_candidates(
            canonical_path=args.canonical,
            candidates_path=args.candidates,
            merge_report_path=args.merge_report,
            merged_output_path=args.merged_output,
            inplace=args.inplace,
        )
        print("Merge complete")
        print(
            {
                **merge_stats,
                "merge_report": str(args.merge_report),
                "output_file": str(args.canonical if args.inplace else args.merged_output),
                "inplace": args.inplace,
            }
        )


if __name__ == "__main__":
    main()
