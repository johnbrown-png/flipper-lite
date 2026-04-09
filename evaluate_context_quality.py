"""
Context Quality Evaluation Tool

Interactive tool for evaluating whether chunk-level or full-transcript context
produces better learning exercises.

For each video, you'll compare 3 exercises generated from:
- First chunk only
- First 3 chunks  
- Full transcript

Score each exercise to determine which context scope is optimal.

Usage:
    python evaluate_context_quality.py context_comparison_results.json
"""

import json
import sys
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Literal


@dataclass
class ContextQualityScore:
    """Quality ratings for comparing context scopes"""
    video_id: str
    model_name: str
    
    # Scores for each context scope (0-5 scale)
    first_chunk_score: int = 0
    first_3_chunks_score: int = 0
    full_transcript_score: int = 0
    
    # Specific criteria
    captures_main_concept: Literal["first_chunk", "first_3_chunks", "full_transcript", "none"] = "none"
    pedagogically_sound: Literal["first_chunk", "first_3_chunks", "full_transcript", "none"] = "none"
    appropriate_scope: Literal["first_chunk", "first_3_chunks", "full_transcript", "none"] = "none"
    
    # Overall assessment
    optimal_context: Literal["first_chunk", "first_3_chunks", "full_transcript"] = "first_chunk"
    notes: str = ""


def display_video_info(video_id: str, results: List[Dict]):
    """Display video metadata"""
    first_result = results[0]
    print(f"\n{'='*100}")
    print(f"VIDEO: {video_id}")
    print(f"{'='*100}\n")


def display_exercise_comparison(video_id: str, model_name: str, exercises_by_scope: Dict):
    """Display exercises side-by-side for comparison"""
    
    print(f"\n{'#'*100}")
    print(f"# MODEL: {model_name}")
    print(f"{'#'*100}\n")
    
    scopes = ["first_chunk", "first_3_chunks", "full_transcript"]
    
    for scope in scopes:
        if scope not in exercises_by_scope or exercises_by_scope[scope].get('error'):
            print(f"[{scope.upper()}] - ERROR or missing\n")
            continue
        
        result = exercises_by_scope[scope]
        exercise = result['response']
        
        print(f"\n{'─'*100}")
        print(f"[{scope.upper()}]")
        print(f"Context: {result.get('context_word_count', 0)} words, {result.get('context_duration_seconds', 0):.0f} seconds")
        print(f"Cost: ${result['cost']:.6f} | Time: {result['response_time']:.2f}s")
        print(f"{'─'*100}\n")
        
        print(f"📚 LEARNING OBJECTIVE:")
        print(f"   {exercise.get('learning_objective', 'N/A')}\n")
        
        print(f"✍️  PROOF OF LEARNING:")
        pol = exercise.get('proof_of_learning', {})
        print(f"   Type: {pol.get('type', 'N/A')}")
        print(f"   Task: {pol.get('task', 'N/A')}")
        print(f"   Success Criteria: {pol.get('success_criteria', 'N/A')}\n")
        
        print(f"💡 WORKED SOLUTION:")
        solution = exercise.get('worked_solution', 'N/A')
        # Truncate if too long
        if len(solution) > 300:
            print(f"   {solution[:300]}...")
        else:
            print(f"   {solution}\n")
        
        print(f"⚠️  COMMON MISCONCEPTION:")
        print(f"   {exercise.get('common_misconception', 'N/A')}\n")
        
        print(f"📊 DIFFICULTY: {exercise.get('difficulty_level', 'N/A')}")
        
    print(f"\n{'='*100}")


def prompt_for_comparison(video_id: str, model_name: str) -> ContextQualityScore:
    """Prompt user to compare the three context scopes"""
    
    print(f"\n{'='*100}")
    print(f"EVALUATION: {model_name} on {video_id}")
    print(f"{'='*100}\n")
    
    print("Rate each exercise on overall quality (0-5):")
    print("  0 = Unusable, 1 = Poor, 2 = Weak, 3 = Acceptable, 4 = Good, 5 = Excellent\n")
    
    # Score each context
    first_chunk_score = int(input("First chunk only score (0-5): ").strip() or "0")
    first_3_chunks_score = int(input("First 3 chunks score (0-5): ").strip() or "0")
    full_transcript_score = int(input("Full transcript score (0-5): ").strip() or "0")
    
    print("\nWhich exercise best captures the MAIN CONCEPT?")
    print("  1 = First chunk, 2 = First 3 chunks, 3 = Full transcript, 0 = None")
    main_concept_choice = input("Choice (0-3): ").strip() or "0"
    main_concept = ["none", "first_chunk", "first_3_chunks", "full_transcript"][int(main_concept_choice)]
    
    print("\nWhich exercise is most PEDAGOGICALLY SOUND?")
    print("  1 = First chunk, 2 = First 3 chunks, 3 = Full transcript, 0 = None")
    pedagogy_choice = input("Choice (0-3): ").strip() or "0"
    pedagogically_sound = ["none", "first_chunk", "first_3_chunks", "full_transcript"][int(pedagogy_choice)]
    
    print("\nWhich exercise uses the most APPROPRIATE SCOPE for this content?")
    print("  1 = First chunk, 2 = First 3 chunks, 3 = Full transcript, 0 = None")
    scope_choice = input("Choice (0-3): ").strip() or "0"
    appropriate_scope = ["none", "first_chunk", "first_3_chunks", "full_transcript"][int(scope_choice)]
    
    print("\nOverall, which CONTEXT SCOPE is optimal for this type of content?")
    print("  1 = First chunk, 2 = First 3 chunks, 3 = Full transcript")
    optimal_choice = input("Choice (1-3): ").strip() or "1"
    optimal_context = ["first_chunk", "first_3_chunks", "full_transcript"][int(optimal_choice) - 1]
    
    notes = input("\nOptional notes or observations: ").strip()
    
    return ContextQualityScore(
        video_id=video_id,
        model_name=model_name,
        first_chunk_score=first_chunk_score,
        first_3_chunks_score=first_3_chunks_score,
        full_transcript_score=full_transcript_score,
        captures_main_concept=main_concept,
        pedagogically_sound=pedagogically_sound,
        appropriate_scope=appropriate_scope,
        optimal_context=optimal_context,
        notes=notes
    )


def evaluate_context_results(input_file: Path, output_file: Path = None):
    """Main evaluation loop"""
    
    # Load results
    with open(input_file) as f:
        data = json.load(f)
    
    results = data['results']
    video_ids = data['test_metadata']['video_ids']
    models = list(set(r['model_name'] for r in results))
    
    print(f"\n{'='*100}")
    print(f"CONTEXT SCOPE QUALITY EVALUATION")
    print(f"{'='*100}\n")
    print(f"Videos: {len(video_ids)}")
    print(f"Models: {len(models)}")
    print(f"Total evaluations: {len(video_ids) * len(models)}\n")
    
    evaluations = []
    
    # Group results by video and model
    for video_id in video_ids:
        for model_name in models:
            # Get all three context scopes for this video+model
            video_model_results = [
                r for r in results 
                if r['video_id'] == video_id and r['model_name'] == model_name
            ]
            
            if not video_model_results:
                continue
            
            # Organize by scope
            exercises_by_scope = {
                r['context_scope']: r for r in video_model_results
            }
            
            # Display comparison
            display_video_info(video_id, video_model_results)
            display_exercise_comparison(video_id, model_name, exercises_by_scope)
            
            # Prompt for evaluation
            evaluation = prompt_for_comparison(video_id, model_name)
            evaluations.append(evaluation)
            
            print("\n✓ Evaluation recorded\n")
    
    # Generate summary
    summary = generate_evaluation_summary(evaluations)
    
    # Save results
    output_data = {
        "input_file": str(input_file),
        "evaluations": [asdict(e) for e in evaluations],
        "summary": summary
    }
    
    if not output_file:
        output_file = input_file.parent / f"{input_file.stem}_evaluation.json"
    
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\n{'='*100}")
    print(f"EVALUATION COMPLETE")
    print(f"{'='*100}\n")
    print(f"Results saved to: {output_file}\n")
    
    print_evaluation_summary(summary)


def generate_evaluation_summary(evaluations: List[ContextQualityScore]) -> Dict:
    """Generate summary statistics from evaluations"""
    
    if not evaluations:
        return {}
    
    # Average scores by context scope
    avg_first_chunk = sum(e.first_chunk_score for e in evaluations) / len(evaluations)
    avg_first_3 = sum(e.first_3_chunks_score for e in evaluations) / len(evaluations)
    avg_full = sum(e.full_transcript_score for e in evaluations) / len(evaluations)
    
    # Count optimal choices
    optimal_counts = {
        "first_chunk": sum(1 for e in evaluations if e.optimal_context == "first_chunk"),
        "first_3_chunks": sum(1 for e in evaluations if e.optimal_context == "first_3_chunks"),
        "full_transcript": sum(1 for e in evaluations if e.optimal_context == "full_transcript")
    }
    
    # Count by criteria
    main_concept_counts = {
        "first_chunk": sum(1 for e in evaluations if e.captures_main_concept == "first_chunk"),
        "first_3_chunks": sum(1 for e in evaluations if e.captures_main_concept == "first_3_chunks"),
        "full_transcript": sum(1 for e in evaluations if e.captures_main_concept == "full_transcript"),
        "none": sum(1 for e in evaluations if e.captures_main_concept == "none")
    }
    
    return {
        "total_evaluations": len(evaluations),
        "average_scores": {
            "first_chunk": avg_first_chunk,
            "first_3_chunks": avg_first_3,
            "full_transcript": avg_full
        },
        "optimal_context_distribution": optimal_counts,
        "main_concept_distribution": main_concept_counts,
        "recommended_context": max(optimal_counts, key=optimal_counts.get)
    }


def print_evaluation_summary(summary: Dict):
    """Print formatted evaluation summary"""
    
    print("EVALUATION SUMMARY:\n")
    
    print(f"Total Evaluations: {summary['total_evaluations']}\n")
    
    print("Average Quality Scores (0-5):")
    for scope, avg_score in summary['average_scores'].items():
        print(f"  {scope:<20} {avg_score:.2f} / 5.0")
    
    print(f"\nOptimal Context Choice Distribution:")
    for scope, count in summary['optimal_context_distribution'].items():
        pct = (count / summary['total_evaluations']) * 100
        print(f"  {scope:<20} {count} ({pct:.1f}%)")
    
    print(f"\n🎯 RECOMMENDATION: {summary['recommended_context'].upper()}")
    print(f"\n{'='*100}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python evaluate_context_quality.py <context_comparison_results.json>")
        print("\nExample:")
        print("  python evaluate_context_quality.py context_comparison_results.json")
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    
    if not input_file.exists():
        print(f"❌ Error: File not found: {input_file}")
        sys.exit(1)
    
    evaluate_context_results(input_file)
