"""
Append 3 new prompts (thought_prompt_num 49, 50, 51) for small step 373
to thought_prompts_pilot.json
"""
import json
from pathlib import Path

json_path = Path('thoughtprompt/pilot_output/thought_prompts_pilot.json')

# Load existing JSON
with open(json_path, 'r', encoding='utf-8') as f:
    prompts = json.load(f)

print(f'Current prompt count: {len(prompts)}')

# Define the 3 new prompts for small step 373 (thought_prompt_num 49, 50, 51)
new_prompts = [
    {
        'thought_prompt_num': 49,
        'small_step_num': 373,
        'small_step_name': 'Represent numbers to 1000',
        'video_id': 'Year 4_8-9_Autumn__Place value_17_Represent numbers to 1000_rank1_placeholder',
        'rank': 1,
        'variant': 1,
        'prompt_text': 'What number is this?',
        'visual_type': 'base10_blocks',
        'visual_params': json.dumps({'thousands': 1, 'ones': 3, 'label': False}),
        'answer_type': 'numeric',
        'correct_answer': '1003',
        'options': json.dumps(['999', '1001', '1003']),
        'difficulty': 'easy'
    },
    {
        'thought_prompt_num': 50,
        'small_step_num': 373,
        'small_step_name': 'Represent numbers to 1000',
        'video_id': 'Year 4_8-9_Autumn__Place value_17_Represent numbers to 1000_rank1_placeholder',
        'rank': 1,
        'variant': 2,
        'prompt_text': 'What number is this?',
        'visual_type': 'base10_blocks',
        'visual_params': json.dumps({'hundreds': 9, 'tens': 9, 'ones': 9, 'label': False}),
        'answer_type': 'numeric',
        'correct_answer': '999',
        'options': json.dumps(['1000', '1001', '999']),
        'difficulty': 'medium'
    },
    {
        'thought_prompt_num': 51,
        'small_step_num': 373,
        'small_step_name': 'Represent numbers to 1000',
        'video_id': 'Year 4_8-9_Autumn__Place value_17_Represent numbers to 1000_rank1_placeholder',
        'rank': 1,
        'variant': 3,
        'prompt_text': 'What number is this?',
        'visual_type': 'base10_blocks',
        'visual_params': json.dumps({'thousands': 1, 'tens': 1, 'label': False}),
        'answer_type': 'numeric',
        'correct_answer': '1010',
        'options': json.dumps(['990', '1010', '1000']),
        'difficulty': 'hard'
    }
]

# Append new prompts
prompts.extend(new_prompts)

# Write back
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(prompts, f, indent=2, ensure_ascii=False)

print(f'New prompt count: {len(prompts)}')
print(f'Added prompts 49, 50, 51 for small step 373')
print(f'Last 3 entries:')
for p in prompts[-3:]:
    print(f"  #{p['thought_prompt_num']}: variant={p['variant']}, answer={p['correct_answer']}, options={p['options']}, difficulty={p['difficulty']}")