
import csv
import re

files = ["openPRs", "closedPRs", "openIssues", "closedIssues"]

for filename in files:
    txtFile = open(filename + ".txt", "r", encoding="utf-8")
    rows = []

    
    for line in txtFile:

        if line.startswith(" |"):
            line = "Title: " + line
        parts = re.split(r"\s*\|\s*(?=(?:Authors|Created at|Closed at|Additions|Deletions|Files Changed):\s)", line.strip())

        try:
            row = {}
            for part in parts:
                key, value = part.split(":", 1)
                row[key.strip()] = value.strip()
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
    writer = csv.DictWriter(csvFile, fieldnames=rows[0].keys(), quoting=csv.QUOTE_ALL)
    writer.writeheader()
    writer.writerows(rows)
    csvFile.close()

    print(filename + ".csv created")
