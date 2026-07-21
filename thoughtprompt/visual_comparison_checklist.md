# Visual Comparison & Selection Checklist

Use this checklist to evaluate Python-generated visuals against open-source alternatives.

---

## Evaluation Summary

**Date**: 2026-07-21  
**Evaluator**: _______________

---

## 1. Base-10 Blocks (Unit Cubes & Ten-Stacks)

### Python-Generated Assessment

**Example Files**:
- `base10_blocks_4_7.png` (47 - four tens, seven ones)
- `base10_blocks_5_8.png` (58 - five tens, eight ones)
- `base10_blocks_9_9.png` (99 - nine tens, nine ones)
- `base10_blocks_3_0.png` (30 - three tens, zero ones)
- `base10_blocks_0_6.png` (06 - zero tens, six ones)

#### Evaluation Criteria

| Criteria | Rating (1-5) | Notes |
|----------|--------------|-------|
| **Age-appropriate design** | ___/5 | Clear for 8-9 year olds? |
| **Mathematical accuracy** | ___/5 | Exact counts? Proportions correct? |
| **Visual clarity** | ___/5 | Easy to distinguish tens vs ones? |
| **Color scheme** | ___/5 | Friendly, not harsh? |
| **Label readability** | ___/5 | Text clear and appropriate size? |
| **Differentiation** | ___/5 | Ten-rods vs unit cubes visually distinct? |

**Overall Python Rating**: ___/30

**Strengths**:
- 
- 
- 

**Weaknesses**:
- 
- 
- 

---

### Open-Source Alternative #1: _____________

**Source**: (Wikimedia/OpenSCAD/Khan Academy/etc.)  
**License**: _______________  
**Setup Time**: _____ minutes

#### Evaluation Criteria

| Criteria | Rating (1-5) | Notes |
|----------|--------------|-------|
| **Age-appropriate design** | ___/5 | |
| **Mathematical accuracy** | ___/5 | |
| **Visual clarity** | ___/5 | |
| **Color scheme** | ___/5 | |
| **Label readability** | ___/5 | |
| **Parameterizability** | ___/5 | Can generate any tens/ones combo? |

**Overall Rating**: ___/30

**Pros**:
- 
- 

**Cons**:
- 
- 

---

### Open-Source Alternative #2: _____________

*(Repeat evaluation criteria as above)*

---

### DECISION: Base-10 Blocks

**Selected Approach**: [ ] Python  [ ] OpenSCAD  [ ] Wikimedia  [ ] Khan Academy  [ ] Other: _______

**Rationale**:




---

## 2. Part-Whole Models (Cherry/Number Bond Diagrams)

### Python-Generated Assessment

**Example Files**:
- `part_whole_47_40_7.png` (47 = 40 + 7)
- `part_whole_100_60_40.png` (100 = 60 + 40)
- `part_whole_47_30_17.png` (47 = 30 + 17, flexible partition)
- `part_whole_100_50_30_20.png` (100 = 50 + 30 + 20, three parts)

#### Evaluation Criteria

| Criteria | Rating (1-5) | Notes |
|----------|--------------|-------|
| **Age-appropriate design** | ___/5 | |
| **Relationship clarity** | ___/5 | Total → parts relationship obvious? |
| **Visual hierarchy** | ___/5 | Total circle visually distinct from parts? |
| **Color scheme** | ___/5 | |
| **Number readability** | ___/5 | |
| **Works with 3+ parts** | ___/5 | Handles flexible partitioning? |

**Overall Python Rating**: ___/30

**Strengths**:
- 
- 

**Weaknesses**:
- 
- 

---

### Open-Source Alternatives

*(Add evaluation sections if found)*

---

### DECISION: Part-Whole Models

**Selected Approach**: [ ] Python  [ ] SVG Library  [ ] Other: _______

**Rationale**:




---

## 3. Bar Models (Tape Diagrams)

### Python-Generated Assessment

**Example Files**:
- `bar_model_add_100_60_40.png` (100 = 60 + 40)
- `bar_model_add_47_40_7.png` (47 = 40 + 7)
- `bar_model_add_150_80_50_20.png` (150 = 80 + 50 + 20)
- `bar_model_sub_100_60_40.png` (100 - 60 = 40)
- `bar_model_sub_47_20_27.png` (47 - 20 = 27)

#### Evaluation Criteria

| Criteria | Rating (1-5) | Notes |
|----------|--------------|-------|
| **Proportional accuracy** | ___/5 | Lengths mathematically correct? |
| **Visual clarity** | ___/5 | Easy to see part relationships? |
| **Color coding** | ___/5 | Different parts visually distinct? |
| **Label placement** | ___/5 | Numbers clearly inside bars? |
| **Addition vs subtraction** | ___/5 | Both operations clear? |
| **Multiple parts** | ___/5 | Works with 3+ addends? |

**Overall Python Rating**: ___/30

**Strengths**:
- 
- 

**Weaknesses**:
- 
- 

---

### Open-Source Alternatives

*(Add evaluation sections if found)*

---

### DECISION: Bar Models

**Selected Approach**: [ ] Python  [ ] Singapore Math Templates  [ ] Other: _______

**Rationale**:




---

## 4. Number Lines

### Python-Generated Assessment

**Example Files**:
- `number_line_0_10_highlight_7.png` (0-10 scale)
- `number_line_0_100_highlight_47.png` (0-100 scale)
- `number_line_0_1000_highlight_650.png` (0-1000 scale)
- `number_line_20_80_highlight_47.png` (non-zero start)
- `number_line_0_10000_highlight_5247.png` (0-10000 scale)

#### Evaluation Criteria

| Criteria | Rating (1-5) | Notes |
|----------|--------------|-------|
| **Scale clarity** | ___/5 | Intervals clearly marked? |
| **Tick mark hierarchy** | ___/5 | Major vs minor ticks obvious? |
| **Highlight visibility** | ___/5 | Highlighted number stands out? |
| **Label readability** | ___/5 | Numbers not overlapping? |
| **Multiple scales** | ___/5 | Works for 0-10 and 0-10000? |
| **Proportional accuracy** | ___/5 | Position mathematically correct? |

**Overall Python Rating**: ___/30

**Strengths**:
- 
- 

**Weaknesses**:
- 
- 

---

### Open-Source Alternatives

*(matplotlib is industry standard - alternatives unlikely to be better)*

---

### DECISION: Number Lines

**Selected Approach**: [ ] Python/matplotlib  [ ] Other: _______

**Rationale**:




---

## Final Summary

### Visual Type Selection

| Visual Type | Selected Approach | Confidence (Low/Med/High) |
|-------------|-------------------|---------------------------|
| Base-10 Blocks | _______________ | ____________ |
| Part-Whole Models | _______________ | ____________ |
| Bar Models | _______________ | ____________ |
| Number Lines | _______________ | ____________ |

---

### Action Items

**Immediate**:
- [ ] Document selected approaches in README
- [ ] If using open-source, download/organize assets
- [ ] If using Python, finalize visual_generator.py
- [ ] Test selected visuals with 1-2 educators/learners for feedback

**Next Phase**:
- [ ] Begin prompt generation (Phase 2)
- [ ] Source video transcripts for lines 374-390
- [ ] Create prompt CSV template

---

### Notes & Observations




---

**Completed**: ___________  
**Signed**: ___________
