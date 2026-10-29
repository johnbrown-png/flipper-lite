"""Check for contradictory readability scores"""
import json

with open('data/video_readability.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Find videos with high ease (>80) but high grade (>10)
problematic = []
for key, value in data.items():
    ease = value.get('flesch_reading_ease')
    grade = value.get('flesch_kincaid_grade')
    
    # Skip if scores are missing
    if ease is None or grade is None:
        continue
    
    # High ease should mean LOW grade (easy = young)
    # If ease > 80 (very easy) but grade > 10 (college), that's wrong
    if ease > 80 and grade > 10:
        problematic.append((key, ease, grade, value.get('word_count', 0)))

print(f"Videos with HIGH ease (>80) but HIGH grade (>10): {len(problematic)}")
print("(This would indicate an error)\n")

if problematic:
    print("Examples:")
    for key, ease, grade, words in problematic[:10]:
        print(f"  {key[:70]}")
        print(f"    Ease: {ease:.2f} | Grade: {grade:.2f} | Words: {words}")
        print()
else:
    print("✓ No contradictory scores found!")

# Show correlation
all_scores = [(v['flesch_reading_ease'], v['flesch_kincaid_grade']) 
              for v in data.values() 
              if v.get('flesch_reading_ease') is not None]

# Calculate correlation
import statistics
if len(all_scores) > 10:
    ease_vals = [e for e, g in all_scores]
    grade_vals = [g for e, g in all_scores]
    
    ease_mean = statistics.mean(ease_vals)
    grade_mean = statistics.mean(grade_vals)
    
    # Covariance
    cov = sum((e - ease_mean) * (g - grade_mean) for e, g in all_scores) / len(all_scores)
    
    # Standard deviations
    ease_std = statistics.stdev(ease_vals)
    grade_std = statistics.stdev(grade_vals)
    
    # Correlation coefficient
    correlation = cov / (ease_std * grade_std)
    
    print("\n" + "="*80)
    print("CORRELATION ANALYSIS")
    print("="*80)
    print(f"Correlation coefficient: {correlation:.4f}")
    print(f"Expected: Negative correlation (higher ease = lower grade)")
    if correlation < -0.5:
        print("✓ Strong negative correlation - scores are correct!")
    elif correlation < 0:
        print("✓ Negative correlation - scores are correct!")
    else:
        print("⚠️  Positive correlation - scores may be inverted!")
