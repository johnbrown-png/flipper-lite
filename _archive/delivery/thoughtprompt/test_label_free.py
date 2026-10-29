"""
Test script to generate label-free base-10 blocks images.
These can be used when you want to add titles externally (e.g., in Streamlit).
"""

from pathlib import Path
from visual_generator import MathVisualGenerator

def generate_label_free_examples():
    """Generate base-10 blocks without embedded titles/labels"""
    generator = MathVisualGenerator()
    
    output_dir = Path(__file__).parent / "comparison_results" / "label_free"
    output_dir.mkdir(exist_ok=True)
    
    test_cases = [
        (4, 7, "47"),
        (5, 8, "58"),
        (3, 0, "30"),
        (0, 6, "06"),
        (9, 9, "99"),
    ]
    
    print("=" * 60)
    print("Generating label-free base-10 blocks...")
    print("=" * 60)
    
    for tens, ones, desc in test_cases:
        # Generate WITHOUT labels
        img = generator.generate_base10_blocks(tens, ones, label=False)
        output_file = output_dir / f"base10_blocks_{tens}_{ones}_no_label.png"
        img.save(output_file)
        print(f"  ✓ {desc} -> {output_file.name}")
    
    print("=" * 60)
    print(f"✓ Label-free images generated in: {output_dir}")
    print()
    print("These images contain ONLY the visual blocks, no text.")
    print("Perfect for embedding in Streamlit with st.markdown() titles above.")
    print("=" * 60)


if __name__ == "__main__":
    generate_label_free_examples()
