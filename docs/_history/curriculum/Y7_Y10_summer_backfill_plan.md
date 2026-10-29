# Y7-Y10 Summer `ss_wr_desc` Backfill Plan (No-Code)

## 1) Purpose
Backfill missing White Rose small-step descriptions (`ss_wr_desc`) for newly published Summer content in Years 7-10, while preserving current flat-schema compatibility and downstream stability.

Primary canonical target remains:
- `Curriculum/Maths/curriculum_22032026_small_steps.csv`

Subproject root for all planning and execution outputs:
- `Curriculum/Maths/pdf_extractor/`

## 2) Scope
In scope:
- Source PDFs under `WR_PDF/Year 7/y7_summer_backfill`, `WR_PDF/Year 8/y8_summer_backfill`, `WR_PDF/Year 9/y9_summer_backfill`, `WR_PDF/Year 10/y10_summer_backfill/foundation`, `WR_PDF/Year 10/y10_summer_backfill/higher`
- Reuse/adapt extraction logic from `Curriculum/Maths/pdf_extractor/extract_pdf_curriculum_hybrid.py`
- Produce flat, one-row-per-small-step backfill output keyed by canonical identifiers
- Controlled update of `ss_wr_desc` in `Curriculum/Maths/curriculum_22032026_small_steps.csv`

Out of scope:
- Wholesale rewrite of all `ss_wr_desc`
- Non-summer terms
- Non-Year 7-10

## 3) Current-State Findings (Important for Design)
- Existing extractor outputs legacy wide rows (`small_step_1...`, `SS1_desc...`) and does not output canonical `small_step_id`/`small_step_key`.
- Existing extractor metadata parse is incomplete for some modern filenames (notably Y10 old-format files with no `SOL` token in name).
- Existing extractor does not recurse subfolders, so it would miss `y7_summer_backfill`, `y8_summer_backfill`, `y9_summer_backfill`, and Y10 `foundation`/`higher` unless explicitly targeted.
- Canonical downstream system expects flat rows with stable identifiers, and many tools consume `ss_wr_desc` directly.

Confirmed operator choice:
- Manual subfolder targeting is accepted and preferred for this project (no recursive scan required if each target subfolder is explicitly run).

## 4) Risks You Already Flagged (Confirmed)
1. Identifier mismatch risk: extractor output not keyed to flat identifiers (`small_step_id`, `small_step_key`).
2. Shape mismatch risk: extractor emits wide block-format columns (`SS{i}_desc`) instead of one-row-per-step flat output.
3. Duplicate PDF risk: duplicated B1 PDFs in root year folders and backfill subfolders can cause duplicate extraction and accidental overwrite churn.

## 5) Additional Bugs/Risks To Account For
1. Folder traversal gap:
- Current extractor only reads `*.pdf` directly in one folder (non-recursive). It will silently miss nested folders unless process is repeated per subfolder.
- For this project, this is mitigated by manually running each required subfolder explicitly.

2. Filename parser fragility (Y10 variants):
- Pattern currently requires `SOL` in old-format Y10 names. Some files like `Y10 Autumn Block 3 Foundation Quadratic expressions and equations.pdf` do not include `SOL`.
- If parser fails, metadata becomes `Unknown`, breaking joins.

3. Abbreviation mismatch on term names:
- New filename parser returns `SPR`/`SUM`; canonical dataset uses `Spring`/`Summer`.
- Without normalization, joins to canonical rows can fail.

4. Filename nomenclature drift (old vs new naming patterns):
- Old style example: `Y7 Spring Block 4 SOL Fractions and percentages of amounts.pdf`
- New style example: `WRE Maths v3 Y7 SUM B1 SOL - Speed distance and time .pdf`
- Parser must support both patterns in the same run and normalize to canonical values.

5. Topic/sub_topic lexical drift:
- Filename-derived topic strings may differ from canonical `topic` labels (hyphenation, punctuation, title variants).
- Reliance on text matching alone will produce false non-matches.

6. Step-title extraction sensitivity:
- Summary page logic expects lines like `Step N` then title line; some PDFs may merge text, split lines, or alter heading typography.
- Missing/shifted titles can desync title list vs description list.

7. Description boundary drift:
- Extraction is bounded by `Notes and guidance` and `Things to look out for` text markers.
- If marker text changes (capitalization/punctuation/line wraps), partial or empty descriptions may occur.

8. One-description-per-page assumption:
- Extractor breaks after first `Notes and guidance` hit per page; multi-step layouts on a single page could be truncated.

9. Duplicate step keys across difficulty tracks:
- Y10 Foundation/Higher need strict difficulty-aware keys in matching and update logic.
- Any blank/normalized difficulty collision can overwrite the wrong row.

10. Empty-overwrite hazard:
- If extraction yields empty strings for a matched step and update writes blindly, good existing `ss_wr_desc` can be erased.

11. Unicode/punctuation normalization mismatches:
- En dash/hyphen/apostrophe variants in small step names can cause failed joins unless normalized consistently.

12. Encoding surprises:
- Existing files use UTF-8 content; if a backfill artifact is written with BOM or different quoting unexpectedly, downstream diffs and tooling may be noisy.

13. Idempotency gap:
- Re-running without deterministic dedupe rule can produce non-repeatable outputs (different winner row for same step).

## 6) Target Data Contract For Backfill Output
Backfill extraction output (planned) should be a flat CSV, one row per candidate update, with at least:
- `small_step_id`
- `small_step_key`
- `year`
- `term`
- `difficulty`
- `topic`
- `small_step_num_in_topic`
- `small_step_name`
- `ss_wr_desc_extracted`
- `source_pdf_path`
- `source_pdf_name`
- `source_pdf_hash` (optional but recommended)
- `extraction_confidence` (e.g., `high|medium|low`)
- `match_method` (e.g., `id_exact|key_exact|metadata+name_fuzzy`)
- `is_duplicate_candidate` (boolean)
- `needs_manual_review` (boolean)
- `review_notes`

All run artifacts for this subproject should remain in `Curriculum/Maths/pdf_extractor/`.

## 7) Planned Deliverables (All in Subproject Folder)
1. `Y7_Y10_summer_backfill_plan.md` (this plan)
2. `Y7_Y10_summer_backfill_risk_register.csv`
3. `y7_y10_backfill_inventory.csv` (PDF inventory + duplicate flags)
4. `y7_y10_backfill_extracted_flat.csv` (candidate flat extraction)
5. `y7_y10_backfill_match_report.csv` (match outcomes vs canonical)
6. `y7_y10_backfill_update_preview.csv` (before/after, no-write preview)
7. `y7_y10_backfill_manual_review_queue.csv` (ambiguous/missing matches)
8. `y7_y10_backfill_validation_report.md` (post-run QA summary)

## 8) Execution Plan (No-Code Phases)
## Phase A: Inventory and de-duplication
- Inventory all target PDFs in backfill subfolders.
- Build duplicate map against year-root PDFs.
- Apply deterministic precedence: prefer backfill-subfolder copy over year-root copy for summer backfill run.

Exit criteria:
- One chosen source PDF per intended Year/Term/Block/Difficulty tuple.

## Phase B: Controlled extraction run design
- Use extractor logic as baseline, but define normalization rules before matching:
  - Term mapping: `AUT->Autumn`, `SPR->Spring`, `SUM->Summer`
  - Difficulty mapping: `F->Foundation`, `H->Higher`, blank preserved for Y7-9
  - Filename pattern support: both legacy (`Yx Term Block n ...`) and v3 (`WRE Maths v3 Yx AUT|SPR|SUM Bn ...`)
  - String normalization for joins (whitespace, dash, apostrophe)
- Produce flat extraction candidates (one row per small step), not wide `SS{i}` columns.

Manual run mode:
- Execute extraction separately for each backfill subfolder:
  - `WR_PDF/Year 7/y7_summer_backfill`
  - `WR_PDF/Year 8/y8_summer_backfill`
  - `WR_PDF/Year 9/y9_summer_backfill`
  - `WR_PDF/Year 10/y10_summer_backfill/foundation`
  - `WR_PDF/Year 10/y10_summer_backfill/higher`

Exit criteria:
- Flat candidate file complete for all target PDFs.

## Phase C: Canonical matching to small-step IDs
- Match candidates to canonical rows in `curriculum_22032026_small_steps.csv` using priority:
  1) exact (`year`,`term`,`difficulty`,`topic`,`small_step_num_in_topic`,`small_step_name`)
  2) exact on `small_step_key` reconstruction
  3) constrained fuzzy name match within same year/term/difficulty/topic/step number
- Route any non-unique match to manual review queue.

Exit criteria:
- 100% rows either matched uniquely or routed to explicit manual queue.

## Phase D: Safe update preview
- Build preview diff with columns:
  - `small_step_id`, `ss_wr_desc_before`, `ss_wr_desc_after`, `change_type`, `source_pdf_name`
- Enforce write guards:
  - never overwrite non-empty with empty
  - never update if match confidence below threshold
  - never update rows outside Y7-Y10 Summer scope

Exit criteria:
- Human-reviewable preview approved.

## Phase E: Canonical update and validation
- Apply approved updates to canonical CSV only.
- Validate downstream compatibility checks:
  - no row count change
  - no identifier change (`small_step_id`, `small_step_key` unchanged)
  - `% non-empty ss_wr_desc` improves only in intended scope
  - random spot-checks by year/difficulty/topic

Exit criteria:
- Validation report confirms no regressions and scoped improvements.

## 9) Quality Gates / Acceptance Criteria
- AC1: Only Y7-Y10 Summer rows are modified.
- AC2: `small_step_id` and `small_step_key` are unchanged for all rows.
- AC3: No non-empty `ss_wr_desc` becomes empty.
- AC4: Duplicate-source handling is deterministic and documented.
- AC5: Y10 Foundation/Higher never cross-overwrite each other.
- AC6: Manual-review queue exists for all uncertain matches.
- AC7: Downstream file consumers continue loading without schema change.

## 10) Rollback Plan
- Keep timestamped backup copy of canonical CSV before write.
- Persist update preview and applied diff in subproject folder.
- Rollback method: restore backup file and rerun validation checks.

## 11) Suggested Run Order
1. Inventory + duplicate map
2. Extraction to flat candidate dataset
3. Canonical matching report
4. Manual review for unresolved/ambiguous items
5. Update preview sign-off
6. Apply updates
7. Post-update validation report

## 12) Decision Log (Initial)
- Canonical source remains `Curriculum/Maths/curriculum_22032026_small_steps.csv`.
- Backfill is targeted and additive, not wholesale rewrite.
- Keep all project outputs in `Curriculum/Maths/pdf_extractor/`.
- Manual subfolder execution is approved and will be used instead of recursive folder walking.
- Filename nomenclature normalization must support both old and v3 names in one pipeline.

## 13) Command Blueprint (After Script Adaptation)
These are the intended run commands once extractor and merge scripts are adapted to flat output and safe canonical merge.

Extraction (per subfolder):
1. `python Curriculum/Maths/pdf_extractor/extract_pdf_curriculum_hybrid.py --folder "WR_PDF/Year 7/y7_summer_backfill" --output "Curriculum/Maths/pdf_extractor/y7_y10_backfill_extracted_flat.csv" --flat`
2. `python Curriculum/Maths/pdf_extractor/extract_pdf_curriculum_hybrid.py --folder "WR_PDF/Year 8/y8_summer_backfill" --output "Curriculum/Maths/pdf_extractor/y7_y10_backfill_extracted_flat.csv" --flat --append`
3. `python Curriculum/Maths/pdf_extractor/extract_pdf_curriculum_hybrid.py --folder "WR_PDF/Year 9/y9_summer_backfill" --output "Curriculum/Maths/pdf_extractor/y7_y10_backfill_extracted_flat.csv" --flat --append`
4. `python Curriculum/Maths/pdf_extractor/extract_pdf_curriculum_hybrid.py --folder "WR_PDF/Year 10/y10_summer_backfill/foundation" --output "Curriculum/Maths/pdf_extractor/y7_y10_backfill_extracted_flat.csv" --flat --append`
5. `python Curriculum/Maths/pdf_extractor/extract_pdf_curriculum_hybrid.py --folder "WR_PDF/Year 10/y10_summer_backfill/higher" --output "Curriculum/Maths/pdf_extractor/y7_y10_backfill_extracted_flat.csv" --flat --append`

Safe insert to canonical small-steps file (planned dedicated merge command):
1. `python Curriculum/Maths/pdf_extractor/merge_backfill_ss_wr_desc.py --canonical "Curriculum/Maths/curriculum_22032026_small_steps.csv" --backfill "Curriculum/Maths/pdf_extractor/y7_y10_backfill_extracted_flat.csv" --preview "Curriculum/Maths/pdf_extractor/y7_y10_backfill_update_preview.csv" --manual-review "Curriculum/Maths/pdf_extractor/y7_y10_backfill_manual_review_queue.csv"`
2. `python Curriculum/Maths/pdf_extractor/merge_backfill_ss_wr_desc.py --canonical "Curriculum/Maths/curriculum_22032026_small_steps.csv" --backfill "Curriculum/Maths/pdf_extractor/y7_y10_backfill_extracted_flat.csv" --apply --backup "Curriculum/Maths/pdf_extractor/curriculum_22032026_small_steps.pre_backfill.csv"`
