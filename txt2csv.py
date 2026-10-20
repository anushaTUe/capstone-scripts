import csv
import re

files = ["openPRs", "unmergedPRs", "mergedPRs", "openIssues", "closedIssues"]

for filename in files:
    txtFile = open(filename + ".txt", "r", encoding="utf-8")
    rows = []

    
    for line in txtFile:

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


    txtFile.close()

    if not rows:
        continue

    csvFile = open(filename + ".csv", "w", newline="", encoding="utf-8-sig")
    writer = csv.DictWriter(csvFile, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    csvFile.close()

    print(filename + ".csv created")
