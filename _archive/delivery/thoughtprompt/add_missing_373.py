"""
Add missing prompts for small step 373 (Represent numbers to 1,000)
"""

import pandas as pd
import json
from pathlib import Path

# Define the 3 prompts for step 373
new_prompts = [
    {
        'small_step_num': 373,
        'small_step_name': 'Represent numbers to 1,000',
        'video_id': 'Year 4_8-9_Autumn__Place value_1_Represent numbers to 1,000_rank1_placeholder',
        'rank': 1,
        'variant': 1,
        'prompt_text': 'How many tens are shown?',
        'visual_type': 'base10_blocks',
        'visual_params': json.dumps({'tens': 4, 'ones': 7, 'label': False}),
        'answer_type': 'numeric',
        'correct_answer': '4',
        'options': None,
        'difficulty': 'easy'
    },
    {
        'small_step_num': 373,
        'small_step_name': 'Represent numbers to 1,000',
        'video_id': 'Year 4_8-9_Autumn__Place value_1_Represent numbers to 1,000_rank1_placeholder',
        'rank': 1,
        'variant': 2,
        'prompt_text': 'What number is represented by these base-10 blocks?',
        'visual_type': 'base10_blocks',
        'visual_params': json.dumps({'tens': 5, 'ones': 8, 'label': False}),
        'answer_type': 'numeric',
        'correct_answer': '58',
        'options': None,
        'difficulty': 'medium'
    },
    {
        'small_step_num': 373,
        'small_step_name': 'Represent numbers to 1,000',
        'video_id': 'Year 4_8-9_Autumn__Place value_1_Represent numbers to 1,000_rank1_placeholder',
        'rank': 1,
        'variant': 3,
        'prompt_text': 'What 2-digit number has 9 tens and 9 ones?',
        'visual_type': 'base10_blocks',
        'visual_params': json.dumps({'tens': 9, 'ones': 9, 'label': False}),
        'answer_type': 'numeric',
        'correct_answer': '99',
        'options': None,
        'difficulty': 'hard'
    }
]

# Load existing prompts
csv_path = Path('thoughtprompt/pilot_output/thought_prompts_pilot.csv')
existing_df = pd.read_csv(csv_path)

# Add new prompts
new_df = pd.DataFrame(new_prompts)
combined_df = pd.concat([new_df, existing_df], ignore_index=True)

# Sort by small_step_num and variant
combined_df = combined_df.sort_values(['small_step_num', 'variant'])

# Save
combined_df.to_csv(csv_path, index=False)

print(f"✓ Added 3 prompts for small step 373")
print(f"✓ Total prompts now: {len(combined_df)}")
print(f"✓ Small steps covered: {sorted(combined_df['small_step_num'].unique())}")
