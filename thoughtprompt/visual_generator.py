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
