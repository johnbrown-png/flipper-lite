"""
Reverse Reorganize Curriculum
Combines split curriculum rows (with A/B/C suffixes) back to original structure.
Preserves correspondence between small_steps and SS{i}_desc_short.

Handles:
- Topics with original suffixes (A, B) that were split into double suffixes (A A, A B, A C)
- Removes only the LAST suffix (the split suffix), preserving original suffix
- Maps split positions back to original consecutive positions
- Expands columns to accommodate all small steps and desc_short fields
"""

import pandas as pd
import re
from pathlib import Path
from datetime import datetime


def calculate_splits(total_steps):
    """
    Replicate the split logic from reorganize_curriculum.py.
    Returns list of (start_idx, end_idx) tuples (1-indexed, inclusive).
    """
    if total_steps < 6:
        return [(1, total_steps)]
    
    splits = []
    splits.append((1, 5))  # First chunk always 1-5
    remaining = total_steps - 5
    current_start = 6
    
    while remaining > 0:
        if remaining <= 7:
            splits.append((current_start, current_start + remaining - 1))
            break
        else:
            splits.append((current_start, current_start + 4))
            current_start += 5
            remaining -= 5
    
    return splits


def extract_base_topic_and_suffix(topic_name):
    """
    Extract base topic name and split suffix.
    Handles double suffixes like "Multiplication and division A B".
    
    Returns:
        (base_topic, split_suffix)
        e.g., "Multiplication and division A B" → ("Multiplication and division A", "B")
        e.g., "Place value within 10 C" → ("Place value within 10", "C")
    """
    if not isinstance(topic_name, str):
        return topic_name, None
    
    # Match pattern: ends with space + single letter (A-Z)
    match = re.search(r'^(.+)\s+([A-Z])$', topic_name.strip())
    
    if match:
        base_topic = match.group(1)
        suffix = match.group(2)
        return base_topic, suffix
    
    return topic_name, None


def count_small_steps(row, prefix="Small Step"):
    """Count non-empty small step columns in a row."""
    count = 0
    for i in range(1, 30):
        col_name = f'{prefix} {i}'
        if col_name in row.index and pd.notna(row[col_name]) and str(row[col_name]).strip():
            count += 1
        else:
            # Check if there are more after a gap
            has_more = False
            for j in range(i+1, 30):
                check_col = f'{prefix} {j}'
                if check_col in row.index and pd.notna(row[check_col]) and str(row[check_col]).strip():
                    has_more = True
                    break
            if not has_more:
                break
            count += 1
    return count


def create_combined_row(group_df, metadata_cols, max_steps=21):
    """
    Combine split rows back into a single row with original positioning.
    
    Args:
        group_df: DataFrame of split rows (A, B, C, etc.) for one topic
        metadata_cols: List of metadata column names to copy
        max_steps: Maximum number of small_step columns to create
        
    Returns:
        Dictionary representing the combined row
    """
    # Sort by suffix (A, B, C, etc.)
    group_df['_suffix_sort'] = group_df['_split_suffix'].fillna('').apply(
        lambda x: x if x else 'NONE'
    )
    group_df = group_df.sort_values('_suffix_sort')
    
    # Initialize combined row with metadata from first split
    first_row = group_df.iloc[0]
    combined = {}
    
    for col in metadata_cols:
        if col == 'Topic':
            # Use base topic name (without split suffix)
            combined['Topic'] = first_row['_base_topic']
        elif col in first_row.index:
            combined[col] = first_row[col]
    
    # Calculate total steps across all splits
    total_steps = 0
    for _, row in group_df.iterrows():
        total_steps += count_small_steps(row)
    
    # Get expected split pattern
    expected_splits = calculate_splits(total_steps)
    
    # Verify we have the expected number of splits
    if len(group_df) != len(expected_splits):
        print(f"⚠️  Warning: Topic '{first_row['_base_topic']}' has {len(group_df)} splits, expected {len(expected_splits)}")
    
    # Map each split's data to original positions
    cumulative_offset = 0
    
    for split_idx, (_, row) in enumerate(group_df.iterrows()):
        # Count steps in this split
        steps_in_split = count_small_steps(row)
        
        # Map each position to original position
        for pos in range(1, steps_in_split + 1):
            original_pos = cumulative_offset + pos
            
            if original_pos > max_steps:
                print(f"⚠️  Warning: Position {original_pos} exceeds max_steps {max_steps} for topic '{first_row['_base_topic']}'")
                continue
            
            # Copy small step
            small_step_col = f'Small Step {pos}'
            if small_step_col in row.index:
                combined[f'Small Step {original_pos}'] = row[small_step_col]
            
            # Copy SS_desc
            ss_desc_col = f'SS{pos}_desc'
            if ss_desc_col in row.index:
                combined[f'SS{original_pos}_desc'] = row[ss_desc_col]
            
            # Copy SS_desc_short
            ss_desc_short_col = f'SS{pos}_desc_short'
            if ss_desc_short_col in row.index:
                combined[f'SS{original_pos}_desc_short'] = row[ss_desc_short_col]
        
        cumulative_offset += steps_in_split
    
    # Recreate UniqueRow without split suffix (include Difficulty after Term)
    if 'Year' in combined and 'Term' in combined and 'Topic' in combined:
        year_str = str(combined['Year']).replace(' ', '')
        term_str = str(combined['Term']).replace(' ', '')
        # Include Difficulty if present (for Year 10/11), filter out 'nan'
        difficulty_val = combined.get('Difficulty', '')
        difficulty_str = str(difficulty_val).replace(' ', '') if pd.notna(difficulty_val) and str(difficulty_val).lower() != 'nan' else ''
        topic_str = str(combined['Topic']).replace(' ', '')
        combined['UniqueRow'] = f"{year_str}{term_str}{difficulty_str}{topic_str}"
    
    return combined


def reverse_reorganize(input_file, output_file, max_steps=21):
    """
    Main function to reverse the curriculum reorganization.
    
    Args:
        input_file: Path to split curriculum CSV (mat_curr_short_import)
        output_file: Path for output combined curriculum CSV
        max_steps: Maximum number of small step columns (default: 21)
    """
    print(f"\n{'='*80}")
    print(f"REVERSE CURRICULUM REORGANIZATION")
    print(f"{'='*80}\n")
    
    print(f"Reading input file: {input_file}")
    df = pd.read_csv(input_file)
    print(f"✓ Loaded {len(df)} rows")
    
    # Extract base topic and split suffix for each row
    df['_base_topic'], df['_split_suffix'] = zip(*df['Topic'].apply(extract_base_topic_and_suffix))
    
    # Identify metadata columns (non-step, non-desc columns)
    metadata_cols = ['UniqueRow', 'Year', 'Age', 'Term', 'block', 'Difficulty', 'macro_topic', 'Topic']
    metadata_cols = [col for col in metadata_cols if col in df.columns]
    
    # Group by base topic and other identifying columns (include Difficulty for Year 10/11)
    group_cols = ['Year', 'Term', 'Difficulty', 'block', '_base_topic']
    
    # Identify rows that need combining (have split suffix)
    split_rows = df[df['_split_suffix'].notna()].copy()
    unsplit_rows = df[df['_split_suffix'].isna()].copy()
    
    print(f"✓ Found {len(split_rows)} split rows to combine")
    print(f"✓ Found {len(unsplit_rows)} unsplit rows to pass through")
    
    # Combine split rows
    combined_rows = []
    
    if len(split_rows) > 0:
        grouped = split_rows.groupby(group_cols, dropna=False)
        print(f"✓ Identified {len(grouped)} unique topics to recombine")
        
        for group_key, group_df in grouped:
            try:
                combined_row = create_combined_row(group_df, metadata_cols, max_steps)
                combined_rows.append(combined_row)
            except Exception as e:
                print(f"❌ Error combining group {group_key}: {e}")
                continue
    
    # Handle unsplit rows - add empty desc_short columns
    for _, row in unsplit_rows.iterrows():
        row_dict = row.to_dict()
        
        # Recreate UniqueRow if needed (include Difficulty after Term)
        if 'Year' in row_dict and 'Term' in row_dict and 'Topic' in row_dict:
            year_str = str(row_dict['Year']).replace(' ', '')
            term_str = str(row_dict['Term']).replace(' ', '')
            # Include Difficulty if present (for Year 10/11), filter out 'nan'
            difficulty_val = row_dict.get('Difficulty', '')
            difficulty_str = str(difficulty_val).replace(' ', '') if pd.notna(difficulty_val) and str(difficulty_val).lower() != 'nan' else ''
            topic_str = str(row_dict['Topic']).replace(' ', '')
            row_dict['UniqueRow'] = f"{year_str}{term_str}{difficulty_str}{topic_str}"
        
        combined_rows.append(row_dict)
    
    # Create output dataframe
    print(f"\n✓ Creating output with {len(combined_rows)} rows")
    output_df = pd.DataFrame(combined_rows)
    
    # Ensure all columns exist in proper order
    output_cols = metadata_cols.copy()
    
    # Add small step columns
    for i in range(1, max_steps + 1):
        output_cols.append(f'Small Step {i}')
    
    # Add SS_desc columns
    for i in range(1, max_steps + 1):
        output_cols.append(f'SS{i}_desc')
    
    # Add SS_desc_short columns
    for i in range(1, max_steps + 1):
        output_cols.append(f'SS{i}_desc_short')
    
    # Add any columns that exist in data but not in output_cols
    for col in output_df.columns:
        if col not in output_cols and not col.startswith('_'):
            output_cols.append(col)
    
    # Reindex with all columns
    output_df = output_df.reindex(columns=output_cols)
    
    # Remove temporary columns
    output_df = output_df[[col for col in output_df.columns if not col.startswith('_')]]
    
    # Save output
    print(f"\nSaving to: {output_file}")
    output_df.to_csv(output_file, index=False)
    print(f"✓ Saved {len(output_df)} rows")
    
    # Summary statistics
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    print(f"Input rows:     {len(df)}")
    print(f"Output rows:    {len(output_df)}")
    print(f"Rows combined:  {len(split_rows) - len(combined_rows) if len(split_rows) > 0 else 0}")
    print(f"Max steps:      {max_steps}")
    print(f"{'='*80}\n")
    
    return output_df


def main():
    """Main entry point."""
    input_file = Path(r"C:\Users\johnf\OneDrive\Documents\Visual Studio Code\flipper16012026\Curriculum\Maths\mat_curr_short_import - 08032026.csv")
    output_dir = Path(r"C:\Users\johnf\OneDrive\Documents\Visual Studio Code\flipper16012026\curr_reorg\reverse_reorg")
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"curriculum_reversed_{timestamp}.csv"
    
    # Run reverse reorganization with max_steps=40 to accommodate topics up to 38 steps
    try:
        result_df = reverse_reorganize(input_file, output_file, max_steps=40)
        print(f"✅ SUCCESS: Reverse reorganization complete!")
        print(f"📁 Output saved to: {output_file}")
        return result_df
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    main()
