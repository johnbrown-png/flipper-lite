"""
Test script for 3D isometric base-10 blocks
Generates example images showing thousands, hundreds, tens, and ones
"""

from visual_generator import MathVisualGenerator
import os

def main():
    """Generate test images for 3D isometric base-10 blocks"""
    
    # Create output directory
    output_dir = 'pilot_output/3d_examples'
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize generator
    gen = MathVisualGenerator()
    
    # Test cases for 4-digit numbers
    test_cases = [
        # (thousands, hundreds, tens, ones, filename)
        (3, 0, 0, 0, '3000_three_thousands'),
        (1, 5, 0, 0, '1500_one_thousand_five_hundreds'),
        (2, 3, 4, 5, '2345_full_example'),
        (0, 7, 0, 0, '700_seven_hundreds'),
        (5, 0, 4, 6, '5046_thousands_tens_ones'),
        (1, 2, 3, 4, '1234_all_places'),
        (9, 9, 9, 9, '9999_maximum'),
        (1, 0, 0, 0, '1000_single_thousand'),
        (0, 1, 0, 0, '100_single_hundred'),
        (4, 2, 0, 0, '4200_thousands_hundreds'),
    ]
    
    print("Generating 3D isometric base-10 block examples...")
    print("-" * 60)
    
    for thousands, hundreds, tens, ones, filename in test_cases:
        try:
            # Generate the image
            img = gen.generate_base10_blocks_4digit(
                thousands=thousands,
                hundreds=hundreds,
                tens=tens,
                ones=ones,
                label=True
            )
            
            # Save the image
            output_path = os.path.join(output_dir, f'{filename}.png')
            img.save(output_path)
            
            total = thousands * 1000 + hundreds * 100 + tens * 10 + ones
            print(f"✓ Generated: {filename}.png (value: {total:,})")
            
        except Exception as e:
            print(f"✗ Failed: {filename}.png - {str(e)}")
    
    print("-" * 60)
    print(f"\nAll images saved to: {output_dir}/")
    print("\nYou can now view these images to verify:")
    print("  - Thousand-cubes (10×10×10) in 3D isometric")
    print("  - Hundred-flats (10×10×1) in 3D isometric")
    print("  - Ten-rods (simple 2D rectangles)")
    print("  - Unit cubes (simple 2D squares)")

if __name__ == '__main__':
    main()
