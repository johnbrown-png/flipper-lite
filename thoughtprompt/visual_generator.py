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
        top_color = '#87CEEB'      # Sky blue
        right_color = '#4682B4'    # Steel blue (darker)
        left_color = '#1E3A8A'     # Dark blue (darkest)
        
        # Total size for 10×10×10 structure
        cube_size = unit_size * 10
        iso_width = cube_size
        iso_height = int(cube_size * 0.5)
        
        # Top face - shows 10×10 grid
        top_points = [
            (x, y),
            (x + iso_width, y + iso_height),
            (x + iso_width, y + iso_height + cube_size),
            (x, y + cube_size)
        ]
        draw.polygon(top_points, fill=top_color, outline=self.colors['line'], width=2)
        
        # Draw grid on top to show 10×10 structure
        for i in range(1, 10):
            # Lines going right-down
            start_x = x + (iso_width // 10) * i
            start_y = y + (iso_height // 10) * i
            end_x = x + (iso_width // 10) * i
            end_y = y + cube_size + (iso_height // 10) * i
            draw.line([start_x, start_y, end_x, end_y],
                     fill=self.colors['line'], width=1)
            
            # Lines going right-up
            start_x = x
            start_y = y + (cube_size // 10) * i
            end_x = x + iso_width
            end_y = y + iso_height + (cube_size // 10) * i
            draw.line([start_x, start_y, end_x, end_y],
                     fill=self.colors['line'], width=1)
        
        # Right face - shows depth with grid
        right_points = [
            (x + iso_width, y + iso_height),
            (x + iso_width, y + iso_height + cube_size),
            (x + iso_width, y + iso_height + cube_size + iso_height),
            (x + iso_width, y + iso_height + iso_height)
        ]
        draw.polygon(right_points, fill=right_color, outline=self.colors['line'], width=2)
        
        # Grid on right face
        for i in range(1, 10):
            # Horizontal lines
            y_pos = y + iso_height + (cube_size // 10) * i
            draw.line([x + iso_width, y_pos, x + iso_width, y_pos + iso_height],
                     fill=self.colors['line'], width=1)
            
            # Vertical lines (showing depth)
            y_pos = y + iso_height + iso_height * (i / 10)
            draw.line([x + iso_width, y_pos, x + iso_width, y_pos + cube_size],
                     fill=self.colors['line'], width=1)
        
        # Left face - shows depth with grid
        left_points = [
            (x, y),
            (x, y + cube_size),
            (x, y + cube_size + iso_height),
            (x, y + iso_height)
        ]
        draw.polygon(left_points, fill=left_color, outline=self.colors['line'], width=2)
        
        # Grid on left face
        for i in range(1, 10):
            # Horizontal lines
            y_pos = y + (cube_size // 10) * i
            draw.line([x, y_pos, x, y_pos + iso_height],
                     fill=self.colors['line'], width=1)
            
            # Vertical lines (showing depth)
            y_pos = y + iso_height * (i / 10)
            draw.line([x, y_pos, x, y_pos + cube_size],
                     fill=self.colors['line'], width=1)
    
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
        img = Image.new('RGB', (self.default_width, self.default_height), 
                        self.colors['background'])
        draw = ImageDraw.Draw(img)
        
        # Define margins
        margin_left = 60
        margin_right = 60
        margin_top = 60 if label else 40  # More space if title present
        margin_bottom = 70 if label else 40  # More space if labels present
        
        # Draw title if labeling
        title_height = 0
        if label:
            title = f"Representing {tens * 10 + ones}"
            draw.text((margin_left, 20), title, fill=self.colors['text'], 
                     font=self.font_medium)
            title_height = 40
        
        # Calculate available space for the blocks
        available_width = self.default_width - margin_left - margin_right
        available_height = self.default_height - margin_top - margin_bottom
        
        # Base dimensions for blocks
        base_unit_size = 40  # Size of one unit cube
        base_spacing = 15
        
        # Calculate required dimensions with base size
        ones_cols = min(ones, 5) if ones > 0 else 0
        ones_rows = 2 if ones > 5 else 1
        
        required_width = tens * (base_unit_size + base_spacing) + (base_spacing * 2 if tens > 0 else 0) + ones_cols * (base_unit_size + base_spacing)
        required_height = base_unit_size * 10  # Ten-rod height is the limiting factor
        
        # Calculate scale factor to fit both width and height
        scale_x = available_width / required_width if required_width > 0 else 1.0
        scale_y = available_height / required_height if required_height > 0 else 1.0
        scale = min(scale_x, scale_y, 1.0)  # Never scale up, only down
        
        # Apply scaling
        unit_size = int(base_unit_size * scale)
        spacing = int(base_spacing * scale)
        ten_rod_width = unit_size
        ten_rod_height = unit_size * 10
        
        # Calculate actual content dimensions
        ones_rows_actual = 2 if ones > 5 else 1
        content_height = max(ten_rod_height, unit_size * ones_rows_actual + spacing if ones > 5 else unit_size)
        content_width = tens * (ten_rod_width + spacing) + (spacing * 2 if tens > 0 else 0) + ones_cols * (unit_size + spacing)
        
        # Center the content within available space
        start_x = margin_left + (available_width - content_width) // 2
        start_y = margin_top + (available_height - content_height) // 2
        
        # Draw ten-rods
        current_x = start_x
        for i in range(tens):
            # Draw the ten-rod rectangle
            draw.rectangle(
                [current_x, start_y, 
                 current_x + ten_rod_width, start_y + ten_rod_height],
                fill=self.colors['ten_rod'],
                outline=self.colors['line'],
                width=2
            )
            
            # Draw horizontal lines to show 10 units
            for j in range(1, 10):
                y = start_y + (j * unit_size)
                draw.line(
                    [current_x, y, current_x + ten_rod_width, y],
                    fill=self.colors['background'],
                    width=1
                )
            
            current_x += ten_rod_width + spacing
        
        # Add spacing between tens and ones
        if tens > 0:
            current_x += spacing * 2
        
        # Draw unit cubes
        ones_start_x = current_x
        for i in range(ones):
            # Arrange ones in 2 rows if more than 5
            if i < 5:
                x = ones_start_x + (i * (unit_size + spacing))
                y = start_y
            else:
                x = ones_start_x + ((i - 5) * (unit_size + spacing))
                y = start_y + unit_size + spacing
            
            draw.rectangle(
                [x, y, x + unit_size, y + unit_size],
                fill=self.colors['unit_cube'],
                outline=self.colors['line'],
                width=2
            )
        
        # Add labels
        if label:
            # Position labels below the content with some spacing
            label_y = start_y + content_height + int(20 * scale)
            
            if tens > 0:
                tens_label_x = start_x + (tens * (ten_rod_width + spacing)) // 2
                draw.text((tens_label_x - 40, label_y), 
                         f"{tens} ten{'s' if tens != 1 else ''}", 
                         fill=self.colors['text'], font=self.font_small)
            
            if ones > 0:
                ones_label_x = ones_start_x + (min(ones, 5) * (unit_size + spacing)) // 2
                draw.text((ones_label_x - 40, label_y), 
                         f"{ones} one{'s' if ones != 1 else ''}", 
                         fill=self.colors['text'], font=self.font_small)
        
        return img
    
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
        # Use larger canvas for 4-digit numbers
        img_width = 1200
        img_height = 700
        img = Image.new('RGB', (img_width, img_height), self.colors['background'])
        draw = ImageDraw.Draw(img)
        
        # Calculate base unit size dynamically based on number of blocks
        # Smaller size when we have many thousands
        total_thousands_space = thousands * 10  # Each thousand needs 10 units of space
        total_hundreds_space = hundreds * 10    # Each hundred needs 10 units of space
        
        # Adjust unit size based on content
        if thousands >= 4 or (thousands > 0 and hundreds >= 5):
            base_unit = 15  # Smaller for many blocks
        elif thousands >= 2 or hundreds >= 5:
            base_unit = 20  # Medium for moderate blocks
        else:
            base_unit = 25  # Larger for fewer blocks
        
        spacing = max(20, int(base_unit * 0.8))
        
        # Margins
        margin_left = 40
        margin_top = 60 if label else 30
        
        # Title
        if label:
            total_value = thousands * 1000 + hundreds * 100 + tens * 10 + ones
            title = f"Representing {total_value:,}"
            draw.text((margin_left, 15), title, fill=self.colors['text'],
                     font=self.font_medium)
        
        # Starting position
        current_x = margin_left
        current_y = margin_top
        
        # Track label positions for later
        label_positions = []
        
        # Calculate block dimensions for layout
        thousand_block_width = (base_unit * 10) + int(base_unit * 5)  # Width including isometric projection
        hundred_block_width = (base_unit * 10) + int(base_unit * 5)
        
        # Draw thousands (10×10×10 cubes)
        if thousands > 0:
            thousands_start_x = current_x
            for i in range(thousands):
                # Arrange in 2 rows if more than 3
                if thousands > 3 and i >= 3:
                    x = thousands_start_x + (i - 3) * (thousand_block_width + spacing)
                    y = current_y + (base_unit * 10) + int(base_unit * 5) + spacing + 20
                else:
                    x = thousands_start_x + i * (thousand_block_width + spacing)
                    y = current_y
                
                self._draw_isometric_thousand_cube(draw, x, y, base_unit)
                label_positions.append(('thousands', x, y, base_unit * 10))
            
            # Move x position past all thousands
            if thousands <= 3:
                current_x = thousands_start_x + thousands * (thousand_block_width + spacing)
            else:
                current_x = thousands_start_x + 3 * (thousand_block_width + spacing)
        
        # Add extra spacing between place values
        if thousands > 0:
            current_x += spacing
        
        # Draw hundreds (10×10×1 flats)
        if hundreds > 0:
            hundreds_start_x = current_x
            for i in range(hundreds):
                # Stack hundreds in 2 rows if more than 4
                if hundreds > 4 and i >= 4:
                    x = hundreds_start_x + (i - 4) * (hundred_block_width + spacing)
                    y = current_y + (base_unit * 10) + spacing + 15
                else:
                    x = hundreds_start_x + i * (hundred_block_width + spacing)
                    y = current_y
                
                self._draw_isometric_hundred_flat(draw, x, y, base_unit)
                label_positions.append(('hundreds', x, y, base_unit * 10))
            
            # Move x position past all hundreds
            if hundreds <= 4:
                current_x = hundreds_start_x + hundreds * (hundred_block_width + spacing)
            else:
                current_x = hundreds_start_x + 4 * (hundred_block_width + spacing)
        
        # Add spacing
        if hundreds > 0:
            current_x += spacing
        
        # Draw tens (simple 2D rectangles, smaller for 4-digit context)
        if tens > 0:
            tens_start_x = current_x
            ten_width = base_unit
            ten_height = base_unit * 10
            
            for i in range(tens):
                draw.rectangle(
                    [current_x, current_y,
                     current_x + ten_width, current_y + ten_height],
                    fill=self.colors['ten_rod'],
                    outline=self.colors['line'],
                    width=2
                )
                
                # Show 10 units with lines
                for j in range(1, 10):
                    y = current_y + (j * base_unit)
                    draw.line(
                        [current_x, y, current_x + ten_width, y],
                        fill=self.colors['background'],
                        width=1
                    )
                
                label_positions.append(('tens', current_x, current_y, ten_height))
                current_x += ten_width + (spacing // 2)
        
        # Add spacing
        if tens > 0:
            current_x += spacing
        
        # Draw ones (simple 2D squares, smaller for 4-digit context)
        if ones > 0:
            ones_start_x = current_x
            unit_size = base_unit
            
            for i in range(ones):
                # Arrange in 2 rows if more than 5
                if i < 5:
                    x = ones_start_x + (i * (unit_size + (spacing // 2)))
                    y = current_y
                else:
                    x = ones_start_x + ((i - 5) * (unit_size + (spacing // 2)))
                    y = current_y + unit_size + (spacing // 2)
                
                draw.rectangle(
                    [x, y, x + unit_size, y + unit_size],
                    fill=self.colors['unit_cube'],
                    outline=self.colors['line'],
                    width=2
                )
                
                if i == 0:
                    label_positions.append(('ones', x, y, unit_size))
        
        # Add labels at bottom
        if label:
            label_y = img_height - 50
            
            # Count each type for labels
            place_counts = {
                'thousands': thousands,
                'hundreds': hundreds,
                'tens': tens,
                'ones': ones
            }
            
            x_offset = margin_left
            for place_name, count in place_counts.items():
                if count > 0:
                    label_text = f"{count} {place_name}" if count > 1 else f"{count} {place_name[:-1]}"
                    draw.text((x_offset, label_y), label_text,
                             fill=self.colors['text'], font=self.font_small)
                    x_offset += 180
        
        return img
    
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
