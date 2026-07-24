"""
Demonstration: Using Pilot Prompts to Generate Visuals

This script shows how to load the pilot prompts and generate the corresponding visuals.
"""

import pandas as pd
import json
from pathlib import Path
import sys

# Add parent directory to path to import visual_generator
sys.path.insert(0, str(Path(__file__).parent.parent))
from visual_generator import MathVisualGenerator


def demo_prompt_to_visual():
    """Demonstrate loading a prompt and generating its visual"""
    
    # Load pilot prompts
    csv_file = Path(__file__).parent / "thought_prompts_pilot.csv"
    prompts_df = pd.read_csv(csv_file)
    
    print("=" * 70)
    print("Thought Prompt Visual Generation Demo")
    print("=" * 70)
    print(f"\nLoaded {len(prompts_df)} prompts from pilot")
    print(f"Visual types: {prompts_df['visual_type'].value_counts().to_dict()}")
    
    # Initialize generator
    gen = MathVisualGenerator()
    
    # Output directory for demo visuals
    output_dir = Path(__file__).parent / "demo_visuals"
    output_dir.mkdir(exist_ok=True)
    
    # Generate visuals for first 10 prompts as examples
    print("\n" + "=" * 70)
    print("Generating example visuals (first 10 prompts)...")
    print("=" * 70)
    
    for idx in range(min(10, len(prompts_df))):
        row = prompts_df.iloc[idx]
        
        # Parse visual parameters
        try:
            params = json.loads(row['visual_params'])
        except json.JSONDecodeError:
            print(f"  ✗ Skipping prompt {idx+1}: Invalid JSON params")
            continue
        
        # Generate visual based on type
        try:
            if row['visual_type'] == 'base10_blocks':
                # Handle both 2-digit and 4-digit formats
                if 'thousands' in params:
                    # 4-digit: Need to extend generator (skip for now)
                    print(f"  ⏭ Prompt {idx+1}: base10_blocks (4-digit) - requires generator extension")
                    continue
                else:
                    img = gen.generate_base10_blocks(**params)
            
            elif row['visual_type'] == 'part_whole_model':
                img = gen.generate(
                    visual_type='part_whole_model',
                    params=params,
                )
            
            elif row['visual_type'] == 'number_line':
                img = gen.generate_number_line(**params)
            
            elif row['visual_type'] == 'bar_model':
                img = gen.generate_bar_model(**params)
            
            else:
                print(f"  ✗ Prompt {idx+1}: Unknown visual type '{row['visual_type']}'")
                continue
            
            # Save the image
            filename = f"prompt_{idx+1:03d}_{row['visual_type']}.png"
            output_path = output_dir / filename
            img.save(output_path)
            
            print(f"  ✓ Prompt {idx+1}: {row['visual_type']} -> {filename}")
            print(f"    Q: {row['prompt_text']}")
            print(f"    A: {row['correct_answer']} ({row['difficulty']})")
        
        except Exception as e:
            print(f"  ✗ Prompt {idx+1}: Error - {str(e)}")
    
    print("\n" + "=" * 70)
    print(f"✓ Demo visuals saved to: {output_dir}")
    print("=" * 70)


def show_sample_prompts():
    """Show a few sample prompts with their details"""
    csv_file = Path(__file__).parent / "thought_prompts_pilot.csv"
    prompts_df = pd.read_csv(csv_file)
    
    print("\n" + "=" * 70)
    print("Sample Prompts")
    print("=" * 70)
    
    # Show one of each visual type
    visual_types = prompts_df['visual_type'].unique()
    
    for vtype in visual_types:
        sample = prompts_df[prompts_df['visual_type'] == vtype].iloc[0]
        
        print(f"\n📊 Visual Type: {vtype}")
        print(f"   Small Step: {sample['small_step_name']}")
        print(f"   Question: {sample['prompt_text']}")
        print(f"   Answer: {sample['correct_answer']}")
        print(f"   Difficulty: {sample['difficulty']}")
        print(f"   Parameters: {sample['visual_params']}")


def analyze_prompt_coverage():
    """Analyze which visual types are used for which small steps"""
    csv_file = Path(__file__).parent / "thought_prompts_pilot.csv"
    prompts_df = pd.read_csv(csv_file)
    
    print("\n" + "=" * 70)
    print("Prompt Coverage Analysis")
    print("=" * 70)
    
    # Group by small_step_name and visual_type
    coverage = prompts_df.groupby(['small_step_name', 'visual_type']).size().unstack(fill_value=0)
    
    print("\nVisual types used per small step:")
    print(coverage.to_string())
    
    print("\n" + "-" * 70)
    print("Summary:")
    print(f"  Total small steps: {prompts_df['small_step_num'].nunique()}")
    print(f"  Total prompts: {len(prompts_df)}")
    print(f"  Average prompts per step: {len(prompts_df) / prompts_df['small_step_num'].nunique():.1f}")
    
    # Visual type preferences by topic area
    print("\nVisual type distribution:")
    for vtype, count in prompts_df['visual_type'].value_counts().items():
        pct = count / len(prompts_df) * 100
        print(f"  {vtype}: {count} ({pct:.1f}%)")


if __name__ == "__main__":
    # Show sample prompts
    show_sample_prompts()
    
    # Analyze coverage
    analyze_prompt_coverage()
    
    # Generate demo visuals
    demo_prompt_to_visual()
