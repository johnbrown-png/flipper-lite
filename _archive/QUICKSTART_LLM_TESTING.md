# Quick Start: LLM Model Comparison Testing

## Step 1: Install Dependencies (One-time setup)

```bash
pip install anthropic
```

## Step 2: Add Anthropic API Key to .env

Add this line to your `.env` file:
```
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

Get your API key from: https://console.anthropic.com/

## Step 3: Run the Comparison Test

```bash
# Activate your virtual environment first
.\.venv\Scripts\Activate.ps1

# Run the test (takes ~2-3 minutes)
python llm_comparison_test.py --num-samples 5

# Review the automated metrics
# Output will be saved to: llm_comparison_results.json
```

## Step 4: Optional - Manual Quality Evaluation

```bash
# Interactive quality scoring (15-20 minutes)
python evaluate_exercise_quality.py --results llm_comparison_results.json
```

---

## Quick Test with Just 2 Transcripts

If you want a very fast test:

```bash
python llm_comparison_test.py --num-samples 2
```

This will test all 4 models on just 2 transcripts (~1 minute total).

---

## Expected Cost for the Test

Running this test will cost approximately:

- **5 transcripts × 4 models = 20 API calls**
- **Total cost: ~$0.10** (ten cents)

Breakdown:
- GPT-4o mini: $0.002
- GPT-4o: $0.036
- Claude 3.5 Sonnet: $0.051
- Claude 3 Haiku: $0.004

---

## Understanding the Output

The test generates a JSON file with:

1. **Performance Metrics** (automated):
   - Response time
   - Token usage
   - Cost per exercise
   - Success/failure rate

2. **Generated Exercises** (for manual review):
   - Learning objective
   - Proof of learning task
   - Worked solution
   - Common misconception
   - Visual specification

3. **Projections**:
   - Cost for 1,635 videos (best 1 of 3)
   - Cost for 4,904 videos (all videos)

---

## What You'll Learn

After 5 minutes of testing, you'll know:

✅ Which model is fastest
✅ Which model is cheapest  
✅ Which model has the best structured output
✅ Approximate costs for your full dataset

After manual evaluation (optional), you'll also know:
✅ Which model produces the most accurate solutions
✅ Which model has the best pedagogical quality
✅ Which model gives best value (quality ÷ cost)

---

## Next Steps After Testing

1. **Review the results** in `llm_comparison_results.json`
2. **Read the recommendations** in `LLM_MODEL_SELECTION_GUIDE.md`
3. **Make your decision**:
   - Premium quality → GPT-4o (~$34 for 4,904 videos)
   - Balanced → Tiered approach (~$25-28)
   - Budget → Claude 3 Haiku (~$4)

4. **Proceed with full generation** using your chosen model(s)

---

## Troubleshooting

**Error: "No module named 'anthropic'"**
```bash
pip install anthropic
```

**Error: "Missing API key"**
- Check your `.env` file has both keys set
- Make sure `.env` is in the project root directory

**Error: "No transcripts found"**
- Make sure you have chunked video files in `data/chunked_output/`
- The system will automatically sample from existing chunks

**Want to test specific videos?**
Create a `sample_transcripts.json` file:
```json
[
  {
    "video_id": "L0e4Y7drlJc",
    "title": "Your Video Title",
    "transcript": "Your transcript text here...",
    "duration": 423
  }
]
```

Then run:
```bash
python llm_comparison_test.py --input sample_transcripts.json
```
