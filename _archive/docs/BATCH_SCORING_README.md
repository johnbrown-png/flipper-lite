# Archived Batch Instruction Quality Scoring System

**Archived:** March 8, 2026  
**Reason:** Legacy system replaced by curriculum-informed scoring

## What This Was

The batch scoring system was an earlier approach to evaluating video instruction quality. It scored videos generically using GPT-4o-mini without any curriculum context, age-specific criteria, or small step objectives.

## Why It Was Archived

After initial testing, it became clear that **curriculum context is critical** for meaningful instruction quality scores. A video that's excellent for teaching one concept to 10-year-olds might be poor for teaching a different concept to 5-year-olds.

The generic batch scores lacked:
- Age-appropriate language evaluation
- Alignment with specific curriculum small steps
- Context about what concept should be taught
- Differentiation between learning objectives

## Archived Files

- **batch_generic_instruction_scorer.py** (formerly `score_instruction_quality.py`)  
  Command-line tool for batch scoring videos from inventory or API cache

- **batch_generic_review_scores.py** (formerly `review_instruction_scores.py`)  
  Tool for reviewing and analyzing batch scores (top/bottom/ranges/samples)

## Current System (March 2026)

Instruction quality scoring is now **curriculum-informed** and integrated directly into `flipper.py`:

- **Scoring location:** Happens at runtime during small step searches
- **Context-aware:** Each score includes age, curriculum topic, and specific small step
- **Cache file:** `data/instruction_quality_runtime_cache.json`
- **Scoring function:** `InstructionQualityScorer.score_for_curriculum_context_async()`

### Cache Key Format
```
{video_id}|{age}|{small_step}
```

Same video can have different scores for different contexts (age/curriculum).

## Preserved for Research

These files are kept for:
- Understanding the evolution of the scoring system
- Research into generic vs. curriculum-specific quality metrics
- Potential future experiments comparing approaches
- Reference for similar batch processing tasks

## Data Cleanup

The generic batch scores file (`data/video_instruction_quality.json` with 13 scores) was deleted during archival as these scores:
- Lacked curriculum context
- Were never used by the production system
- Could cause confusion with the curriculum-informed cache

All future scoring uses curriculum-informed evaluation only.
