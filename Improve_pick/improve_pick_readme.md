# Improve Pick

## Summary

This sub-project is dedicated to investigating and improving the semantic retrieval stage that powers curriculum video recommendations in `precompute_curriculum_recommendations.py`.

The core objective is to make FAISS returns from the `text-embedding-3-large` style retrieval workflow more closely match the true learning objective of each curriculum small step. The main focus is the first query sent into the FAISS index, especially when it is built from `topic`, `Small Step`, `SS{i}_desc`, and related descriptive fields.

## Problem Statement

Some curriculum description strings, especially `SS{i}_desc` and `SS{i}_desc_short`, are too broad, noisy, or internally mixed. They often contain distractor terms or background context that dilute the main mathematical intent of the small step. When these strings are embedded and sent to FAISS, the nearest-neighbour results can drift toward loosely related videos instead of the most instructionally relevant ones.

The practical goal of this sub-project is to identify why those descriptions underperform and to refine the retrieval text so that recommended videos are more tightly aligned to the intended learning goals.

## Motivating Example

In `precomputed_recommendations_flat.csv` around the `Mass and capacity` topic, the `Use scales` step includes the following long description in `SS1_desc`:

> In Year 2, children began using grams and kilograms when exploring mass. In this block, children continue to explore mass in kilograms and grams before moving on to capacity. An essential skill in this block is for children to be able to use and understand scales. This small step provides opportunity for children to become more familiar with using scales to read measurements. The focus is on dividing 100 into 2/4/5/10 equal parts using number lines, before applying this skill in various contexts later in the block. By working out what the interval gaps are on a number line, children become more experienced at reading scales in the context of measurement. They learn what size groups are made when 100 is split into equal parts, then extend this learning to other multiples of 100.

That query currently recommends video `SdmfsBgR2lI`, which is not tightly matched to the intended objective. A shorter, human-authored alternative such as the text below produces a more relevant topic match:

> Weight, mass and capacity in kilograms and grams dividing scales of weight measurement into scales of 100.

This example suggests that retrieval quality is sensitive to how strongly the query foregrounds the true learning target and how effectively it suppresses distractor phrasing.

## Investigation Goals

1. Determine how the retrieval query is currently composed in `precompute_curriculum_recommendations.py`.
2. Identify common failure patterns in `SS{i}_desc` and `SS{i}_desc_short`, including verbosity, mixed objectives, and distractor vocabulary.
3. Test whether more compact, objective-led query rewrites improve FAISS recall for curriculum-relevant videos.
4. Establish repeatable diagnostics and scripts for comparing baseline and revised query strings.
5. Recommend code or data-processing changes that measurably improve topic relevance.

## Working Rules

- All documents, scripts, notes, and command recipes for this sub-project should live inside `Improve_pick`.
- The only expected exception is the VS Code custom agent registration file, which must live in `.github/agents/improve_pick.agent.md` to be discoverable by Copilot Chat.
- Changes should be evidence-led. Each proposed improvement should compare the baseline retrieval text against at least one revised alternative.
- Keep the work focused on improving the initial semantic retrieval before changing downstream ranking unless evidence points elsewhere.

## Suggested Work Products

- A small reproducible test set of failing curriculum rows.
- Scripts for replaying FAISS retrieval with baseline and revised descriptions.
- Notes on which wording patterns help or hurt semantic search.
- A shortlist of candidate strategies, such as query compression, keyword foregrounding, distractor removal, or structured query templates.

## Primary Code Touchpoints

- `precompute_curriculum_recommendations.py`
- `query_embedder.py`
- `precomputed_recommendations_flat.csv`

## Immediate Next Step

Build a small evidence pack in `Improve_pick` that compares the current query text against hand-refined alternatives for several failing rows, then use that evidence to decide whether the best intervention is query rewriting, field selection, preprocessing, or ranking adjustment.

---

## Phase 1 Findings — Comparator Test Results (April 2026)

The four-comparator test harness (`compare_queries.py`) was run on the motivating example (Year 3, Mass and capacity, Use scales). Results confirmed the following:

- **Manual** (human-written, ~15 words) and **Hybrid** (LLM-assisted edit of `SS{i}_desc` with distractor removal) both returned substantially more topic-relevant video recommendations than either the Original or Short strings.
- **Original** (`SS{i}_desc`, ~140 words) produced poor matches. The embedding was dominated by the prior-learning preamble and capacity misdirection, pulling results toward unrelated Reception-level capacity videos.
- **Short** (`SS{i}_desc_short`, GPT-4o compressed to ~50 words) did not materially improve on Original. The compression preserved the prior-learning framing and the capacity misdirection, so the retrieval drift transferred to the shorter string almost unchanged.

### Key conclusion

The FAISS index matches on **vocabulary density**, not intent. Long preamble paragraphs flood the embedding with contextually irrelevant tokens and dilute the signal from the actual learning objective. The current shortening strategy (`_archive/curriculum_shortener.py`) compresses length but preserves the noise patterns that cause poor retrieval.

---

## Phase 2 Plan — Selective LLM Rewriting of `SS{i}_desc`

### Rationale

Not all `SS{i}_desc` strings will be equally problematic. Many White Rose descriptions are adequately specific and will produce good FAISS matches as-is. The aim is to identify and rewrite only the ambiguous ones, not all descriptions.

### Step 1 — Manual sampling to identify and confirm rules

A sample of full `SS{i}_desc` texts will be reviewed manually to identify recurring patterns that introduce retrieval ambiguity. Candidate patterns to look for and validate:

| Pattern type | Examples to look for |
|---|---|
| Prior-learning preamble | "In Year X, children began...", "Building on...", "Having already..." |
| Forward references | "before moving on to...", "in contexts later in the block", "applying this skill in various contexts" |
| Exploration/experience language | "opportunity to explore", "become familiar with", "experience working with", "continue to..." |
| Topic-mixing | Step mentions two topics (e.g. mass and capacity) when the step is only about one |
| Ambiguous mathematical purpose | "continue", "explore", "experience" used where a specific operation (add, compare, convert, read, divide) would be more accurate |

Manual review will either confirm these patterns are reliably problematic or identify additional patterns not yet anticipated.

### Step 2 — Revise rules based on findings

Rules will be refined after manual inspection before being used to guide any automated pass, to avoid encoding assumptions that do not hold across the full curriculum.

### Step 3 — LLM classification pass

Once rules are validated, an LLM classification pass will flag each `SS{i}_desc` as needing rewriting or not. This is a lighter-touch pass than rewriting — the classifier only needs to identify which strings contain the problematic patterns.

### Step 4 — LLM rewriting of flagged strings

For flagged strings, a tightly specified rewriting prompt will instruct the LLM to:

- Remove prior-learning history and forward references
- Replace open-ended language ("explore", "become familiar with") with operational terms ("practise", "identify", "calculate", "apply", "read intervals on")
- Resolve ambiguous mathematical purpose into a specific named operation
- Protect named mathematical objects, units, and domain vocabulary (e.g. "kilograms and grams", "intervals of 100")
- Target 40–60 words, operational tone, beginning from the current step only

The rewriting prompt receives three anchors: the **small step label** (ground truth of intent), the **topic**, and the **original `SS{i}_desc`**.

### Step 5 — Quality control

Rewritten strings will be validated using the existing comparator harness. Any rewrite that scores worse than Short (the GPT-4o compressed baseline) on a known test case will be flagged for manual review before being accepted.

### Output column

Rewritten strings will be stored in a new column `SS{i}_desc_retrieval` in the curriculum CSV. This preserves `SS{i}_desc` (original) and `SS{i}_desc_short` (display) unchanged and gives `precompute_curriculum_recommendations.py` a clean, opt-in retrieval string to use.

---

## Current Status

| Step | Status |
|---|---|
| Comparator harness implemented (`compare_queries.py`) | Done |
| Motivating example tested | Done |
| Manual sampling to confirm rewriting rules | **Next** |
| Rule revision after manual review | Not started |
| LLM classification pass | Not started |
| LLM rewriting of flagged strings | Not started |
| QC with comparator harness | Not started |

---

## Session Continuation Note — Stricter LLM Appositeness Prompt (April 13, 2026)

### Goal of this change

For LLM-based appraisal/reranking, scoring should give materially higher reward to transcripts that explicitly teach the exact `ss_wr_desc` objective and strongly penalize near-miss or adjacent-topic transcripts.

### Proposed strict evaluation design (GPT-4o)

Use `ss_wr_desc` as the authoritative target and enforce:

- Dominant weight on objective match
- Evidence-based scoring from transcript quotes
- Hard caps when key objective is missing, only mentioned briefly, or replaced by adjacent-topic teaching

Recommended weighted components:

- `objective_match_score` (0-5), weight `0.55`
- `instructional_evidence_score` (0-5), weight `0.20`
- `depth_coverage_score` (0-5), weight `0.15`
- `age_stage_appropriateness_score` (0-5), weight `0.10`

Computation:

- `weighted_5pt = 0.55*objective_match + 0.20*instructional_evidence + 0.15*depth_coverage + 0.10*age_stage_appropriateness`
- `base_score_100 = round(weighted_5pt * 20)`
- Apply hard caps/penalties after base score.

Hard-penalty rules:

- If key objective is absent: `objective_match_score` must be `0` or `1`.
- If objective is only briefly mentioned without explanation: cap final score at `45`.
- If transcript is mostly adjacent-topic rather than target small-step: cap final score at `35`.
- If transcript teaches an incompatible/contradictory method: final score must be `<= 20`.

### Suggested prompt frame (ready to embed)

Role:

- "You are an educational relevance judge. Evaluate transcript appositeness to the target small-step objective in `ss_wr_desc`."

Core instruction:

- "Reward direct instructional alignment to the exact objective. Penalize generic overlap, adjacent-topic similarity, and missing key learning action."

Output:

- JSON-only output with:
	- `final_score`
	- component scores
	- `objective_presence` (`explicit|partial|absent`)
	- `evidence_quotes`
	- `objective_gap_reason`
	- `penalties_applied`
	- `confidence`

Decision bias rule:

- "Be strict. If uncertain between true objective alignment and adjacent similarity, choose the lower score."

### Why this is expected to help

- Prevents generous scoring for semantically related but instructionally wrong videos.
- Makes explicit objective teaching the primary signal.
- Produces audit-ready outputs (quotes + penalty tags) for later QA analysis.

### Next practical implementation step

Add this strict prompt as an optional scoring mode (for example, `strict_appositeness_v1`) in the Improve_pick QA flow so baseline vs strict scoring can be compared on the same test rows before promoting to default.

---

## Session Summary — Pipeline Restructure Discussion (April 14, 2026)

### User objective

Improve recommendation appositeness to intended curriculum objectives in `ss_wr_desc`, especially when objective details are specific (for example number ranges such as "up to 10").

### Current pipeline (as discussed)

1. Stage 1 semantic shortlist via FAISS chunk matching from curriculum objective text.
2. Stage 2 LLM scoring using `data_pipeline/instruction_quality_scorer.py` where alignment and pedagogy are currently mixed in one score.
3. Final blend currently weighted toward semantic plus instruction quality (commonly referenced as 60/40).

### Main problem identified

The current LLM instruction score already includes some alignment judgement, but alignment is not isolated as a first-class score. This allows some near-miss videos to survive if they are pedagogically decent, and makes objective-specific misses harder to control.

### Recommended architecture from this session

Adopt a **hybrid staged rerank**:

1. Stage 1: FAISS retrieval for broad recall.
2. Stage 1.5: Optional deterministic objective constraints gate (for explicit must-have/must-not-have conditions).
3. Stage 2: Dedicated LLM curriculum-alignment score (strict objective match).
4. Stage 3: Dedicated LLM instruction-quality score (pedagogy only, with alignment removed from rubric).
5. Final score: weighted blend where alignment is the dominant component, and alignment threshold/gating prevents misaligned videos from being rescued by pedagogy score.

Suggested starter blend discussed:

- `semantic = 0.25`
- `alignment = 0.55`
- `instruction = 0.20`

Suggested alignment floor for pass-through (tune in QA):

- `alignment >= 0.55` (start point)

### Cost-control guidance (important)

Avoid full dual-LLM scoring on all 40 FAISS candidates. Use progressive narrowing:

1. FAISS aggregate shortlist: ~20 videos.
2. After constraint gate: ~10 videos.
3. Alignment LLM: evaluate ~10.
4. Instruction LLM: evaluate only top ~5 alignment-pass videos.

This keeps call volume manageable while still improving objective specificity.

### Alternative considered: manual critical-parameter rules only

Discussed example: rules such as "exclude videos using numbers greater than 10".

Conclusion:

1. Rule-only method is low-cost and strong for hard boundaries.
2. Rule-only method is brittle and cannot fully replace semantic/LLM judgement.
3. Best cost-benefit is hybrid: deterministic rules for hard filters + LLM alignment for nuanced objective fit.

### QA GUI feasibility and plan

Feasible to extend `Improve_pick/gui_precompute_recommendation_qa.py` with an experimentation tab/panel containing:

1. Weight controls for semantic/alignment/instruction.
2. Shortlist size controls per stage.
3. Alignment threshold control.
4. Constraint toggle + simple parameter editor.
5. Per-video stage breakdown table (semantic, alignment, instruction, final, pass/fail reason, rank delta).
6. Cost estimator (expected LLM calls per small step under current settings).

### Prompt design split agreed

1. Alignment prompt should judge objective match strictly and report evidence/violations.
2. Instruction prompt should score pedagogical quality only (clarity, examples, sequencing, age appropriateness, engagement), without curriculum-alignment criterion.

### Practical phased rollout

1. Phase 1 (MVP): add constraint gate + dedicated alignment stage + revised blend.
2. Phase 2: split instruction stage and run only on alignment-pass finalists.
3. Phase 3: calibrate thresholds/weights by topic family using audit results.

### Note for future sessions

When comparing variants, track both quality and efficiency:

1. Top-k appositeness judgement (human QA).
2. Objective-violation rate (for explicit constraints).
3. LLM calls per small step (and cache hit rate).

Do not promote a heavier configuration unless appositeness gain justifies call growth.