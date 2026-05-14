"""
Flipper Search - Natural language curriculum topic search

Two-stage retrieval: lexical (fast, zero-cost) + semantic rerank (high-quality)
"""

from .curriculum_index import CurriculumIndex
from .epoch_definitions import EPOCHS, get_epoch_year_range

__all__ = [
    'CurriculumIndex',
    'EPOCHS',
    'get_epoch_year_range',
]
