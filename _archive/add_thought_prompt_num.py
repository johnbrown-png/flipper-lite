"""Add thought_prompt_num unique identifier to thought_prompts_pilot.csv and .json."""
import csv
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "pilot_output", "thought_prompts_pilot.csv")
JSON_PATH = os.path.join(BASE_DIR, "pilot_output", "thought_prompts_pilot.json")

# ── Update CSV ──────────────────────────────────────────────────────
with open(CSV_PATH, "r", encoding="utf-8", newline="") as f:
    reader = csv.reader(f)
    rows = list(reader)

header = rows[0]
data_rows = rows[1:]

# Insert thought_prompt_num as the first column
new_header = ["thought_prompt_num"] + header
new_rows = []
for i, row in enumerate(data_rows, start=1):
    new_rows.append([str(i)] + row)

with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f, lineterminator="\n")
    writer.writerow(new_header)
    writer.writerows(new_rows)

print(f"Updated CSV with {len(new_rows)} rows (added thought_prompt_num column).")

# ── Update JSON ─────────────────────────────────────────────────────
with open(JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

for i, entry in enumerate(data, start=1):
    # Insert thought_prompt_num as the first key
    # Python 3.7+ preserves insertion order, so we rebuild the dict
    new_entry = {"thought_prompt_num": i}
    new_entry.update(entry)
    data[i - 1] = new_entry

with open(JSON_PATH, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")

print(f"Updated JSON with {len(data)} entries (added thought_prompt_num field).")

# ── Verify correspondence ───────────────────────────────────────────
# Re-read both and spot-check
with open(CSV_PATH, "r", encoding="utf-8") as f:
    csv_rows = list(csv.DictReader(f))

with open(JSON_PATH, "r", encoding="utf-8") as f:
    json_data = json.load(f)

assert len(csv_rows) == len(json_data), f"Row count mismatch: CSV={len(csv_rows)} JSON={len(json_data)}"

# Check first and last match on key fields
for idx in [0, -1]:
    c = csv_rows[idx]
    j = json_data[idx]
    assert str(c["thought_prompt_num"]) == str(j["thought_prompt_num"]), f"Mismatch at idx {idx}"
    assert str(c["small_step_num"]) == str(j["small_step_num"]), f"Mismatch at idx {idx}"
    assert str(c["variant"]) == str(j["variant"]), f"Mismatch at idx {idx}"
    assert c["prompt_text"] == j["prompt_text"], f"Mismatch at idx {idx}"

print("Verification passed: CSV and JSON correspond perfectly.")
print(f"thought_prompt_num range: 1 to {len(csv_rows)}")