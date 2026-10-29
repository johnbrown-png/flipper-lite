import pandas as pd

# Paths
csv_file = r"Curriculum\Maths\curriculum_08052026_small_steps.csv"

# Read CSV
df = pd.read_csv(csv_file, encoding='utf-8-sig')

# Final desired state
# Topic: Quadratic expressions and equations
# Difficulty: Foundation
# Steps:
target_steps = [
    (1212, 1, "Expand double brackets"),
    (1214, 2, "Factorise quadratic expressions"),
    (1216, 3, "Difference of two squares (E)"),
    (1218, 4, "Solve quadratic equations equal to 0"),
    (1220, 5, "Solve quadratic equations by factorisation"),
    (1222, 6, "Factorise quadratic expressions (positive only)"),
    (1224, 7, "Quadratic graphs of the form y = x2 + a")
]

# Find the indices of the current Foundation Quadratic rows
mask = (df['topic'] == 'Quadratic expressions and equations') & (df['difficulty'] == 'Foundation')
indices = df[mask].index.tolist()

print(f"Current indices: {indices}")

# We found 7 rows earlier. Let's just update them.
for i, (new_num, new_topic_num, name) in enumerate(target_steps):
    idx = indices[i]
    df.loc[idx, 'small_step_num'] = new_num
    df.loc[idx, 'small_step_num_in_topic'] = new_topic_num
    df.loc[idx, 'small_step_name'] = name
    df.loc[idx, 'topic'] = 'Quadratic expressions and equations'
    
    # Update IDs
    df.loc[idx, 'small_step_id'] = f'Year 10_14-15_Autumn_Foundation_Quadratic expressions and equations_{new_topic_num}_{name}'
    key_name = name.lower().replace(' ', '-').replace('(', '').replace(')', '').replace('_', '-')
    df.loc[idx, 'small_step_key'] = f'year-10__14-15__autumn__foundation__quadratic-expressions-and-equations__{new_topic_num}__{key_name}'

# Set the desc for the last step
last_idx = indices[6]
df.loc[last_idx, 'ss_wr_desc'] = "In this small step, students will revisit previous content from Year 9 on plotting graphs in the form y = x2 ± a using a table of values. Ensure students are confident substituting values, including negative numbers, into quadratic. Draw students' attention to the fact quadratic graphs are drawn with a smooth curve and not straight lines. Graphs in the form y = x2 ± bx ± c will be covered in later steps, so it is not necessary to address them now. If appropriate, challenge students to plot graphs with a negative coefficient of x2, for example, y = 5 – x2"

# Save
df.to_csv(csv_file, index=False, encoding='utf-8-sig')

print("\nFinal Verification - Foundation Quadratic rows:")
final_mask = (df['topic'] == 'Quadratic expressions and equations') & (df['difficulty'] == 'Foundation')
print(df[final_mask][['small_step_num', 'small_step_num_in_topic', 'small_step_name', 'topic']].to_string(index=False))
