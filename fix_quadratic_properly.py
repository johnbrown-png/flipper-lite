import pandas as pd

csv_file = r"Curriculum\Maths\curriculum_08052026_small_steps.csv"
df = pd.read_csv(csv_file, encoding='utf-8-sig')

# Step 1: Increment ALL small_step_num >= 1213 by 1
mask_to_increment = (df['small_step_num'] >= 1213)
df.loc[mask_to_increment, 'small_step_num'] = df.loc[mask_to_increment, 'small_step_num'] + 1

# Step 2: Fix Foundation Quadratic row names
correct_names = {
    1213: "Factorise quadratic expressions (positive only)",
    1214: "Factorise quadratic expressions",
    1215: "Difference of two squares (E)",
    1216: "Solve quadratic equations equal to 0",
    1217: "Solve quadratic equations by factorisation",
    1223: "Quadratic graphs of the form y = x2 + a"
}

for small_step_num, correct_name in correct_names.items():
    mask = (df['small_step_num'] == small_step_num) & (df['topic'] == 'Quadratic expressions and equations')
    if mask.any():
        df.loc[mask, 'small_step_name'] = correct_name
        # Update small_step_id
        year_part = df.loc[mask, 'year'].values[0]
        age_part = df.loc[mask, 'age'].values[0]
        term_part = df.loc[mask, 'term'].values[0]
        difficulty_part = df.loc[mask, 'difficulty'].values[0]
        step_in_topic = df.loc[mask, 'small_step_num_in_topic'].values[0]
        df.loc[mask, 'small_step_id'] = f'{year_part}_{age_part}_{term_part}_{difficulty_part}_Quadratic expressions and equations_{step_in_topic}_{correct_name}'
        
        # Update small_step_key
        key_name = correct_name.lower().replace(' ', '-').replace('(', '').replace(')', '')
        df.loc[mask, 'small_step_key'] = f'year-10__14-15__autumn__foundation__quadratic-expressions-and-equations__{step_in_topic}__{key_name}'

# Save
df.to_csv(csv_file, index=False, encoding='utf-8-sig')

# Verify Foundation Quadratic rows
print("Foundation Quadratic rows after fix:")
quad_mask = (df['topic'] == 'Quadratic expressions and equations') & (df['difficulty'] == 'Foundation')
print(df[quad_mask][['small_step_num', 'small_step_num_in_topic', 'small_step_name']].to_string(index=False))

# Check if all small_step_num are unique and contiguous
all_nums = sorted(df['small_step_num'].unique())
print(f"\nContiguity check: {len(all_nums)} unique values, min={all_nums[0]}, max={all_nums[-1]}")
expected_count = all_nums[-1] - all_nums[0] + 1
print(f"Expected {expected_count} rows for contiguous sequence, have {len(all_nums)}")
