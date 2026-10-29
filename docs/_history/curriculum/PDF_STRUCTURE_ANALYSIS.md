## PDF STRUCTURE ANALYSIS SUMMARY

### BLOCK TYPES IDENTIFIED:

**Type 1: First Block in Year (e.g., Y1 Autumn Block 1 - Place value)**
- Total Pages: 59
- Small Steps Summary: Pages 13-14
- Number of Steps: 15
- Has lengthy introductory overview pages (1-12)

**Type 2: Subsequent Blocks (e.g., Block 2 - Addition and subtraction)**
- Total Pages: 55
- Small Steps Summary: Pages 2-4
- Number of Steps: 17
- More concise format, starts immediately

**Type 3: Short Blocks (e.g., Block 3 - Shape)**
- Total Pages: 17
- Small Steps Summary: Page 2
- Number of Steps: 5
- Compact format

---

### CONSISTENT ELEMENTS ACROSS ALL BLOCKS:

✅ **Small Steps Summary**
- Always has heading "Small steps"
- Format: "Step 1 [Description]", "Step 2 [Description]", etc.
- Location: Either pages 2-4 OR pages 13-14

✅ **Individual Step Details**
- Always has "Notes and guidance" section
- First paragraph after this heading = step description
- Consistent across all blocks

✅ **Filename Pattern**
- Format: "Y[Year] [Term] Block [N] SOL [Topic].pdf"
- Example: "Y1 Autumn Block 1 SOL Place value within 10.pdf"

---

### EXTRACTION STRATEGY:

1. **Parse Filename:**
   - Year: Y1 → Year 1
   - Term: Autumn, Spring, Summer
   - Block Number: 1, 2, 3, etc.
   - Sub_topic: "Place value within 10", "Addition and subtraction within 10", "Shape"

2. **Find Small Steps Summary Page:**
   - Search all pages for "Small steps" heading
   - Extract all lines starting with "Step [N] "
   - Count determines dynamic column creation

3. **Extract Topic:**
   - From page headers: "Year 1 | Autumn term | Block 1 – [Place value]"

4. **Extract Step Descriptions:**
   - Find each page with "Notes and guidance"
   - Extract first paragraph (the description)
   - Match to corresponding step number

5. **Generate Dynamic CSV:**
   - Columns: year, term, topic, sub_topic
   - Then: small_step_1, small_step_2, ..., small_step_N (N varies per PDF)
   - Then: SS1_desc, SS2_desc, ..., SSN_desc

---

### EXAMPLE OUTPUT STRUCTURE:

For Block 1 (15 steps):
year,term,topic,sub_topic,small_step_1,small_step_2,...,small_step_15,SS1_desc,SS2_desc,...,SS15_desc

For Block 2 (17 steps):
year,term,topic,sub_topic,small_step_1,small_step_2,...,small_step_17,SS1_desc,SS2_desc,...,SS17_desc

For Block 3 (5 steps):
year,term,topic,sub_topic,small_step_1,small_step_2,...,small_step_5,SS1_desc,SS2_desc,...,SS5_desc

---

### CONFIDENCE LEVEL: 95%

**Strengths:**
- All PDFs are text-based (not scanned images)
- Consistent "Small steps" and "Notes and guidance" markers
- Predictable structure within each PDF
- Variable step counts handled by dynamic column generation

**Minor Challenges:**
- Need to search for "Small steps" page (varies between blocks)
- Text extraction may have line breaks mid-paragraph (need to concatenate)
- First paragraph extraction requires identifying next heading

**Recommended Approach:**
1. Build prototype for these 3 PDFs
2. Test on remaining PDFs in folder
3. Add error handling for edge cases
