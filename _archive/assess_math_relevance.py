"""
Assess video title relevance to mathematics education using GPT-4o-mini.
Outputs a CSV with relevance scores: 1 = possibly irrelevant, 0 = likely relevant.

Estimated cost: $0.11 - $0.13 for ~4,800 videos
"""

import csv
import os
import json
import time
from openai import OpenAI
from tqdm import tqdm
from dotenv import load_dotenv

# Configuration
INPUT_CSV = "video_inventory.csv"
OUTPUT_CSV = "video_inventory_relevance_scores.csv"
STATE_FILE = "relevance_assessment_state.json"
BATCH_SIZE = 50  # Process in batches for better error recovery
MODEL = "gpt-4o-mini"

# Pricing for cost tracking (per 1M tokens)
INPUT_COST_PER_1M = 0.150
OUTPUT_COST_PER_1M = 0.600


def load_state():
    """Load processing state to resume if interrupted."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {"processed_ids": [], "total_input_tokens": 0, "total_output_tokens": 0}


def save_state(state):
    """Save processing state."""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def assess_title_relevance(client, title):
    """
    Assess if a video title is relevant to mathematics education.
    
    Returns:
        tuple: (score, reason, input_tokens, output_tokens)
        score: 0 = relevant to math, 1 = possibly irrelevant
    """
    prompt = f"""You are assessing whether a video is relevant to mathematics education.

Video Title: "{title}"

Determine if this video is likely about mathematics education/instruction/tutoring.

SCORE 0 (RELEVANT) if the video is about:
- Teaching math concepts, formulas, or problem-solving
- Math tutorials, lessons, or explanations
- Educational math content for any grade level
- Math practice, exercises, or worked examples

SCORE 1 (POSSIBLY IRRELEVANT) if the video is about:
- Entertainment or songs (even if math-themed)
- Clickbait or "magic tricks" rather than instruction
- Non-educational children's entertainment
- Gaming, vlogs, or other non-instructional content
- Content where math is tangential, not the main focus

Respond with ONLY a JSON object:
{{"score": 0 or 1, "reason": "brief explanation"}}"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a precise classifier. Respond only with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=50
        )
        
        result_text = response.choices[0].message.content.strip()
        result = json.loads(result_text)
        
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        
        return result['score'], result['reason'], input_tokens, output_tokens
        
    except json.JSONDecodeError:
        # Fallback: try to extract score if JSON parsing fails
        if '"score": 0' in result_text or '"score":0' in result_text:
            return 0, "JSON parse fallback", response.usage.prompt_tokens, response.usage.completion_tokens
        elif '"score": 1' in result_text or '"score":1' in result_text:
            return 1, "JSON parse fallback", response.usage.prompt_tokens, response.usage.completion_tokens
        else:
            return 0, "Parse error - assumed relevant", 0, 0
    
    except Exception as e:
        print(f"\nError processing title '{title}': {e}")
        return 0, f"Error: {str(e)}", 0, 0


def calculate_cost(input_tokens, output_tokens):
    """Calculate cost in USD."""
    input_cost = (input_tokens / 1_000_000) * INPUT_COST_PER_1M
    output_cost = (output_tokens / 1_000_000) * OUTPUT_COST_PER_1M
    return input_cost + output_cost


def main():
    # Load environment variables from .env file
    load_dotenv()
    
    # Check for OpenAI API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not found in .env file.")
        print("Please add it to your .env file: OPENAI_API_KEY='your-api-key'")
        return
    
    client = OpenAI(api_key=api_key)
    
    # Load existing state
    state = load_state()
    processed_ids = set(state["processed_ids"])
    total_input_tokens = state["total_input_tokens"]
    total_output_tokens = state["total_output_tokens"]
    
    # Read input CSV
    print(f"Reading {INPUT_CSV}...")
    videos = []
    with open(INPUT_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        videos = list(reader)
    
    print(f"Total videos: {len(videos)}")
    print(f"Already processed: {len(processed_ids)}")
    print(f"Remaining: {len(videos) - len(processed_ids)}")
    
    if len(processed_ids) > 0:
        print(f"\nResuming from previous run...")
        current_cost = calculate_cost(total_input_tokens, total_output_tokens)
        print(f"Cost so far: ${current_cost:.4f}")
    
    # Prepare output file
    output_exists = os.path.exists(OUTPUT_CSV)
    output_file = open(OUTPUT_CSV, 'a', newline='', encoding='utf-8')
    writer = csv.DictWriter(output_file, fieldnames=[
        'video_id', 'channel', 'title', 'language', 'is_song', 
        'duration_seconds', 'duration_formatted', 
        'relevance_score', 'relevance_reason'
    ])
    
    if not output_exists:
        writer.writeheader()
    
    # Process videos
    print(f"\nProcessing videos (batch size: {BATCH_SIZE})...")
    print(f"Model: {MODEL}")
    print(f"Estimated total cost: $0.11 - $0.13\n")
    
    batch_count = 0
    
    try:
        for video in tqdm(videos, desc="Assessing relevance"):
            video_id = video['video_id']
            
            # Skip if already processed
            if video_id in processed_ids:
                continue
            
            # Assess relevance
            score, reason, input_tok, output_tok = assess_title_relevance(
                client, 
                video['title']
            )
            
            # Track tokens and cost
            total_input_tokens += input_tok
            total_output_tokens += output_tok
            
            # Write result
            video['relevance_score'] = score
            video['relevance_reason'] = reason
            writer.writerow(video)
            
            # Update state
            processed_ids.add(video_id)
            batch_count += 1
            
            # Save state periodically
            if batch_count % BATCH_SIZE == 0:
                output_file.flush()
                state['processed_ids'] = list(processed_ids)
                state['total_input_tokens'] = total_input_tokens
                state['total_output_tokens'] = total_output_tokens
                save_state(state)
            
            # Small delay to avoid rate limits
            time.sleep(0.05)
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Progress saved.")
    
    except Exception as e:
        print(f"\n\nError occurred: {e}")
        print("Progress saved. You can resume by running the script again.")
    
    finally:
        output_file.close()
        
        # Save final state
        state['processed_ids'] = list(processed_ids)
        state['total_input_tokens'] = total_input_tokens
        state['total_output_tokens'] = total_output_tokens
        save_state(state)
        
        # Print summary
        final_cost = calculate_cost(total_input_tokens, total_output_tokens)
        print(f"\n{'='*60}")
        print(f"SUMMARY")
        print(f"{'='*60}")
        print(f"Videos processed: {len(processed_ids)}/{len(videos)}")
        print(f"Input tokens: {total_input_tokens:,}")
        print(f"Output tokens: {total_output_tokens:,}")
        print(f"Total cost: ${final_cost:.4f}")
        print(f"\nOutput saved to: {OUTPUT_CSV}")
        
        if len(processed_ids) == len(videos):
            print(f"\n✓ All videos processed successfully!")
            
            # Calculate statistics
            with open(OUTPUT_CSV, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                scores = [int(row['relevance_score']) for row in reader if row.get('relevance_score')]
                
            irrelevant_count = sum(scores)
            relevant_count = len(scores) - irrelevant_count
            
            print(f"\nRELEVANCE STATISTICS:")
            print(f"  Likely relevant (score=0): {relevant_count} ({relevant_count/len(scores)*100:.1f}%)")
            print(f"  Possibly irrelevant (score=1): {irrelevant_count} ({irrelevant_count/len(scores)*100:.1f}%)")
            print(f"\nNext steps:")
            print(f"  1. Review videos with score=1 in {OUTPUT_CSV}")
            print(f"  2. Sort by 'relevance_score' to see potentially irrelevant videos")
            print(f"  3. Manually verify before deletion")
        else:
            print(f"\nRun the script again to continue processing remaining videos.")


if __name__ == "__main__":
    main()
