import csv
import re
from pathlib import Path

files = ["openPRs", "unmergedPRs", "mergedPRs", "openIssues", "closedIssues"]
data_dir = Path(__file__).resolve().parent / "txt data files"

for filename in files:
    txt_file_path = data_dir / (filename + ".txt")
    csv_file_path = data_dir / (filename + ".csv")
    rows = []

    with txt_file_path.open("r", encoding="utf-8") as txt_file:
        for line in txt_file:

            if line.startswith(" |"):
                line = "Title: " + line
            parts = re.split(r"\s*\|\s*(?=(?:Authors|Contributors|Created at|Closed at|Merged at|Status|Additions|Deletions|Files Changed|Reason):\s)", line.strip())

            try:
                row = dict(part.split(":", 1) for part in parts)
                rows.append(row)
            except ValueError:
                print("Problem in file:", filename)
                print("Problematic line:", repr(line))
                print("Split result:", parts)
                raise

    if not rows:
        continue

    with csv_file_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(csv_file_path.name + " created")
