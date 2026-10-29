# FAISS Query Comparator Test — Design Document

## Confirmed Pipeline Facts

### Embedding model
`text-embedding-3-large`, 3072 dimensions — same model used to index video transcripts (see `query_embedder.py`).

### Exact FAISS query string used by `precompute_curriculum_recommendations.py`

```python
query_text = f"{topic}: {small_step}"
if small_step_desc:
    query_text += f" - {small_step_desc}"
```

`small_step_desc` is loaded from `SS{step_num}_desc` (line 217–218). The complete query therefore is:

> `"{Topic}: {Small Step label} - {SS{i}_desc full text}"`

No truncation, weighting or preprocessing is applied. The entire long White Rose description paragraph is appended.

### Script that produced `SS{i}_desc_short`
`_archive/curriculum_shortener.py` — GPT-4 batch compression from ~140 words → ~50 words.
The output columns (`SS{i}_desc_short`) are already written into the live curriculum CSV:
`Curriculum/Maths/curriculum_22032026.csv`.

`search_app/curriculum_assistant.py` **reads** `SS{i}_desc_short` for display only; it does not create it.

---

## Four Comparator Types

| Label | Source | Description |
|-------|--------|-------------|
| **Original** | `SS{i}_desc` | Full White Rose curriculum description, ~140 words. Currently used by `precompute_curriculum_recommendations.py`. |
| **Short** | `SS{i}_desc_short` | GPT-4 compressed version, ~50 words. Already present in the CSV. Acts as a control / ablation. |
| **Manual** | Hand-authored string | Human-created search string targeting the precise learning objective. Ignores background context entirely. |
| **Hybrid** | Hand-edited `SS{i}_desc` | Human removes distractor clauses about prior learning history, replaces ambiguous mathematical phrasing with precise language, but retains structural framing. |

---

## Worked Example — Mass and capacity / Use scales (Year 3 Spring)

This is the motivating row. CSV source rows are around line 2139 of `precomputed_recommendations_flat.csv`.

### Original (current, ~140 words)
```
Mass and capacity: Use scales - In Year 2, children began using grams and kilograms when
exploring mass. In this block, children continue to explore mass in kilograms and grams before
moving on to capacity. An essential skill in this block is for children to be able to use and
understand scales. This small step provides opportunity for children to become more familiar with
using scales to read measurements. The focus is on dividing 100 into 2/4/5/10 equal parts using
number lines, before applying this skill in various contexts later in the block. By working out what
the interval gaps are on a number line, children become more experienced at reading scales in the
context of measurement. They learn what size groups are made when 100 is split into equal parts,
then extend this learning to other multiples of 100.
```
**FAISS top-1 result:** `SdmfsBgR2lI` — "Reception Numeracy - Comparing capacity - holds more/holds less" (cosmetic similarity score 0.711)  
**Problem:** The model latches onto "capacity", "mass", and "100" scattered through the noisy background, returning a Reception-level capacity video unrelated to the actual step (reading/dividing scales).

### Short (~50 words, GPT-4 compressed)
```
In Year 2, students progress from using grams and kilograms to explore mass, to understanding
capacity. They learn to use scales and read measurements, focusing on dividing 100 into equal parts
using number lines. This skill is applied in various contexts, enhancing their ability to read scales
and comprehend equal partitioning of multiples of 100.
```
**Still contains** prior-learning context ("Year 2", "progress from") and the capacity misdirection. Likely to have similar retrieval issues.

### Manual (human-authored)
```
Weight, mass and capacity in kilograms and grams dividing scales of weight measurement into
scales of 100
```
**Result reported by user:** Returns a topic-relevant video recommendation.  
**Why it works:** Strips all background context, foregrounds exact skill terms, specifies the mathematical operation (dividing into scales of 100).

### Hybrid (to be authored)
A version of the Original text with the following edits applied:
- Remove the prior-learning intro ("In Year 2, children began using...")
- Remove forward references to later blocks ("before moving on to capacity", "applying this skill in various contexts later in the block")
- Replace "dividing 100 into 2/4/5/10 equal parts using number lines" with "reading measurement scales calibrated in intervals of 100, 50, 25, 20 and 10"
- Retain the context about interval gaps and multiples of 100

**Proposed Hybrid draft:**
```
Children use and understand reading scales to take measurements. The focus is on reading scales
calibrated in intervals of 100, 50, 25, 20 and 10. By working out the interval gaps on a number
line, children become more experienced at reading scales in the context of weight measurement.
They extend this to other multiples of 100.
```

---

## Proposed Test Harness Design

### Purpose
Run all four comparator query strings through the FAISS index for a set of target curriculum steps and compare the top-K results by video ID, title, and cosine similarity score.

### Inputs
- A test set of ~10–20 failing curriculum rows identified from `precomputed_recommendations_flat.csv`
- For each row: `topic`, `small_step`, and the four comparator query strings (Original, Short, Manual, Hybrid)
- The live FAISS index at `data/faiss_index/faiss_index.bin`

### Output
A CSV with columns:
```
row_id, topic, small_step, comparator_type, query_text, rank, video_id, title, cosine_similarity
```

### Query template options to test
Three query construction templates should be compared, not just the text source:

| Template ID | Format |
|------------|--------|
| T1 (current) | `"{topic}: {small_step} - {desc}"` |
| T2 | `"{small_step}: {desc}"` (remove topic from prefix) |
| T3 | `"{desc}"` (desc string only, no prefix) |

### Suggested test set — known failing rows
Based on the working example, the test set should include:
- Year 3, Mass and capacity, Small Step 1 (Use scales) — confirmed failing
- Additional failing rows to be identified by reviewing `precomputed_recommendations_flat.csv` for low `semantic_score` (< 0.75) or obviously off-topic video titles

---

## Candidate Script: `compare_queries.py`

To be created in `Improve_pick/`. The script should:
1. Accept a CSV of test rows (topic, small_step, and comparator query strings)
2. Load the FAISS index via `query_embedder.QueryEmbedder` and `faiss.read_index`
3. For each row, build all four comparator query strings and all three templates
4. Run each query through FAISS, collect top-5 video IDs and cosine similarities
5. Write results to `Improve_pick/comparator_results.csv`

**No implementation yet — awaiting explicit instruction.**

---

## Next Steps (recommended)

1. Build the test row CSV (`Improve_pick/test_rows.csv`) with 10–20 failing examples.
2. Add Manual and Hybrid text for each row.
3. Implement `compare_queries.py` once test rows are ready.
4. Analyse output CSV to identify which comparator type and which query template performs best on the test set.
5. Use findings to decide whether the fix is a curriculum CSV pre-processing step, a change to the query assembly code in `precompute_curriculum_recommendations.py`, or both.
