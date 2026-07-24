"""
Visual Generator for Thought Prompts
Generates mathematically precise visual representations for Year 3/4 place value concepts.

Supports 4 visual types:
1. Base-10 blocks (unit cubes and ten-stacks)
2. Part-whole models (cherry/number bond diagrams)
3. Bar models (proportional rectangles)
4. Number lines (with intervals and highlighting)
"""

from PIL import Image, ImageDraw, ImageFont
import io
import base64
from typing import Dict, Any, Tuple


class MathVisualGenerator:
    """Generate conceptually-correct math visuals for thought prompts"""
    
    def __init__(self, default_width=800, default_height=400):
        self.default_width = default_width
        self.default_height = default_height
        
        # Color palette - friendly for young learners
        self.colors = {
            'ten_rod': '#8B4513',      # Brown
            'unit_cube': '#DEB887',    # Burlywood (lighter brown)
            'background': '#FFFFFF',   # White
            'text': '#000000',         # Black
            'line': '#333333',         # Dark gray
            'highlight': '#FF6B6B',    # Coral red
            'circle_main': '#4ECDC4',  # Turquoise
            'circle_part': '#95E1D3',  # Light turquoise
            'bar_total': '#6C5CE7',    # Purple
            'bar_part1': '#74B9FF',    # Light blue
            'bar_part2': '#FD79A8',    # Pink
            'number_line': '#2C3E50',  # Dark blue-gray
        }
        
        # Try to load a font, fall back to default if not available
        try:
            self.font_large = ImageFont.truetype("arial.ttf", 36)
            self.font_medium = ImageFont.truetype("arial.ttf", 24)
            self.font_small = ImageFont.truetype("arial.ttf", 18)
        except:
            # Fallback to default PIL font
            self.font_large = ImageFont.load_default()
            self.font_medium = ImageFont.load_default()
            self.font_small = ImageFont.load_default()
    
    # Isometric 3D drawing helpers
    def _draw_isometric_cube(self, draw: ImageDraw.Draw, x: int, y: int, 
                            size: int, color: str, darker_color: str = None,
                            darkest_color: str = None) -> None:
        """
        Draw an isometric cube (unit cube) at position (x, y).
        
        The cube is drawn with 3 visible faces:
        - Top face (lightest)
        - Right face (medium)
        - Left face (darkest)
        
        Args:
            draw: ImageDraw object
            x, y: Top corner position
            size: Size of the cube
            color: Base color
            darker_color: Color for shaded face (auto-generated if None)
            darkest_color: Color for darkest face (auto-generated if None)
        """
        # Auto-generate shading colors if not provided
        if darker_color is None:
            # Darken by 20%
            if color.startswith('#'):
                r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
                darker_color = f'#{int(r*0.7):02x}{int(g*0.7):02x}{int(b*0.7):02x}'
            else:
                darker_color = color
        
        if darkest_color is None:
            # Darken by 40%
            if color.startswith('#'):
                r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
                darkest_color = f'#{int(r*0.5):02x}{int(g*0.5):02x}{int(b*0.5):02x}'
            else:
                darkest_color = color
        
        # Isometric projection constants
        # For a cube: side faces go at 30° angle, height is proportional
        iso_width = size
        iso_height = int(size * 0.5)  # Height of the diamond faces
        
        # Top face (parallelogram) - lightest
        top_points = [
            (x, y),                                    # Top corner
            (x + iso_width, y + iso_height),           # Right corner
            (x + iso_width, y + iso_height + size),    # Bottom-right corner
            (x, y + size),                             # Left corner
        ]
        draw.polygon(top_points, fill=color, outline=self.colors['line'], width=1)
        
        # Right face (parallelogram) - medium shade
        right_points = [
            (x + iso_width, y + iso_height),           # Top corner
            (x + iso_width, y + iso_height + size),    # Bottom corner
            (x + iso_width, y + iso_height + size + iso_height), # Bottom-right
            (x + iso_width, y + iso_height + iso_height), # Right corner
        ]
        draw.polygon(right_points, fill=darker_color, outline=self.colors['line'], width=1)
        
        # Left face (parallelogram) - darkest shade
        left_points = [
            (x, y),                                    # Top corner
            (x, y + size),                             # Bottom-left corner
            (x, y + size + iso_height),               # Bottom corner
            (x, y + iso_height),                      # Left corner
        ]
        draw.polygon(left_points, fill=darkest_color, outline=self.colors['line'], width=1)
    
    def _draw_isometric_hundred_flat(self, draw: ImageDraw.Draw, x: int, y: int,
                                     unit_size: int) -> None:
        """
        Draw a hundred-flat (10×10×1 grid) in isometric view.
        
        A hundred-flat is a flat square made of 100 unit cubes arranged in a 10×10 grid.
        
        Args:
            draw: ImageDraw object
            x, y: Top-left corner position
            unit_size: Size of each unit cube
        """
        # Colors for the hundred flat
        top_color = '#FFD700'      # Gold
        right_color = '#DAA520'    # Goldenrod (darker)
        left_color = '#B8860B'     # Dark goldenrod (darkest)
        
        # A hundred-flat is 10×10 unit cubes, but drawn as a single flat surface
        # with grid lines to show the individual units
        
        iso_width = unit_size * 10
        iso_height = int(unit_size * 0.5 * 10)
        flat_thickness = int(unit_size * 0.1)  # Very thin
        
        # Top face - 10×10 grid
        top_points = [
            (x, y),
            (x + iso_width, y + iso_height),
            (x + iso_width, y + iso_height + iso_width),
            (x, y + iso_width)
        ]
        draw.polygon(top_points, fill=top_color, outline=self.colors['line'], width=2)
        
        # Draw grid lines to show 10×10 structure
        for i in range(1, 10):
            # Horizontal lines (going right-down)
            start_x = x + (iso_width // 10) * i
            start_y = y + (iso_height // 10) * i
            end_x = x + (iso_width // 10) * i
            end_y = y + iso_width + (iso_height // 10) * i
            draw.line([start_x, start_y, end_x, end_y], 
                     fill=self.colors['line'], width=1)
            
            # Vertical lines (going right-up)
            start_x = x
            start_y = y + (iso_width // 10) * i
            end_x = x + iso_width
            end_y = y + iso_height + (iso_width // 10) * i
            draw.line([start_x, start_y, end_x, end_y], 
                     fill=self.colors['line'], width=1)
        
        # Right edge (thin depth)
        right_points = [
            (x + iso_width, y + iso_height),
            (x + iso_width, y + iso_height + iso_width),
            (x + iso_width, y + iso_height + iso_width + flat_thickness),
            (x + iso_width, y + iso_height + flat_thickness)
        ]
        draw.polygon(right_points, fill=right_color, outline=self.colors['line'], width=1)
        
        # Left edge (thin depth)
        left_points = [
            (x, y),
            (x, y + iso_width),
            (x, y + iso_width + flat_thickness),
            (x, y + flat_thickness)
        ]
        draw.polygon(left_points, fill=left_color, outline=self.colors['line'], width=1)
    
    def _draw_isometric_thousand_cube(self, draw: ImageDraw.Draw, x: int, y: int,
                                      unit_size: int) -> None:
        """
        Draw a thousand-cube (10×10×10) in isometric view.
        
        A thousand-cube is a large cube made of 1000 unit cubes.
        Shows gridlines to indicate structure.
        
        Args:
            draw: ImageDraw object
            x, y: Top corner position
            unit_size: Size of each unit cube
        """
        # Colors for the thousand cube
        front_color = '#1E3A8A'    # Dark blue
        right_color = '#4682B4'    # Steel blue
        top_color = '#87CEEB'      # Sky blue

        span = unit_size * 10
        depth = int(unit_size * 6.5)

        # Front face corners
        front_tl = (x, y)
        front_tr = (x + span, y)
        front_br = (x + span, y + span)
        front_bl = (x, y + span)

        # Oblique depth offsets (up-right)
        back_tl = (x + depth, y - depth)
        back_tr = (x + span + depth, y - depth)
        back_br = (x + span + depth, y + span - depth)

        # Draw three visible faces only: front, right, top
        draw.polygon([front_tl, front_tr, front_br, front_bl],
                     fill=front_color, outline=self.colors['line'], width=2)
        draw.polygon([front_tr, back_tr, back_br, front_br],
                     fill=right_color, outline=self.colors['line'], width=2)
        draw.polygon([front_tl, back_tl, back_tr, front_tr],
                     fill=top_color, outline=self.colors['line'], width=2)

        # Grid on front face (10x10)
        for i in range(1, 10):
            offset = i * unit_size
            draw.line([x + offset, y, x + offset, y + span], fill=self.colors['line'], width=1)
            draw.line([x, y + offset, x + span, y + offset], fill=self.colors['line'], width=1)

        # Grid on top face
        for i in range(1, 10):
            t = i / 10
            # Width direction lines
            sx = front_tl[0] + int(span * t)
            sy = front_tl[1]
            ex = back_tl[0] + int(span * t)
            ey = back_tl[1]
            draw.line([sx, sy, ex, ey], fill=self.colors['line'], width=1)

            # Depth direction lines
            sx = front_tl[0] + int(depth * t)
            sy = front_tl[1] - int(depth * t)
            ex = front_tr[0] + int(depth * t)
            ey = front_tr[1] - int(depth * t)
            draw.line([sx, sy, ex, ey], fill=self.colors['line'], width=1)

        # Grid on right face
        for i in range(1, 10):
            t = i / 10
            # Vertical (height) subdivisions
            sy = front_tr[1] + int(span * t)
            ey = back_tr[1] + int(span * t)
            draw.line([front_tr[0], sy, back_tr[0], ey], fill=self.colors['line'], width=1)

            # Depth subdivisions
            sx = front_tr[0] + int(depth * t)
            sy = front_tr[1] - int(depth * t)
            ex = front_br[0] + int(depth * t)
            ey = front_br[1] - int(depth * t)
            draw.line([sx, sy, ex, ey], fill=self.colors['line'], width=1)

    def _base10_face_colors(self, family: str) -> Dict[str, str]:
        """Color palettes aligned to the SVG cube-family style."""
        palettes = {
            'one': {'front': '#ffcc00', 'side': '#cc9900', 'top': '#ffee99'},
            'ten': {'front': '#009fff', 'side': '#0680c9', 'top': '#41b6fe'},
            'hundred': {'front': '#ff0000', 'side': '#cc0000', 'top': '#ff6666'},
            'thousand': {'front': '#1db954', 'side': '#15803d', 'top': '#4ade80'},
        }
        return palettes[family]

    def _draw_oblique_unit_cube(self, draw: ImageDraw.Draw, x: int, y: int,
                                size: int, family: str, include_top: bool = True) -> None:
        """Draw a single oblique unit cube with optional top face."""
        c = self._base10_face_colors(family)
        depth = size * 0.5

        # Front face
        draw.polygon(
            [(x, y), (x + size, y), (x + size, y + size), (x, y + size)],
            fill=c['front'], outline='#000000', width=1,
        )

        # Right face
        draw.polygon(
            [
                (x + size, y),
                (x + size + depth, y - depth),
                (x + size + depth, y + size - depth),
                (x + size, y + size),
            ],
            fill=c['side'], outline='#000000', width=1,
        )

        if include_top:
            # Top face
            draw.polygon(
                [
                    (x, y),
                    (x + depth, y - depth),
                    (x + size + depth, y - depth),
                    (x + size, y),
                ],
                fill=c['top'], outline='#000000', width=1,
            )

    def _draw_oblique_ten_rod(self, draw: ImageDraw.Draw, x: int, y: int, size: int) -> None:
        """Draw a ten-rod as ten stacked cubes with realistic occlusion."""
        for i in range(10):
            self._draw_oblique_unit_cube(
                draw,
                x=x,
                y=y + (i * size),
                size=size,
                family='ten',
                include_top=(i == 0),
            )

    def _draw_oblique_hundred_plate(self, draw: ImageDraw.Draw, x: int, y: int, size: int) -> None:
        """Draw a fused hundred plate (10x10x1) with front grid and thin depth."""
        c = self._base10_face_colors('hundred')
        span = size * 10
        depth = size * 0.5

        # Front face
        draw.polygon(
            [(x, y), (x + span, y), (x + span, y + span), (x, y + span)],
            fill=c['front'], outline='#000000', width=1,
        )

        # Right thin face
        draw.polygon(
            [
                (x + span, y),
                (x + span + depth, y - depth),
                (x + span + depth, y + span - depth),
                (x + span, y + span),
            ],
            fill=c['side'], outline='#000000', width=1,
        )

        # Top thin face
        draw.polygon(
            [(x, y), (x + depth, y - depth), (x + span + depth, y - depth), (x + span, y)],
            fill=c['top'], outline='#000000', width=1,
        )

        # 10x10 front grid
        for i in range(1, 10):
            offset = i * size
            draw.line([x + offset, y, x + offset, y + span], fill='#000000', width=1)
            draw.line([x, y + offset, x + span, y + offset], fill='#000000', width=1)

    def _draw_oblique_thousand_cube(self, draw: ImageDraw.Draw, x: int, y: int, size: int) -> None:
        """Draw a foreshortened thousand cube aligned to the SVG perspective style."""
        c = self._base10_face_colors('thousand')
        span = size * 10
        depth = size * 3.25
        perspective_scale = 0.64
        back_span = span * perspective_scale

        def lerp(p1, p2, t):
            return (p1[0] + (p2[0] - p1[0]) * t, p1[1] + (p2[1] - p1[1]) * t)

        front_tl = (x, y)
        front_tr = (x + span, y)
        front_br = (x + span, y + span)
        front_bl = (x, y + span)

        back_tr = (x + span + depth, y - depth)
        back_tl = (back_tr[0] - back_span, back_tr[1])
        back_br = (x + span + depth, y - depth + back_span)

        draw.polygon([front_tl, front_tr, front_br, front_bl], fill=c['front'], outline='#000000', width=1)
        draw.polygon([front_tr, back_tr, back_br, front_br], fill=c['side'], outline='#000000', width=1)
        draw.polygon([front_tl, back_tl, back_tr, front_tr], fill=c['top'], outline='#000000', width=1)

        # Front grid
        for i in range(1, 10):
            offset = i * size
            draw.line([x + offset, y, x + offset, y + span], fill='#000000', width=1)
            draw.line([x, y + offset, x + span, y + offset], fill='#000000', width=1)

        # Top grid
        for i in range(1, 10):
            t = i / 10
            p1 = lerp(front_tl, front_tr, t)
            p2 = lerp(back_tl, back_tr, t)
            draw.line([p1[0], p1[1], p2[0], p2[1]], fill='#000000', width=1)

            p1 = lerp(front_tl, back_tl, t)
            p2 = lerp(front_tr, back_tr, t)
            draw.line([p1[0], p1[1], p2[0], p2[1]], fill='#000000', width=1)

        # Right-face grid
        for i in range(1, 10):
            t = i / 10
            p1 = lerp(front_tr, front_br, t)
            p2 = lerp(back_tr, back_br, t)
            draw.line([p1[0], p1[1], p2[0], p2[1]], fill='#000000', width=1)

            p1 = lerp(front_tr, back_tr, t)
            p2 = lerp(front_br, back_br, t)
            draw.line([p1[0], p1[1], p2[0], p2[1]], fill='#000000', width=1)

    def _generate_base10_scene(self, thousands: int, hundreds: int, tens: int, ones: int,
                               label: bool, width: int, height: int) -> Image.Image:
        """Unified 3D base10 scene renderer shared by 2-digit and 4-digit prompts."""
        img = Image.new('RGB', (width, height), self.colors['background'])
        draw = ImageDraw.Draw(img)

        margin_left = 40
        margin_right = 40
        baseline_y = int(height * 0.75)
        margin_top = 60 if label else 20

        def projected_width(kind: str, unit: int) -> float:
            if kind == 'one':
                return unit * 1.5
            if kind == 'ten':
                return unit * 1.5
            if kind == 'hundred':
                return unit * 10.5
            return unit * 13.25  # thousand

        def front_height(kind: str, unit: int) -> int:
            if kind == 'one':
                return unit
            return unit * 10

        groups = [
            ('thousand', max(0, int(thousands))),
            ('hundred', max(0, int(hundreds))),
            ('ten', max(0, int(tens))),
            ('one', max(0, int(ones))),
        ]

        def spacing_for_unit(unit: int) -> tuple[int, int]:
            intra = max(2, int(unit * 0.35))
            inter = max(4, int(unit * 1.1))
            return intra, inter

        def total_width_for_unit(unit: int) -> float:
            intra, inter = spacing_for_unit(unit)
            total = 0.0
            active = 0
            for kind, count in groups:
                if count <= 0:
                    continue
                active += 1
                w = projected_width(kind, unit)
                total += (count * w) + ((count - 1) * intra)
            if active > 1:
                total += (active - 1) * inter
            return total

        def vertical_extent_for_unit(unit: int) -> float:
            """Estimate tallest draw height above the baseline anchor."""
            extent = 0.0
            for kind, count in groups:
                if count <= 0:
                    continue
                if kind == 'thousand':
                    extent = max(extent, unit * 13.25)
                elif kind in ('hundred', 'ten'):
                    extent = max(extent, unit * 10.5)
                else:
                    extent = max(extent, unit * 1.5)
            return extent

        available_width = width - margin_left - margin_right
        available_height = baseline_y - margin_top

        base_unit = 3
        for candidate in range(22, 2, -1):
            if (
                total_width_for_unit(candidate) <= available_width
                and vertical_extent_for_unit(candidate) <= available_height
            ):
                base_unit = candidate
                break

        intra_spacing, inter_spacing = spacing_for_unit(base_unit)
        layout_width = total_width_for_unit(base_unit)
        current_x = margin_left + max(0, int((available_width - layout_width) // 2))

        if label:
            total_value = thousands * 1000 + hundreds * 100 + tens * 10 + ones
            draw.text((margin_left, 15), f"Representing {total_value:,}", fill=self.colors['text'], font=self.font_medium)

        for kind, count in groups:
            if count <= 0:
                continue

            item_w = projected_width(kind, base_unit)
            item_h = front_height(kind, base_unit)
            y = baseline_y - item_h

            for i in range(count):
                x = int(current_x + i * (item_w + intra_spacing))
                if kind == 'thousand':
                    self._draw_oblique_thousand_cube(draw, x, y, base_unit)
                elif kind == 'hundred':
                    self._draw_oblique_hundred_plate(draw, x, y, base_unit)
                elif kind == 'ten':
                    self._draw_oblique_ten_rod(draw, x, y, base_unit)
                else:
                    self._draw_oblique_unit_cube(draw, x, y, base_unit, family='one', include_top=True)

            group_w = (count * item_w) + ((count - 1) * intra_spacing)
            current_x += group_w + inter_spacing

        if label:
            label_y = height - 50
            x_offset = margin_left
            for kind, count in groups:
                if count <= 0:
                    continue
                text = f"{count} {kind}" if count == 1 else f"{count} {kind}s"
                draw.text((x_offset, label_y), text, fill=self.colors['text'], font=self.font_small)
                x_offset += 180

        return img
    
    def generate_base10_blocks(self, tens: int, ones: int, 
                               label: bool = True) -> Image.Image:
        """
        Generate base-10 blocks visualization.
        
        Args:
            tens: Number of ten-rods to draw (0-9)
            ones: Number of unit cubes to draw (0-9)
            label: Whether to add text labels
        
        Returns:
            PIL Image with ten-rods and unit cubes
        """
        return self._generate_base10_scene(
            thousands=0,
            hundreds=0,
            tens=tens,
            ones=ones,
            label=label,
            width=self.default_width,
            height=self.default_height,
        )
    
    def generate_base10_blocks_4digit(self, thousands: int = 0, hundreds: int = 0,
                                      tens: int = 0, ones: int = 0,
                                      label: bool = True) -> Image.Image:
        """
        Generate 4-digit base-10 blocks visualization with 3D isometric rendering.
        
        Args:
            thousands: Number of thousand-cubes (0-9)
            hundreds: Number of hundred-flats (0-9)
            tens: Number of ten-rods (0-9)
            ones: Number of unit cubes (0-9)
            label: Whether to add text labels
        
        Returns:
            PIL Image with isometric 3D representation
        """
        return self._generate_base10_scene(
            thousands=thousands,
            hundreds=hundreds,
            tens=tens,
            ones=ones,
            label=label,
            width=self.default_width,
            height=self.default_height,
        )
    
    def generate_part_whole_model(self, total: int, parts: list, 
                                  label: bool = True) -> Image.Image:
        """
        Generate part-whole (cherry/number bond) diagram.
        
        Args:
            total: The whole number
            parts: List of parts (usually 2-3 parts)
            label: Whether to add text labels
        
        Returns:
            PIL Image with part-whole diagram
        """
        img = Image.new('RGB', (self.default_width, self.default_height), 
                        self.colors['background'])
        draw = ImageDraw.Draw(img)
        
        # Circle dimensions
        circle_radius = 60
        
        # Position for total (top)
        total_x = self.default_width // 2
        total_y = 100
        
        # Positions for parts (bottom, spread horizontally)
        num_parts = len(parts)
        part_spacing = 200
        parts_y = 280
        
        # Calculate starting x for parts to center them
        total_parts_width = (num_parts - 1) * part_spacing
        parts_start_x = (self.default_width - total_parts_width) // 2
        
        # Draw title
        if label:
            draw.text((20, 20), f"Part-Whole Model: {total}", 
                     fill=self.colors['text'], font=self.font_medium)
        
        # Draw lines from total to parts first (so they're behind circles)
        for i, part in enumerate(parts):
            part_x = parts_start_x + (i * part_spacing)
            draw.line([total_x, total_y + circle_radius, 
                      part_x, parts_y - circle_radius],
                     fill=self.colors['line'], width=3)
        
        # Draw total circle (main)
        draw.ellipse(
            [total_x - circle_radius, total_y - circle_radius,
             total_x + circle_radius, total_y + circle_radius],
            fill=self.colors['circle_main'],
            outline=self.colors['line'],
            width=3
        )
        
        # Draw total number
        total_text = str(total)
        # Get text size for centering
        bbox = draw.textbbox((0, 0), total_text, font=self.font_large)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        draw.text((total_x - text_width // 2, total_y - text_height // 2), 
                 total_text, fill=self.colors['text'], font=self.font_large)
        
        # Draw part circles
        for i, part in enumerate(parts):
            part_x = parts_start_x + (i * part_spacing)
            
            # Draw circle
            draw.ellipse(
                [part_x - circle_radius, parts_y - circle_radius,
                 part_x + circle_radius, parts_y + circle_radius],
                fill=self.colors['circle_part'],
                outline=self.colors['line'],
                width=3
            )
            
            # Draw part number
            part_text = str(part)
            bbox = draw.textbbox((0, 0), part_text, font=self.font_large)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            draw.text((part_x - text_width // 2, parts_y - text_height // 2), 
                     part_text, fill=self.colors['text'], font=self.font_large)
        
        return img
    
    def generate_bar_model(self, total: int, parts: list, 
                          operation: str = 'addition',
                          label: bool = True) -> Image.Image:
        """
        Generate bar model (tape diagram).
        
        Args:
            total: The total value
            parts: List of part values
            operation: 'addition' or 'subtraction'
            label: Whether to add text labels
        
        Returns:
            PIL Image with bar model
        """
        img = Image.new('RGB', (self.default_width, self.default_height), 
                        self.colors['background'])
        draw = ImageDraw.Draw(img)
        
        # Bar dimensions
        bar_height = 60
        max_bar_width = 600
        start_x = 100
        start_y = 150
        
        # Calculate scaling factor
        scale = max_bar_width / total
        
        # Draw title
        if label:
            if operation == 'addition':
                title = f"Bar Model: {' + '.join(map(str, parts))} = {total}"
            else:
                title = f"Bar Model: {total} - {parts[0]} = {parts[1]}"
            draw.text((20, 20), title, fill=self.colors['text'], 
                     font=self.font_medium)
        
        if operation == 'addition':
            # Draw individual part bars
            current_x = start_x
            colors = [self.colors['bar_part1'], self.colors['bar_part2'], 
                     '#A29BFE', '#FD79A8']  # Add more colors for multiple parts
            
            for i, part in enumerate(parts):
                part_width = int(part * scale)
                color = colors[i % len(colors)]
                
                # Draw part bar
                draw.rectangle(
                    [current_x, start_y, current_x + part_width, start_y + bar_height],
                    fill=color,
                    outline=self.colors['line'],
                    width=2
                )
                
                # Draw part label
                label_text = str(part)
                bbox = draw.textbbox((0, 0), label_text, font=self.font_medium)
                text_width = bbox[2] - bbox[0]
                draw.text((current_x + part_width // 2 - text_width // 2, 
                          start_y + bar_height // 2 - 10), 
                         label_text, fill=self.colors['text'], 
                         font=self.font_medium)
                
                current_x += part_width
            
            # Draw total bar below
            total_bar_y = start_y + bar_height + 40
            draw.rectangle(
                [start_x, total_bar_y, start_x + max_bar_width, 
                 total_bar_y + bar_height],
                fill=self.colors['bar_total'],
                outline=self.colors['line'],
                width=2
            )
            
            # Draw total label
            total_text = str(total)
            bbox = draw.textbbox((0, 0), total_text, font=self.font_medium)
            text_width = bbox[2] - bbox[0]
            draw.text((start_x + max_bar_width // 2 - text_width // 2, 
                      total_bar_y + bar_height // 2 - 10), 
                     total_text, fill=self.colors['text'], font=self.font_medium)
        
        else:  # subtraction
            # Draw total bar
            draw.rectangle(
                [start_x, start_y, start_x + max_bar_width, start_y + bar_height],
                fill=self.colors['bar_total'],
                outline=self.colors['line'],
                width=2
            )
            
            # Draw label for total
            total_text = str(total)
            draw.text((start_x + max_bar_width // 2 - 20, start_y - 30), 
                     total_text, fill=self.colors['text'], font=self.font_medium)
            
            # Draw subtracted part below
            part_width = int(parts[0] * scale)
            part_y = start_y + bar_height + 40
            
            draw.rectangle(
                [start_x, part_y, start_x + part_width, part_y + bar_height],
                fill=self.colors['bar_part1'],
                outline=self.colors['line'],
                width=2
            )
            
            # Draw remaining part
            remaining_width = max_bar_width - part_width
            draw.rectangle(
                [start_x + part_width, part_y, start_x + max_bar_width, 
                 part_y + bar_height],
                fill=self.colors['bar_part2'],
                outline=self.colors['line'],
                width=2
            )
            
            # Labels
            draw.text((start_x + part_width // 2 - 10, part_y + bar_height // 2 - 10), 
                     str(parts[0]), fill=self.colors['text'], font=self.font_medium)
            draw.text((start_x + part_width + remaining_width // 2 - 10, 
                      part_y + bar_height // 2 - 10), 
                     str(parts[1]), fill=self.colors['text'], font=self.font_medium)
        
        return img
    
    def generate_number_line(self, start: int, end: int, 
                            highlight: int = None,
                            interval: int = None,
                            label: bool = True) -> Image.Image:
        """
        Generate number line with optional highlighting.
        
        Args:
            start: Starting number
            end: Ending number
            highlight: Number to highlight (optional)
            interval: Interval between marks (auto-calculated if None)
            label: Whether to add text labels
        
        Returns:
            PIL Image with number line
        """
        img = Image.new('RGB', (self.default_width, self.default_height), 
                        self.colors['background'])
        draw = ImageDraw.Draw(img)
        
        # Number line dimensions
        line_y = 200
        line_start_x = 80
        line_end_x = self.default_width - 80
        line_length = line_end_x - line_start_x
        
        # Calculate interval if not provided
        if interval is None:
            range_size = end - start
            if range_size <= 10:
                interval = 1
            elif range_size <= 100:
                interval = 10
            elif range_size <= 1000:
                interval = 100
            else:
                interval = 1000
        
        # Draw title
        if label:
            draw.text((20, 20), f"Number Line: {start} to {end}", 
                     fill=self.colors['text'], font=self.font_medium)
        
        # Draw main line
        draw.line([line_start_x, line_y, line_end_x, line_y], 
                 fill=self.colors['number_line'], width=4)
        
        # Calculate positions and draw tick marks
        range_size = end - start
        scale = line_length / range_size
        
        current = start
        while current <= end:
            # Calculate x position
            offset = current - start
            x = line_start_x + int(offset * scale)
            
            # Determine tick height (longer for major intervals)
            if current == start or current == end or current % (interval * 10) == 0:
                tick_height = 25
                label_font = self.font_medium
            elif current % interval == 0:
                tick_height = 15
                label_font = self.font_small
            else:
                tick_height = 8
                label_font = self.font_small
            
            # Draw tick mark
            draw.line([x, line_y - tick_height, x, line_y + tick_height], 
                     fill=self.colors['number_line'], width=2)
            
            # Draw label for major ticks
            if current % interval == 0:
                label_text = str(current)
                bbox = draw.textbbox((0, 0), label_text, font=label_font)
                text_width = bbox[2] - bbox[0]
                draw.text((x - text_width // 2, line_y + 35), 
                         label_text, fill=self.colors['text'], font=label_font)
            
            current += max(1, interval // 10)  # Smaller steps for minor ticks
        
        # Highlight specific number if provided
        if highlight is not None and start <= highlight <= end:
            offset = highlight - start
            x = line_start_x + int(offset * scale)
            
            # Draw highlight circle
            circle_radius = 12
            draw.ellipse(
                [x - circle_radius, line_y - circle_radius,
                 x + circle_radius, line_y + circle_radius],
                fill=self.colors['highlight'],
                outline=self.colors['line'],
                width=3
            )
            
            # Draw arrow pointing to highlight
            arrow_y = line_y - 60
            draw.line([x, arrow_y, x, line_y - circle_radius - 5], 
                     fill=self.colors['highlight'], width=3)
            draw.polygon([x, arrow_y, x - 8, arrow_y + 15, x + 8, arrow_y + 15], 
                        fill=self.colors['highlight'])
            
            # Label the highlighted number
            label_text = str(highlight)
            bbox = draw.textbbox((0, 0), label_text, font=self.font_medium)
            text_width = bbox[2] - bbox[0]
            draw.text((x - text_width // 2, arrow_y - 30), 
                     label_text, fill=self.colors['highlight'], 
                     font=self.font_medium)
        
        return img
    
    def to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string for web display"""
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"
    
    def generate(self, visual_type: str, params: Dict[str, Any]) -> Image.Image:
        """
        Main generation method - routes to appropriate generator.
        
        Args:
            visual_type: One of 'base10_blocks', 'part_whole_model', 
                        'bar_model', 'number_line'
            params: Dictionary of parameters for the visual type
        
        Returns:
            PIL Image
        """
        if visual_type == 'base10_blocks':
            # Check if this is a 4-digit number (has thousands or hundreds)
            if 'thousands' in params or 'hundreds' in params:
                return self.generate_base10_blocks_4digit(
                    thousands=params.get('thousands', 0),
                    hundreds=params.get('hundreds', 0),
                    tens=params.get('tens', 0),
                    ones=params.get('ones', 0),
                    label=params.get('label', True)
                )
            else:
                # 2-digit representation (original method)
                return self.generate_base10_blocks(
                    tens=params.get('tens', 0),
                    ones=params.get('ones', 0),
                    label=params.get('label', True)
                )
        elif visual_type == 'part_whole_model':
            return self.generate_part_whole_model(
                total=params.get('total', 0),
                parts=params.get('parts', []),
                label=params.get('label', True)
            )
        elif visual_type == 'bar_model':
            return self.generate_bar_model(
                total=params.get('total', 0),
                parts=params.get('parts', []),
                operation=params.get('operation', 'addition'),
                label=params.get('label', True)
            )
        elif visual_type == 'number_line':
            return self.generate_number_line(
                start=params.get('start', 0),
                end=params.get('end', 100),
                highlight=params.get('highlight'),
                interval=params.get('interval'),
                label=params.get('label', True)
            )
        else:
            raise ValueError(f"Unknown visual type: {visual_type}")
