# Thought Prompt System

Interactive learning enhancement for Flipper Lite - generates concept-checking prompts with visual aids after each video.

---

## Overview

This subproject adds an active learning layer to the Flipper video system by:
1. **Generating thought prompts** aligned with video content
2. **Displaying visual aids** (base-10 blocks, bar models, number lines, etc.)
3. **Capturing learner responses** via key presses and numeric input
4. **Tracking accuracy** in an educator-only portal

---

## Project Scope (Pilot Phase)

### Target Audience
- **Year 4 students** (ages 8-9)
- **Curriculum focus**: Place Value (lines 374-390 in curriculum CSV)
- **Scope**: 17 small steps, first video only per step

### Visual Types Supported
1. **Base-10 Blocks** - Unit cubes and ten-stacks for place value
2. **Part-Whole Models** - Cherry/number bond diagrams for partitioning
3. **Bar Models** - Proportional rectangles for operations
4. **Number Lines** - Scaled lines with interval marking

### Response Types
1. **Multiple choice** - Radio button selection (A/B/C/D)
2. **Numeric input** - Single number entry
3. **Numeric two-part** - Separate inputs (e.g., tens and ones)

### Key Features
- **3 prompt variants per video** - Progressive difficulty if first attempt incorrect
- **Per small-step tracking** - Accuracy metrics grouped by learning objective
- **Educator view only** - Responses hidden from learners, visible to teachers

---

## Project Structure

```
thoughtprompt/
├── README.md                      # This file
├── visual_generator.py            # Core visual generation library
├── test_visuals.py                # Generate example images for comparison
├── research_open_source.md        # Open-source alternatives research
├── comparison_results/            # Generated example images
│   ├── base10_blocks_*.png
│   ├── part_whole_*.png
│   ├── bar_model_*.png
│   └── number_line_*.png
├── prompts/                       # Prompt definitions (to be created)
│   └── year4_place_value.csv
├── responses/                     # Response tracking (to be created)
│   └── responses.csv
└── integration/                   # Flipper Lite integration code (to be created)
    └── prompt_display.py
```

---

## Development Phases

### ✅ Phase 1: Visual Template Creation (Current)
**Goal**: Create and compare visual generation approaches

**Tasks**:
- [x] Build Python visual generator with 4 template types
- [x] Generate example images for all types
- [x] Document open-source alternatives research
- [ ] Run `test_visuals.py` to generate comparison images
- [ ] Compare Python vs open-source visual quality
- [ ] Select optimal approach per visual type

**Deliverable**: Finalized visual template library

---

### ⏳ Phase 2: Prompt Generation (Next)
**Goal**: Create thought prompts for Year 4 Place Value videos

**Approach**:
1. **Manual creation** (pilot): 17 prompts × 3 variants = 51 prompts
2. **AI-assisted** (scale-up): Use Claude Sonnet to generate from transcripts

**Data Schema**:
```csv
small_step_id,video_id,variant,prompt_text,answer_type,correct_answer,visual_type,visual_params,options
year-4__partition-1000,VIDEO_ID,1,"Partition 347. Hundreds: ___ Tens: ___ Ones: ___",numeric_three_part,"3,4,7",base10_blocks,"{""hundreds"":3,""tens"":4,""ones"":7}",""
```

**Tasks**:
- [ ] Source video transcripts for lines 374-390
- [ ] Manually create 3 prompts for first 5 small steps (test format)
- [ ] Build prompt data CSV
- [ ] Validate prompts align with small step learning objectives

**Deliverable**: `prompts/year4_place_value.csv` with 51 prompts

---

### ⏳ Phase 3: Flipper Lite Integration
**Goal**: Display prompts after video viewing and capture responses

**Components**:
1. **Prompt trigger** - "I've finished watching" button
2. **Visual display** - Render appropriate diagram using visual_generator
3. **Response UI** - Input fields based on answer_type
4. **Response storage** - Save to CSV with timestamp
5. **Session state** - Track current prompt variant (1, 2, or 3)

**Integration Points** in `flipper_lite.py`:
- Modify `render_video_player()` to add prompt trigger
- New function `render_thought_prompt()` 
- New session state variables:
  - `st.session_state.thought_prompt_mode` (on/off toggle)
  - `st.session_state.current_prompt`
  - `st.session_state.prompt_attempt` (1-3)
  - `st.session_state.prompt_responses` (list)

**Tasks**:
- [ ] Create `integration/prompt_display.py` 
- [ ] Add prompt loading function (video_id → prompt data)
- [ ] Build response UI components
- [ ] Implement 3-attempt logic (variant progression)
- [ ] Add response recording function
- [ ] Test with 2-3 sample videos

**Deliverable**: Working prompt system in flipper_lite.py

---

### ⏳ Phase 4: Educator Portal
**Goal**: Display learner responses and accuracy metrics

**Approach**: New Streamlit page `pages/educator_view.py`

**Features**:
- Response history table (timestamp, video, prompt, answer, correctness)
- Filters: by small_step, by date, by accuracy
- Metrics: 
  - Overall accuracy %
  - Per-small-step accuracy
  - Common wrong answers
  - Time distribution (if tracked)

**Tasks**:
- [ ] Create `pages/educator_view.py`
- [ ] Load responses from CSV
- [ ] Build filtering UI
- [ ] Add accuracy visualizations (bar charts)
- [ ] Test with sample response data

**Deliverable**: Educator dashboard accessible via sidebar

---

### ⏳ Phase 5: Scale-Up with AI
**Goal**: Generate prompts for all Year 4 videos using Claude Sonnet

**Approach**:
1. Build `generate_prompts.py` script
2. Use Claude Sonnet API to analyze transcripts
3. Generate 3 variants per video automatically
4. Manual QA on 20-30 generated prompts
5. Batch generate remaining prompts

**Prompt Engineering** (for Claude Sonnet):
```
You are an expert Year 4 maths educator (ages 8-9).

Small Step: [name and description]
Video Transcript: [full transcript]

Generate 3 thought prompt VARIANTS testing the same concept:
- Variant 1: Basic (similar difficulty to video examples)
- Variant 2: Slightly harder (different numbers, more complex)
- Variant 3: Most challenging (flexible thinking required)

For EACH variant, output JSON:
{
  "prompt_text": "Natural language question",
  "answer_type": "multiple_choice | numeric | numeric_two_part | numeric_three_part",
  "correct_answer": "...",
  "visual_type": "base10_blocks | part_whole_model | bar_model | number_line | none",
  "visual_params": {...},
  "options": [...] // if multiple_choice
}
```

**Estimated Cost**:
- 17 small steps × 5-10 videos average = ~100 videos
- ~$0.50-1.00 per video (3 prompts)
- **Total: ~$50-100** (covered by Sonnet subscription)

**Tasks**:
- [ ] Create `generate_prompts.py` with Claude Sonnet integration
- [ ] Source transcripts for all Year 4 Place Value videos
- [ ] Run generation on 5 test videos
- [ ] Manual QA and refinement
- [ ] Batch generate remaining videos
- [ ] Merge into main prompts CSV

**Deliverable**: Complete prompt database for Year 4 Place Value

---

## Usage Instructions

### Generate Visual Examples

```powershell
cd thoughtprompt
python test_visuals.py
```

This creates ~20-25 example images in `comparison_results/` directory.

### Review Generated Images

Navigate to `comparison_results/` and view:
- Base-10 block examples (various tens/ones combinations)
- Part-whole model examples (different partitions)
- Bar model examples (addition and subtraction)
- Number line examples (different ranges and highlights)

### Compare with Open-Source Options

1. Follow research steps in `research_open_source.md`
2. Download/generate open-source alternatives
3. Place in `comparison_results/opensrc/` for side-by-side comparison
4. Evaluate using criteria matrix in research doc

### Use Visual Generator in Code

```python
from thoughtprompt.visual_generator import MathVisualGenerator

gen = MathVisualGenerator()

# Generate base-10 blocks for 47
img = gen.generate_base10_blocks(tens=4, ones=7, label=True)
img.save("output.png")

# Generate part-whole model
img = gen.generate_part_whole_model(total=47, parts=[40, 7])
img.save("part_whole.png")

# Generate bar model
img = gen.generate_bar_model(total=100, parts=[60, 40], operation='addition')
img.save("bar_model.png")

# Generate number line
img = gen.generate_number_line(start=0, end=100, highlight=47, interval=10)
img.save("number_line.png")

# Convert to base64 for Streamlit display
base64_str = gen.to_base64(img)
st.markdown(f'<img src="{base64_str}">', unsafe_allow_html=True)
```

---

## Technical Specifications

### Dependencies
- **PIL (Pillow)** - Image generation
- **matplotlib** - Number line plotting (future)
- **pandas** - CSV data handling
- **streamlit** - UI integration
- **anthropic** - Claude Sonnet API (for prompt generation)

### Image Specifications
- **Format**: PNG
- **Default size**: 800×400 pixels
- **Background**: White (#FFFFFF)
- **Color palette**: Age-appropriate, friendly colors
- **Font**: Arial (with fallback to PIL default)
- **Output**: Base64 encoded for Streamlit or saved as PNG files

### Data Schemas

**Prompts CSV**:
```
small_step_id, video_id, variant, prompt_text, answer_type, 
correct_answer, visual_type, visual_params, options
```

**Responses CSV**:
```
timestamp, session_id, small_step_id, video_id, variant, 
prompt_text, learner_answer, correct_answer, is_correct
```

---

## Design Decisions

### Why Python for Visual Generation?
1. **Mathematically precise** - Exact counts, proportions guaranteed
2. **Parameterizable** - Easy to generate any number combination
3. **Zero cost** - No external dependencies or licensing
4. **Fast** - Sub-second generation per image
5. **Maintainable** - Pure Python, no external tools required

### Why 3 Prompt Variants?
- **Educational best practice**: Progressive difficulty supports learning
- **Engagement**: Immediate correction without frustration
- **Data quality**: Distinguishes "got it" from "guessed correctly"
- **Ceiling**: 3 attempts balances learning vs time-on-task

### Why First Video Only (Pilot)?
- **Feasibility**: Manageable scope for manual creation
- **Validation**: Test concept before investing in scale-up
- **Iteration**: Learn what works before generating 100+ prompts
- **Cost control**: Minimize AI generation costs during testing

---

## Success Metrics (Post-Pilot)

### Engagement
- [ ] % of learners who attempt thought prompts
- [ ] Average time spent on prompts
- [ ] Completion rate (finish all 3 attempts if needed)

### Learning Outcomes
- [ ] Accuracy on first attempt (target: >60%)
- [ ] Improvement from variant 1 → variant 3
- [ ] Correlation with educator assessments

### Technical Performance
- [ ] Visual generation speed (<1s per image)
- [ ] UI responsiveness
- [ ] Response data integrity

### User Experience
- [ ] Learner feedback (age-appropriate survey)
- [ ] Educator feedback (usefulness of response data)
- [ ] Visual clarity ratings

---

## Future Enhancements (Post-Pilot)

### Phase 6+: Expand to Other Topics
- Year 3 Place Value
- Addition and Subtraction
- Multiplication and Division
- Fractions

### Advanced Features
- **Adaptive difficulty** - AI adjusts based on learner performance
- **Text-to-speech** - Auditory prompt delivery for younger learners
- **Animated visuals** - Show manipulation of blocks/models
- **Learner dashboard** - Progress tracking visible to students
- **Collaborative mode** - Peer discussion prompts

### Technical Improvements
- **Real-time generation** - Create prompts on-the-fly from any video
- **A/B testing** - Compare prompt types for effectiveness
- **Analytics dashboard** - Advanced metrics and visualizations
- **Export reports** - PDF summaries for parent-teacher conferences

---

## Contributing

### Adding New Visual Types
1. Add method to `MathVisualGenerator` class
2. Update `generate()` routing method
3. Add test cases to `test_visuals.py`
4. Document in this README

### Adding New Prompt Types
1. Update CSV schema if needed
2. Add UI component to `integration/prompt_display.py`
3. Update response recording logic
4. Test with sample data

---

## License & Attribution

- **Python code**: Own creation, free to modify
- **Open-source assets**: See `research_open_source.md` for specific licenses
- **Generated visuals**: Own creation, no restrictions

---

## Contact & Support

For questions about this subproject, refer to main Flipper Lite documentation or contact project maintainer.

---

**Last Updated**: 2026-07-21  
**Status**: Phase 1 (Visual Template Creation) - In Progress  
**Next Milestone**: Generate comparison images and select visual approaches
