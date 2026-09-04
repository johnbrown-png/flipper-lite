"""SVG circular progress gauge used by result cards."""

import math


def create_circular_progress_svg(score_pct, size=80, text_scale=1.0):
    """
    Create an SVG circular progress indicator.

    Args:
        score_pct: Score as percentage (0-100)
        size: Diameter of the circle in pixels
        text_scale: Multiplier for score text size in the center

    Returns:
        HTML string with SVG element
    """
    # Color based on score (Red -> Yellow -> Green spectrum)
    if score_pct >= 70:
        color = "#22c55e"  # Green
    elif score_pct >= 40:
        color = "#eab308"  # Yellow/Gold
    else:
        color = "#ef4444"  # Red

    # Calculate circle parameters
    radius = (size - 10) / 2
    circumference = 2 * math.pi * radius

    # Calculate the arc length for the scored portion
    # stroke-dasharray and stroke-dashoffset create the progress effect
    progress = (score_pct / 100) * circumference

    svg = f"""
    <svg width="{size}" height="{size}" style="transform: rotate(-90deg);">
        <!-- Background circle (gray) -->
        <circle
            cx="{size/2}"
            cy="{size/2}"
            r="{radius}"
            fill="none"
            stroke="#e5e7eb"
            stroke-width="8"
        />
        <!-- Progress circle (colored) -->
        <circle
            cx="{size/2}"
            cy="{size/2}"
            r="{radius}"
            fill="none"
            stroke="{color}"
            stroke-width="8"
            stroke-dasharray="{circumference}"
            stroke-dashoffset="{circumference - progress}"
            stroke-linecap="round"
        />
        <!-- Score text in center -->
        <text
            x="{size/2}"
            y="{size/2}"
            text-anchor="middle"
            dominant-baseline="middle"
            font-size="{20 * text_scale}"
            font-weight="bold"
            fill="{color}"
            style="transform: rotate(90deg); transform-origin: {size/2}px {size/2}px;"
        >{score_pct}%</text>
    </svg>
    """
    return svg
