"""
White Rose PDF Curriculum Extractor - Hybrid Approach

Strategies:
1. Extract step titles from "Small steps" summary pages.
2. Extract descriptions from text between "Notes and guidance" and
   "Things to look out for".

This script supports both filename styles in one run:
- Legacy: Y7 Spring Block 4 SOL Fractions and percentages of amounts.pdf
- v3: WRE Maths v3 Y7 SUM B1 SOL - Speed distance and time .pdf

Install: pip install PyMuPDF pandas
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

import fitz  # PyMuPDF
import pandas as pd


TERM_MAP = {
    "AUT": "Autumn",
    "AUTUMN": "Autumn",
    "SPR": "Spring",
    "SPRING": "Spring",
    "SUM": "Summer",
    "SUMMER": "Summer",
}


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def normalize_term(term_token: str) -> str:
    token = clean_text(term_token).upper()
    return TERM_MAP.get(token, term_token.title())


def normalize_difficulty(diff_token: str) -> str:
    token = clean_text(diff_token).upper()
    if token == "F":
        return "Foundation"
    if token == "H":
        return "Higher"
    if token in ("FOUNDATION", "HIGHER"):
        return token.title()
    return clean_text(diff_token)


def normalize_topic_for_match(text: str) -> str:
    normalized = clean_text(text).lower()
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"\s*[-–—]\s*", "-", normalized)
    return normalized.strip()


class PDFCurriculumExtractorHybrid:
    def __init__(
        self,
        output_csv: str = "curriculum_data_hybrid.csv",
        skip_files: Optional[List[str]] = None,
        append_mode: bool = False,
        flat_output: bool = False,
    ):
        self.output_csv = output_csv
        self.all_data: List[Dict[str, object]] = []
        self.skip_files = skip_files or []
        self.append_mode = append_mode
        self.flat_output = flat_output

    def parse_filename(self, filename: str) -> Dict[str, str]:
        """Parse year/term/block/difficulty/sub_topic from old and v3 names."""
        name = filename.replace(".pdf", "").strip()

        # v3 format with optional difficulty and flexible SOL separator
        # Example: WRE Maths v3 Y10 SUM B1 H SOL - Angles
        # Example: WRE Maths v3 Y8 SUM B1 SOL Angles in parallel lines and polygons
        v3_pattern = (
            r"^WRE\s+Maths\s+v3\s+Y(?P<year>\d+)\s+"
            r"(?P<term>AUT|SPR|SUM|Autumn|Spring|Summer)\s+"
            r"B(?P<block>\d+)\s*"
            r"(?:(?P<difficulty>[FH])\s+)?"
            r"SOL\s*(?:-|–|—)?\s*(?P<sub_topic>.+)$"
        )
        match = re.match(v3_pattern, name, flags=re.IGNORECASE)
        if match:
            groups = match.groupdict()
            return {
                "year": f"Year {groups['year']}",
                "term": normalize_term(groups["term"]),
                "block": clean_text(groups["block"]),
                "difficulty": normalize_difficulty(groups.get("difficulty") or ""),
                "sub_topic": clean_text(groups["sub_topic"]),
            }

        # Legacy format with optional SOL and optional difficulty
        # Example: Y10 Autumn Block 3 Foundation Quadratic expressions and equations
        legacy_pattern = (
            r"^Y(?P<year>\d+)\s+"
            r"(?P<term>AUT|SPR|SUM|Autumn|Spring|Summer)\s+"
            r"Block\s+(?P<block>\d+)\s*"
            r"(?:(?P<difficulty>Foundation|Higher)\s+)?"
            r"(?:SOL\s+)?"
            r"(?P<sub_topic>.+)$"
        )
        match = re.match(legacy_pattern, name, flags=re.IGNORECASE)
        if match:
            groups = match.groupdict()
            return {
                "year": f"Year {groups['year']}",
                "term": normalize_term(groups["term"]),
                "block": clean_text(groups["block"]),
                "difficulty": normalize_difficulty(groups.get("difficulty") or ""),
                "sub_topic": clean_text(groups["sub_topic"]),
            }

        print(f"⚠ Warning: Could not parse filename: {filename}")
        return {
            "year": "Unknown",
            "term": "Unknown",
            "block": "Unknown",
            "difficulty": "",
            "sub_topic": name,
        }

    def extract_text_from_page(self, page) -> str:
        try:
            return page.get_text("text") or ""
        except Exception:
            return ""

    def extract_topic_from_filename(self, metadata: Dict[str, str]) -> str:
        # Preserve full topic string from filename metadata; truncation caused
        # mismatches in downstream QA/merge workflows.
        return clean_text(metadata.get("sub_topic", ""))

    def _page_matches_metadata(self, text: str, metadata: Dict[str, str]) -> bool:
        """Return True when a page appears to belong to the parsed block metadata."""
        year_match = re.search(r"(\d+)", clean_text(metadata.get("year", "")))
        block = clean_text(metadata.get("block", ""))
        term = normalize_term(clean_text(metadata.get("term", "")))

        if not year_match or not block or not term:
            return True

        year_num = year_match.group(1)
        term_pattern = re.escape(term)
        block_pattern = re.escape(block)
        year_pattern = re.escape(year_num)

        # Typical White Rose header pattern:
        # Year 7 | Summer term | Block 1 – Speed, distance and time
        header_regex = (
            rf"Year\s*{year_pattern}\s*\|\s*"
            rf"{term_pattern}\s+term\s*\|\s*"
            rf"Block\s*{block_pattern}\b"
        )

        return re.search(header_regex, text, flags=re.IGNORECASE) is not None

    def find_small_steps_pages(self, doc, metadata: Dict[str, str]) -> List[int]:
        pages = []
        for page_num in range(len(doc)):
            text = self.extract_text_from_page(doc[page_num])
            if "Small steps" in text and self._page_matches_metadata(text, metadata):
                pages.append(page_num)
        return pages

    def extract_small_step_titles(self, doc, metadata: Dict[str, str]) -> List[str]:
        steps: List[str] = []
        pages = self.find_small_steps_pages(doc, metadata)
        print(f"   Found {len(pages)} 'Small steps' summary pages")

        for page_num in pages:
            text = self.extract_text_from_page(doc[page_num])
            if not text:
                continue

            lines = [line.strip() for line in text.split("\n")]
            i = 0
            while i < len(lines):
                line = lines[i]
                step_match = re.match(r"^Step\s+(\d+)$", line)
                if step_match:
                    title = None
                    for j in range(i + 1, min(i + 6, len(lines))):
                        next_line = lines[j].strip()
                        if not next_line:
                            continue
                        if re.match(r"^Step\s+\d+$", next_line):
                            break
                        if any(skip in next_line for skip in ["Small steps", "White Rose", "©", "|"]):
                            continue
                        title = next_line
                        break

                    if title and len(title) > 2:
                        steps.append(title)
                i += 1

        return steps

    def extract_description_below_notes(self, lines: List[str], notes_idx: int) -> str:
        description_lines: List[str] = []

        i = notes_idx + 1
        while i < len(lines) and not lines[i].strip():
            i += 1

        while i < len(lines):
            line = lines[i].strip()
            line_lower = line.lower()

            if line_lower.startswith("things to look out for"):
                break

            if "©" in line or "white rose" in line_lower or "whitero" in line_lower:
                i += 1
                continue

            if line:
                description_lines.append(line)

            i += 1

        description = " ".join(description_lines)
        description = re.sub(r"\s+", " ", description)
        return description.strip()

    def extract_step_descriptions(self, doc, metadata: Dict[str, str]) -> List[str]:
        descriptions: List[str] = []
        print("   Searching for 'Notes and guidance' sections...")

        for page_num in range(len(doc)):
            text = self.extract_text_from_page(doc[page_num])
            if not text or "Notes and guidance" not in text:
                continue

            if not self._page_matches_metadata(text, metadata):
                continue

            lines = text.split("\n")
            for line_idx, line in enumerate(lines):
                if "Notes and guidance" in line:
                    description = self.extract_description_below_notes(lines, line_idx)
                    if description:
                        descriptions.append(description)
                    break

        return descriptions

    def process_pdf(self, pdf_path: str) -> Optional[Dict[str, object]]:
        filename = os.path.basename(pdf_path)
        print(f"\nProcessing: {filename}")

        metadata = self.parse_filename(filename)

        try:
            doc = fitz.open(pdf_path)
            topic = self.extract_topic_from_filename(metadata)

            small_steps = self.extract_small_step_titles(doc, metadata)
            descriptions = self.extract_step_descriptions(doc, metadata)
            doc.close()

            print(f"   Found {len(small_steps)} step titles and {len(descriptions)} descriptions")
            if len(small_steps) != len(descriptions):
                print("   Warning: titles/descriptions count mismatch")

            return {
                "year": metadata["year"],
                "term": metadata["term"],
                "block": metadata["block"],
                "difficulty": metadata.get("difficulty", ""),
                "topic": topic,
                "sub_topic": metadata["sub_topic"],
                "small_steps": small_steps,
                "descriptions": descriptions,
                "source_pdf_path": str(Path(pdf_path).as_posix()),
                "source_pdf_name": filename,
            }
        except Exception as exc:
            print(f"   Error processing {filename}: {exc}")
            return None

    def create_dynamic_row(self, data: Dict[str, object]) -> Dict[str, object]:
        row: Dict[str, object] = {
            "year": data["year"],
            "term": data["term"],
            "block": data["block"],
            "difficulty": data.get("difficulty", ""),
            "topic": data["topic"],
            "sub_topic": data["sub_topic"],
        }

        for i, step in enumerate(data["small_steps"], 1):
            row[f"small_step_{i}"] = step

        for i, desc in enumerate(data["descriptions"], 1):
            row[f"SS{i}_desc"] = desc

        return row

    def create_flat_rows(self, data: Dict[str, object]) -> List[Dict[str, object]]:
        steps = [clean_text(s) for s in data.get("small_steps", [])]
        descs = [clean_text(d) for d in data.get("descriptions", [])]
        # Anchor row count to step titles where available; this avoids creating
        # synthetic blank-step rows when a PDF yields an extra description.
        row_count = len(steps) if steps else len(descs)
        rows: List[Dict[str, object]] = []

        for idx in range(row_count):
            step_name = steps[idx] if idx < len(steps) else ""
            ss_desc = descs[idx] if idx < len(descs) else ""

            confidence = "high"
            needs_manual_review = False

            if not step_name or not ss_desc:
                confidence = "low"
                needs_manual_review = True
            elif len(steps) != len(descs):
                confidence = "medium"

            rows.append(
                {
                    "year": data["year"],
                    "term": data["term"],
                    "block": data["block"],
                    "difficulty": data.get("difficulty", ""),
                    "topic": data["topic"],
                    "sub_topic": data["sub_topic"],
                    "small_step_num_in_topic": idx + 1,
                    "small_step_name": step_name,
                    "ss_wr_desc_extracted": ss_desc,
                    "source_pdf_path": data.get("source_pdf_path", ""),
                    "source_pdf_name": data.get("source_pdf_name", ""),
                    "source_pdf_hash": "",
                    "extraction_confidence": confidence,
                    "match_method": "",
                    "is_duplicate_candidate": False,
                    "needs_manual_review": needs_manual_review,
                    "review_notes": "" if not needs_manual_review else "Missing step title or description",
                    "small_step_id": "",
                    "small_step_key": "",
                    "topic_normalized": normalize_topic_for_match(clean_text(data.get("topic", ""))),
                }
            )

        return rows

    def process_folder(self, folder_path: str) -> None:
        folder = Path(folder_path)
        if not folder.exists():
            print(f"Error: Folder not found: {folder_path}")
            return

        pdf_files = sorted(folder.glob("*.pdf"))
        if not pdf_files:
            print(f"No PDF files found in: {folder_path}")
            return

        print("\n" + "=" * 80)
        print(f"Processing folder: {folder_path}")
        print(f"Found {len(pdf_files)} PDF files")
        print("Hybrid extraction mode enabled")
        print("=" * 80)

        successful = 0
        failed = 0
        skipped = 0

        for pdf_file in pdf_files:
            if pdf_file.name in self.skip_files:
                print(f"\nSkipping: {pdf_file.name} (in skip list)")
                skipped += 1
                continue

            data = self.process_pdf(str(pdf_file))
            if not data:
                failed += 1
                continue

            if self.flat_output:
                rows = self.create_flat_rows(data)
                if rows:
                    self.all_data.extend(rows)
                    successful += 1
                else:
                    failed += 1
            else:
                if data.get("small_steps"):
                    self.all_data.append(self.create_dynamic_row(data))
                    successful += 1
                else:
                    failed += 1

        print("\n" + "=" * 80)
        print(f"Completed: {successful} successful, {failed} failed, {skipped} skipped")
        print("=" * 80)

    def save_csv(self) -> None:
        if not self.all_data:
            print("No data to save")
            return

        new_df = pd.DataFrame(self.all_data)

        if self.append_mode and os.path.exists(self.output_csv):
            existing_df = pd.read_csv(self.output_csv, encoding="utf-8-sig")
            df = pd.concat([existing_df, new_df], ignore_index=True)
            print(f"Appending to existing CSV. Existing rows: {len(existing_df)} | New rows: {len(new_df)}")
        else:
            df = new_df

        if self.flat_output:
            ordered_cols = [
                "year",
                "term",
                "block",
                "difficulty",
                "topic",
                "sub_topic",
                "small_step_num_in_topic",
                "small_step_name",
                "ss_wr_desc_extracted",
                "source_pdf_path",
                "source_pdf_name",
                "source_pdf_hash",
                "extraction_confidence",
                "match_method",
                "is_duplicate_candidate",
                "needs_manual_review",
                "review_notes",
                "small_step_id",
                "small_step_key",
                "topic_normalized",
            ]
            df = df[[col for col in ordered_cols if col in df.columns]]
        else:
            fixed_cols = ["year", "term", "block", "difficulty", "topic", "sub_topic"]
            small_step_cols = sorted(
                [col for col in df.columns if col.startswith("small_step_")],
                key=lambda x: int(x.split("_")[-1]),
            )
            desc_cols = sorted(
                [col for col in df.columns if col.startswith("SS") and col.endswith("_desc")],
                key=lambda x: int(re.search(r"SS(\d+)_desc", x).group(1)),
            )
            ordered_cols = fixed_cols + small_step_cols + desc_cols
            ordered_cols = [col for col in ordered_cols if col in df.columns]
            df = df[ordered_cols]

        df.to_csv(self.output_csv, index=False, encoding="utf-8-sig")
        print("\n" + "=" * 80)
        print(f"CSV saved: {self.output_csv}")
        print(f"Rows: {len(df)}")
        print(f"Columns: {len(df.columns)}")
        print("=" * 80)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract curriculum data using hybrid approach",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--folder", required=True, help="Path to folder with PDFs")
    parser.add_argument("--output", default="curriculum_data_hybrid.csv", help="Output CSV path")
    parser.add_argument("--skip", nargs="*", default=[], help="Files to skip")
    parser.add_argument("--append", action="store_true", help="Append to existing CSV")
    parser.add_argument(
        "--flat",
        action="store_true",
        help="Write one-row-per-small-step flat output for backfill workflows",
    )

    args = parser.parse_args()

    extractor = PDFCurriculumExtractorHybrid(
        output_csv=args.output,
        skip_files=args.skip,
        append_mode=args.append,
        flat_output=args.flat,
    )

    try:
        extractor.process_folder(args.folder)
    except KeyboardInterrupt:
        print("\nProcessing interrupted by user")
    finally:
        extractor.save_csv()


if __name__ == "__main__":
    main()
