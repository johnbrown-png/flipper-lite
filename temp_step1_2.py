import pandas as pd
import os

curriculum_path = 'Curriculum/Maths/curriculum_08052026_small_steps.csv'
flat_path = 'precomputed_recommendations_flat.csv'
staging_curriculum_path = 'Curriculum/Maths/pdf_extractor/curriculum_08052026_year5_perimeter_ids_staging.csv'
stats_id = 'Year 5_9-10_Spring__Statistics_1_Draw line graphs'

# 1) Capture Statistics step-1 rows
flat = pd.read_csv(flat_path)
stats_rows = flat[flat['small_step_id'] == stats_id]
print('--- Current Statistics step-1 rows ---')
print(stats_rows[['small_step_num_global','small_step_num_in_topic','topic','small_step_name','rank','video_id']].to_string(index=False))

# 2) Build staging CSV
can = pd.read_csv(curriculum_path)
# We want Exactly 6 rows for Perimeter and area Year 5 Spring
mask = (can['year'].astype(str).str.strip() == 'Year 5') & \
       (can['term'].astype(str).str.strip() == 'Spring') & \
       (can['topic'].astype(str).str.strip() == 'Perimeter and area') & \
       (can['small_step_num_in_topic'].between(1, 6))

peri_rows = can[mask].copy().sort_values('small_step_num_in_topic')
print('\n--- Staging Rows ---')
print(peri_rows[['small_step_num','small_step_num_in_topic','year','term','topic','small_step_name','small_step_id']].to_string(index=False))
peri_rows.to_csv(staging_curriculum_path, index=False)
