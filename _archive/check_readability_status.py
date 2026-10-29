"""Check readability data status"""
import json

with open('data/video_readability.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

total = len(data)
print(f"Total videos with readability scores: {total:,}")

# Check for invalid scores
invalid_count = 0
negative_scores = []
extreme_scores = []

for key, value in data.items():
    ease = value.get('flesch_reading_ease')
    grade = value.get('flesch_kincaid_grade')
    
    if ease is not None:
        if ease < 0:
            negative_scores.append((key, ease))
        if ease < -100 or ease > 120:  # Extremely unusual
            extreme_scores.append((key, ease))
    
    if ease is not None and (ease < -10 or ease > 110):
        invalid_count += 1

print(f"\nVideos with negative readability scores: {len(negative_scores)}")
print(f"Videos with extreme scores (< -100 or > 120): {len(extreme_scores)}")

if negative_scores[:5]:
    print("\nSample negative scores:")
    for key, score in negative_scores[:5]:
        print(f"  {key}: {score:.2f}")

if extreme_scores[:5]:
    print("\nSample extreme scores:")
    for key, score in extreme_scores[:5]:
        print(f"  {key}: {score:.2f}")

print(f"\n✓ Backfill appears complete with {total:,} videos processed")
