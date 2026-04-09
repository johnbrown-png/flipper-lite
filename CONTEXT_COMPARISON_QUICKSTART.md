# Context Scope Comparison Test - Quick Start Guide

## What This Tests

**Critical Question:** Should learning exercises be generated from:
1. **First chunk only** (~250 tokens, 60-70 seconds) - Fastest, cheapest
2. **First 3 chunks** (~750 tokens, 3 minutes) - Balanced context
3. **Full transcript** (entire video) - Complete context, most expensive

This test generates exercises using all three approaches so you can compare quality.

---

## Prerequisites

1. **API Keys** - Add to your `.env` file:
   ```
   OPENAI_API_KEY=sk-...
   ANTHROPIC_API_KEY=sk-ant-...
   ```

2. **Install Dependencies**:
   ```powershell
   pip install anthropic
   ```

---

## Step 1: Run the Comparison Test

The script will randomly select 5 videos and test each with both models and all three context scopes.

```powershell
python llm_context_comparison_test.py --num-samples 5
```

**What happens:**
- Selects 5 random videos from `data/chunked_output/`
- For each video, generates 3 exercises (one per context scope)
- Tests with GPT-4o and Claude-3-Haiku
- Total tests: 5 videos × 2 models × 3 scopes = **30 exercises**

**Expected cost:** ~$0.15-0.25 (negligible)

**Output:** `context_comparison_results.json`

**Duration:** ~5-10 minutes

---

## Step 2: Evaluate the Results

Manually compare the exercises to determine which context scope produces the best quality:

```powershell
python evaluate_context_quality.py context_comparison_results.json
```

**What you'll do:**
- For each video+model combination, compare the 3 exercises side-by-side
- Rate each exercise (0-5 scale)
- Answer questions:
  - Which captures the main concept?
  - Which is most pedagogically sound?
  - Which uses appropriate scope?
  - Overall, which context is optimal?

**Output:** `context_comparison_results_evaluation.json`

---

## Step 3: Interpret the Results

Look at the summary statistics:

```json
{
  "recommended_context": "first_3_chunks",
  "average_scores": {
    "first_chunk": 3.2,
    "first_3_chunks": 4.5,
    "full_transcript": 4.3
  },
  "optimal_context_distribution": {
    "first_chunk": 2,
    "first_3_chunks": 6,
    "full_transcript": 2
  }
}
```

**Interpretation:**
- If `first_chunk` wins: Use chunk-level generation ✅ (cheapest, fastest)
- If `first_3_chunks` wins: Use 3-chunk context (balanced)
- If `full_transcript` wins: Need full transcript (more expensive)

---

## Decision Framework

### ✅ Use FIRST CHUNK if:
- Average score difference < 0.5 points
- 60%+ of evaluations choose first_chunk as optimal
- Your videos are self-contained micro-lessons

**Impact:** 
- Cost: $3.43 for 4,904 videos
- Speed: Fast parallel processing possible

---

### ⚖️ Use FIRST 3 CHUNKS if:
- Better than first_chunk by 0.5+ points
- Better pedagogical soundness
- Videos build concepts gradually

**Impact:**
- Cost: ~$10 for 4,904 videos
- Speed: Still very fast

---

### 🎯 Use FULL TRANSCRIPT if:
- Significantly better than chunk-level (1+ points)
- Concepts build across entire video
- Mathematical proofs or complex derivations

**Impact:**
- Cost: $10.30 for 4,904 videos (still negligible)
- Speed: Slower, still manageable

---

## What to Look For When Evaluating

### ❌ Poor Exercise (chunk too small):
```
Learning Objective: "Understand substitution"
Proof: "Explain what substitution is"
```
↳ Too vague, doesn't capture the actual lesson

### ✅ Good Exercise (chunk sufficient):
```
Learning Objective: "Substitute values into algebraic expressions and simplify"
Proof: "Given x=3, y=5, evaluate: 2x² + 3y - 4"
```
↳ Specific, testable, focused

### 🎯 Excellent Exercise (full context):
```
Learning Objective: "Apply substitution to solve simultaneous equations using elimination method"
Proof: "Solve: 2x + 3y = 13, x - y = 1"
```
↳ Captures full method, appropriate complexity

---

## Cost Comparison

| Context Scope | Avg Tokens | Cost per Exercise | Total Cost (4,904 videos) |
|---------------|------------|-------------------|---------------------------|
| First chunk   | 350        | $0.0007           | $3.43                     |
| First 3 chunks| 900        | $0.0018           | $8.80                     |
| Full transcript| 1,500     | $0.0021           | $10.30                    |

**Key Insight:** Even if full transcript is needed, the cost difference is only **$6.87** total. Quality >> cost at this scale.

---

## Next Steps After Testing

1. **If chunk-level works:**
   - Modify `llm_comparison_test.py` to use first chunk only
   - Run full generation on all 4,904 videos

2. **If full transcript needed:**
   - Modify extraction script to use full transcripts
   - May need to increase token limits for longer videos

3. **If results mixed:**
   - Implement hybrid approach:
     - Chunk-level for videos < 5 minutes
     - Full transcript for videos > 5 minutes
   - Use model_config.py tiered strategy

---

## Example Output

```
CONTEXT SCOPE COMPARISON SUMMARY
================================================================================

Context Scope Comparison (averaged across all models):

Scope                Avg Words    Avg Duration    Avg Tokens   Avg Cost    
------------------------------------------------------------------------------------
first_chunk          93          38s            350          $0.000721   
first_3_chunks       289         145s           897          $0.001845   
full_transcript      487         281s           1502         $0.002089   

================================================================================

GPT-4o:
  Scope                Tests    Avg Time     Avg Cost     Context              
  --------------------------------------------------------------------------------
  first_chunk          5        1.23s       $0.000850    93 words, 38s
  first_3_chunks       5        1.87s       $0.002456    289 words, 145s
  full_transcript      5        2.34s       $0.002781    487 words, 281s

Claude-3-Haiku:
  Scope                Tests    Avg Time     Avg Cost     Context              
  --------------------------------------------------------------------------------
  first_chunk          5        0.89s       $0.000592    93 words, 38s
  first_3_chunks       5        1.45s       $0.001234    289 words, 145s
  full_transcript      5        1.92s       $0.001397    487 words, 281s
```

---

## Troubleshooting

**"No videos found"**
→ Check that `data/chunked_output/` contains *_chunked.json files

**"API key not found"**
→ Add keys to `.env` file in project root

**"JSON parsing error"**
→ Model returned invalid JSON, check the error message in results

**"Rate limit exceeded"**
→ Add delays between API calls (uncomment time.sleep in script)

---

## Manual Inspection Tips

When evaluating, ask yourself:

1. **Does the exercise test the RIGHT concept?**
   - If first_chunk generates exercise about "substitution" but video is actually about "simultaneous equations", it's wrong

2. **Is the difficulty appropriate?**
   - Should match video complexity
   - Not too easy (just recall)
   - Not too hard (beyond what video covers)

3. **Could a student actually DO this?**
   - Proof of learning should be actionable
   - Not just "explain the concept"
   - Requires demonstration

4. **Is the solution correct?**
   - Check mathematical accuracy
   - Verify step-by-step logic

---

## Ready to Run?

```powershell
# 1. Run test (5-10 minutes)
python llm_context_comparison_test.py --num-samples 5

# 2. Evaluate results (15-20 minutes of your time)
python evaluate_context_quality.py context_comparison_results.json

# 3. Check recommendation
# Look at "recommended_context" in the evaluation summary

# 4. Make decision and proceed with full generation
```

**Total time investment:** ~30 minutes  
**Total cost:** ~$0.20  
**Value:** Validates approach for $34+ project, ensures quality for business-critical content
