"""
LLM Context Comparison Test - Compare First Chunk vs First 3 Chunks vs Full Transcript

Tests whether using more transcript context produces better learning exercises.
Each video gets 3 exercises generated using different context scopes:
1. First chunk only (~250 tokens, 60-70 seconds)
2. First 3 chunks (~750 tokens, 3 minutes)
3. Full transcript (varies by video length)

Usage:
    python llm_context_comparison_test.py --num-samples 5 --output context_comparison_results.json
"""

import json
import time
from pathlib import Path
from typing import List, Dict, Any, Literal
from dataclasses import dataclass, asdict
from datetime import datetime
import openai
from anthropic import Anthropic
import os
from dotenv import load_dotenv
import random

load_dotenv()

# Initialize clients
openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
anthropic_client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))


ContextScope = Literal["first_chunk", "first_3_chunks", "full_transcript"]


@dataclass
class ModelConfig:
    """Configuration for each LLM model to test"""
    name: str
    provider: str
    model_id: str
    input_cost_per_1m: float
    output_cost_per_1m: float


# Models to test (you can reduce this list if desired)
MODELS_TO_TEST = [
    ModelConfig("GPT-4o", "openai", "gpt-4o", 2.50, 10.00),
    ModelConfig("Claude-3-Haiku", "anthropic", "claude-3-haiku-20240307", 0.25, 1.25),
]


EXERCISE_GENERATION_PROMPT = """You are an expert mathematics teacher creating learning exercises.

**Input:**
Video transcript excerpt: {transcript}
Video title: {title}
Duration: {duration} seconds
Context scope: {context_scope}

**Task:**
Generate a learning exercise based on this transcript. Output as JSON with this exact structure:

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
- If you only have partial context (first chunk), focus on what IS covered
- Be concise but pedagogically sound
"""


@dataclass
class TestResult:
    """Results from testing a model on a transcript with specific context"""
    model_name: str
    video_id: str
    context_scope: ContextScope
    response_time: float
    input_tokens: int
    output_tokens: int
    cost: float
    response: Dict[str, Any]
    error: str = None
    timestamp: str = None
    
    # Context metadata
    context_word_count: int = 0
    context_duration_seconds: float = 0
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


def load_random_videos(num_samples: int = 5) -> List[Dict]:
    """Load random videos from chunked output"""
    chunked_dir = Path("data/chunked_output")
    
    if not chunked_dir.exists():
        print(f"❌ Directory not found: {chunked_dir}")
        return []
    
    # Get all chunked files
    all_files = list(chunked_dir.glob("*_chunked.json"))
    
    if len(all_files) < num_samples:
        print(f"⚠️  Only {len(all_files)} videos available, using all")
        selected_files = all_files
    else:
        # Random sample
        selected_files = random.sample(all_files, num_samples)
    
    videos = []
    for file_path in selected_files:
        with open(file_path) as f:
            data = json.load(f)
            
            if not data.get('chunks') or len(data['chunks']) == 0:
                continue
            
            videos.append({
                'video_id': data['video_id'],
                'title': data['title'],
                'channel': data.get('channel', 'Unknown'),
                'duration': data['duration'],
                'total_chunks': data['total_chunks'],
                'chunks': data['chunks']
            })
    
    return videos


def get_transcript_by_scope(video: Dict, scope: ContextScope) -> tuple[str, int, float]:
    """
    Extract transcript text based on context scope.
    
    Returns:
        (transcript_text, word_count, duration_seconds)
    """
    chunks = video['chunks']
    
    if scope == "first_chunk":
        text = chunks[0]['text']
        duration = chunks[0].get('end_time', 0) - chunks[0].get('start_time', 0)
        
    elif scope == "first_3_chunks":
        num_chunks = min(3, len(chunks))
        text = " ".join([c['text'] for c in chunks[:num_chunks]])
        duration = chunks[num_chunks-1].get('end_time', 0) - chunks[0].get('start_time', 0)
        
    else:  # full_transcript
        text = " ".join([c['text'] for c in chunks])
        duration = video['duration']
    
    word_count = len(text.split())
    
    return text, word_count, duration


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
        content = json.loads(response.choices[0].message.content)
        
        return (
            content,
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
            response_time
        )
    
    except Exception as e:
        print(f"OpenAI error: {e}")
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


def test_model_on_context(
    model: ModelConfig,
    video: Dict,
    scope: ContextScope
) -> TestResult:
    """Test a model on a specific context scope"""
    
    # Get transcript for this scope
    transcript, word_count, duration = get_transcript_by_scope(video, scope)
    
    # Format prompt
    prompt = EXERCISE_GENERATION_PROMPT.format(
        transcript=transcript,
        title=video['title'],
        duration=video['duration'],
        context_scope=scope
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
            video_id=video['video_id'],
            context_scope=scope,
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
            video_id=video['video_id'],
            context_scope=scope,
            response_time=response_time,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            response={},
            context_word_count=word_count,
            context_duration_seconds=duration,
            error="API call failed or JSON parsing error"
        )
    
    return TestResult(
        model_name=model.name,
        video_id=video['video_id'],
        context_scope=scope,
        response_time=response_time,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost=cost,
        response=response,
        context_word_count=word_count,
        context_duration_seconds=duration
    )


def run_context_comparison_test(
    videos: List[Dict],
    models: List[ModelConfig] = MODELS_TO_TEST,
    output_path: Path = None
) -> Dict[str, Any]:
    """Run comparison test across all models, videos, and context scopes"""
    
    results = []
    context_scopes: List[ContextScope] = ["first_chunk", "first_3_chunks", "full_transcript"]
    
    print(f"\n{'='*100}")
    print(f"CONTEXT SCOPE COMPARISON TEST")
    print(f"{'='*100}")
    print(f"Testing {len(models)} models × {len(videos)} videos × {len(context_scopes)} context scopes")
    print(f"Total tests: {len(models) * len(videos) * len(context_scopes)}\n")
    
    for i, video in enumerate(videos, 1):
        print(f"\n{'#'*100}")
        print(f"# Video {i}/{len(videos)}: {video['video_id']}")
        print(f"# Title: {video['title'][:70]}...")
        print(f"# Duration: {video['duration']}s | Chunks: {video['total_chunks']}")
        print(f"{'#'*100}\n")
        
        for scope in context_scopes:
            # Get preview of what's included
            _, word_count, duration = get_transcript_by_scope(video, scope)
            print(f"\n  === Context: {scope.upper()} ({word_count} words, {duration:.0f}s) ===")
            
            for model in models:
                print(f"    {model.name}...", end=" ", flush=True)
                
                result = test_model_on_context(model, video, scope)
                results.append(result)
                
                if result.error:
                    print(f"❌ ERROR: {result.error}")
                else:
                    print(f"✓ {result.response_time:.2f}s | ${result.cost:.6f}")
    
    # Generate summary
    summary = generate_context_summary(results, models, context_scopes)
    
    # Save results
    output_data = {
        "test_metadata": {
            "timestamp": datetime.now().isoformat(),
            "num_videos": len(videos),
            "num_models": len(models),
            "context_scopes": context_scopes,
            "models_tested": [m.name for m in models],
            "video_ids": [v['video_id'] for v in videos]
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


def generate_context_summary(
    results: List[TestResult],
    models: List[ModelConfig],
    scopes: List[ContextScope]
) -> Dict:
    """Generate summary comparing context scopes"""
    
    summary = {
        "by_model_and_scope": {},
        "context_scope_comparison": {}
    }
    
    # Summary by model and scope
    for model in models:
        summary["by_model_and_scope"][model.name] = {}
        
        for scope in scopes:
            scope_results = [
                r for r in results 
                if r.model_name == model.name and r.context_scope == scope and not r.error
            ]
            
            if not scope_results:
                continue
            
            summary["by_model_and_scope"][model.name][scope] = {
                "total_tests": len(scope_results),
                "avg_response_time": sum(r.response_time for r in scope_results) / len(scope_results),
                "avg_input_tokens": sum(r.input_tokens for r in scope_results) / len(scope_results),
                "avg_output_tokens": sum(r.output_tokens for r in scope_results) / len(scope_results),
                "avg_cost": sum(r.cost for r in scope_results) / len(scope_results),
                "avg_context_words": sum(r.context_word_count for r in scope_results) / len(scope_results),
                "avg_context_duration": sum(r.context_duration_seconds for r in scope_results) / len(scope_results),
            }
    
    # Context scope comparison (averaged across models)
    for scope in scopes:
        scope_results = [r for r in results if r.context_scope == scope and not r.error]
        
        if not scope_results:
            continue
        
        summary["context_scope_comparison"][scope] = {
            "total_tests": len(scope_results),
            "avg_cost": sum(r.cost for r in scope_results) / len(scope_results),
            "avg_input_tokens": sum(r.input_tokens for r in scope_results) / len(scope_results),
            "avg_context_words": sum(r.context_word_count for r in scope_results) / len(scope_results),
            "avg_context_duration": sum(r.context_duration_seconds for r in scope_results) / len(scope_results),
        }
    
    return summary


def print_summary_table(summary: Dict):
    """Print formatted summary comparing context scopes"""
    
    print(f"\n\n{'='*100}")
    print(f"CONTEXT SCOPE COMPARISON SUMMARY")
    print(f"{'='*100}\n")
    
    # Compare context scopes
    print("Context Scope Comparison (averaged across all models):\n")
    print(f"{'Scope':<20} {'Avg Words':<12} {'Avg Duration':<15} {'Avg Tokens':<12} {'Avg Cost':<12}")
    print(f"{'-'*100}")
    
    for scope, stats in summary.get("context_scope_comparison", {}).items():
        print(
            f"{scope:<20} "
            f"{stats['avg_context_words']:<11.0f} "
            f"{stats['avg_context_duration']:<14.0f}s "
            f"{stats['avg_input_tokens']:<11.0f} "
            f"${stats['avg_cost']:<11.6f}"
        )
    
    print(f"\n{'='*100}\n")
    
    # By model and scope
    print("Results by Model and Context Scope:\n")
    
    for model_name, scopes in summary.get("by_model_and_scope", {}).items():
        print(f"\n{model_name}:")
        print(f"  {'Scope':<20} {'Tests':<8} {'Avg Time':<12} {'Avg Cost':<12} {'Context':<20}")
        print(f"  {'-'*80}")
        
        for scope, stats in scopes.items():
            print(
                f"  {scope:<20} "
                f"{stats['total_tests']:<8} "
                f"{stats['avg_response_time']:<11.2f}s "
                f"${stats['avg_cost']:<11.6f} "
                f"{stats['avg_context_words']:.0f} words, {stats['avg_context_duration']:.0f}s"
            )


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Compare context scopes for exercise generation")
    parser.add_argument("--num-samples", type=int, default=5, help="Number of random videos to test")
    parser.add_argument("--output", type=Path, default=Path("context_comparison_results.json"), help="Output JSON file")
    
    args = parser.parse_args()
    
    # Load random videos
    print("Loading random sample of videos...")
    videos = load_random_videos(args.num_samples)
    
    if not videos:
        print("❌ No videos found. Please check your data/chunked_output directory.")
        exit(1)
    
    print(f"✓ Loaded {len(videos)} videos:")
    for v in videos:
        print(f"  - {v['video_id']}: {v['title'][:60]}...")
    
    # Run comparison
    results = run_context_comparison_test(videos, MODELS_TO_TEST, args.output)
    
    # Print summary
    print_summary_table(results['summary'])
    
    print("\n✅ Context comparison test complete!")
    print(f"\nFull results saved to: {args.output}")
    print("\n📊 NEXT STEPS:")
    print("  1. Review the JSON output to see all generated exercises")
    print("  2. For each video, compare exercises from different context scopes:")
    print("     - Does first_chunk capture the main concept?")
    print("     - Does first_3_chunks provide better context?")
    print("     - Is full_transcript necessary?")
    print("  3. Look for patterns across videos")
    print("  4. Decide on optimal context strategy for your content")
