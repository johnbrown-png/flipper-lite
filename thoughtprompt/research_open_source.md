# Open-Source Visual Asset Research

Research document for comparing Python-generated visuals with open-source alternatives for thought prompt imagery.

---

## 1. Unit Cubes & Ten-Stacks (Base-10 Blocks)

### Open-Source Options to Investigate:

#### **OpenSCAD Mathematical Manipulatives**
- **Repository**: Search GitHub for "openscad base 10 blocks" or "dienes blocks openscad"
- **URL Candidates**:
  - https://www.thingiverse.com/search?q=base+10+blocks
  - https://github.com/search?q=base+10+blocks+openscad
  
- **Pros**: 
  - 3D rendered, professional appearance
  - Parametric (can adjust sizes programmatically)
  - Realistic representation of physical manipulatives
  
- **Cons**:
  - Requires OpenSCAD installation
  - Slower rendering than 2D
  - May be visually "too busy" for screen-based learning
  - Needs 2D export for web display
  
- **Setup Time**: 1-2 hours (install OpenSCAD, test rendering)
- **Modification Complexity**: Medium (need to learn OpenSCAD syntax)

#### **Wikimedia Commons**
- **Search terms**: "base 10 blocks", "Dienes blocks", "place value blocks"
- **URL**: https://commons.wikimedia.org/wiki/Category:Base_ten_blocks
  
- **Pros**:
  - Ready-made, professionally created
  - Public domain or CC-licensed
  - No generation needed
  
- **Cons**:
  - Fixed images (not parametric)
  - May need to manually create each tens/ones combination
  - Style consistency issues if using multiple sources
  - May not have all needed combinations (4 tens + 7 ones, etc.)
  
- **Licensing**: Check each image (most are CC-BY or public domain)

#### **Khan Academy Resources**
- **Repository**: https://github.com/Khan
- **Potential resources**:
  - Perseus (exercise framework): https://github.com/Khan/perseus
  - Math input widgets: May contain SVG templates
  
- **Status**: Need to investigate if they have released base-10 block SVGs
- **Licensing**: Varies - check each repository (many are MIT licensed)

#### **NRICH/Cambridge Maths Hub**
- **URL**: https://nrich.maths.org/
- **Description**: Educational resources, may have downloadable manipulative images
- **Licensing**: Typically educational use allowed, but verify

---

## 2. Part-Whole Models (Cherry/Number Bond Diagrams)

### Open-Source Options:

#### **SVG Circle Diagrams**
- **Approach**: Simple SVG templates with circles and connecting lines
- **Sources**:
  - Search GitHub: "number bonds svg", "part whole model svg"
  - Create from scratch using SVG (simpler than base-10 blocks)
  
- **Pros**: 
  - Lightweight, scalable
  - Easy to parameterize
  - Clean, minimalist appearance
  
- **Cons**:
  - May need to create from scratch if no good templates exist

#### **Python Alternative Assessment**
- Part-whole models are geometrically simple (circles + lines)
- Python PIL/SVG generation is likely SUFFICIENT
- **Recommendation**: Stick with Python unless you find exceptional SVG templates

---

## 3. Bar Models (Tape Diagrams)

### Open-Source Options:

#### **Singapore Math Bar Model Resources**
- **Search**: "Singapore math bar model template", "tape diagram svg"
- **Potential sources**:
  - Math education blogs (often share templates)
  - Teachers Pay Teachers (some free resources)
  - Wikimedia Commons
  
- **Licensing**: Varies - verify before use

#### **Educational SVG Libraries**
- **Khan Academy Perseus** may have bar model components
- **GeoGebra** materials (check https://www.geogebra.org/materials)
  
- **Pros**: 
  - Battle-tested in educational contexts
  - Professional appearance
  
- **Cons**:
  - May require attribution
  - Parameterization may be complex

#### **Python Alternative Assessment**
- Bar models are simple rectangles with proportional lengths
- Python rectangle drawing is trivial and precise
- **Recommendation**: Python PIL is likely OPTIMAL for bar models (mathematically precise proportions)

---

## 4. Number Lines

### Open-Source Options:

#### **Matplotlib (Python Standard)**
- **Status**: Already using this in Python approach
- **Assessment**: Industry standard for mathematical plotting
- **Recommendation**: No need to look for alternatives - matplotlib IS the standard

#### **D3.js/SVG Number Lines**
- **If considering web-native rendering**:
  - D3.js for interactive number lines
  - Could generate static SVGs server-side
  
- **Pros**: 
  - Highly customizable
  - Web-native
  
- **Cons**:
  - More complex setup
  - Overkill for static images

#### **Wikimedia Commons**
- **Search**: "number line", "mathematical number line"
- **Assessment**: Likely to find examples, but parameterization would be manual
- **Recommendation**: Python/matplotlib superior for automated generation

---

## Comparison Matrix

| Visual Type | Python Quality | Open-Source Alternatives | Recommendation |
|-------------|----------------|--------------------------|----------------|
| **Base-10 Blocks** | ⭐⭐⭐⭐ Good | OpenSCAD (⭐⭐⭐⭐⭐), Wikimedia (⭐⭐⭐) | **COMPARE**: Test OpenSCAD vs Python |
| **Part-Whole Models** | ⭐⭐⭐⭐⭐ Excellent | SVG templates (⭐⭐⭐⭐) | **Python SUFFICIENT** |
| **Bar Models** | ⭐⭐⭐⭐⭐ Excellent | Singapore math templates (⭐⭐⭐⭐) | **Python OPTIMAL** (precision needed) |
| **Number Lines** | ⭐⭐⭐⭐⭐ Excellent | D3.js (⭐⭐⭐⭐), Wikimedia (⭐⭐⭐) | **Python/matplotlib IS STANDARD** |

---

## Search Strategy

### Immediate Actions (30-60 minutes):

1. **Wikimedia Commons Search**:
   ```
   - Search: "base 10 blocks"
   - Filter: Public domain or CC-BY
   - Download 3-5 examples
   - Compare visual quality to Python output
   ```

2. **GitHub Search**:
   ```
   - "openscad base 10 blocks"
   - "dienes blocks 3d model"
   - "math manipulatives svg"
   - Clone promising repos and test rendering
   ```

3. **Khan Academy Investigation**:
   ```
   - Browse https://github.com/Khan repositories
   - Search for "blocks", "manipulatives", "svg"
   - Check Perseus exercise examples
   ```

4. **GeoGebra Materials**:
   ```
   - Visit https://www.geogebra.org/materials
   - Search "base 10", "place value", "bar model"
   - Check if materials are exportable/downloadable
   ```

---

## Licensing Considerations

### Safe to Use:
- ✅ Public Domain (CC0)
- ✅ CC-BY (with attribution)
- ✅ CC-BY-SA (with attribution, same license)
- ✅ MIT License
- ✅ Own creations (Python-generated)

### Check Carefully:
- ⚠️ CC-BY-NC (non-commercial only)
- ⚠️ CC-BY-ND (no derivatives)
- ⚠️ GPL (copyleft requirements)

### Avoid:
- ❌ All rights reserved
- ❌ Unclear licensing
- ❌ "Educational use" without explicit license

---

## Evaluation Criteria for Selected Visuals

When comparing Python vs open-source options, evaluate on:

### 1. **Age-Appropriateness** (7-9 year olds)
- [ ] Clean, uncluttered design
- [ ] Large, readable numbers
- [ ] Friendly colors (not harsh)
- [ ] Intuitive visual logic

### 2. **Mathematical Accuracy**
- [ ] Correct proportions (bar models, number lines)
- [ ] Exact counts (4 tens = exactly 4 rectangles)
- [ ] Clear place value representation

### 3. **Parameterizability**
- [ ] Can generate any number combination?
- [ ] Easy to modify (e.g., 47 → 82)?
- [ ] Batch generation feasible?

### 4. **Technical Feasibility**
- [ ] Setup time < 2 hours?
- [ ] Rendering time < 1 second per image?
- [ ] Integration with Python pipeline straightforward?

### 5. **Visual Appeal**
- [ ] Would engage 7-9 year olds?
- [ ] Professional appearance?
- [ ] Consistent style across all types?

---

## Next Steps After Research

1. **Generate Python examples** (run `test_visuals.py`)
2. **Conduct 30-60 min open-source asset hunt**
3. **Create side-by-side comparison images**
4. **Make decision per visual type**:
   - Base-10 blocks: Python vs OpenSCAD vs Wikimedia
   - Part-whole: Python (likely sufficient)
   - Bar models: Python (optimal for precision)
   - Number lines: Python/matplotlib (standard)
5. **Document decision in `visual_selection.md`**
6. **Proceed to prompt generation phase**

---

## Resources & Links

### GitHub Searches:
- https://github.com/search?q=base+10+blocks
- https://github.com/search?q=dienes+blocks
- https://github.com/search?q=math+manipulatives+svg

### Asset Repositories:
- Thingiverse: https://www.thingiverse.com/search?q=base+10+blocks
- Wikimedia Commons: https://commons.wikimedia.org/
- GeoGebra: https://www.geogebra.org/materials

### Educational Resources:
- Khan Academy GitHub: https://github.com/Khan
- NRICH: https://nrich.maths.org/
- OpenStax: https://openstax.org/ (textbooks with diagrams)

---

## Research Log

### Date: 2026-07-21
**Researcher**: [Your name]

#### Findings:
- [ ] Wikimedia Commons search completed
- [ ] GitHub OpenSCAD repos investigated
- [ ] Khan Academy materials reviewed
- [ ] GeoGebra resources checked

#### Initial Assessment:
*[Record your findings after conducting searches]*

#### Decision:
*[Document which approach selected for each visual type]*

---

**Last Updated**: 2026-07-21
