import pandas as pd
import os

# Paths
csv_file = r"Curriculum\Maths\curriculum_08052026_small_steps.csv"

# Read CSV
df = pd.read_csv(csv_file, encoding='utf-8-sig')

# Find Foundation "Expand double brackets" rows (currently rows with index 1211, 1213, 1215, 1217, 1219, 1221 in 0-indexed)
# small_step_num values: 1212, 1214, 1216, 1218, 1220, 1222
foundation_rows_mask = (df['topic'] == 'Expand double brackets') & (df['difficulty'] == 'Foundation')
foundation_indices = df[foundation_rows_mask].index.tolist()

print(f"Found Foundation rows at indices: {foundation_indices}")
print(f"small_step_num values: {df.loc[foundation_indices, 'small_step_num'].tolist()}")

# Extract data from first Foundation row (current 1212)
first_row_idx = foundation_indices[0]
first_row_data = df.loc[first_row_idx].copy()
print(f"\nFirst row ss_wr_desc (first 100 chars): {first_row_data['ss_wr_desc'][:100]}")

# Create new row for step 1 "Expand double brackets"
new_row = {
    'unique_row': 'Year10AutumnFoundationQuadraticexpressionsandequations',
    'year': 'Year 10',
    'age': '14-15',
    'term': 'Autumn',
    'difficulty': 'Foundation',
    'block_num': 3,
    'macro_topic': 'Algebra',
    'topic': 'Quadratic expressions and equations',
    'small_step_num': 1212,
    'small_step_num_in_topic': 1,
    'small_step_name': 'Expand double brackets',
    'ss_wr_desc': first_row_data['ss_wr_desc'],  # Keep from current 1212
    'ss_desc': 'Students expand double brackets in various forms using area models and algebra tiles.',
    'small_step_id': 'Year 10_14-15_Autumn_Foundation_Quadratic expressions and equations_1_Expand double brackets',
    'small_step_key': 'year-10__14-15__autumn__foundation__quadratic-expressions-and-equations__1__expand-double-brackets',
    'year_order': first_row_data['year_order'],
    'term_order': first_row_data['term_order'],
    'topic_order': first_row_data['topic_order'],
    'source_row_index': first_row_data['source_row_index'],
    'legacy_step_position': first_row_data['legacy_step_position']
}

# Insert new row at position 1211 (0-indexed)
df = pd.concat([df.iloc[:1211], pd.DataFrame([new_row]), df.iloc[1211:]], ignore_index=False).reset_index(drop=True)

# Now update all Foundation Quadratic rows
# Re-find the indices after insertion
foundation_rows_mask = (df['topic'] == 'Expand double brackets') & (df['difficulty'] == 'Foundation')
foundation_indices = df[foundation_rows_mask].index.tolist()

print(f"\nAfter insertion, Foundation rows at indices: {foundation_indices}")

# Update each Foundation row
for i, idx in enumerate(foundation_indices):
    # Skip the new row (first one)
    if i == 0:
        continue
    
    new_step_num_in_topic = i + 1
    current_small_step_num = df.loc[idx, 'small_step_num']
    
    # Increment small_step_num by 1 (since we inserted one row before)
    new_small_step_num = current_small_step_num + 1
    
    # Update topic
    df.loc[idx, 'topic'] = 'Quadratic expressions and equations'
    df.loc[idx, 'small_step_num'] = new_small_step_num
    df.loc[idx, 'small_step_num_in_topic'] = new_step_num_in_topic
    
    # Get current name
    current_name = df.loc[idx, 'small_step_name']
    
    # Regenerate IDs with new topic
    df.loc[idx, 'small_step_id'] = f'Year 10_14-15_Autumn_Foundation_Quadratic expressions and equations_{new_step_num_in_topic}_{current_name}'
    
    # Generate small_step_key: lowercase, replace spaces with hyphens, remove punctuation
    key_name = current_name.lower().replace(' ', '-').replace('(', '').replace(')', '').replace('_', '-')
    df.loc[idx, 'small_step_key'] = f'year-10__14-15__autumn__foundation__quadratic-expressions-and-equations__{new_step_num_in_topic}__{key_name}'

# Update the last row (step 7) with new ss_wr_desc
last_foundation_idx = foundation_indices[-1]
new_quadratic_desc = "In this small step, students will revisit previous content from Year 9 on plotting graphs in the form y = x2 ± a using a table of values. Ensure students are confident substituting values, including negative numbers, into quadratic. Draw students' attention to the fact quadratic graphs are drawn with a smooth curve and not straight lines. Graphs in the form y = x2 ± bx ± c will be covered in later steps, so it is not necessary to address them now. If appropriate, challenge students to plot graphs with a negative coefficient of x2, for example, y = 5 – x2"

df.loc[last_foundation_idx, 'ss_wr_desc'] = new_quadratic_desc
df.loc[last_foundation_idx, 'topic'] = 'Quadratic expressions and equations'
df.loc[last_foundation_idx, 'small_step_num_in_topic'] = 7

# Fix the small_step_id for the last row
last_name = df.loc[last_foundation_idx, 'small_step_name']
last_step_num = df.loc[last_foundation_idx, 'small_step_num']
df.loc[last_foundation_idx, 'small_step_id'] = f'Year 10_14-15_Autumn_Foundation_Quadratic expressions and equations_7_{last_name}'

# Generate key for last row
key_name_last = last_name.lower().replace(' ', '-').replace('(', '').replace(')', '').replace('_', '-')
df.loc[last_foundation_idx, 'small_step_key'] = f'year-10__14-15__autumn__foundation__quadratic-expressions-and-equations__7__{key_name_last}'

# Save the updated CSV
df.to_csv(csv_file, index=False, encoding='utf-8-sig')

print("\n✓ Curriculum updated successfully")
print(f"\nVerification - Foundation Quadratic rows:")
quad_mask = (df['topic'] == 'Quadratic expressions and equations') & (df['difficulty'] == 'Foundation')
quad_df = df[quad_mask][['small_step_num', 'small_step_num_in_topic', 'small_step_name', 'topic']]
print(quad_df.to_string(index=False))
print(f"\nTotal Foundation steps: {len(quad_df)}")
