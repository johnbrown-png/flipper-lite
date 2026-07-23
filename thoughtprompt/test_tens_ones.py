"""
Quick test for tens and ones only
"""
from visual_generator import MathVisualGenerator

gen = MathVisualGenerator()

# Test with just tens and ones (no thousands/hundreds)
img = gen.generate_base10_blocks_4digit(
    thousands=0,
    hundreds=0,
    tens=3,
    ones=4,
    label=True
)

img.save('pilot_output/3d_examples/test_34_tens_ones.png')
print("✓ Generated test_34_tens_ones.png")

# Test with just hundreds, tens, ones (no thousands)
img2 = gen.generate_base10_blocks_4digit(
    thousands=0,
    hundreds=2,
    tens=3,
    ones=4,
    label=True
)

img2.save('pilot_output/3d_examples/test_234_no_thousands.png')
print("✓ Generated test_234_no_thousands.png")
