import pandas as pd

csv_file = r"Curriculum\Maths\curriculum_08052026_small_steps.csv"
df = pd.read_csv(csv_file, encoding='utf-8-sig')

# The current state is highly fragmented with incorrect topic names.
# We will rebuild the Quadratic section starting at 1212.

# 1. Store everything BEFORE 1212
head = df[df['small_step_num'] < 1212].copy()

# 2. Store everything currently assigned to 'Quadratic' or 'Expand double brackets' (topics) but after 1211
# We want to re-sequence them logicially based on their names.
# Actually, it might be cleaner to just manually sort the ones that were there.

# 3. Create the sequence we want
# Foundation Quadratic: 1 to 7
# Higher Quadratic: 8 to 18 (based on names in terminal output)
# Note: "Expand double brackets" seems to have been used as a topic name incorrectly.

# Identify all rows that should be in the Quadratic topic
quad_topic_rows = df[(df['topic'] == 'Quadratic expressions and equations') | (df['topic'] == 'Expand double brackets')].copy()
quad_topic_rows['topic'] = 'Quadratic expressions and equations'

# Remove duplicates if any (e.g. 1225 was duplicated)
quad_topic_rows = quad_topic_rows.drop_duplicates(subset=['small_step_name', 'difficulty'])

# Manually sequence the Foundation ones (7 steps)
foundation_steps = [
    "Expand double brackets",
    "Factorise quadratic expressions (positive only)",
    "Factorise quadratic expressions",
    "Difference of two squares (E)",
    "Solve quadratic equations equal to 0",
    "Solve quadratic equations by factorisation",
    "Quadratic graphs of the form y = x2 + a"
]

# Manually sequence the Higher ones
higher_steps = [
    "Expand triple brackets",
    "Factorise quadratic expressions",
    "Factorise more complex quadratic expressions (E)",
    "Difference of two squares",
    "Solve quadratic equations equal to 0",
    "Solve quadratic equations by factorisation",
    "Solve more complex quadratic equations by factorisation (E)",
    "Complete the square",
    "Complete the square with more complex quadratic expressions (E)",
    "Solve quadratic equations by completing the square (E)",
    "Solve quadratic equations using the quadratic formula"
]

# Re-map existing rows to these names/sequences
new_quad_rows = []

# Foundation
for i, name in enumerate(foundation_steps, 1):
    new_quad_rows.append({
        'year': 'Year 10', 'age': '14-15', 'term': 'Autumn', 'difficulty': 'Foundation',
        'topic': 'Quadratic expressions and equations', 'small_step_num_in_topic': i, 'small_step_name': name
    })

# Higher
for i, name in enumerate(higher_steps, 1):
    new_quad_rows.append({
        'year': 'Year 10', 'age': '14-15', 'term': 'Autumn', 'difficulty': 'Higher',
        'topic': 'Quadratic expressions and equations', 'small_step_num_in_topic': i, 'small_step_name': name
    })

quad_df = pd.DataFrame(new_quad_rows)

# Number them starting from 1212
quad_df['small_step_num'] = range(1212, 1212 + len(quad_df))

# Add missing columns from original df (e.g., small_step_id, small_step_key)
# For simplicity, we calculate them
def make_id(row):
    return f"{row['year']}_{row['age']}_{row['term']}_{row['difficulty']}_{row['topic']}_{row['small_step_num_in_topic']}_{row['small_step_name']}"

def make_key(row):
    k_name = row['small_step_name'].lower().replace(' ', '-').replace('(', '').replace(')', '')
    return f"{row['year'].lower().replace(' ', '-')}__{row['age'].replace(' ', '-')}__{row['term'].lower()}__{row['difficulty'].lower()}__{row['topic'].lower().replace(' ', '-')}__{row['small_step_num_in_topic']}__{k_name}"

quad_df['small_step_id'] = quad_df.apply(make_id, axis=1)
quad_df['small_step_key'] = quad_df.apply(make_key, axis=1)

# 4. Store everything AFTER the old quadratic block. 
# Previously, "Percentages" was at 1230. 
# New end of quadratic is 1212 + 7 + 11 - 1 = 1229. 
# So Percentages stays at 1230? Actually we should shift everything after the original block.
tail = df[df['small_step_num'] > 1230].copy()
percentages_row = df[df['small_step_num'] == 1230].copy()

# Note: The original file might have had items > 1230.
# Let's shift them if necessary.
offset = quad_df['small_step_num'].max() - 1229 # 1229 was the old end-ish 

# Actually, let's just combine: head + quad_df + everything after 1230 (renumbered)
final_tail = df[df['small_step_num'] >= 1230].copy()
final_tail['small_step_num'] = final_tail['small_step_num'] + (quad_df['small_step_num'].max() - 1229)

result = pd.concat([head, quad_df, final_tail], ignore_index=True)

# Save
result.to_csv(csv_file, index=False, encoding='utf-8-sig')

# Verify
print("Foundation Quadratic rows after fix:")
print(result[(result['topic'] == 'Quadratic expressions and equations') & (result['difficulty'] == 'Foundation')][['small_step_num', 'small_step_num_in_topic', 'small_step_name']])
print("\nHigher Quadratic rows after fix:")
print(result[(result['topic'] == 'Quadratic expressions and equations') & (result['difficulty'] == 'Higher')][['small_step_num', 'small_step_num_in_topic', 'small_step_name']])

all_nums = sorted(result['small_step_num'].unique())
print(f"\nContiguity check: {len(all_nums)} unique values, min={all_nums[0]}, max={all_nums[-1]}")
