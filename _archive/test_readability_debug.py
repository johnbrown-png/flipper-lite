"""Debug readability calculation for specific video"""
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent))

from data_pipeline.readability_calculator import ReadabilityCalculator

# Test the problematic video
bad_video = r"data\captions_output\The_Eagle's_Nest_-_Our_Online_Classroom\Grade 2 Math Lesson 82 Identifying and Writing Addition and Subtraction Fact Families_Dj_t4PPo2T8.json"

calc = ReadabilityCalculator()

# Load caption file
with open(bad_video, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Extract text without punctuation
text_no_punct = calc._extract_transcript_text(data)
print("Text without punctuation (first 200 chars):")
print(text_no_punct[:200])
print(f"\nLength: {len(text_no_punct)} chars")

# Extract text with punctuation
text_with_punct = calc._add_sentence_boundaries(text_no_punct, data)
print("\n" + "="*80)
print("Text with punctuation (first 500 chars):")
print(text_with_punct[:500])
print(f"\nLength: {len(text_with_punct)} chars")

# Count sentences
import re
sentences = [s.strip() for s in text_with_punct.split('.') if s.strip()]
print(f"\nSentences detected: {len(sentences)}")
print("\nFirst 3 sentences:")
for i, sent in enumerate(sentences[:3]):
    print(f"  {i+1}. {sent}")

# Calculate scores
try:
    import textstat
    flesch_ease = textstat.flesch_reading_ease(text_with_punct)
    flesch_grade = textstat.flesch_kincaid_grade(text_with_punct)
    word_count = textstat.lexicon_count(text_with_punct, removepunct=True)
    sentence_count = textstat.sentence_count(text_with_punct)
    
    print("\n" + "="*80)
    print("TEXTSTAT ANALYSIS:")
    print(f"  Word count: {word_count}")
    print(f"  Sentence count: {sentence_count}")
    print(f"  Flesch Reading Ease: {flesch_ease:.2f}")
    print(f"  Flesch-Kincaid Grade: {flesch_grade:.2f}")
    
    if sentence_count == 0:
        print("\n⚠️  WARNING: Zero sentences detected!")
    
except Exception as e:
    print(f"\n❌ Error during calculation: {e}")
