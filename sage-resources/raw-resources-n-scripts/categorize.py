###
### This script is use to turn the HTML data of the Healthy Democracy webpage into easily parseable JSONL files
###
import re
from collections import defaultdict
import os
import json
import html

input_file = "Healthy-Democracy-Sample-Links.html"
output_dir = "states_output"
os.makedirs(output_dir, exist_ok=True)

state_data = defaultdict(list)

# Regex updated to capture data-key (URL)
pattern = re.compile(
    r'data-key="(.*?)".*?'                         # URL
    r'data-lng="(.*?)"\s+data-lat="(.*?)".*?'      # lng, lat
    r'<div class="org-title">(.*?)</div>.*?'       # name
    r'<div class="org-meta">(.*?),\s*(.*?)</div>'  # location, state
    r'(?:.*?<div class="org-meta"><strong>Category:</strong>\s*(.*?)</div>)?',  # category (optional)
    re.IGNORECASE
)

with open(input_file, "r", encoding="utf-8") as f:
    for line in f:
        match = pattern.search(line)
        if match:
            url = html.unescape(match.group(1).strip())
            lng = float(match.group(2))
            lat = float(match.group(3))
            org_name = html.unescape(match.group(4).strip())
            location = html.unescape(match.group(5).strip())
            state = html.unescape(match.group(6).strip())

            category = match.group(7)
            if not category:
                continue  # skip entries without category

            category = html.unescape(category.strip())

            entry = {
                "name": org_name,
                "location": location,
                "state": state,
                "category": category,
                "url": url,
                "latitude": lat,
                "longitude": lng
            }

            state_data[state].append(entry)

# Write JSONL files
for state, entries in state_data.items():
    safe_state = state.replace(" ", "_")
    output_path = os.path.join(output_dir, f"{safe_state}.jsonl")

    with open(output_path, "w", encoding="utf-8") as out_file:
        for entry in entries:
            out_file.write(json.dumps(entry) + "\n")

print("Done! JSONL files with URLs created in:", output_dir)