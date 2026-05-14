"""
Epoch definitions for curriculum filtering.

Overlapping year ranges to handle learners who skip ahead or go back to basics.
"""

# Epoch definitions: (epoch_name, year_min, year_max, age_min, age_max)
EPOCHS = {
    'Early Primary': {
        'years': (1, 3),
        'ages': (5, 8),
        'display': 'Early Primary (Y1–3, Ages 5–8)'
    },
    'Middle Primary': {
        'years': (3, 5),
        'ages': (7, 10),
        'display': 'Middle Primary (Y3–5, Ages 7–10)'
    },
    'Late Primary': {
        'years': (5, 6),
        'ages': (9, 11),
        'display': 'Late Primary (Y5–6, Ages 9–11)'
    },
    'Early Secondary': {
        'years': (6, 9),
        'ages': (11, 14),
        'display': 'Early Secondary (Y6–9, Ages 11–14)'
    },
    'Middle Secondary': {
        'years': (8, 10),
        'ages': (13, 15),
        'display': 'Middle Secondary (Y8–10, Ages 13–15)'
    },
    'Late Secondary': {
        'years': (9, 11),
        'ages': (14, 16),
        'display': 'Late Secondary (Y9–11, Ages 14–16)'
    },
}


def get_epoch_year_range(epoch_name):
    """
    Get the year range for an epoch.
    
    Args:
        epoch_name: Key from EPOCHS dict
    
    Returns:
        Tuple of (year_min, year_max) or None if epoch not found
    """
    if epoch_name not in EPOCHS:
        return None
    return EPOCHS[epoch_name]['years']


def get_epoch_display_name(epoch_name):
    """Get the display-friendly name for an epoch."""
    if epoch_name not in EPOCHS:
        return epoch_name
    return EPOCHS[epoch_name]['display']


def parse_year_from_string(year_str):
    """
    Parse year number from curriculum year field (e.g., 'Year 1' → 1).
    
    Args:
        year_str: String like 'Year 1', 'Year 10', etc.
    
    Returns:
        Integer year, or None if parse fails
    """
    if not year_str or not isinstance(year_str, str):
        return None
    
    year_str = year_str.strip().lower()
    if year_str.startswith('year'):
        parts = year_str.split()
        if len(parts) >= 2:
            try:
                return int(parts[1])
            except ValueError:
                return None
    
    return None


def filter_curriculum_by_epoch(curriculum_df, epoch_name):
    """
    Filter curriculum DataFrame to only rows within epoch year range.
    
    Args:
        curriculum_df: Pandas DataFrame with 'year' column
        epoch_name: Key from EPOCHS dict
    
    Returns:
        Filtered DataFrame
    """
    year_range = get_epoch_year_range(epoch_name)
    if year_range is None:
        return curriculum_df  # Return all if epoch not found
    
    year_min, year_max = year_range
    
    # Parse year column and filter
    def extract_year(year_str):
        return parse_year_from_string(year_str)
    
    curriculum_df['_parsed_year'] = curriculum_df['year'].apply(extract_year)
    filtered = curriculum_df[
        (curriculum_df['_parsed_year'] >= year_min) &
        (curriculum_df['_parsed_year'] <= year_max)
    ].copy()
    filtered.drop(columns=['_parsed_year'], inplace=True)
    
    return filtered
