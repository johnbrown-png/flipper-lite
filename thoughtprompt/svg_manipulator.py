"""
SVG Base-10 Block Manipulator
Manipulates the professional SVG base-10 blocks to display specific numbers.

Uses the transparent 3D isometric cubes from Wikimedia Commons.
"""

import xml.etree.ElementTree as ET
from pathlib import Path


class SVGBase10Manipulator:
    """Manipulate SVG base-10 blocks to show specific tens and ones"""
    
    def __init__(self, template_path):
        """Load the template SVG"""
        self.template_path = Path(template_path)
        self.tree = ET.parse(str(self.template_path))
        self.root = self.tree.getroot()
        self.ns = {'svg': 'http://www.w3.org/2000/svg'}
        
        # Parse the namespace
        if self.root.tag.startswith('{'):
            self.ns_uri = self.root.tag.split('}')[0] + '}'
        else:
            self.ns_uri = ''
    
    def create_unit_cube(self, x, y, color_scheme='blue'):
        """
        Create a single unit cube (3 faces: front, right, top)
        
        Args:
            x, y: Base position for the cube
            color_scheme: 'blue' or 'red' or 'yellow'
        
        Returns:
            List of 3 path elements
        """
        colors = {
            'blue': {'front': '#009fff', 'side': '#0680c9', 'top': '#41b6fe'},
            'red': {'front': '#ff0000', 'side': '#cc0000', 'top': '#ff6666'},
            'yellow': {'front': '#ffcc00', 'side': '#cc9900', 'top': '#ffee99'},
        }
        
        c = colors.get(color_scheme, colors['blue'])
        
        # Cube size
        size = 25
        depth = 12.5  # Isometric depth
        
        # Front face (square)
        front = ET.Element('path')
        front.set('d', f'M{x},{y} L{x+size},{y} L{x+size},{y+size} L{x},{y+size} L{x},{y} Z')
        front.set('fill', c['front'])
        front.set('stroke', '#000000')
        front.set('stroke-width', '2')
        front.set('stroke-linejoin', 'round')
        
        # Right side face (parallelogram)
        side = ET.Element('path')
        side.set('d', f'M{x+size},{y} L{x+size+depth},{y-depth} L{x+size+depth},{y+size-depth} L{x+size},{y+size} L{x+size},{y} Z')
        side.set('fill', c['side'])
        side.set('stroke', '#000000')
        side.set('stroke-width', '2')
        side.set('stroke-linejoin', 'round')
        
        # Top face (parallelogram)
        top = ET.Element('path')
        top.set('d', f'M{x},{y} L{x+depth},{y-depth} L{x+size+depth},{y-depth} L{x+size},{y} L{x},{y} Z')
        top.set('fill', c['top'])
        top.set('stroke', '#000000')
        top.set('stroke-width', '2')
        top.set('stroke-linejoin', 'round')
        
        return [front, side, top]
    
    def create_ten_rod(self, x, y, color_scheme='blue'):
        """Create a ten-rod (10 cubes stacked vertically)"""
        cubes = []
        size = 25
        for i in range(10):
            cube_y = y + (i * size)
            cubes.extend(self.create_unit_cube(x, cube_y, color_scheme))
        return cubes
    
    def generate_number_display(self, tens, ones, output_path=None):
        """
        Generate SVG showing specified tens and ones.
        
        Args:
            tens: Number of ten-rods (0-9)
            ones: Number of unit cubes (0-9)
            output_path: Where to save the SVG
        
        Returns:
            Path to saved file
        """
        # Create new SVG root
        svg = ET.Element('svg')
        svg.set('xmlns', 'http://www.w3.org/2000/svg')
        svg.set('viewBox', '0 0 800 400')
        svg.set('width', '800')
        svg.set('height', '400')
        
        # Create main group
        main_group = ET.SubElement(svg, 'g')
        
        # Add title
        title_text = ET.SubElement(main_group, 'text')
        title_text.set('x', '20')
        title_text.set('y', '30')
        title_text.set('font-family', 'Arial, sans-serif')
        title_text.set('font-size', '24')
        title_text.set('fill', '#000000')
        title_text.text = f'Representing {tens * 10 + ones}'
        
        # Starting position
        start_x = 80
        start_y = 300  # Start from bottom
        cube_size = 25
        spacing = 10
        
        # Draw ten-rods
        current_x = start_x
        for i in range(tens):
            rod_elements = self.create_ten_rod(current_x, start_y - (10 * cube_size), 'blue')
            for elem in rod_elements:
                main_group.append(elem)
            current_x += cube_size + spacing
        
        # Add spacing between tens and ones
        if tens > 0:
            current_x += spacing * 2
        
        # Draw unit cubes
        ones_start_x = current_x
        for i in range(ones):
            # Arrange ones in rows of 5
            row = i // 5
            col = i % 5
            cube_x = ones_start_x + (col * (cube_size + spacing))
            cube_y = start_y - cube_size - (row * (cube_size + spacing))
            
            cube_elements = self.create_unit_cube(cube_x, cube_y, 'yellow')
            for elem in cube_elements:
                main_group.append(elem)
        
        # Add labels
        label_y = 350
        if tens > 0:
            tens_label = ET.SubElement(main_group, 'text')
            tens_label_x = start_x + (tens * (cube_size + spacing)) // 2 - 30
            tens_label.set('x', str(tens_label_x))
            tens_label.set('y', str(label_y))
            tens_label.set('font-family', 'Arial, sans-serif')
            tens_label.set('font-size', '18')
            tens_label.set('fill', '#000000')
            tens_label.text = f"{tens} ten{'s' if tens != 1 else ''}"
        
        if ones > 0:
            ones_label = ET.SubElement(main_group, 'text')
            ones_rows = (ones - 1) // 5 + 1
            ones_label_x = ones_start_x + (min(ones, 5) * (cube_size + spacing)) // 2 - 30
            ones_label.set('x', str(ones_label_x))
            ones_label.set('y', str(label_y))
            ones_label.set('font-family', 'Arial, sans-serif')
            ones_label.set('font-size', '18')
            ones_label.set('fill', '#000000')
            ones_label.text = f"{ones} one{'s' if ones != 1 else ''}"
        
        # Save to file
        if output_path is None:
            output_path = f'svg_base10_{tens}_{ones}.svg'
        
        output_path = Path(output_path)
        
        tree = ET.ElementTree(svg)
        ET.indent(tree, space='  ')
        tree.write(str(output_path), encoding='utf-8', xml_declaration=True)
        
        return output_path


def generate_test_cases(template_path, output_dir):
    """Generate the same test cases as the Python version"""
    manipulator = SVGBase10Manipulator(template_path)
    
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    test_cases = [
        (4, 7, "47 - Four tens and seven ones"),
        (5, 8, "58 - Five tens and eight ones"),
        (3, 0, "30 - Three tens and zero ones"),
        (0, 6, "06 - Zero tens and six ones"),
        (9, 9, "99 - Nine tens and nine ones"),
    ]
    
    print("Generating SVG base-10 blocks from Wikimedia template...")
    print("=" * 60)
    
    for tens, ones, description in test_cases:
        output_file = output_dir / f"svg_base10_blocks_{tens}_{ones}.svg"
        manipulator.generate_number_display(tens, ones, output_file)
        print(f"  ✓ {description} -> {output_file.name}")
    
    print("=" * 60)
    print(f"✓ All SVG files generated in: {output_dir.absolute()}")
    print(f"\nNow converting to PNG for comparison...")
    
    return output_dir


def convert_svg_to_png(svg_dir):
    """Convert SVG files to PNG using cairosvg or PIL"""
    try:
        import cairosvg
        
        svg_files = list(Path(svg_dir).glob("svg_base10_*.svg"))
        for svg_file in svg_files:
            png_file = svg_file.with_suffix('.png')
            cairosvg.svg2png(url=str(svg_file), write_to=str(png_file), 
                           output_width=800, output_height=400)
            print(f"  ✓ Converted: {png_file.name}")
        
        print(f"\n✓ All SVG files converted to PNG")
        return True
        
    except ImportError:
        print("\n⚠️  cairosvg not installed - SVG files created but not converted to PNG")
        print("To convert: pip install cairosvg")
        print("Or open SVG files in browser and take screenshots")
        return False


if __name__ == "__main__":
    template_path = r"C:\Users\johnf\Downloads\Base_ten_blocks_(transparent).svg"
    output_dir = Path(__file__).parent / "comparison_results" / "svg_wikimedia"
    
    # Generate SVG files
    svg_dir = generate_test_cases(template_path, output_dir)
    
    # Try to convert to PNG
    convert_svg_to_png(svg_dir)
    
    print("\n" + "-" * 60)
    print("Comparison:")
    print("-" * 60)
    print("Python-generated: thoughtprompt/comparison_results/base10_blocks_*.png")
    print("SVG-based:        thoughtprompt/comparison_results/svg_wikimedia/")
    print("\nOpen both sets side-by-side to compare quality!")
    print("-" * 60)
