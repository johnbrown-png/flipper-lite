"""
LLM Comparison Testing System for Learning Exercise Generation

Tests multiple LLMs on the same transcripts to compare:
- Quality of learning objectives
- Accuracy of mathematical content
- Pedagogical appropriateness
- Cost efficiency
- Response time

Usage:
    python llm_comparison_test.py --input sample_transcripts.json --output comparison_results.json
"""

import json
import time
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import openai
from anthropic import Anthropic
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize clients
openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
anthropic_client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))


@dataclass
class ModelConfig:
    """Configuration for each LLM model to test"""
    name: str
    provider: str
    model_id: str
    input_cost_per_1m: float  # USD per 1M input tokens
    output_cost_per_1m: float  # USD per 1M output tokens
    
    
# Models to compare
MODELS_TO_TEST = [
    ModelConfig("GPT-4o-mini", "openai", "gpt-4o-mini", 0.15, 0.60),
    ModelConfig("GPT-4o", "openai", "gpt-4o", 2.50, 10.00),
    ModelConfig("Claude-3.5-Sonnet", "anthropic", "claude-3-5-sonnet-20241022", 3.00, 15.00),
    ModelConfig("Claude-3-Haiku", "anthropic", "claude-3-haiku-20240307", 0.25, 1.25),
]


EXERCISE_GENERATION_PROMPT = """You are an expert mathematics teacher creating learning exercises.

**Input:**
Video transcript: {transcript}
Video title: {title}
Duration: {duration} seconds

**Task:**
Generate a learning exercise based on this transcript chunk. Output as JSON with this exact structure:

{{
  "learning_objective": "Clear, specific learning objective (what the student will be able to do)",
  "proof_of_learning": {{
    "type": "worked_example|explanation|diagram|calculation|problem",
    "task": "Specific task the learner must complete to demonstrate understanding",
    "success_criteria": "What a correct response should include"
  }},
  "worked_solution": "Complete step-by-step solution with reasoning",
  "common_misconception": "One common mistake students make with this concept",
  "difficulty_level": "beginner|intermediate|advanced",
  "visual_spec": {{
    "needed": true/false,
    "type": "coordinate_plane|geometric_figure|number_line|graph|none",
    "description": "Brief description of what should be visualized"
  }}
}}

**Guidelines:**
- Learning objective should be measurable and specific
- Proof of learning should require demonstration, not just recognition
- Worked solution must be mathematically correct
- Common misconception should be relevant and helpful
- Be concise but pedagogically sound
"""


@dataclass
class TestResult:
    """Results from testing a single model on a single transcript"""
    model_name: str
    transcript_id: str
    response_time: float
    input_tokens: int
    output_tokens: int
    cost: float
    response: Dict[str, Any]
    error: str = None
    timestamp: str = None
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


def load_sample_transcripts(input_path: Path, limit: int = 5) -> List[Dict]:
    """Load sample transcripts from chunked video files"""
    chunked_dir = Path("data/chunked_output")
    
    if input_path.exists():
        # Load from specified file
        with open(input_path) as f:
            return json.load(f)
    
    # Otherwise load from chunked files
    samples = []
    chunked_files = sorted(list(chunked_dir.glob("*_chunked.json")))[:limit]
    
    for file_path in chunked_files:
        with open(file_path) as f:
            data = json.load(f)
            # Get first chunk from each video
            if data.get('chunks') and len(data['chunks']) > 0:
                chunk = data['chunks'][0]
                samples.append({
                    'video_id': data['video_id'],
                    'title': data['title'],
                    'channel': data.get('channel', 'Unknown'),
                    'duration': data['duration'],
                    'chunk_index': chunk['chunk_index'],
                    'transcript': chunk['text'],
                    'start_time': chunk.get('start_time', 0),
                    'end_time': chunk.get('end_time', 0),
                    'token_count': chunk.get('token_count', 0)
                })
    
    return samples


def call_openai_model(model_id: str, prompt: str, max_tokens: int = 2000) -> tuple[Dict, int, int, float]:
    """Call OpenAI model and return response, token counts, and time"""
    start_time = time.time()
    
    try:
        response = openai_client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": "You are an expert mathematics teacher. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=max_tokens,
            temperature=0.7
        )
        
        response_time = time.time() - start_time
        
        # Parse JSON response
        content = json.loads(response.choices[0].message.content)
        
        return (
            content,
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
            response_time
        )
    
    except Exception as e:
        return None, 0, 0, time.time() - start_time


def call_anthropic_model(model_id: str, prompt: str, max_tokens: int = 2000) -> tuple[Dict, int, int, float]:
    """Call Anthropic model and return response, token counts, and time"""
    start_time = time.time()
    
    try:
        response = anthropic_client.messages.create(
            model=model_id,
            max_tokens=max_tokens,
            temperature=0.7,
            system="You are an expert mathematics teacher. Always respond with valid JSON only.",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        response_time = time.time() - start_time
        
        # Extract text and parse JSON
        content_text = response.content[0].text
        content = json.loads(content_text)
        
        return (
            content,
            response.usage.input_tokens,
            response.usage.output_tokens,
            response_time
        )
    
    except Exception as e:
        print(f"Anthropic error: {e}")
        return None, 0, 0, time.time() - start_time


def test_model_on_transcript(
    model: ModelConfig,
    transcript_data: Dict
) -> TestResult:
    """Test a single model on a single transcript"""
    
    # Format prompt
    prompt = EXERCISE_GENERATION_PROMPT.format(
        transcript=transcript_data['transcript'],
        title=transcript_data['title'],
        duration=transcript_data.get('duration', 'unknown')
    )
    
    # Call appropriate API
    if model.provider == "openai":
        response, input_tokens, output_tokens, response_time = call_openai_model(
            model.model_id, prompt
        )
    elif model.provider == "anthropic":
        response, input_tokens, output_tokens, response_time = call_anthropic_model(
            model.model_id, prompt
        )
    else:
        return TestResult(
            model_name=model.name,
            transcript_id=transcript_data['video_id'],
            response_time=0,
            input_tokens=0,
            output_tokens=0,
            cost=0,
            response={},
            error=f"Unknown provider: {model.provider}"
        )
    
    # Calculate cost
    cost = (
        (input_tokens / 1_000_000) * model.input_cost_per_1m +
        (output_tokens / 1_000_000) * model.output_cost_per_1m
    )
    
    # Handle errors
    if response is None:
        return TestResult(
            model_name=model.name,
            transcript_id=transcript_data['video_id'],
            response_time=response_time,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            response={},
            error="API call failed or JSON parsing error"
        )
    
    return TestResult(
        model_name=model.name,
        transcript_id=transcript_data['video_id'],
        response_time=response_time,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost=cost,
        response=response
    )


def run_comparison_test(
    transcripts: List[Dict],
    models: List[ModelConfig] = MODELS_TO_TEST,
    output_path: Path = None
) -> Dict[str, Any]:
    """Run comparison test across all models and transcripts"""
    
    results = []
    
    print(f"\n{'='*80}")
    print(f"Starting LLM Comparison Test")
    print(f"{'='*80}")
    print(f"Testing {len(models)} models on {len(transcripts)} transcripts\n")
    
    for i, transcript in enumerate(transcripts, 1):
        print(f"\n--- Transcript {i}/{len(transcripts)}: {transcript['video_id']} ---")
        print(f"Title: {transcript['title'][:60]}...")
        
        for model in models:
            print(f"  Testing {model.name}...", end=" ", flush=True)
            
            result = test_model_on_transcript(model, transcript)
            results.append(result)
            
            if result.error:
                print(f"❌ ERROR: {result.error}")
            else:
                print(f"✓ {result.response_time:.2f}s | ${result.cost:.6f}")
    
    # Generate summary statistics
    summary = generate_summary(results, models)
    
    # Save results
    output_data = {
        "test_metadata": {
            "timestamp": datetime.now().isoformat(),
            "num_transcripts": len(transcripts),
            "num_models": len(models),
            "models_tested": [m.name for m in models]
        },
        "results": [asdict(r) for r in results],
        "summary": summary
    }
    
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)
        print(f"\n✓ Results saved to: {output_path}")
    
    return output_data


def generate_summary(results: List[TestResult], models: List[ModelConfig]) -> Dict:
    """Generate summary statistics comparing models"""
    
    summary = {}
    
    for model in models:
        model_results = [r for r in results if r.model_name == model.name]
        
        if not model_results:
            continue
        
        successful_results = [r for r in model_results if not r.error]
        
        summary[model.name] = {
            "total_tests": len(model_results),
            "successful": len(successful_results),
            "failed": len(model_results) - len(successful_results),
            "avg_response_time": sum(r.response_time for r in successful_results) / len(successful_results) if successful_results else 0,
            "avg_input_tokens": sum(r.input_tokens for r in successful_results) / len(successful_results) if successful_results else 0,
            "avg_output_tokens": sum(r.output_tokens for r in successful_results) / len(successful_results) if successful_results else 0,
            "avg_cost_per_exercise": sum(r.cost for r in successful_results) / len(successful_results) if successful_results else 0,
            "total_cost": sum(r.cost for r in model_results),
            "projected_cost_1635_videos": sum(r.cost for r in model_results) / len(model_results) * 1635 if model_results else 0,
            "projected_cost_4904_videos": sum(r.cost for r in model_results) / len(model_results) * 4904 if model_results else 0,
        }
    
    return summary


def print_comparison_table(summary: Dict):
    """Print a formatted comparison table"""
    
    print(f"\n{'='*120}")
    print(f"COMPARISON SUMMARY")
    print(f"{'='*120}\n")
    
    # Header
    print(f"{'Model':<25} {'Success':<10} {'Avg Time':<12} {'Avg Cost':<12} {'Cost (1,635)':<15} {'Cost (4,904)':<15}")
    print(f"{'-'*120}")
    
    # Sort by average cost
    sorted_models = sorted(summary.items(), key=lambda x: x[1]['avg_cost_per_exercise'])
    
    for model_name, stats in sorted_models:
        print(
            f"{model_name:<25} "
            f"{stats['successful']}/{stats['total_tests']:<8} "
            f"{stats['avg_response_time']:<11.2f}s "
            f"${stats['avg_cost_per_exercise']:<11.6f} "
            f"${stats['projected_cost_1635_videos']:<14.2f} "
            f"${stats['projected_cost_4904_videos']:<14.2f}"
        )
    
    print(f"{'-'*120}\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Compare LLM models for exercise generation")
    parser.add_argument("--input", type=Path, default=None, help="Input JSON file with transcripts")
    parser.add_argument("--output", type=Path, default=Path("llm_comparison_results.json"), help="Output JSON file")
    parser.add_argument("--num-samples", type=int, default=5, help="Number of transcripts to test")
    
    args = parser.parse_args()
    
    # Load transcripts
    print("Loading sample transcripts...")
    transcripts = load_sample_transcripts(args.input or Path("sample_transcripts.json"), args.num_samples)
    
    if not transcripts:
        print("❌ No transcripts found. Please check your data directory.")
        exit(1)
    
    print(f"✓ Loaded {len(transcripts)} transcripts\n")
    
    # Run comparison
    results = run_comparison_test(transcripts, MODELS_TO_TEST, args.output)
    
    # Print summary
    print_comparison_table(results['summary'])
    
    print("\n✅ Comparison test complete!")
    print(f"\nFull results saved to: {args.output}")
    print("\nRecommendation: Review the detailed JSON output to assess:")
    print("  1. Quality of learning objectives")
    print("  2. Accuracy of worked solutions")
    print("  3. Appropriateness of difficulty levels")
    print("  4. Cost-benefit ratio for your use case")
