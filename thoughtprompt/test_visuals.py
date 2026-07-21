"""
Test script to generate example images for visual comparison.
Generates multiple variants of each visual type to evaluate quality and usability.
"""

import os
from pathlib import Path
from visual_generator import MathVisualGenerator


def create_output_dir():
    """Create output directory for comparison images"""
    output_dir = Path(__file__).parent / "comparison_results"
    output_dir.mkdir(exist_ok=True)
    return output_dir


def test_base10_blocks(generator, output_dir):
    """Generate base-10 block examples"""
    print("Generating base-10 blocks examples...")
    
    test_cases = [
        (4, 7, "47 - Four tens and seven ones"),
        (5, 8, "58 - Five tens and eight ones"),
        (3, 0, "30 - Three tens and zero ones"),
        (0, 6, "06 - Zero tens and six ones"),
        (9, 9, "99 - Nine tens and nine ones"),
    ]
    
    for tens, ones, description in test_cases:
        img = generator.generate_base10_blocks(tens, ones, label=True)
        filename = f"base10_blocks_{tens}_{ones}.png"
        img.save(output_dir / filename)
        print(f"  ✓ {description} -> {filename}")


def test_part_whole_models(generator, output_dir):
    """Generate part-whole model examples"""
    print("\nGenerating part-whole model examples...")
    
    test_cases = [
        (47, [40, 7], "47 partitioned into 40 and 7"),
        (100, [60, 40], "100 partitioned into 60 and 40"),
        (58, [50, 8], "58 partitioned into 50 and 8"),
        (47, [30, 17], "47 flexible partition: 30 and 17"),
        (100, [50, 30, 20], "100 into three parts: 50, 30, 20"),
    ]
    
    for total, parts, description in test_cases:
        img = generator.generate_part_whole_model(total, parts, label=True)
        filename = f"part_whole_{total}_{'_'.join(map(str, parts))}.png"
        img.save(output_dir / filename)
        print(f"  ✓ {description} -> {filename}")


def test_bar_models(generator, output_dir):
    """Generate bar model examples"""
    print("\nGenerating bar model examples...")
    
    # Addition examples
    addition_cases = [
        (100, [60, 40], "100 = 60 + 40"),
        (47, [40, 7], "47 = 40 + 7"),
        (150, [80, 50, 20], "150 = 80 + 50 + 20"),
    ]
    
    for total, parts, description in addition_cases:
        img = generator.generate_bar_model(total, parts, operation='addition', label=True)
        filename = f"bar_model_add_{total}_{'_'.join(map(str, parts))}.png"
        img.save(output_dir / filename)
        print(f"  ✓ Addition: {description} -> {filename}")
    
    # Subtraction examples
    subtraction_cases = [
        (100, [60, 40], "100 - 60 = 40"),
        (47, [20, 27], "47 - 20 = 27"),
    ]
    
    for total, parts, description in subtraction_cases:
        img = generator.generate_bar_model(total, parts, operation='subtraction', label=True)
        filename = f"bar_model_sub_{total}_{'_'.join(map(str, parts))}.png"
        img.save(output_dir / filename)
        print(f"  ✓ Subtraction: {description} -> {filename}")


def test_number_lines(generator, output_dir):
    """Generate number line examples"""
    print("\nGenerating number line examples...")
    
    test_cases = [
        (0, 10, 7, 1, "0-10 with 7 highlighted, interval=1"),
        (0, 100, 47, 10, "0-100 with 47 highlighted, interval=10"),
        (0, 1000, 650, 100, "0-1000 with 650 highlighted, interval=100"),
        (20, 80, 47, 10, "20-80 with 47 highlighted, interval=10"),
        (400, 500, 470, 10, "400-500 with 470 highlighted, interval=10"),
        (0, 10000, 5247, 1000, "0-10000 with 5247 highlighted, interval=1000"),
    ]
    
    for start, end, highlight, interval, description in test_cases:
        img = generator.generate_number_line(start, end, highlight, interval, label=True)
        filename = f"number_line_{start}_{end}_highlight_{highlight}.png"
        img.save(output_dir / filename)
        print(f"  ✓ {description} -> {filename}")


def generate_comparison_grid():
    """Generate a simple comparison grid showing all types"""
    print("\n" + "="*60)
    print("Generating visual comparison examples...")
    print("="*60)
    
    generator = MathVisualGenerator()
    output_dir = create_output_dir()
    
    # Generate all test cases
    test_base10_blocks(generator, output_dir)
    test_part_whole_models(generator, output_dir)
    test_bar_models(generator, output_dir)
    test_number_lines(generator, output_dir)
    
    print("\n" + "="*60)
    print(f"✓ All images generated successfully!")
    print(f"✓ Output directory: {output_dir.absolute()}")
    print("="*60)
    
    # Count files
    num_files = len(list(output_dir.glob("*.png")))
    print(f"\nTotal images generated: {num_files}")
    
    return output_dir


if __name__ == "__main__":
    output_dir = generate_comparison_grid()
    
    print("\n" + "-"*60)
    print("Next Steps:")
    print("-"*60)
    print("1. Review the generated images in:")
    print(f"   {output_dir.absolute()}")
    print("2. Compare with open-source alternatives (see research_open_source.md)")
    print("3. Evaluate each visual type for:")
    print("   - Age-appropriateness (7-9 year olds)")
    print("   - Mathematical clarity")
    print("   - Visual appeal")
    print("   - Ease of understanding")
    print("-"*60)
