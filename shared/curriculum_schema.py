"""Curriculum and recommendation schema helpers."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd


LEGACY_SMALL_STEP_LIMIT = 40
TERM_ORDER = {
    "autumn": 1,
    "spring": 2,
    "summer": 3,
}


def clean_text(value: Any) -> str:
    """Return a stripped string value with NaN-like values normalized to empty."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def build_small_step_id(
    year: Any,
    age: Any,
    term: Any,
    difficulty: Any,
    topic: Any,
    small_step_num_in_topic: Any,
    small_step_name: Any,
) -> str:
    """Build a human-readable curriculum identifier preserving spaces inside fields."""
    components = [
        clean_text(year),
        clean_text(age),
        clean_text(term),
        clean_text(difficulty),
        clean_text(topic),
        clean_text(small_step_num_in_topic),
        clean_text(small_step_name),
    ]
    return "_".join(components)


def build_small_step_key(
    year: Any,
    age: Any,
    term: Any,
    difficulty: Any,
    topic: Any,
    small_step_num_in_topic: Any,
    small_step_name: Any,
) -> str:
    """Build a machine-safe identifier for a curriculum step."""

    def slugify(component: Any) -> str:
        text = clean_text(component).lower()
        if not text:
            return "blank"
        text = re.sub(r"\s+", "-", text)
        text = re.sub(r"[^a-z0-9\-]", "", text)
        return text or "blank"

    components = [year, age, term, difficulty, topic, small_step_num_in_topic, small_step_name]
    return "__".join(slugify(component) for component in components)


def build_recommendation_id(small_step_id: Any, recommendation_num: Any) -> str:
    """Build a recommendation identifier from a small-step identifier."""
    step_id = clean_text(small_step_id)
    rank = clean_text(recommendation_num)
    if not step_id or not rank:
        return ""
    return f"{step_id}_recommendation_{rank}"


def detect_curriculum_schema(df: pd.DataFrame) -> str:
    """Detect whether a curriculum dataframe is in legacy wide or long format."""
    columns = {str(column).strip().lower() for column in df.columns}
    if "small_step_name" in columns:
        return "long"
    if any(re.fullmatch(r"small step \d+", column) for column in columns):
        return "wide"
    if any(re.fullmatch(r"small_step_name_\d+", column) for column in columns):
        return "wide"
    return "long"


def normalize_precomputed_df(df: pd.DataFrame) -> pd.DataFrame:
    """Add compatibility aliases and additive identifier columns to recommendation data."""
    result = df.copy()

    if 'video_title' not in result.columns and 'title' in result.columns:
        result['video_title'] = result['title']
    if 'title' not in result.columns and 'video_title' in result.columns:
        result['title'] = result['video_title']

    if 'duration_formatted' not in result.columns and 'duration' in result.columns:
        result['duration_formatted'] = result['duration']
    if 'duration' not in result.columns and 'duration_formatted' in result.columns:
        result['duration'] = result['duration_formatted']

    if 'small_step_name' not in result.columns and 'small_step' in result.columns:
        result['small_step_name'] = result['small_step']
    if 'small_step' not in result.columns and 'small_step_name' in result.columns:
        result['small_step'] = result['small_step_name']

    if 'ss_wr_desc' not in result.columns and 'small_step_desc' in result.columns:
        result['ss_wr_desc'] = result['small_step_desc']
    if 'small_step_desc' not in result.columns and 'ss_wr_desc' in result.columns:
        result['small_step_desc'] = result['ss_wr_desc']

    if 'recommendation_num' not in result.columns:
        if 'rank' in result.columns:
            result['recommendation_num'] = result['rank']
        else:
            result['recommendation_num'] = 1

    if 'small_step_num_in_topic' not in result.columns and 'small_step_num' in result.columns:
        result['small_step_num_in_topic'] = result['small_step_num']

    result['small_step_id'] = result.apply(
        lambda row: build_small_step_id(
            row.get('year', ''),
            row.get('age', ''),
            row.get('term', ''),
            row.get('difficulty', ''),
            row.get('topic', ''),
            row.get('small_step_num_in_topic', row.get('small_step_num', '')),
            row.get('small_step_name', row.get('small_step', '')),
        ),
        axis=1,
    )

    result['small_step_key'] = result.apply(
        lambda row: build_small_step_key(
            row.get('year', ''),
            row.get('age', ''),
            row.get('term', ''),
            row.get('difficulty', ''),
            row.get('topic', ''),
            row.get('small_step_num_in_topic', row.get('small_step_num', '')),
            row.get('small_step_name', row.get('small_step', '')),
        ),
        axis=1,
    )

    result['recommendation_id'] = result.apply(
        lambda row: build_recommendation_id(
            row.get('small_step_id', ''),
            row.get('recommendation_num', row.get('rank', '')),
        ),
        axis=1,
    )

    return result


def enrich_precomputed_with_curriculum(
    precomputed_df: pd.DataFrame,
    curriculum_long_df: pd.DataFrame,
) -> pd.DataFrame:
    """Fill recommendation identifiers and step numbers from canonical curriculum data."""
    result = normalize_precomputed_df(precomputed_df)
    curriculum_lookup = curriculum_long_df[
        [
            'small_step_id',
            'small_step_key',
            'small_step_num',
            'small_step_num_in_topic',
            'year',
            'age',
            'term',
            'difficulty',
            'topic',
            'small_step_name',
        ]
    ].drop_duplicates(subset=['small_step_id'])

    merged = result.merge(
        curriculum_lookup,
        on='small_step_id',
        how='left',
        suffixes=('', '_curriculum'),
    )

    if 'small_step_num_global' not in merged.columns:
        merged['small_step_num_global'] = merged['small_step_num_curriculum']
    else:
        merged['small_step_num_global'] = merged['small_step_num_global'].where(
            merged['small_step_num_global'].notna(),
            merged['small_step_num_curriculum'],
        )

    if 'small_step_num_in_topic' in merged.columns:
        merged['small_step_num_in_topic'] = merged['small_step_num_in_topic'].where(
            merged['small_step_num_in_topic'].notna(),
            merged['small_step_num_in_topic_curriculum'],
        )
    else:
        merged['small_step_num_in_topic'] = merged['small_step_num_in_topic_curriculum']

    merged['small_step_key'] = merged['small_step_key'].where(
        merged['small_step_key'].astype(str).str.len() > 0,
        merged['small_step_key_curriculum'],
    )

    if 'age' in merged.columns:
        merged['age'] = merged['age'].where(merged['age'].astype(str).str.len() > 0, merged['age_curriculum'])

    for column in ['year', 'term', 'difficulty', 'topic', 'small_step_name']:
        curriculum_column = f'{column}_curriculum'
        if curriculum_column in merged.columns:
            merged[column] = merged[column].where(
                merged[column].astype(str).str.len() > 0,
                merged[curriculum_column],
            )

    if 'small_step' in merged.columns and 'small_step_name' in merged.columns:
        merged['small_step'] = merged['small_step_name']

    if 'recommendation_num' not in merged.columns and 'rank' in merged.columns:
        merged['recommendation_num'] = merged['rank']

    merged['recommendation_id'] = merged.apply(
        lambda row: build_recommendation_id(
            row.get('small_step_id', ''),
            row.get('recommendation_num', row.get('rank', '')),
        ),
        axis=1,
    )

    drop_columns = [
        column
        for column in merged.columns
        if column.endswith('_curriculum')
    ]
    return merged.drop(columns=drop_columns)


def curriculum_to_long_df(df: pd.DataFrame) -> pd.DataFrame:
    """Convert either curriculum schema into a canonical one-row-per-small-step dataframe."""
    schema = detect_curriculum_schema(df)
    if schema == 'wide':
        long_df = _expand_wide_curriculum_df(df)
    else:
        long_df = _normalize_long_curriculum_df(df)

    if long_df.empty:
        return long_df

    long_df['year'] = long_df['year'].map(clean_text)
    long_df['age'] = long_df['age'].map(clean_text)
    long_df['term'] = long_df['term'].map(clean_text)
    long_df['difficulty'] = long_df['difficulty'].map(clean_text)
    long_df['block'] = long_df['block'].map(clean_text)
    long_df['macro_topic'] = long_df['macro_topic'].map(clean_text)
    long_df['topic'] = long_df['topic'].map(clean_text)
    long_df['small_step_name'] = long_df['small_step_name'].map(clean_text)
    long_df['ss_wr_desc'] = long_df['ss_wr_desc'].map(clean_text)
    long_df['ss_desc'] = long_df['ss_desc'].map(clean_text)
    long_df['unique_row'] = long_df['unique_row'].map(clean_text)

    long_df['year_order'] = long_df.apply(
        lambda row: _parse_year_order(row.get('year', ''), row.get('age', '')),
        axis=1,
    )
    long_df['term_order'] = long_df['term'].map(_parse_term_order)

    long_df['small_step_num_in_topic'] = pd.to_numeric(
        long_df['small_step_num_in_topic'],
        errors='coerce',
    )

    missing_in_topic = long_df['small_step_num_in_topic'].isna()
    if missing_in_topic.any():
        long_df.loc[missing_in_topic, 'small_step_num_in_topic'] = (
            long_df.groupby(['year', 'term', 'difficulty', 'topic']).cumcount() + 1
        )[missing_in_topic]

    long_df['small_step_num_in_topic'] = long_df['small_step_num_in_topic'].astype(int)
    long_df['topic_order'] = _assign_topic_order(long_df)

    long_df = long_df.sort_values(
        ['year_order', 'term_order', 'topic_order', 'small_step_num_in_topic', 'source_row_index'],
        kind='stable',
    ).reset_index(drop=True)

    long_df['small_step_num'] = range(1, len(long_df) + 1)
    long_df['small_step_id'] = long_df.apply(
        lambda row: build_small_step_id(
            row.get('year', ''),
            row.get('age', ''),
            row.get('term', ''),
            row.get('difficulty', ''),
            row.get('topic', ''),
            row.get('small_step_num_in_topic', ''),
            row.get('small_step_name', ''),
        ),
        axis=1,
    )
    long_df['small_step_key'] = long_df.apply(
        lambda row: build_small_step_key(
            row.get('year', ''),
            row.get('age', ''),
            row.get('term', ''),
            row.get('difficulty', ''),
            row.get('topic', ''),
            row.get('small_step_num_in_topic', ''),
            row.get('small_step_name', ''),
        ),
        axis=1,
    )

    return long_df[
        [
            'unique_row',
            'year',
            'age',
            'term',
            'difficulty',
            'block',
            'macro_topic',
            'topic',
            'small_step_num',
            'small_step_num_in_topic',
            'small_step_name',
            'ss_wr_desc',
            'ss_desc',
            'small_step_id',
            'small_step_key',
            'year_order',
            'term_order',
            'topic_order',
            'source_row_index',
            'legacy_step_position',
        ]
    ]


def add_identifier_columns_to_wide_curriculum(df: pd.DataFrame) -> pd.DataFrame:
    """Append additive identifier columns to the legacy wide curriculum schema."""
    if detect_curriculum_schema(df) != 'wide':
        return df.copy()

    result = df.copy()
    long_df = curriculum_to_long_df(df)
    step_numbers = _legacy_step_numbers(df)
    lookup = {
        (int(row['source_row_index']), int(row['legacy_step_position'])): row
        for _, row in long_df.iterrows()
    }
    additive_columns: dict[str, list[Any]] = {}

    for step_num in step_numbers:
        id_column = f'small_step_id_{step_num}'
        key_column = f'small_step_key_{step_num}'
        num_column = f'small_step_num_global_{step_num}'
        ids = []
        keys = []
        nums = []

        for row_index in range(len(result)):
            match = lookup.get((row_index, step_num))
            if match is None:
                ids.append('')
                keys.append('')
                nums.append('')
                continue
            ids.append(match['small_step_id'])
            keys.append(match['small_step_key'])
            nums.append(int(match['small_step_num']))

        additive_columns[id_column] = ids
        additive_columns[key_column] = keys
        additive_columns[num_column] = nums

    return pd.concat([result, pd.DataFrame(additive_columns)], axis=1)


def _assign_topic_order(long_df: pd.DataFrame) -> list[int]:
    topic_orders: dict[tuple[str, str, str, str, str], int] = {}
    next_order_by_segment: dict[tuple[str, str, str, str], int] = {}
    orders: list[int] = []

    for row in long_df.itertuples(index=False):
        segment_key = (row.year, row.term, row.difficulty, row.age)
        topic_key = segment_key + (row.topic,)
        if topic_key not in topic_orders:
            next_order_by_segment[segment_key] = next_order_by_segment.get(segment_key, 0) + 1
            topic_orders[topic_key] = next_order_by_segment[segment_key]
        orders.append(topic_orders[topic_key])

    return orders


def _actual_column(columns: list[Any], *candidates: str) -> str | None:
    lookup = {str(column).strip().lower(): str(column) for column in columns}
    for candidate in candidates:
        actual = lookup.get(candidate.lower())
        if actual is not None:
            return actual
    return None


def _value_from_row(row: pd.Series, columns: list[Any], *candidates: str) -> str:
    for candidate in candidates:
        actual = _actual_column(columns, candidate)
        if actual is None:
            continue
        value = clean_text(row.get(actual, ''))
        if value:
            return value
    return ''


def _expand_wide_curriculum_df(df: pd.DataFrame) -> pd.DataFrame:
    columns = list(df.columns)
    rows: list[dict[str, Any]] = []
    step_numbers = _legacy_step_numbers(df)

    ordered = df.copy()
    ordered['_source_row_index'] = range(len(ordered))
    ordered['_year_order'] = ordered.apply(
        lambda row: _parse_year_order(
            _value_from_row(row, columns, 'Year', 'year'),
            _value_from_row(row, columns, 'Age', 'age'),
        ),
        axis=1,
    )
    ordered['_term_order'] = ordered.apply(
        lambda row: _parse_term_order(_value_from_row(row, columns, 'Term', 'term')),
        axis=1,
    )
    ordered = ordered.sort_values(['_year_order', '_term_order', '_source_row_index'], kind='stable')

    for _, row in ordered.iterrows():
        source_row_index = int(row['_source_row_index'])
        year = _value_from_row(row, columns, 'Year', 'year')
        age = _value_from_row(row, columns, 'Age', 'age')
        term = _value_from_row(row, columns, 'Term', 'term')
        difficulty = _value_from_row(row, columns, 'Difficulty', 'difficulty')
        block = _value_from_row(row, columns, 'block')
        macro_topic = _value_from_row(row, columns, 'macro_topic', 'Macro_Topic')
        topic = _value_from_row(row, columns, 'Topic', 'topic')
        unique_row = _value_from_row(row, columns, 'UniqueRow', 'unique_row')
        if not unique_row:
            unique_row = f"row_{source_row_index + 1}"

        for step_num in step_numbers:
            step_name = _value_from_row(
                row,
                columns,
                f'Small Step {step_num}',
                f'small_step_name_{step_num}',
            )
            if not step_name:
                continue

            ss_wr_desc = _value_from_row(
                row,
                columns,
                f'SS{step_num}_desc',
                f'ss{step_num}_wr_desc',
            )
            ss_desc = _value_from_row(
                row,
                columns,
                f'SS{step_num}_desc_short',
                f'ss{step_num}_desc',
            )

            rows.append(
                {
                    'unique_row': unique_row,
                    'year': year,
                    'age': age,
                    'term': term,
                    'difficulty': difficulty,
                    'block': block,
                    'macro_topic': macro_topic,
                    'topic': topic,
                    'small_step_num_in_topic': step_num,
                    'small_step_name': step_name,
                    'ss_wr_desc': ss_wr_desc,
                    'ss_desc': ss_desc,
                    'source_row_index': source_row_index,
                    'legacy_step_position': step_num,
                }
            )

    return pd.DataFrame(rows)


def _normalize_long_curriculum_df(df: pd.DataFrame) -> pd.DataFrame:
    columns = list(df.columns)
    rows: list[dict[str, Any]] = []

    for source_row_index, row in df.iterrows():
        small_step_name = _value_from_row(row, columns, 'small_step_name', 'small_step')
        if not small_step_name:
            continue

        rows.append(
            {
                'unique_row': _value_from_row(row, columns, 'unique_row', 'UniqueRow'),
                'year': _value_from_row(row, columns, 'year', 'Year'),
                'age': _value_from_row(row, columns, 'age', 'Age'),
                'term': _value_from_row(row, columns, 'term', 'Term'),
                'difficulty': _value_from_row(row, columns, 'difficulty', 'Difficulty'),
                'block': _value_from_row(row, columns, 'block'),
                'macro_topic': _value_from_row(row, columns, 'macro_topic'),
                'topic': _value_from_row(row, columns, 'topic', 'Topic'),
                'small_step_num': _value_from_row(row, columns, 'small_step_num', 'small_step_num_global'),
                'small_step_num_in_topic': _value_from_row(row, columns, 'small_step_num_in_topic', 'step_num_in_topic'),
                'small_step_name': small_step_name,
                'ss_wr_desc': _value_from_row(row, columns, 'ss_wr_desc', 'small_step_desc'),
                'ss_desc': _value_from_row(row, columns, 'ss_desc', 'ss_desc_short'),
                'source_row_index': source_row_index,
                'legacy_step_position': _value_from_row(row, columns, 'legacy_step_position', 'small_step_num_in_topic'),
            }
        )

    return pd.DataFrame(rows)


def _legacy_step_numbers(df: pd.DataFrame) -> list[int]:
    step_numbers: set[int] = set()
    for column in df.columns:
        match = re.fullmatch(r'Small Step (\d+)', str(column))
        if match:
            step_numbers.add(int(match.group(1)))
            continue
        match = re.fullmatch(r'small_step_name_(\d+)', str(column))
        if match:
            step_numbers.add(int(match.group(1)))
    if step_numbers:
        return sorted(step_numbers)
    return list(range(1, LEGACY_SMALL_STEP_LIMIT + 1))


def _parse_term_order(term: str) -> int:
    return TERM_ORDER.get(clean_text(term).lower(), 99)


def _parse_year_order(year: str, age: str) -> int:
    year_match = re.search(r'(\d+)', clean_text(year))
    if year_match:
        return int(year_match.group(1))

    age_match = re.match(r'(\d+)', clean_text(age))
    if age_match:
        return int(age_match.group(1))

    return 999