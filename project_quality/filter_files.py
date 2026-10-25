import csv
from pathlib import Path

SOURCE = Path(__file__).with_name('metrics_before.csv')
OUTPUT = Path(__file__).with_name('metrics_before_files_only.csv')

if not SOURCE.exists():
    raise SystemExit(f'Input file not found: {SOURCE}')

with SOURCE.open('r', encoding='utf-8-sig', newline='') as source, \
        OUTPUT.open('w', encoding='utf-8-sig', newline='') as target:
    reader = csv.DictReader(source)
    if not reader.fieldnames or 'Kind' not in reader.fieldnames:
        raise SystemExit('The input CSV does not contain a Kind column.')
    writer = csv.DictWriter(target, fieldnames=reader.fieldnames)
    writer.writeheader()
    retained = 0
    total = 0
    for record in reader:
        total += 1
        if record['Kind'].strip() == 'File':
            writer.writerow(record)
            retained += 1

print(f'Original records: {total:,}')
print(f'File records kept: {retained:,}')
print(f'Output: {OUTPUT}')
