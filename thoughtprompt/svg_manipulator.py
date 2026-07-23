"""
SVG Base-10 Block Manipulator
Manipulates the professional SVG base-10 blocks to display specific numbers.

Uses the transparent 3D isometric cubes from Wikimedia Commons.
"""

import xml.etree.ElementTree as ET
from pathlib import Path


class SVGBase10Manipulator:
    """Manipulate SVG base-10 blocks to show specific tens and ones"""
    
    def __init__(self, template_path=None):
        """Load the template SVG if provided."""
        self.template_path = Path(template_path) if template_path else None
        self.tree = None
        self.root = None
        self.ns = {'svg': 'http://www.w3.org/2000/svg'}
        self.ns_uri = ''

        if self.template_path:
            if not self.template_path.exists():
                raise FileNotFoundError(f"Template not found: {self.template_path}")

            self.tree = ET.parse(str(self.template_path))
            self.root = self.tree.getroot()

            # Parse the namespace
            if self.root.tag.startswith('{'):
                self.ns_uri = self.root.tag.split('}')[0] + '}'

    @staticmethod
    def _create_path(path_data, fill):
        """Create a consistently styled SVG path element."""
        path = ET.Element('path')
        path.set('d', path_data)
        path.set('fill', fill)
        path.set('stroke', '#000000')
        path.set('stroke-width', '2')
        path.set('stroke-linejoin', 'round')
        return path

    @staticmethod
    def _create_line(x1, y1, x2, y2, width='1'):
        """Create a grid line element with consistent styling."""
        line = ET.Element('line')
        line.set('x1', str(x1))
        line.set('y1', str(y1))
        line.set('x2', str(x2))
        line.set('y2', str(y2))
        line.set('stroke', '#000000')
        line.set('stroke-width', str(width))
        return line
    
    def create_unit_cube(self, x, y, color_scheme='blue', include_top_face=True):
        """
        Create a single unit cube (3 faces: front, right, top)
        
        Args:
            x, y: Base position for the cube
            color_scheme: 'blue' or 'red' or 'yellow'
            include_top_face: Whether to draw the cube's top face
        
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
        front = self._create_path(
            f'M{x},{y} L{x+size},{y} L{x+size},{y+size} L{x},{y+size} L{x},{y} Z',
            c['front'],
        )
        
        # Right side face (parallelogram)
        side = self._create_path(
            f'M{x+size},{y} L{x+size+depth},{y-depth} L{x+size+depth},{y+size-depth} L{x+size},{y+size} L{x+size},{y} Z',
            c['side'],
        )
        
        elements = [front, side]

        if include_top_face:
            # Top face (parallelogram)
            top = self._create_path(
                f'M{x},{y} L{x+depth},{y-depth} L{x+size+depth},{y-depth} L{x+size},{y} L{x},{y} Z',
                c['top'],
            )
            elements.append(top)
        
        return elements
    
    def create_ten_rod(self, x, y, color_scheme='blue'):
        """Create a ten-rod (10 cubes stacked vertically)"""
        cubes = []
        size = 25
        for i in range(10):
            cube_y = y + (i * size)
            cubes.extend(
                self.create_unit_cube(
                    x,
                    cube_y,
                    color_scheme,
                    include_top_face=(i == 0),
                )
            )
        return cubes

    def create_hundred_plate(self, x, y, color_scheme='red'):
        """
        Create a fused hundred plate (10x10x1) with no gaps between ten-stacks.

        The plate is drawn as one continuous front face plus oblique top/right faces,
        with 10x10 grid lines to show unit structure.
        """
        colors = {
            'blue': {'front': '#009fff', 'side': '#0680c9', 'top': '#41b6fe'},
            'red': {'front': '#ff0000', 'side': '#cc0000', 'top': '#ff6666'},
            'yellow': {'front': '#ffcc00', 'side': '#cc9900', 'top': '#ffee99'},
        }
        c = colors.get(color_scheme, colors['red'])

        size = 25
        depth = 12.5
        span = size * 10

        elements = []

        # Fused faces
        elements.append(
            self._create_path(
                f'M{x},{y} L{x+span},{y} L{x+span},{y+span} L{x},{y+span} L{x},{y} Z',
                c['front'],
            )
        )
        elements.append(
            self._create_path(
                f'M{x+span},{y} L{x+span+depth},{y-depth} L{x+span+depth},{y+span-depth} L{x+span},{y+span} L{x+span},{y} Z',
                c['side'],
            )
        )
        elements.append(
            self._create_path(
                f'M{x},{y} L{x+depth},{y-depth} L{x+span+depth},{y-depth} L{x+span},{y} L{x},{y} Z',
                c['top'],
            )
        )

        # Front grid: exactly 10x10 with no gaps
        for i in range(1, 10):
            offset = i * size
            elements.append(self._create_line(x + offset, y, x + offset, y + span))
            elements.append(self._create_line(x, y + offset, x + span, y + offset))

        return elements

    def create_thousand_cube(self, x, y, color_scheme='green'):
        """
        Create a fused thousand cube (10x10x10) with oblique depth.

        The cube is one solid block with 10x10 unit grids on visible faces.
        """
        colors = {
            'blue': {'front': '#009fff', 'side': '#0680c9', 'top': '#41b6fe'},
            'red': {'front': '#ff0000', 'side': '#cc0000', 'top': '#ff6666'},
            'yellow': {'front': '#ffcc00', 'side': '#cc9900', 'top': '#ffee99'},
            'green': {'front': '#1db954', 'side': '#15803d', 'top': '#4ade80'},
        }
        c = colors.get(color_scheme, colors['green'])

        size = 25
        unit_depth = 12.5
        span = size * 10
        depth_total = unit_depth * 6.5
        perspective_scale = 0.64
        back_span = span * perspective_scale

        elements = []

        def lerp(p1, p2, t):
            return (
                p1[0] + (p2[0] - p1[0]) * t,
                p1[1] + (p2[1] - p1[1]) * t,
            )

        # Front face corners
        front_tl = (x, y)
        front_tr = (x + span, y)
        front_br = (x + span, y + span)
        front_bl = (x, y + span)

        # Back/top reference corners (foreshortened)
        back_tr = (x + span + depth_total, y - depth_total)
        back_tl = (back_tr[0] - back_span, back_tr[1])
        back_br = (x + span + depth_total, y - depth_total + back_span)

        # Fused faces
        elements.append(
            self._create_path(
                f'M{front_tl[0]},{front_tl[1]} L{front_tr[0]},{front_tr[1]} L{front_br[0]},{front_br[1]} L{front_bl[0]},{front_bl[1]} L{front_tl[0]},{front_tl[1]} Z',
                c['front'],
            )
        )
        elements.append(
            self._create_path(
                f'M{front_tr[0]},{front_tr[1]} L{back_tr[0]},{back_tr[1]} L{back_br[0]},{back_br[1]} L{front_br[0]},{front_br[1]} L{front_tr[0]},{front_tr[1]} Z',
                c['side'],
            )
        )
        elements.append(
            self._create_path(
                f'M{front_tl[0]},{front_tl[1]} L{back_tl[0]},{back_tl[1]} L{back_tr[0]},{back_tr[1]} L{front_tr[0]},{front_tr[1]} L{front_tl[0]},{front_tl[1]} Z',
                c['top'],
            )
        )

        # Front face grid (10x10)
        for i in range(1, 10):
            offset = i * size
            elements.append(self._create_line(x + offset, y, x + offset, y + span))
            elements.append(self._create_line(x, y + offset, x + span, y + offset))

        # Top face grid
        for i in range(1, 10):
            t = i / 10
            top_front_point = lerp(front_tl, front_tr, t)
            top_back_point = lerp(back_tl, back_tr, t)
            left_depth_point = lerp(front_tl, back_tl, t)
            right_depth_point = lerp(front_tr, back_tr, t)

            elements.append(
                self._create_line(
                    top_front_point[0],
                    top_front_point[1],
                    top_back_point[0],
                    top_back_point[1],
                )
            )
            elements.append(
                self._create_line(
                    left_depth_point[0],
                    left_depth_point[1],
                    right_depth_point[0],
                    right_depth_point[1],
                )
            )

        # Right face grid
        for i in range(1, 10):
            t = i / 10
            front_vertical_point = lerp(front_tr, front_br, t)
            back_vertical_point = lerp(back_tr, back_br, t)
            top_depth_point = lerp(front_tr, back_tr, t)
            bottom_depth_point = lerp(front_br, back_br, t)

            elements.append(
                self._create_line(
                    front_vertical_point[0],
                    front_vertical_point[1],
                    back_vertical_point[0],
                    back_vertical_point[1],
                )
            )
            elements.append(
                self._create_line(
                    top_depth_point[0],
                    top_depth_point[1],
                    bottom_depth_point[0],
                    bottom_depth_point[1],
                )
            )

        return elements

    @staticmethod
    def _create_base_svg(width=800, height=400):
        """Create a new SVG root element with a standard canvas."""
        svg = ET.Element('svg')
        svg.set('xmlns', 'http://www.w3.org/2000/svg')
        svg.set('viewBox', f'0 0 {width} {height}')
        svg.set('width', str(width))
        svg.set('height', str(height))
        return svg

    @staticmethod
    def _add_text(parent, x, y, text, font_size='24'):
        """Add consistently styled text to an SVG group."""
        text_node = ET.SubElement(parent, 'text')
        text_node.set('x', str(x))
        text_node.set('y', str(y))
        text_node.set('font-family', 'Arial, sans-serif')
        text_node.set('font-size', str(font_size))
        text_node.set('fill', '#000000')
        text_node.text = text
        return text_node

    @staticmethod
    def _projected_width(place_value):
        """Projected width for one primitive of the requested place value."""
        size = 25
        depth = 12.5
        if place_value == 'one':
            return size + depth
        if place_value == 'ten':
            return size + depth
        if place_value == 'hundred':
            return (size * 10) + depth
        if place_value == 'thousand':
            return (size * 10) + (depth * 6.5)
        raise ValueError(f"Unsupported place value: {place_value}")

    @staticmethod
    def _front_height(place_value):
        """Front-face height for baseline alignment."""
        size = 25
        if place_value == 'one':
            return size
        return size * 10

    @staticmethod
    def _label_text(place_value, count):
        """Human-readable label for each place-value group."""
        names = {
            'one': 'one',
            'ten': 'ten',
            'hundred': 'hundred',
            'thousand': 'thousand',
        }
        word = names[place_value]
        suffix = '' if count == 1 else 's'
        return f"{count} {word}{suffix}"

    def _create_place_value_elements(self, place_value, x, y):
        """Return SVG elements for a single primitive at x/y."""
        if place_value == 'one':
            return self.create_unit_cube(x, y, 'yellow')
        if place_value == 'ten':
            return self.create_ten_rod(x, y, 'blue')
        if place_value == 'hundred':
            return self.create_hundred_plate(x, y, 'red')
        if place_value == 'thousand':
            return self.create_thousand_cube(x, y, 'green')
        raise ValueError(f"Unsupported place value: {place_value}")
    
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
        svg = self._create_base_svg()
        
        # Create main group
        main_group = ET.SubElement(svg, 'g')
        
        # Add title
        self._add_text(main_group, 20, 30, f'Representing {tens * 10 + ones}', font_size='24')
        
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

    def generate_one_block_display(self, output_path=None):
        """Generate an SVG showing one 3D unit cube primitive."""
        svg = self._create_base_svg()
        main_group = ET.SubElement(svg, 'g')

        self._add_text(main_group, 20, 30, 'Representing 1 (one unit cube)', font_size='24')

        one_elements = self.create_unit_cube(x=260, y=160, color_scheme='yellow')
        for elem in one_elements:
            main_group.append(elem)

        self._add_text(main_group, 250, 240, '1 one', font_size='18')

        if output_path is None:
            output_path = 'svg_base10_one_block.svg'

        output_path = Path(output_path)
        tree = ET.ElementTree(svg)
        ET.indent(tree, space='  ')
        tree.write(str(output_path), encoding='utf-8', xml_declaration=True)
        return output_path

    def generate_ten_rod_display(self, output_path=None):
        """Generate an SVG showing one 3D ten-rod primitive."""
        svg = self._create_base_svg()
        main_group = ET.SubElement(svg, 'g')

        self._add_text(main_group, 20, 30, 'Representing 10 (one ten rod)', font_size='24')

        ten_elements = self.create_ten_rod(x=250, y=80, color_scheme='blue')
        for elem in ten_elements:
            main_group.append(elem)

        self._add_text(main_group, 240, 360, '1 ten', font_size='18')

        if output_path is None:
            output_path = 'svg_base10_ten_rod.svg'

        output_path = Path(output_path)
        tree = ET.ElementTree(svg)
        ET.indent(tree, space='  ')
        tree.write(str(output_path), encoding='utf-8', xml_declaration=True)
        return output_path

    def generate_hundred_block_display(self, output_path=None):
        """Generate an SVG showing one fused hundred plate (10x10x1)."""
        svg = self._create_base_svg()
        main_group = ET.SubElement(svg, 'g')

        self._add_text(main_group, 20, 30, 'Representing 100 (one hundred plate)', font_size='24')

        hundred_elements = self.create_hundred_plate(x=150, y=80, color_scheme='red')
        for elem in hundred_elements:
            main_group.append(elem)

        self._add_text(main_group, 250, 360, '1 hundred', font_size='18')

        if output_path is None:
            output_path = 'svg_base10_hundred_block.svg'

        output_path = Path(output_path)
        tree = ET.ElementTree(svg)
        ET.indent(tree, space='  ')
        tree.write(str(output_path), encoding='utf-8', xml_declaration=True)
        return output_path

    def generate_thousand_block_display(self, output_path=None):
        """Generate an SVG showing one fused thousand cube (10x10x10)."""
        svg = self._create_base_svg()
        main_group = ET.SubElement(svg, 'g')

        self._add_text(main_group, 20, 30, 'Representing 1000 (one thousand cube)', font_size='24')

        thousand_elements = self.create_thousand_cube(x=120, y=140, color_scheme='green')
        for elem in thousand_elements:
            main_group.append(elem)

        self._add_text(main_group, 290, 360, '1 thousand', font_size='18')

        if output_path is None:
            output_path = 'svg_base10_thousand_block.svg'

        output_path = Path(output_path)
        tree = ET.ElementTree(svg)
        ET.indent(tree, space='  ')
        tree.write(str(output_path), encoding='utf-8', xml_declaration=True)
        return output_path

    def generate_four_digit_scene(
        self,
        thousands,
        hundreds,
        tens,
        ones,
        output_path=None,
        scene_width=1400,
        scene_height=700,
    ):
        """
        Generate a 4-digit place-value scene with consistent inter-group spacing.

        Inter-group spacing is fixed across all groups and derived from the projected
        hundred width so parade spacing remains regular and visually coherent.
        """
        svg = self._create_base_svg(width=scene_width, height=scene_height)
        main_group = ET.SubElement(svg, 'g')

        number_value = (thousands * 1000) + (hundreds * 100) + (tens * 10) + ones
        self._add_text(main_group, 30, 50, f'Representing {number_value}', font_size='38')

        # Baseline for front faces (all groups share this front-plane alignment).
        baseline_y = 480
        start_x = 80

        # Keep one fixed inter-group gap calibrated from the preferred 100↔10 spacing.
        inter_group_gap = self._projected_width('hundred') / 15
        intra_group_gap = self._projected_width('one') / 3

        place_order = [
            ('thousand', thousands),
            ('hundred', hundreds),
            ('ten', tens),
            ('one', ones),
        ]

        current_x = start_x
        label_y = 610

        for place_value, count in place_order:
            if count <= 0:
                continue

            item_width = self._projected_width(place_value)
            front_height = self._front_height(place_value)

            group_start_x = current_x
            group_total_width = (count * item_width) + ((count - 1) * intra_group_gap)

            for index in range(count):
                item_x = group_start_x + (index * (item_width + intra_group_gap))
                item_y = baseline_y - front_height
                elements = self._create_place_value_elements(place_value, item_x, item_y)
                for elem in elements:
                    main_group.append(elem)

            label_x = group_start_x + (group_total_width / 2) - 30
            self._add_text(
                main_group,
                label_x,
                label_y,
                self._label_text(place_value, count),
                font_size='24',
            )

            current_x = group_start_x + group_total_width + inter_group_gap

        if output_path is None:
            output_path = f'svg_base10_blocks_{thousands}{hundreds}{tens}{ones}.svg'

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


def generate_hundred_thousand_examples(template_path, output_dir):
    """Generate SVG examples for the new 100 and 1000 block primitives."""
    manipulator = SVGBase10Manipulator(template_path)

    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    print("Generating fused 100 and 1000 SVG block examples...")
    print("=" * 60)

    hundred_output = output_dir / 'svg_base10_hundred_block.svg'
    thousand_output = output_dir / 'svg_base10_thousand_block.svg'

    manipulator.generate_hundred_block_display(hundred_output)
    print(f"  ✓ 100 block -> {hundred_output.name}")

    manipulator.generate_thousand_block_display(thousand_output)
    print(f"  ✓ 1000 block -> {thousand_output.name}")

    print("=" * 60)
    print(f"✓ New SVG files generated in: {output_dir.absolute()}")

    return output_dir


def generate_core_primitive_examples(template_path, output_dir):
    """Generate 3D primitive examples for 1, 10, 100, and 1000 blocks."""
    manipulator = SVGBase10Manipulator(template_path)

    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    print("Generating full 3D primitive family (1/10/100/1000)...")
    print("=" * 60)

    output_map = {
        'one': output_dir / 'svg_base10_one_block.svg',
        'ten': output_dir / 'svg_base10_ten_rod.svg',
        'hundred': output_dir / 'svg_base10_hundred_block.svg',
        'thousand': output_dir / 'svg_base10_thousand_block.svg',
    }

    manipulator.generate_one_block_display(output_map['one'])
    print(f"  ✓ 1 block -> {output_map['one'].name}")

    manipulator.generate_ten_rod_display(output_map['ten'])
    print(f"  ✓ 10 block -> {output_map['ten'].name}")

    manipulator.generate_hundred_block_display(output_map['hundred'])
    print(f"  ✓ 100 block -> {output_map['hundred'].name}")

    manipulator.generate_thousand_block_display(output_map['thousand'])
    print(f"  ✓ 1000 block -> {output_map['thousand'].name}")

    print("=" * 60)
    print(f"✓ Full 3D primitive family generated in: {output_dir.absolute()}")

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
    if not Path(template_path).exists():
        print("Template file not found. Continuing with generated 3D primitives only.")
        template_path = None

    output_dir = Path(__file__).parent / "comparison_results" / "svg_wikimedia"
    
    # Generate SVG files
    svg_dir = generate_test_cases(template_path, output_dir)
    generate_core_primitive_examples(template_path, output_dir)
    
    # Try to convert to PNG
    convert_svg_to_png(svg_dir)
    
    print("\n" + "-" * 60)
    print("Comparison:")
    print("-" * 60)
    print("Python-generated: thoughtprompt/comparison_results/base10_blocks_*.png")
    print("SVG-based:        thoughtprompt/comparison_results/svg_wikimedia/")
    print("\nOpen both sets side-by-side to compare quality!")
    print("-" * 60)
