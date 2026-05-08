import pandas as pd
import shutil
import os

flat_path = 'precomputed_recommendations_flat.csv'
staging_out = 'precomputed_recommendations_staging_year5_perimeter_ids.csv'
backup_path = f'precomputed_recommendations_flat.backup_before_year5_perimeter_id_refresh_{20260508_150838}.csv'
stats_id = 'Year 5_9-10_Spring__Statistics_1_Draw line graphs'

# 4) Backup
shutil.copy2(flat_path, backup_path)
print(f'Backup created: {backup_path}')

# 5) Upsert
flat = pd.read_csv(flat_path)
staging = pd.read_csv(staging_out)
new_ids = staging['small_step_id'].unique()

print(f'Staging IDs to update: {new_ids}')

count_before = len(flat)
flat_filtered = flat[~flat['small_step_id'].isin(new_ids)]
count_after_remove = len(flat_filtered)

# Align columns
staging = staging[flat.columns]
final_flat = pd.concat([flat_filtered, staging], ignore_index=True)
final_flat.to_csv(flat_path, index=False)

print(f'\nRemoved {count_before - count_after_remove} rows.')
print(f'Added {len(staging)} rows.')
print(f'Total flat row count: {len(final_flat)}')

# 6) Verify
peri_check = final_flat[final_flat['small_step_id'].isin(new_ids)]
print(f'\nRows for Perimeter IDs: {len(peri_check)}')

stats_check = final_flat[final_flat['small_step_id'] == stats_id]
print(f'\nRows for Statistics step-1: {len(stats_check)}')

dupes = final_flat[final_flat.duplicated('recommendation_id')]
print(f'Duplicate recommendation_id count: {len(dupes)}')
