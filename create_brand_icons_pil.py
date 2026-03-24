"""
Create brand icon PNG files directly using Pillow for social media platforms.
Uses Professional Blue color scheme matching flipper.py lines 326-330.
Sizes: 512x512 (general), 1024x1024 (high-res), 180x180 (favicon), 256x256
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_circular_icon(size):
    """Create a circular brand icon with the flipper school branding in Professional Blue."""
    
    # Create image with transparent background
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Professional Blue color scheme (from flipper.py lines 326-330)
    # Gradient: #1e3a5f, #2c5f8d, #4a90c8
    bg_color_dark = (30, 58, 95)     # #1e3a5f - Dark blue
    bg_color_mid = (44, 95, 141)     # #2c5f8d - Medium blue
    bg_color_light = (74, 144, 200)  # #4a90c8 - Light blue
    text_color = (240, 244, 248)     # #f0f4f8 - Light gray/white
    accent_color = (255, 215, 0)     # #FFD700 - Gold accent
    
    # Create gradient background - using radial gradient effect
    center_x = size // 2
    center_y = size // 2
    
    # Draw gradient circles from outside to inside
    for i in range(size // 2, 0, -1):
        progress = i / (size // 2)
        # Interpolate between dark and light blue
        if progress > 0.5:
            # Outer half: dark to mid
            factor = (progress - 0.5) * 2
            r = int(bg_color_mid[0] + (bg_color_dark[0] - bg_color_mid[0]) * factor)
            g = int(bg_color_mid[1] + (bg_color_dark[1] - bg_color_mid[1]) * factor)
            b = int(bg_color_mid[2] + (bg_color_dark[2] - bg_color_mid[2]) * factor)
        else:
            # Inner half: mid to light
            factor = progress * 2
            r = int(bg_color_light[0] + (bg_color_mid[0] - bg_color_light[0]) * factor)
            g = int(bg_color_light[1] + (bg_color_mid[1] - bg_color_light[1]) * factor)
            b = int(bg_color_light[2] + (bg_color_mid[2] - bg_color_light[2]) * factor)
        
        color = (r, g, b)
        draw.ellipse([center_x - i, center_y - i, center_x + i, center_y + i], fill=color)
    
    # Draw circumference circle border with gap from edge (1-2mm inset)
    border_width = max(3, size // 100)  # Thicker border for visibility
    gap = size // 150  # Gap from edge (approximately 1-2mm)
    draw.ellipse([gap + border_width//2, gap + border_width//2, 
                  size - gap - border_width//2, size - gap - border_width//2], 
                 outline=text_color, width=border_width)
    
    # Calculate font sizes based on image size (increased for maximum visibility)
    main_font_size = size // 5      # Much larger for "Flipper"
    school_font_size = size // 6    # Much larger for "School"
    
    # Try to load a nice font, fallback to default
    try:
        # Try Arial Bold for main text
        main_font = ImageFont.truetype("arialbd.ttf", main_font_size)
        school_font = ImageFont.truetype("arialbd.ttf", school_font_size)
    except:
        try:
            # Try regular Arial
            main_font = ImageFont.truetype("arial.ttf", main_font_size)
            school_font = ImageFont.truetype("arial.ttf", school_font_size)
        except:
            # Fallback to default
            main_font = ImageFont.load_default()
            school_font = ImageFont.load_default()
    
    # Draw "Flipper" text (centered, large, capitalized)
    flipper_text = "Flipper"
    flipper_bbox = draw.textbbox((0, 0), flipper_text, font=main_font)
    flipper_width = flipper_bbox[2] - flipper_bbox[0]
    flipper_x = center_x - flipper_width // 2
    flipper_y = center_y - size // 6  # Brought closer to center
    draw.text((flipper_x, flipper_y), flipper_text, fill=text_color, font=main_font)
    
    # Draw "School" text (centered, large, proper case)
    school_text = "School"
    school_bbox = draw.textbbox((0, 0), school_text, font=school_font)
    school_width = school_bbox[2] - school_bbox[0]
    school_x = center_x - school_width // 2
    school_y = center_y + size // 20  # Brought closer to center
    draw.text((school_x, school_y), school_text, fill=text_color, font=school_font)
    
    return img

# Generate icons in various sizes
sizes = {
    'flipper_school_icon_1024.png': 1024,    # High resolution - best quality
    'flipper_school_icon_512.png': 512,      # General social media
    'flipper_school_icon_256.png': 256,      # Common profile size
    'flipper_school_icon_180.png': 180,      # Favicon/small icon
}

output_dir = 'images'
os.makedirs(output_dir, exist_ok=True)

print("Creating brand icons with Professional Blue color scheme...")
for filename, size in sizes.items():
    print(f"Creating {filename} ({size}x{size})...", end=' ')
    icon = create_circular_icon(size)
    output_path = os.path.join(output_dir, filename)
    icon.save(output_path, 'PNG', quality=95)
    print("✓")

print("\nAll icon files created successfully!")
print(f"Files saved to: {os.path.abspath(output_dir)}")
print("\nColor scheme: Professional Blue (matching flipper.py)")
print("Recommended usage:")
print("  • 1024x1024: YouTube, LinkedIn, high-res platforms")
print("  • 512x512: Instagram, TikTok, Facebook, Twitter")
print("  • 256x256: Google Workspace, smaller profiles")
print("  • 180x180: Favicon, app icons")
