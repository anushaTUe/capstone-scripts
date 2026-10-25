"""Keep only function and method entries in SciTools Understand metrics_before.csv.

Run in Windows CMD:
    py filter_only_functions_methods.py

The CSV must be in the same folder as this script. All source paths are kept,
including node_modules, tests, and generated files; only Kind is filtered.
"""
import csv
from pathlib import Path

source = Path(__file__).with_name('metrics_before.csv')
output = Path(__file__).with_name('metrics_before_functions_methods_only.csv')

with source.open('r', encoding='utf-8-sig', newline='') as inp, \
     output.open('w', encoding='utf-8-sig', newline='') as out:
    reader = csv.DictReader(inp)
    if not reader.fieldnames or 'Kind' not in reader.fieldnames:
        raise ValueError("CSV must contain a 'Kind' column")
    writer = csv.DictWriter(out, fieldnames=reader.fieldnames)
    writer.writeheader()
    n = 0
    for row in reader:
        kind = row['Kind'].strip().lower()
        if 'function' in kind or 'method' in kind:
            writer.writerow(row)
            n += 1

print(f'Saved {n:,} function and method records to {output.name}')