import pandas as pd

# Load the CSV
df = pd.read_csv('Curriculum/Maths/mat_curr_short_import - 03032026.csv')

print("Testing curriculum data...")
print(f"Total rows: {len(df)}")
print(f"\nYear groups: {df['Year'].unique()}")

# Test Year 1 (should work)
print("\n" + "="*60)
print("YEAR 1 TEST")
print("="*60)
year1 = df[df['Year'] == 'Year 1']
print(f"Year 1 rows: {len(year1)}")
row1 = year1.iloc[0]
print(f"Topic: {row1['Topic']}")
print(f"Small Step 1: {row1['Small Step 1']}")
print(f"Has SS1_desc_short: {pd.notna(row1['SS1_desc_short'])}")

# Test Year 10 (with difficulty)
print("\n" + "="*60)
print("YEAR 10 TEST")
print("="*60)
year10 = df[df['Year'] == 'Year 10']
print(f"Year 10 rows: {len(year10)}")
print(f"Difficulty values: {year10['Difficulty'].unique()}")
print(f"\nFiltering by Foundation:")
foundation = year10[year10['Difficulty'] == 'Foundation']
print(f"Foundation rows: {len(foundation)}")
if len(foundation) > 0:
    row10 = foundation.iloc[0]
    print(f"Topic: {row10['Topic']}")
    print(f"Small Step 1: {row10['Small Step 1']}")
    print(f"Has SS1_desc_short: {pd.notna(row10['SS1_desc_short'])}")

print("\n✅ All tests complete!")
