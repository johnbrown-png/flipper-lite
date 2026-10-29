# Curriculum Assistant User Guide

## Overview
The Curriculum Assistant feature helps you search for educational videos aligned with the White Rose Maths curriculum (Years 3-10).

## How to Use

### 1. **Open the Curriculum Assistant**
   - In the Streamlit search interface, look for the expandable section: **"📚 Curriculum Assistant - White Rose Maths"**
   - Click to expand it

### 2. **Navigate Using Cascading Filters**

The filters work in a hierarchy:

```
Year Group → Term → Topic → Select Statement Type
```

**Example workflow:**
1. **Year Group**: Select "Year 3 (age 7–8)"
2. **Term**: Select "Spring (Term 2)"
3. **Topic**: Select "Fractions A"
4. **View Both Statement Types**: 
   - **📋 Statutory NC Statement** - Official National Curriculum requirements
   - **🎯 Operational Learning Objective** - Detailed teaching objectives
5. **Choose Which to Insert**: Click Insert or Append for the statement you want

### 3. **View Your Selection**

After selecting Year, Term, and Topic, you'll see **BOTH** statement types displayed:

**Statutory NC Statement:**
```
Recognise unit fractions; find fractions of quantities
```

**Operational Learning Objective:**
```
Represent fractions visually; locate on number lines
```

Each has its own Insert and Append buttons.

### 4. **Insert or Append to Search**

Four action buttons are available (two for each statement type):

**✏️ Insert Statutory NC / Insert Operational**
- Replaces the entire search box with the selected statement
- Use this when starting a new search

**➕ Append Statutory NC / Append Operational**
- Adds the statement to existing search query (with a semicolon separator)
- Use this to combine multiple curriculum objectives

### 5. **Edit the Text (Important!)**

After inserting:
- The text appears in the search box
- **You can freely edit it!**
- Useful for searching only part of an objective
- Example: Change "Recognise unit fractions; find fractions of quantities" to just "unit fractions"

### 6. **Perform the Search**

Click the **🔍 Search** button to run a semantic search across all video transcripts.

## Example Use Cases

### Use Case 1: Find Videos for a Specific Topic
```
1. Select: Year 4 → Spring → Multiplication & Division
2. View both statement types displayed
3. Click: Insert Statutory NC (or Insert Operational)
4. Edit if needed
5. Click: Search
```

### Use Case 2: Combine Multiple Objectives
```
1. Select first topic → Insert Statutory NC
2. Select second topic → Append Operational
3. Edit the combined text as needed
4. Click: Search
```

### Use Case 3: Compare Statement Types
```
1. Select: Year 5 → Autumn → Place Value
2. Read both the Statutory NC and Operational versions
3. Choose which one better matches your teaching goal
4. Click the Insert button for your preferred version
5. Click: Search
```

## Tips

✅ **Edit freely** - The search box is fully editable after insertion  
✅ **Combine objectives** - Use Append to search multiple topics  
✅ **Preview first** - Check the preview before inserting  
✅ **Clear button** - Use 🗑️ Clear to start fresh  

## Troubleshooting

**Q: I don't see the Curriculum Assistant**
- Check that the CSV file exists at: `Curriculum/Maths/Maths Curriculum Sequence - Year3to10WhiteRose.csv`

**Q: The filters aren't showing options**
- The filters cascade: select Year first, then Term, then Topic
- Each filter depends on the previous selection

**Q: Can I type directly without using filters?**
- Yes! The search box works independently
- You can type any query without using the assistant

## Technical Details

- **Data Source**: White Rose Maths Curriculum (Years 3-10)
- **Scope**: UK National Curriculum aligned mathematics topics
- **Coverage**: Autumn, Spring, and Summer terms for each year group
- **Search Type**: Semantic search (finds videos by meaning, not exact words)
