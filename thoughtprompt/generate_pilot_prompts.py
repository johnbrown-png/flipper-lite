"""
Pilot Thought Prompt Generator
Generates 3 thought prompt variants for Year 4 Place Value small steps (373-389)

Each prompt includes:
- Prompt text (question)
- Visual type assignment
- Visual parameters
- Correct answer
- Answer type (multiple_choice, numeric, text_match)
"""

import csv
import json
from pathlib import Path
from typing import List, Dict
import random

# Set seed for reproducible examples
random.seed(42)


class ThoughtPromptGenerator:
    """Generate thought prompts with visual assignments"""
    
    def __init__(self):
        self.visual_types = ['base10_blocks', 'part_whole_model', 'bar_model', 'number_line']
        
    def generate_prompts_for_small_step(self, small_step_num: int, small_step_name: str, 
                                       video_id: str, rank: int = 1) -> List[Dict]:
        """Generate 3 prompt variants for a small step"""
        
        # Map small_step_num to appropriate prompt generator
        generators = {
            373: self._represent_to_1000,
            374: self._partition_to_1000,
            375: self._number_line_to_1000,
            376: self._thousands,
            377: self._represent_to_10000,
            378: self._partition_to_10000,
            379: self._flexible_partition_to_10000,
            380: self._find_more_less,
            381: self._number_line_to_10000,
            382: self._estimate_number_line_10000,
            383: self._compare_to_10000,
            384: self._order_to_10000,
            385: self._roman_numerals,
            386: self._round_nearest_10,
            387: self._round_nearest_100,
            388: self._round_nearest_1000,
            389: self._round_to_10_100_1000,
        }
        
        generator_func = generators.get(small_step_num)
        if generator_func:
            return generator_func(small_step_num, small_step_name, video_id, rank)
        else:
            return []
    
    def _represent_to_1000(self, ss_num, ss_name, video_id, rank):
        """Represent numbers to 1,000"""
        return [
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 1,
                'prompt_text': 'How many hundreds, tens and ones are shown?',
                'visual_type': 'base10_blocks',
                'visual_params': json.dumps({'tens': 4, 'ones': 7, 'label': False}),
                'answer_type': 'text_match',
                'correct_answer': '4 tens and 7 ones',
                'options': None,
                'difficulty': 'medium'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 2,
                'prompt_text': 'What number is represented by these blocks?',
                'visual_type': 'base10_blocks',
                'visual_params': json.dumps({'tens': 6, 'ones': 3, 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '63',
                'options': None,
                'difficulty': 'easy'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 3,
                'prompt_text': 'This shows a number with zero ones. What is the number?',
                'visual_type': 'base10_blocks',
                'visual_params': json.dumps({'tens': 8, 'ones': 0, 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '80',
                'options': None,
                'difficulty': 'medium'
            }
        ]
    
    def _partition_to_1000(self, ss_num, ss_name, video_id, rank):
        """Partition numbers to 1,000"""
        return [
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 1,
                'prompt_text': 'What are the two parts that make this whole?',
                'visual_type': 'part_whole_model',
                'visual_params': json.dumps({'total': 47, 'parts': [40, 7], 'label': False}),
                'answer_type': 'text_match',
                'correct_answer': '40 and 7',
                'options': None,
                'difficulty': 'easy'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 2,
                'prompt_text': 'Complete this partition: 58 = ___ + 8',
                'visual_type': 'part_whole_model',
                'visual_params': json.dumps({'total': 58, 'parts': [50, 8], 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '50',
                'options': None,
                'difficulty': 'medium'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 3,
                'prompt_text': 'This part-whole shows a number with zero in the ones place. What is the missing part?',
                'visual_type': 'part_whole_model',
                'visual_params': json.dumps({'total': 90, 'parts': [30, '?'], 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '60',
                'options': None,
                'difficulty': 'hard'
            }
        ]
    
    def _number_line_to_1000(self, ss_num, ss_name, video_id, rank):
        """Number line to 1,000"""
        return [
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 1,
                'prompt_text': 'What number is shown by the arrow?',
                'visual_type': 'number_line',
                'visual_params': json.dumps({'start': 0, 'end': 100, 'highlight': 47, 'interval': 10, 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '47',
                'options': None,
                'difficulty': 'medium'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 2,
                'prompt_text': 'Each interval represents 10. What is the value at the midpoint?',
                'visual_type': 'number_line',
                'visual_params': json.dumps({'start': 20, 'end': 80, 'highlight': 50, 'interval': 10, 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '50',
                'options': None,
                'difficulty': 'medium'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 3,
                'prompt_text': 'What is the value of each interval on this number line?',
                'visual_type': 'number_line',
                'visual_params': json.dumps({'start': 0, 'end': 100, 'highlight': None, 'interval': 10, 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '10',
                'options': None,
                'difficulty': 'easy'
            }
        ]
    
    def _thousands(self, ss_num, ss_name, video_id, rank):
        """Thousands"""
        return [
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 1,
                'prompt_text': 'How many hundreds are equal to 3,000?',
                'visual_type': 'base10_blocks',
                'visual_params': json.dumps({'tens': 30, 'ones': 0, 'label': False, 'note': 'Show as 30 hundred-blocks'}),
                'answer_type': 'numeric',
                'correct_answer': '30',
                'options': None,
                'difficulty': 'medium'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 2,
                'prompt_text': 'If I count in thousands, what comes after 5,000?',
                'visual_type': 'number_line',
                'visual_params': json.dumps({'start': 0, 'end': 10000, 'highlight': 6000, 'interval': 1000, 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '6000',
                'options': None,
                'difficulty': 'easy'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 3,
                'prompt_text': 'Complete: ___ hundreds = 2,000',
                'visual_type': 'bar_model',
                'visual_params': json.dumps({'total': 2000, 'parts': [100, 100, 100, 100, 100], 'operation': 'addition', 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '20',
                'options': None,
                'difficulty': 'hard'
            }
        ]
    
    def _represent_to_10000(self, ss_num, ss_name, video_id, rank):
        """Represent numbers to 10,000"""
        return [
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 1,
                'prompt_text': 'What 4-digit number is shown?',
                'visual_type': 'base10_blocks',
                'visual_params': json.dumps({'thousands': 3, 'hundreds': 2, 'tens': 4, 'ones': 7, 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '3247',
                'options': None,
                'difficulty': 'medium'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 2,
                'prompt_text': 'This number has zero hundreds. What is the number?',
                'visual_type': 'base10_blocks',
                'visual_params': json.dumps({'thousands': 5, 'hundreds': 0, 'tens': 4, 'ones': 6, 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '5046',
                'options': None,
                'difficulty': 'hard'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 3,
                'prompt_text': 'Which place value column represents 1,000?',
                'visual_type': 'base10_blocks',
                'visual_params': json.dumps({'thousands': 1, 'hundreds': 0, 'tens': 0, 'ones': 0, 'label': False}),
                'answer_type': 'text_match',
                'correct_answer': 'thousands',
                'options': json.dumps(['ones', 'tens', 'hundreds', 'thousands']),
                'difficulty': 'easy'
            }
        ]
    
    def _partition_to_10000(self, ss_num, ss_name, video_id, rank):
        """Partition numbers to 10,000"""
        return [
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 1,
                'prompt_text': 'Partition 5,346 into thousands and the rest. What is the rest?',
                'visual_type': 'part_whole_model',
                'visual_params': json.dumps({'total': 5346, 'parts': [5000, 346], 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '346',
                'options': None,
                'difficulty': 'medium'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 2,
                'prompt_text': 'Complete: 7,205 = 7,000 + ___ + 5',
                'visual_type': 'part_whole_model',
                'visual_params': json.dumps({'total': 7205, 'parts': [7000, 200, 5], 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '200',
                'options': None,
                'difficulty': 'hard'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 3,
                'prompt_text': 'What is 4,872 in expanded form?',
                'visual_type': 'base10_blocks',
                'visual_params': json.dumps({'thousands': 4, 'hundreds': 8, 'tens': 7, 'ones': 2, 'label': False}),
                'answer_type': 'text_match',
                'correct_answer': '4000 + 800 + 70 + 2',
                'options': None,
                'difficulty': 'medium'
            }
        ]
    
    def _flexible_partition_to_10000(self, ss_num, ss_name, video_id, rank):
        """Flexible partitioning"""
        return [
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 1,
                'prompt_text': 'Both part-whole models show the same number. What is the missing part?',
                'visual_type': 'part_whole_model',
                'visual_params': json.dumps({'total': 6429, 'parts': [6000, 400, 20, 9], 'alternative': [5000, 1400, 20, 9], 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '1400',
                'options': None,
                'difficulty': 'hard'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 2,
                'prompt_text': 'Is this partition correct? 3,825 = 2,000 + 1,800 + 20 + 5',
                'visual_type': 'part_whole_model',
                'visual_params': json.dumps({'total': 3825, 'parts': [2000, 1800, 20, 5], 'label': False}),
                'answer_type': 'text_match',
                'correct_answer': 'yes',
                'options': json.dumps(['yes', 'no']),
                'difficulty': 'medium'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 3,
                'prompt_text': '5,000 + 600 + 90 + 3 = 4,000 + ___ + 90 + 3. What is the missing part?',
                'visual_type': 'bar_model',
                'visual_params': json.dumps({'total': 5693, 'parts': [5000, 600, 90, 3], 'operation': 'addition', 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '1600',
                'options': None,
                'difficulty': 'hard'
            }
        ]
    
    def _find_more_less(self, ss_num, ss_name, video_id, rank):
        """Find 1, 10, 100, 1000 more or less"""
        return [
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 1,
                'prompt_text': 'What is 100 more than 3,247?',
                'visual_type': 'base10_blocks',
                'visual_params': json.dumps({'thousands': 3, 'hundreds': 2, 'tens': 4, 'ones': 7, 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '3347',
                'options': None,
                'difficulty': 'medium'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 2,
                'prompt_text': 'What is 1,000 less than 5,046?',
                'visual_type': 'number_line',
                'visual_params': json.dumps({'start': 0, 'end': 10000, 'highlight': 5046, 'interval': 1000, 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '4046',
                'options': None,
                'difficulty': 'medium'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 3,
                'prompt_text': 'What is 10 more than 6,995? (Hint: This crosses a multiple of 1,000)',
                'visual_type': 'base10_blocks',
                'visual_params': json.dumps({'thousands': 6, 'hundreds': 9, 'tens': 9, 'ones': 5, 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '7005',
                'options': None,
                'difficulty': 'hard'
            }
        ]
    
    def _number_line_to_10000(self, ss_num, ss_name, video_id, rank):
        """Number line to 10,000"""
        return [
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 1,
                'prompt_text': 'What number is at the arrow?',
                'visual_type': 'number_line',
                'visual_params': json.dumps({'start': 0, 'end': 10000, 'highlight': 5247, 'interval': 1000, 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '5247',
                'options': None,
                'difficulty': 'hard'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 2,
                'prompt_text': 'What is the value of each interval?',
                'visual_type': 'number_line',
                'visual_params': json.dumps({'start': 400, 'end': 500, 'highlight': 470, 'interval': 10, 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '10',
                'options': None,
                'difficulty': 'easy'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 3,
                'prompt_text': 'What number is halfway between 2,000 and 8,000?',
                'visual_type': 'number_line',
                'visual_params': json.dumps({'start': 2000, 'end': 8000, 'highlight': 5000, 'interval': 1000, 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '5000',
                'options': None,
                'difficulty': 'medium'
            }
        ]
    
    def _estimate_number_line_10000(self, ss_num, ss_name, video_id, rank):
        """Estimate on number line to 10,000"""
        return [
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 1,
                'prompt_text': 'Estimate where 6,500 would be on this number line',
                'visual_type': 'number_line',
                'visual_params': json.dumps({'start': 6000, 'end': 7000, 'highlight': None, 'interval': 100, 'label': False}),
                'answer_type': 'text_match',
                'correct_answer': 'halfway',
                'options': json.dumps(['beginning', 'one-quarter', 'halfway', 'three-quarters', 'end']),
                'difficulty': 'medium'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 2,
                'prompt_text': 'Is 6,429 closer to 6,000 or 7,000?',
                'visual_type': 'number_line',
                'visual_params': json.dumps({'start': 6000, 'end': 7000, 'highlight': 6429, 'interval': 100, 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '6000',
                'options': None,
                'difficulty': 'medium'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 3,
                'prompt_text': 'The arrow points to approximately what value? (Nearest hundred)',
                'visual_type': 'number_line',
                'visual_params': json.dumps({'start': 4000, 'end': 5000, 'highlight': 4700, 'interval': 100, 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '4700',
                'options': None,
                'difficulty': 'hard'
            }
        ]
    
    def _compare_to_10000(self, ss_num, ss_name, video_id, rank):
        """Compare numbers to 10,000"""
        return [
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 1,
                'prompt_text': 'Which is greater: 3,247 or 3,274?',
                'visual_type': 'base10_blocks',
                'visual_params': json.dumps({'number_a': 3247, 'number_b': 3274, 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '3274',
                'options': None,
                'difficulty': 'medium'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 2,
                'prompt_text': 'Complete with <, > or =: 5,046 ___ 5,064',
                'visual_type': 'number_line',
                'visual_params': json.dumps({'start': 5000, 'end': 5100, 'highlight': [5046, 5064], 'interval': 10, 'label': False}),
                'answer_type': 'text_match',
                'correct_answer': '<',
                'options': json.dumps(['<', '>', '=']),
                'difficulty': 'medium'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 3,
                'prompt_text': 'Which number is smaller: 6,429 or 6,924?',
                'visual_type': 'base10_blocks',
                'visual_params': json.dumps({'number_a': 6429, 'number_b': 6924, 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '6429',
                'options': None,
                'difficulty': 'easy'
            }
        ]
    
    def _order_to_10000(self, ss_num, ss_name, video_id, rank):
        """Order numbers to 10,000"""
        return [
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 1,
                'prompt_text': 'Put these in ascending order: 3,247, 3,274, 3,427',
                'visual_type': 'number_line',
                'visual_params': json.dumps({'start': 3200, 'end': 3500, 'highlight': [3247, 3274, 3427], 'interval': 50, 'label': False}),
                'answer_type': 'text_match',
                'correct_answer': '3247, 3274, 3427',
                'options': None,
                'difficulty': 'medium'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 2,
                'prompt_text': 'Which number comes first in descending order: 5,046, 5,406, 5,604?',
                'visual_type': 'base10_blocks',
                'visual_params': json.dumps({'numbers': [5046, 5406, 5604], 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '5604',
                'options': None,
                'difficulty': 'medium'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 3,
                'prompt_text': 'Order these from smallest to greatest: 6,429, 6,042, 6,240',
                'visual_type': 'number_line',
                'visual_params': json.dumps({'start': 6000, 'end': 6500, 'highlight': [6429, 6042, 6240], 'interval': 100, 'label': False}),
                'answer_type': 'text_match',
                'correct_answer': '6042, 6240, 6429',
                'options': None,
                'difficulty': 'hard'
            }
        ]
    
    def _roman_numerals(self, ss_num, ss_name, video_id, rank):
        """Roman numerals"""
        return [
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 1,
                'prompt_text': 'What does the Roman numeral XL represent?',
                'visual_type': 'base10_blocks',
                'visual_params': json.dumps({'tens': 4, 'ones': 0, 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '40',
                'options': None,
                'difficulty': 'medium'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 2,
                'prompt_text': 'Write 90 in Roman numerals',
                'visual_type': 'base10_blocks',
                'visual_params': json.dumps({'tens': 9, 'ones': 0, 'label': False}),
                'answer_type': 'text_match',
                'correct_answer': 'XC',
                'options': json.dumps(['LC', 'XC', 'CX', 'LXXXX']),
                'difficulty': 'hard'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 3,
                'prompt_text': 'Which is larger: L or C?',
                'visual_type': 'number_line',
                'visual_params': json.dumps({'start': 0, 'end': 100, 'highlight': [50, 100], 'interval': 10, 'label': False}),
                'answer_type': 'text_match',
                'correct_answer': 'C',
                'options': json.dumps(['L', 'C']),
                'difficulty': 'easy'
            }
        ]
    
    def _round_nearest_10(self, ss_num, ss_name, video_id, rank):
        """Round to nearest 10"""
        return [
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 1,
                'prompt_text': 'Round 47 to the nearest 10',
                'visual_type': 'number_line',
                'visual_params': json.dumps({'start': 40, 'end': 50, 'highlight': 47, 'interval': 1, 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '50',
                'options': None,
                'difficulty': 'easy'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 2,
                'prompt_text': 'What is 304 rounded to the nearest 10?',
                'visual_type': 'number_line',
                'visual_params': json.dumps({'start': 300, 'end': 310, 'highlight': 304, 'interval': 1, 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '300',
                'options': None,
                'difficulty': 'medium'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 3,
                'prompt_text': 'Which multiples of 10 is 63 between?',
                'visual_type': 'number_line',
                'visual_params': json.dumps({'start': 60, 'end': 70, 'highlight': 63, 'interval': 1, 'label': False}),
                'answer_type': 'text_match',
                'correct_answer': '60 and 70',
                'options': None,
                'difficulty': 'medium'
            }
        ]
    
    def _round_nearest_100(self, ss_num, ss_name, video_id, rank):
        """Round to nearest 100"""
        return [
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 1,
                'prompt_text': 'Round 347 to the nearest 100',
                'visual_type': 'number_line',
                'visual_params': json.dumps({'start': 300, 'end': 400, 'highlight': 347, 'interval': 10, 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '300',
                'options': None,
                'difficulty': 'medium'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 2,
                'prompt_text': 'What is 672 rounded to the nearest 100?',
                'visual_type': 'number_line',
                'visual_params': json.dumps({'start': 600, 'end': 700, 'highlight': 672, 'interval': 10, 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '700',
                'options': None,
                'difficulty': 'easy'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 3,
                'prompt_text': 'Round 48 to the nearest 100. (Remember: what is the previous multiple of 100?)',
                'visual_type': 'number_line',
                'visual_params': json.dumps({'start': 0, 'end': 100, 'highlight': 48, 'interval': 10, 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '0',
                'options': None,
                'difficulty': 'hard'
            }
        ]
    
    def _round_nearest_1000(self, ss_num, ss_name, video_id, rank):
        """Round to nearest 1,000"""
        return [
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 1,
                'prompt_text': 'Round 3,247 to the nearest 1,000',
                'visual_type': 'number_line',
                'visual_params': json.dumps({'start': 3000, 'end': 4000, 'highlight': 3247, 'interval': 100, 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '3000',
                'options': None,
                'difficulty': 'medium'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 2,
                'prompt_text': 'What is 6,829 rounded to the nearest 1,000?',
                'visual_type': 'number_line',
                'visual_params': json.dumps({'start': 6000, 'end': 7000, 'highlight': 6829, 'interval': 100, 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '7000',
                'options': None,
                'difficulty': 'easy'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 3,
                'prompt_text': 'Round 472 to the nearest 1,000',
                'visual_type': 'number_line',
                'visual_params': json.dumps({'start': 0, 'end': 1000, 'highlight': 472, 'interval': 100, 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '0',
                'options': None,
                'difficulty': 'hard'
            }
        ]
    
    def _round_to_10_100_1000(self, ss_num, ss_name, video_id, rank):
        """Round to nearest 10, 100 or 1,000"""
        return [
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 1,
                'prompt_text': 'Round 3,247 to the nearest 100',
                'visual_type': 'number_line',
                'visual_params': json.dumps({'start': 3200, 'end': 3300, 'highlight': 3247, 'interval': 10, 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '3200',
                'options': None,
                'difficulty': 'medium'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 2,
                'prompt_text': 'Round 6,829 to the nearest 10',
                'visual_type': 'number_line',
                'visual_params': json.dumps({'start': 6820, 'end': 6830, 'highlight': 6829, 'interval': 1, 'label': False}),
                'answer_type': 'numeric',
                'correct_answer': '6830',
                'options': None,
                'difficulty': 'easy'
            },
            {
                'small_step_num': ss_num,
                'small_step_name': ss_name,
                'video_id': video_id,
                'rank': rank,
                'variant': 3,
                'prompt_text': 'Which degree of accuracy is most appropriate for estimating a town population: 10, 100, or 1,000?',
                'visual_type': 'number_line',
                'visual_params': json.dumps({'start': 0, 'end': 10000, 'highlight': 5347, 'interval': 1000, 'label': False}),
                'answer_type': 'text_match',
                'correct_answer': '1000',
                'options': json.dumps(['10', '100', '1000']),
                'difficulty': 'hard'
            }
        ]


def generate_pilot_prompts():
    """Generate pilot prompts for all 17 small steps"""
    generator = ThoughtPromptGenerator()
    
    # Read curriculum CSV to get video IDs
    curriculum_file = Path(__file__).parent.parent / "Curriculum" / "Maths" / "curriculum_08052026_small_steps.with_ss_desc_generated.csv"
    
    all_prompts = []
    
    # Read lines 374-390 (small_step_num 373-389)
    with open(curriculum_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=1):
            if 374 <= row_num <= 390:
                small_step_num = int(row['small_step_num'])
                small_step_name = row['small_step_name']
                small_step_id = row['small_step_id']
                # Use small_step_id as video_id placeholder for pilot (will be first-ranked video)
                video_id = f"{small_step_id}_rank1_placeholder"
                
                prompts = generator.generate_prompts_for_small_step(
                    small_step_num, small_step_name, video_id, rank=1
                )
                all_prompts.extend(prompts)
    
    return all_prompts


def save_to_csv(prompts, output_file):
    """Save prompts to CSV"""
    fieldnames = ['small_step_num', 'small_step_name', 'video_id', 'rank', 'variant',
                  'prompt_text', 'visual_type', 'visual_params', 'answer_type',
                  'correct_answer', 'options', 'difficulty']
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(prompts)


def save_to_json(prompts, output_file):
    """Save prompts to JSON"""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(prompts, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    print("=" * 70)
    print("Thought Prompt Pilot Generator")
    print("Year 4 Place Value (Small Steps 373-389)")
    print("=" * 70)
    
    # Generate prompts
    print("\nGenerating thought prompts...")
    prompts = generate_pilot_prompts()
    
    # Output directory
    output_dir = Path(__file__).parent / "pilot_output"
    output_dir.mkdir(exist_ok=True)
    
    # Save to CSV
    csv_file = output_dir / "thought_prompts_pilot.csv"
    save_to_csv(prompts, csv_file)
    print(f"✓ CSV saved: {csv_file}")
    
    # Save to JSON
    json_file = output_dir / "thought_prompts_pilot.json"
    save_to_json(prompts, json_file)
    print(f"✓ JSON saved: {json_file}")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total prompts generated: {len(prompts)}")
    print(f"Small steps covered: {len(prompts) // 3}")
    print(f"Variants per small step: 3")
    
    # Visual type distribution
    visual_counts = {}
    for p in prompts:
        vtype = p['visual_type']
        visual_counts[vtype] = visual_counts.get(vtype, 0) + 1
    
    print("\nVisual type distribution:")
    for vtype, count in sorted(visual_counts.items()):
        print(f"  {vtype}: {count}")
    
    # Difficulty distribution
    difficulty_counts = {}
    for p in prompts:
        diff = p['difficulty']
        difficulty_counts[diff] = difficulty_counts.get(diff, 0) + 1
    
    print("\nDifficulty distribution:")
    for diff, count in sorted(difficulty_counts.items()):
        print(f"  {diff}: {count}")
    
    print("\n" + "=" * 70)
    print("✓ Pilot generation complete!")
    print("=" * 70)
