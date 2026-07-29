"""Fix CSV: _17_ -> _1_ video IDs for rows 49-51, and tena -> tens typo"""
from pathlib import Path

csv_path = Path('thoughtprompt/pilot_output/thought_prompts_multiplechoice.csv')

with open(csv_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: _17_ -> _1_ for rows 49, 50, 51
content = content.replace('_Place value_17_Represent numbers to 1000', '_Place value_1_Represent numbers to 1000')

# Fix 2: tena -> tens
content = content.replace('"tena"', '"tens"')

with open(csv_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('CSV fixes applied:')
print('  - Video IDs changed _17_ -> _1_ for rows 49-51')
print('  - Typo tena -> tens on row 52')