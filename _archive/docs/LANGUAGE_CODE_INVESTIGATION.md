## Investigation: Language Code Issue in caption_extractor.py

### Investigation Date: 2026-02-13

### Issue Hypothesis
User suspected that caption_extractor.py might be missing videos because it only requests language='en', when some English videos might have captions coded as:
- 'en-US' (US English)
- 'en-GB' (British English)  
- 'a.en' (auto-generated English)

### Example Video Tested
https://www.youtube.com/watch?v=SfxULALs_u8

### Test Results

**Test 1: Example Video (SfxULALs_u8)**
- ✓ Requesting `['en']` alone: SUCCESS (50 segments)
- ✓ Requesting `['en', 'en-US', 'en-GB', 'a.en']`: SUCCESS (50 segments)
- **Conclusion**: This video works with just 'en'

**Test 2: Additional Videos**
- Khan Academy videos: All work with `['en']`
- Numberblocks (UK): Works with `['en']`
- **Conclusion**: All tested videos work with just 'en'

**Test 3: Individual Language Codes**
- `['en']`: ✓ SUCCESS
- `['en-GB']`: ✗ NoTranscriptFound
- `['en-US']`: ✗ NoTranscriptFound
- **Conclusion**: The tested videos only have 'en' transcripts, not regional variants

### API Documentation Findings

From `YouTubeTranscriptApi.fetch()` documentation:
```
languages: A list of language codes in a descending priority. For    
    example, if this is set to ["de", "en"] it will first try to fetch the  
    german transcript (de) and then fetch the english transcript (en) if    
    it fails to do so. This defaults to ["en"].
```

**Key Points:**
1. The `languages` parameter acts as a **fallback chain**
2. The API tries each language in order until it finds a match
3. If 'en' doesn't exist but 'en-GB' does, requesting only 'en' **might not match**
4. The API tests individual language codes, NOT hierarchical matching

### Current Code (caption_extractor.py, line 408)
```python
caption_data = api.fetch(video_id, ['en'])
```

### Findings Summary

**Good News:**
- All tested videos work fine with just `['en']`
- The example video SfxULALs_u8 does NOT demonstrate the issue

**Potential Edge Cases:**
1. **Regional-only captions**: Some videos might have ONLY 'en-GB' or 'en-US' but not 'en'
   - Example: BBC videos might have manual 'en-GB' captions only
   - Rare but possible, especially for region-specific content
   
2. **Auto-generated variants**: Some videos might code auto-captions as 'a.en'
   - Not observed in testing but theoretically possible
   
3. **Manual vs Auto**: Videos might have manual 'en-GB' and auto-generated 'en'
   - Current code might miss the manual version

### Risk Assessment

**Low to Medium Risk:**
- Most videos use 'en' as the standard language code
- The tested videos all work correctly
- However, edge cases likely exist with regional content

**Cost of Fix:**
- Zero performance impact (API supports multiple language codes)
- Makes the extractor more robust
- No downside to implementing

### Recommendation

**IMPLEMENT THIS SAFETY NET:**

Change in `caption_extractor.py` at line 408:
```python
# OLD:
caption_data = api.fetch(video_id, ['en'])

# NEW (recommended):
caption_data = api.fetch(video_id, ['en', 'en-US', 'en-GB', 'a.en', 'en-CA', 'en-AU'])
```

**Rationale:**
1. **Safety net**: Catches edge cases with regional-only captions
2. **Zero cost**: No performance or API quota impact
3. **Better coverage**: Handles more caption variants
4. **Fallback chain**: Tries 'en' first, then falls back to variants
5. **Future-proof**: Handles YouTube's caption coding changes

### Conclusion

**The issue is REAL but RARE:**
- The example video works fine with current code
- However, edge cases likely exist (especially BBC, regional content)
- The fix is trivial and has no downside
- **Recommendation: Implement the fix as a safety measure**

### Implementation Status
**NOT IMPLEMENTED** (per user request to investigate only)
