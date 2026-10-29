"""
Reorganize curriculum CSV to split rows with 6+ small steps into multiple rows
with a maximum of 7 small steps per row, preserving the correspondence between
small_step_N and KQN columns.
"""

import pandas as pd
import string
from pathlib import Path


def count_small_steps(row):
    """Count non-empty small_step columns in a row."""
    count = 0
    for i in range(1, 30):  # small_step_1 through small_step_29
        col_name = f'small_step_{i}'
        if col_name in row.index and pd.notna(row[col_name]) and str(row[col_name]).strip():
            count += 1
        else:
            break  # Stop at first empty cell (assuming contiguous)
    return count


def calculate_splits(total_steps):
    """
    Calculate how to split steps based on the balanced distribution strategy:
    - 6-10 steps: A (1-5), B (6-end)
    - 11-17 steps: A (1-5), B (6-10), C (11-end, up to 7)
    - 18+ steps: Continue 5-step chunks until remainder <8, then put all in last row
    
    Returns list of (start_idx, end_idx) tuples (1-indexed, inclusive)
    """
    if total_steps < 6:
        return [(1, total_steps)]
    
    splits = []
    
    # First chunk is always 1-5
    splits.append((1, 5))
    remaining = total_steps - 5
    current_start = 6
    
    while remaining > 0:
        if remaining <= 7:
            # Put all remaining in last chunk
            splits.append((current_start, current_start + remaining - 1))
            break
        else:
            # Take next 5 steps
            splits.append((current_start, current_start + 4))
            current_start += 5
            remaining -= 5
    
    return splits


def create_split_row(original_row, start_idx, end_idx, suffix, metadata_cols):
    """
    Create a new row with small_steps from start_idx to end_idx,
    shifting them to start at small_step_1.
    """
    new_row = {}
    
    # Copy metadata fields
    for col in metadata_cols:
        if col == 'sub_topic':
            # Append suffix to sub_topic
            original_value = original_row[col]
            if pd.notna(original_value) and str(original_value).strip():
                new_row[col] = f"{original_value} {suffix}"
            else:
                new_row[col] = f" {suffix}"
        else:
            new_row[col] = original_row[col]
    
    # Copy small_steps and corresponding KQ, shifting to start at position 1
    for new_pos, orig_pos in enumerate(range(start_idx, end_idx + 1), start=1):
        # Copy small_step
        small_step_col = f'small_step_{orig_pos}'
        new_small_step_col = f'small_step_{new_pos}'
        if small_step_col in original_row.index:
            new_row[new_small_step_col] = original_row[small_step_col]
        
        # Copy corresponding KQ if it exists
        kq_col = f'KQ{orig_pos}'
        new_kq_col = f'KQ{new_pos}'
        if kq_col in original_row.index:
            new_row[new_kq_col] = original_row[kq_col]
    
    return new_row


def reorganize_curriculum(input_file, output_file):
    """Main function to reorganize the curriculum CSV."""
    
    print(f"Reading {input_file}...")
    df = pd.read_csv(input_file)
    
    print(f"Original CSV has {len(df)} rows")
    
    # Identify metadata columns
    metadata_cols = ['year', 'term', 'block', 'difficulty', 'topic', 'sub_topic']
    
    # Identify small_step and KQ columns
    small_step_cols = [col for col in df.columns if col.startswith('small_step_')]
    kq_cols = [col for col in df.columns if col.startswith('KQ') and col[2:].isdigit()]
    
    all_data_cols = metadata_cols + small_step_cols + kq_cols
    
    new_rows = []
    split_count = 0
    unchanged_count = 0
    
    for idx, row in df.iterrows():
        total_steps = count_small_steps(row)
        
        if total_steps < 6:
            # No split needed, keep row as-is
            new_rows.append(row)
            unchanged_count += 1
        else:
            # Split the row
            splits = calculate_splits(total_steps)
            split_count += 1
            
            print(f"  Row {idx + 1}: '{row['sub_topic']}' has {total_steps} steps -> splitting into {len(splits)} rows")
            
            # Create new rows with letter suffixes
            for split_idx, (start, end) in enumerate(splits):
                suffix = string.ascii_uppercase[split_idx]
                new_row_data = create_split_row(row, start, end, suffix, metadata_cols)
                
                # Create a complete row with all columns
                full_row = pd.Series(index=df.columns, dtype=object)
                for col, val in new_row_data.items():
                    if col in full_row.index:
                        full_row[col] = val
                
                new_rows.append(full_row)
                
                print(f"    -> {suffix} (steps {start}-{end})")
    
    # Create new DataFrame
    new_df = pd.DataFrame(new_rows, columns=df.columns)
    
    # Write to output file
    print(f"\nWriting to {output_file}...")
    new_df.to_csv(output_file, index=False)
    
    print(f"\n✓ Complete!")
    print(f"  Original rows: {len(df)}")
    print(f"  Output rows: {len(new_df)}")
    print(f"  Rows split: {split_count}")
    print(f"  Rows unchanged: {unchanged_count}")
    print(f"  New rows created: {len(new_df) - len(df)}")


if __name__ == "__main__":
    input_file = Path(r"C:\Users\johnf\OneDrive\Documents\Visual Studio Code\flipper16012026\curr_reorg\all_years_KQ.csv")
    output_file = Path(r"C:\Users\johnf\OneDrive\Documents\Visual Studio Code\flipper16012026\curr_reorg\reorg_KQ.csv")
    
    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
    else:
        reorganize_curriculum(input_file, output_file)
        print(f"\n✓ Reorganized curriculum saved to: {output_file}")
