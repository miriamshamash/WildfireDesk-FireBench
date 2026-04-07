import csv
import json
import os
from collections import defaultdict

input_csv = "Local_News_Directory_4_2_26.csv"
output_dir = "states_output"
os.makedirs(output_dir, exist_ok=True)

# Group rows by state
state_data = defaultdict(list)

with open(input_csv, "r", encoding="utf-8", newline="") as csv_file:
    reader = csv.DictReader(csv_file)

    for row in reader:
        # Clean whitespace
        cleaned_row = {k: v.strip() if isinstance(v, str) else v for k, v in row.items()}

        state = cleaned_row.get("State", "Unknown") or "Unknown"
        state_data[state].append(cleaned_row)

# Write one JSONL file per state
for state, rows in state_data.items():
    safe_state = state.replace(" ", "_")
    output_path = os.path.join(output_dir, f"{safe_state}.jsonl")

    with open(output_path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")

print("Done! JSONL files created in:", output_dir)