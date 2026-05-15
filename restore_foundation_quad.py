# -*- coding: utf-8-sig -*-
import pandas as pd
import os

csv_file = r"Curriculum\Maths\curriculum_08052026_small_steps.csv"

# Read the CSV
df = pd.read_csv(csv_file, encoding='utf-8-sig')

# Define complete Foundation Quadratic data with all required columns
foundation_quadratic_data = [
    {
        'unique_row': 'Year10AutumnFoundationQuadraticexpressionsandequations',
        'year': 'Year 10',
        'age': '14-15',
        'term': 'Autumn',
        'difficulty': 'Foundation',
        'block_num': 3,
        'macro_topic': 'Algebra',
        'topic': 'Quadratic expressions and equations',
        'small_step_num': 1212,
        'small_step_num_in_topic': 1,
        'small_step_name': 'Expand double brackets',
        'ss_wr_desc': "In this small step, students will build on their knowledge of expanding double brackets in the form (ax +/- b)(cx +/- d) from Key Stage 3. Begin with expressions in the form (x + a)(x + b), with all positive terms, and introduce negative terms as students' confidence develops, before introducing expressions with coefficients of the variable. Expressions in unfamiliar forms such as (x + 2)^2 or (x + 2)(3 + x) can also be explored. Recap the use of an area model as a visual prompt for discussion on how to expand binomials, using algebra tiles to support if necessary. Students need to be confident with simplification and calculating with negative numbers. Where appropriate, extend students by expanding brackets in other mathematical contexts, for example, expressing the area of rectilinear shapes with binomial dimensions.",
        'ss_desc': 'Students expand double brackets in various forms using area models and algebra tiles.',
        'small_step_id': 'Year 10_14-15_Autumn_Foundation_Quadratic expressions and equations_1_Expand double brackets',
        'small_step_key': 'year-10__14-15__autumn__foundation__quadratic-expressions-and-equations__1__expand-double-brackets',
        'year_order': 10,
        'term_order': 1,
        'topic_order': 3,
        'source_row_index': 12,
        'legacy_step_position': 1
    },
    {
        'unique_row': 'Year10AutumnFoundationQuadraticexpressionsandequations',
        'year': 'Year 10',
        'age': '14-15',
        'term': 'Autumn',
        'difficulty': 'Foundation',
        'block_num': 3,
        'macro_topic': 'Algebra',
        'topic': 'Quadratic expressions and equations',
        'small_step_num': 1213,
        'small_step_num_in_topic': 2,
        'small_step_name': 'Factorise quadratic expressions (positive only)',
        'ss_wr_desc': "In this small step, students will build on their knowledge of expanding double brackets in the form (ax +/- b)(cx +/- d) from Key Stage 3. Begin with expressions in the form (x + a)(x + b), with all positive terms, and introduce negative terms as students' confidence develops, before introducing expressions with coefficients of the variable. Expressions in unfamiliar forms such as (x + 2)^2 or (x + 2)(3 + x) can also be explored. Recap the use of an area model as a visual prompt for discussion on how to expand binomials, using algebra tiles to support if necessary. Students need to be confident with simplification and calculating with negative numbers. Where appropriate, extend students by expanding brackets in other mathematical contexts, for example, expressing the area of rectilinear shapes with binomial dimensions.",
        'ss_desc': 'Students begin factorising quadratics in the form x2 + bx + c using number bonds and area models.',
        'small_step_id': 'Year 10_14-15_Autumn_Foundation_Quadratic expressions and equations_2_Factorise quadratic expressions (positive only)',
        'small_step_key': 'year-10__14-15__autumn__foundation__quadratic-expressions-and-equations__2__factorise-quadratic-expressions-positive-only',
        'year_order': 10,
        'term_order': 1,
        'topic_order': 3,
        'source_row_index': 12,
        'legacy_step_position': 2
    },
    {
        'unique_row': 'Year10AutumnFoundationQuadraticexpressionsandequations',
        'year': 'Year 10',
        'age': '14-15',
        'term': 'Autumn',
        'difficulty': 'Foundation',
        'block_num': 3,
        'macro_topic': 'Algebra',
        'topic': 'Quadratic expressions and equations',
        'small_step_num': 1214,
        'small_step_num_in_topic': 3,
        'small_step_name': 'Factorise quadratic expressions',
        'ss_wr_desc': "In this small step, students will factorise quadratic expressions in the form x2 + bx + c, which they may have previously explored in Key Stage 3. Students will look at factorising expressions including negatives in the following step. Begin by asking students to find two numbers that make a specific sum and product, for example, find two numbers that have a sum of 7 and a product of 10 Support students to make connections by explicitly showing that factorising is the inverse of expanding brackets. Using algebra tiles and multiplication grids can strengthen students' conceptual understanding.",
        'ss_desc': 'Students factorise quadratic expressions with positive and negative terms in the form x2 +/- bx +/- c.',
        'small_step_id': 'Year 10_14-15_Autumn_Foundation_Quadratic expressions and equations_3_Factorise quadratic expressions',
        'small_step_key': 'year-10__14-15__autumn__foundation__quadratic-expressions-and-equations__3__factorise-quadratic-expressions',
        'year_order': 10,
        'term_order': 1,
        'topic_order': 3,
        'source_row_index': 12,
        'legacy_step_position': 3
    },
    {
        'unique_row': 'Year10AutumnFoundationQuadraticexpressionsandequations',
        'year': 'Year 10',
        'age': '14-15',
        'term': 'Autumn',
        'difficulty': 'Foundation',
        'block_num': 3,
        'macro_topic': 'Algebra',
        'topic': 'Quadratic expressions and equations',
        'small_step_num': 1215,
        'small_step_num_in_topic': 4,
        'small_step_name': 'Difference of two squares (E)',
        'ss_wr_desc': "In this small step, students will factorise quadratic expressions in the form x2 +/- bx +/- c. This will build on students' understanding from the previous step of factorising expressions in the form x2 + bx + c. In this step, it may be useful to recap calculations with directed numbers. Similarly to the last step, begin by asking students to find two numbers that make a specific sum and product, for example, find two numbers that have a sum of -6 and a product of 8, and encourage students to factorise an expression using these values, for example, x2 - 6x + 8 Using algebra tiles and multiplication grids can strengthen students' conceptual understanding. Once students are confident, progress onto factorising expressions such as x2 + 7x - 30 and x2 - x - 12",
        'ss_desc': 'Students explore and identify the difference of two squares pattern (x^2 - a^2) and use it to factorise expressions efficiently.',
        'small_step_id': 'Year 10_14-15_Autumn_Foundation_Quadratic expressions and equations_4_Difference of two squares (E)',
        'small_step_key': 'year-10__14-15__autumn__foundation__quadratic-expressions-and-equations__4__difference-of-two-squares-e',
        'year_order': 10,
        'term_order': 1,
        'topic_order': 3,
        'source_row_index': 12,
        'legacy_step_position': 4
    },
    {
        'unique_row': 'Year10AutumnFoundationQuadraticexpressionsandequations',
        'year': 'Year 10',
        'age': '14-15',
        'term': 'Autumn',
        'difficulty': 'Foundation',
        'block_num': 3,
        'macro_topic': 'Algebra',
        'topic': 'Quadratic expressions and equations',
        'small_step_num': 1216,
        'small_step_num_in_topic': 5,
        'small_step_name': 'Solve quadratic equations equal to 0',
        'ss_wr_desc': "In this small step, students will explore expressions in the form x2 - a2 where a is an integer. Encourage students to expand brackets of the form (x +/- a)(x +/- a) to uncover the difference of two squares and explore the connection to quadratics in the form x2 +/- bx +/- c, noting how the middle term bx is eliminated. This exploration should help them make the link before moving onto factorisation. Highlight to students that, for example, in the expression x2 - 36, the value of b is 0, hence why it is omitted. Then encourage students to consider a factor pair of -36 that sum to 0, to enable them to factorise the expression. Repeat with other expressions in this form, encouraging students to spot that the value of c is always a square number. If appropriate, explore fully factorising expressions such as 48 - 3y2",
        'ss_desc': 'Students prepare to solve quadratic equations by understanding the principle that if (x+a)(x+b)=0, then x=-a or x=-b.',
        'small_step_id': 'Year 10_14-15_Autumn_Foundation_Quadratic expressions and equations_5_Solve quadratic equations equal to 0',
        'small_step_key': 'year-10__14-15__autumn__foundation__quadratic-expressions-and-equations__5__solve-quadratic-equations-equal-to-0',
        'year_order': 10,
        'term_order': 1,
        'topic_order': 3,
        'source_row_index': 12,
        'legacy_step_position': 5
    },
    {
        'unique_row': 'Year10AutumnFoundationQuadraticexpressionsandequations',
        'year': 'Year 10',
        'age': '14-15',
        'term': 'Autumn',
        'difficulty': 'Foundation',
        'block_num': 3,
        'macro_topic': 'Algebra',
        'topic': 'Quadratic expressions and equations',
        'small_step_num': 1217,
        'small_step_num_in_topic': 6,
        'small_step_name': 'Solve quadratic equations by factorisation',
        'ss_wr_desc': "In this small step, students will solve quadratic expressions equal to zero in the form (x + a)(x + b) = 0. The purpose of this step is to prepare students for solving quadratic equations by factorisation. Firstly, practise solving linear equations equal to zero such as x + 2 = 0 and ab = 0, varying the value of a or b before solving. Draw students' attention to the fact that if the product of two numbers or terms is zero, then at least one of the two numbers or terms must be zero. This understanding helps explain why quadratic equations can have up to two solutions. Remind students that (x + a)(x + b) = 0 represents (x + a) * (x + b) = 0, and so to solve it, the value of either bracket must be 0",
        'ss_desc': 'Students apply quadratic factorisation to solve equations, checking solutions by substitution.',
        'small_step_id': 'Year 10_14-15_Autumn_Foundation_Quadratic expressions and equations_6_Solve quadratic equations by factorisation',
        'small_step_key': 'year-10__14-15__autumn__foundation__quadratic-expressions-and-equations__6__solve-quadratic-equations-by-factorisation',
        'year_order': 10,
        'term_order': 1,
        'topic_order': 3,
        'source_row_index': 12,
        'legacy_step_position': 6
    },
    {
        'unique_row': 'Year10AutumnFoundationQuadraticexpressionsandequations',
        'year': 'Year 10',
        'age': '14-15',
        'term': 'Autumn',
        'difficulty': 'Foundation',
        'block_num': 3,
        'macro_topic': 'Algebra',
        'topic': 'Quadratic expressions and equations',
        'small_step_num': 1218,
        'small_step_num_in_topic': 7,
        'small_step_name': 'Quadratic graphs of the form y = x2 + a',
        'ss_wr_desc': "In this small step, students will revisit previous content from Year 9 on plotting graphs in the form y = x2 +/- a using a table of values. Ensure students are confident substituting values, including negative numbers, into quadratic. Draw students' attention to the fact quadratic graphs are drawn with a smooth curve and not straight lines. Graphs in the form y = x2 +/- bx +/- c will be covered in later steps, so it is not necessary to address them now. If appropriate, challenge students to plot graphs with a negative coefficient of x2, for example, y = 5 - x2",
        'ss_desc': 'Students plot quadratic graphs and identify key features like the y-intercept and axis of symmetry.',
        'small_step_id': 'Year 10_14-15_Autumn_Foundation_Quadratic expressions and equations_7_Quadratic graphs of the form y = x2 + a',
        'small_step_key': 'year-10__14-15__autumn__foundation__quadratic-expressions-and-equations__7__quadratic-graphs-of-the-form-y-=-x2-+-a',
        'year_order': 10,
        'term_order': 1,
        'topic_order': 3,
        'source_row_index': 12,
        'legacy_step_position': 7
    }
]

# Remove existing Foundation Quadratic rows
df_cleaned = df[~((df['topic'] == 'Quadratic expressions and equations') & (df['difficulty'] == 'Foundation'))].copy()

# Find the start of Higher Quadratic rows to place Foundation rows before them
higher_quad_rows = df_cleaned[(df_cleaned['topic'] == 'Quadratic expressions and equations') & (df_cleaned['difficulty'] == 'Higher')]

if not higher_quad_rows.empty:
    insertion_idx = higher_quad_rows.index.min()
    head = df_cleaned.iloc[:insertion_idx]
    tail = df_cleaned.iloc[insertion_idx:]
    foundation_df = pd.DataFrame(foundation_quadratic_data)
    foundation_df = foundation_df.reindex(columns=df.columns)
    df_final = pd.concat([head, foundation_df, tail], ignore_index=True)
else:
    foundation_df = pd.DataFrame(foundation_quadratic_data)
    df_final = pd.concat([df_cleaned, foundation_df], ignore_index=True)

# Save
df_final.to_csv(csv_file, index=False, encoding='utf-8-sig')
print("? Foundation Quadratic topic successfully restored.")
