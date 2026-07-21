# Base-10 Blocks: Label Options Comparison

## Overview
The visual generator now supports two modes for base-10 blocks:
1. **With Labels** (default): Includes title and count labels
2. **Label-Free**: Clean blocks only, for external text placement

---

## Option 1: With Labels (`label=True`)

### Example Images
- `base10_blocks_4_7.png` - With "Representing 47", "4 tens", "7 ones"
- `base10_blocks_9_9.png` - With "Representing 99", "9 tens", "9 ones"

### Features
✅ Complete, self-contained image  
✅ Title at top: "Representing {number}"  
✅ Labels at bottom: "X tens", "Y ones"  
✅ Proper margins around all text and blocks  
✅ Automatic scaling to fit title + content + labels  

### Use Cases
- Standalone worksheets
- Printed materials
- Email/PDF attachments
- Self-explanatory visuals

### Usage
```python
from thoughtprompt.visual_generator import MathVisualGenerator

gen = MathVisualGenerator()
img = gen.generate_base10_blocks(tens=4, ones=7, label=True)  # Default
img.save("output.png")
```

---

## Option 2: Label-Free (`label=False`)

### Example Images
- `label_free/base10_blocks_4_7_no_label.png` - Blocks only
- `label_free/base10_blocks_9_9_no_label.png` - Blocks only

### Features
✅ Clean, minimalist image with only blocks  
✅ Larger margins (more breathing room)  
✅ Perfect for custom text placement  
✅ Smaller file size  
✅ More flexible layout options  

### Use Cases
- **Streamlit apps** - Add `st.markdown()` titles above images
- Custom layouts with external text boxes
- Multi-language support (add translated text externally)
- Dynamic titles based on context
- Thought prompt system (where prompt text is separate)

### Usage
```python
from thoughtprompt.visual_generator import MathVisualGenerator

gen = MathVisualGenerator()
img = gen.generate_base10_blocks(tens=4, ones=7, label=False)
img.save("output.png")
```

### Streamlit Example
```python
import streamlit as st
from thoughtprompt.visual_generator import MathVisualGenerator

gen = MathVisualGenerator()

# Generate label-free image
img = gen.generate_base10_blocks(tens=4, ones=7, label=False)

# Add custom title in Streamlit
st.markdown("### How many do you see?")
st.image(img, use_column_width=True)
st.markdown("**Hint:** Count the tens and ones!")
```

---

## Visual Comparison

### With Labels (label=True)
```
┌────────────────────────────────────────┐
│ Representing 47                        │ ← Title
│                                        │
│      ████  ████  ████  ████   □□□□□   │
│      ████  ████  ████  ████   □□       │ ← Blocks
│      ████  ████  ████  ████           │
│                                        │
│      4 tens          7 ones            │ ← Labels
└────────────────────────────────────────┘
```

### Label-Free (label=False)
```
┌────────────────────────────────────────┐
│                                        │ ← More margin
│      ████  ████  ████  ████   □□□□□   │
│      ████  ████  ████  ████   □□       │ ← Blocks only
│      ████  ████  ████  ████           │
│                                        │ ← More margin
└────────────────────────────────────────┘
```

---

## Margin Differences

| Feature | With Labels | Label-Free |
|---------|-------------|------------|
| **Top Margin** | 60px | 40px |
| **Bottom Margin** | 70px | 40px |
| **Content Space** | ~270px | ~320px |
| **Result** | Smaller blocks (more scaling) | Larger blocks (less scaling) |

---

## Recommendation for Thought Prompt System

### ✅ Use **Label-Free (`label=False`)**

**Reasons:**
1. **Flexibility**: Prompt text is separate from visual
2. **Localization**: Easy to translate prompt text
3. **Dynamic content**: Can change questions without regenerating images
4. **Cleaner separation**: Image = representation, Text = question
5. **Better UX**: More control over layout in Streamlit

### Example Workflow
```python
# Generate visual once
img = gen.generate_base10_blocks(tens=4, ones=7, label=False)
img_base64 = gen.to_base64(img)

# Store in CSV with prompt text
prompts_df = pd.DataFrame([{
    'visual_base64': img_base64,
    'prompt_text': 'How many tens and ones do you see?',
    'correct_answer': '4 tens and 7 ones',
    # ... other fields
}])

# Display in Streamlit
st.markdown(f"### {row['prompt_text']}")
st.image(row['visual_base64'])
```

---

## Files Generated

### With Labels
```
thoughtprompt/comparison_results/
├── base10_blocks_4_7.png   (with title/labels)
├── base10_blocks_5_8.png
├── base10_blocks_3_0.png
├── base10_blocks_0_6.png
└── base10_blocks_9_9.png
```

### Label-Free
```
thoughtprompt/comparison_results/label_free/
├── base10_blocks_4_7_no_label.png   (blocks only)
├── base10_blocks_5_8_no_label.png
├── base10_blocks_3_0_no_label.png
├── base10_blocks_0_6_no_label.png
└── base10_blocks_9_9_no_label.png
```

---

## Summary

| Aspect | With Labels | Label-Free |
|--------|-------------|------------|
| **Flexibility** | Low | High |
| **File size** | Larger | Smaller |
| **Standalone use** | Yes | No (needs external text) |
| **Streamlit integration** | Good | Excellent |
| **Internationalization** | Hard | Easy |
| **Dynamic prompts** | Requires regeneration | Just change text |
| **Recommended for** | PDFs, worksheets | Web apps, thought prompts |

---

**For the Flipper Lite thought prompt system, use `label=False` for maximum flexibility.**
