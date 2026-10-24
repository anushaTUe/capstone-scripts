# Bot Filtering Report

This report documents the bot activity removed by `filter-bots.py` from the
commit log and the five CSV exports in `richer data`.

The filtered copies are in [`filtered richer data`](./filtered%20richer%20data).
The machine-readable source report is
[`bot-report.csv`](./filtered%20richer%20data/bot-report.csv).

## Run details

- **Run date:** 2026-10-22
- **Input data:** `commit-log.csv` and all five files in `richer data`
- **Output data:** `filtered richer data`
- **Bot author strings identified:** 6
- **Underlying accounts represented:** 3

## Filtering criteria

An author was classified as a likely bot when at least two independent
signals were present:

1. The author name contains an explicit bot or service marker such as
   `[bot]`, `bot`, or `dependabot`.
2. At least 75% of the author's titles, with at least three matching titles,
   match dependency, release, translation, or CI automation patterns.
3. The same normalized title appears at least three times. Normalization
   removes issue numbers and version numbers.
4. Activity timing is unusually regular.

Rows were removed when any author or contributor listed in the row matched one
of the identified bot author strings. The six author strings and their
evidence are listed below.

## Bots filtered

### `dependabot-preview[bot]`

- **Account:** [dependabot-preview[bot]](https://github.com/dependabot-preview%5Bbot%5D)
- **Evidence score:** 3/4
- **Records considered:** 232
- **Reasons for filtering:**
  - The author name contains an explicit bot/service marker.
  - 100% of titles match dependency/release automation patterns.
  - The same normalized title appears 24 times.

### `dependabot[bot]`

- **Account:** [dependabot[bot]](https://github.com/dependabot%5Bbot%5D)
- **Evidence score:** 3/4
- **Records considered:** 605
- **Reasons for filtering:**
  - The author name contains an explicit bot/service marker.
  - 100% of titles match dependency/release automation patterns.
  - The same normalized title appears 25 times.

### `Excalidraw Bot`

- **Account:** [excalibot](https://github.com/excalibot)
- **Evidence score:** 3/4
- **Records considered:** 70
- **Reasons for filtering:**
  - The author name contains an explicit bot/service marker.
  - 97% of titles match dependency/release automation patterns.
  - The same normalized title appears 64 times.

### `dependabot-preview[bot] (dependabot-preview[bot])`

- **Account:** [dependabot-preview[bot]](https://github.com/dependabot-preview%5Bbot%5D)
- **Evidence score:** 2/4
- **Records considered:** 262
- **Reasons for filtering:**
  - The author name contains an explicit bot/service marker.
  - The same normalized title appears 232 times.

This is a contributor-format variant of `dependabot-preview[bot]` in the
richer data exports.

### `dependabot[bot] (dependabot[bot])`

- **Account:** [dependabot[bot]](https://github.com/dependabot%5Bbot%5D)
- **Evidence score:** 2/4
- **Records considered:** 1,059
- **Reasons for filtering:**
  - The author name contains an explicit bot/service marker.
  - The same normalized title appears 606 times.

This is a contributor-format variant of `dependabot[bot]` in the richer data
exports.

### `excalibot (Excalidraw Bot)`

- **Account:** [excalibot](https://github.com/excalibot)
- **Evidence score:** 2/4
- **Records considered:** 76
- **Reasons for filtering:**
  - The author name contains an explicit bot/service marker.
  - The same normalized title appears 70 times.

This is a contributor-format variant of `Excalidraw Bot` in the richer data
exports.

## Account summary

The six filtered author strings map to these three accounts:

| Account | Filtered author strings |
| --- | --- |
| [dependabot[bot]](https://github.com/dependabot%5Bbot%5D) | `dependabot[bot]`; `dependabot[bot] (dependabot[bot])` |
| [dependabot-preview[bot]](https://github.com/dependabot-preview%5Bbot%5D) | `dependabot-preview[bot]`; `dependabot-preview[bot] (dependabot-preview[bot])` |
| [excalibot](https://github.com/excalibot) | `Excalidraw Bot`; `excalibot (Excalidraw Bot)` |

The report describes *likely* bots based on observable data signals; it does
not claim that every automated-looking activity has been removed unless its
author matched the criteria above.
