#!/usr/bin/env python3
"""Remove likely bot activity from commit, issue, and pull-request CSV exports.

The script uses observable evidence only. It writes filtered copies and a report
showing why each author was classified as a likely bot.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


DEFAULT_FILES = (
	Path("commit-log.csv"),
	Path("issues and prs/closedIssues.csv"),
	Path("issues and prs/closedPRs.csv"),
	Path("issues and prs/openIssues.csv"),
	Path("issues and prs/openPRs.csv"),
)
AUTHOR_COLUMN = "Author"
ISSUE_PR_AUTHOR_COLUMN = "Authors"
TITLE_COLUMNS = ("Subject", "Title")
DATE_COLUMNS = ("Date", "Created at")
BOT_NAME_RE = re.compile(
	r"(?:\[bot\]|\bbot\b|\bdependabot(?:-preview)?\b|\brenovate\b|"
	r"\bgithub-actions\b|\bsemantic-release\b|\brelease-bot\b)",
	re.IGNORECASE,
)
BOT_TITLE_RE = re.compile(
	r"(?:^chore\((?:deps?|release|translations?|ci)[^)]*\):|"
	r"\bbump\s+.+\s+from\s+\S+\s+to\s+\S+|"
	r"\bupdate translations? from crowdin\b)",
	re.IGNORECASE,
)
ISSUE_NUMBER_RE = re.compile(r"\s*\(#\d+\)|\s*#\d+", re.IGNORECASE)
VERSION_RE = re.compile(r"\b\d+(?:\.\d+)+(?:-[0-9a-z.-]+)?\b", re.IGNORECASE)
REPEATED_TITLE_THRESHOLD = 3


def parse_date(value: str) -> datetime:
	parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
	return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def author_column(fieldnames: Sequence[str]) -> str:
	for column in (AUTHOR_COLUMN, ISSUE_PR_AUTHOR_COLUMN):
		if column in fieldnames:
			return column
	raise ValueError("CSV must contain an Author or Authors column")


def title_column(fieldnames: Sequence[str]) -> str:
	for column in TITLE_COLUMNS:
		if column in fieldnames:
			return column
	raise ValueError("CSV must contain a Subject or Title column")


def date_column(fieldnames: Sequence[str]) -> str:
	for column in DATE_COLUMNS:
		if column in fieldnames:
			return column
	raise ValueError("CSV must contain a Date or Created at column")


def normalise_title(title: str) -> str:
	title = ISSUE_NUMBER_RE.sub("", title.lower())
	title = VERSION_RE.sub("<version>", title)
	return re.sub(r"\s+", " ", title).strip()


def load_rows(paths: list[Path]) -> tuple[dict[Path, list[dict[str, str]]], dict[str, list[dict]]]:
	files: dict[Path, list[dict[str, str]]] = {}
	by_author: dict[str, list[dict]] = defaultdict(list)
	for path in paths:
		with path.open(newline="", encoding="utf-8-sig") as handle:
			reader = csv.DictReader(handle)
			fieldnames = reader.fieldnames or []
			author_key = author_column(fieldnames)
			title_key = title_column(fieldnames)
			date_key = date_column(fieldnames)
			rows = list(reader)
			files[path] = rows
			for row in rows:
				author = (row.get(author_key) or "").strip()
				if author in {"", "Unknown", "null"}:
					continue
				by_author[author].append({
					"title": (row.get(title_key) or "").strip(),
					"date": parse_date(row[date_key]),
				})
	return files, by_author


def bot_evidence(by_author: dict[str, list[dict]]) -> dict[str, dict]:
	evidence = {}
	for author, records in by_author.items():
		titles = [record["title"] for record in records]
		normalised_titles = [normalise_title(title) for title in titles]
		routine_titles = sum(bool(BOT_TITLE_RE.search(title)) for title in titles)
		routine_ratio = routine_titles / len(records)
		repeated_title_count = max(Counter(normalised_titles).values(), default=0)
		dates = sorted(record["date"] for record in records)
		intervals = [(later - earlier).total_seconds() for earlier, later in zip(dates, dates[1:])]
		regular_timing = False
		if len(intervals) >= 3:
			mean = sum(intervals) / len(intervals)
			variance = sum((interval - mean) ** 2 for interval in intervals) / len(intervals)
			regular_timing = mean > 0 and variance**0.5 / mean < 0.05

		signals = []
		name_signal = bool(BOT_NAME_RE.search(author))
		if name_signal:
			signals.append("author name contains an explicit bot/service marker")
		if routine_ratio >= 0.75 and routine_titles >= 3:
			signals.append(f"{routine_ratio:.0%} of titles match dependency/release automation patterns")
		if repeated_title_count >= REPEATED_TITLE_THRESHOLD:
			signals.append(f"the same normalised title appears {repeated_title_count} times")
		if regular_timing:
			signals.append("activity timing is unusually regular")

		# A name marker is strong evidence; other signals must agree twice.
		score = int(name_signal) + int(routine_ratio >= 0.75 and routine_titles >= 3)
		score += int(repeated_title_count >= REPEATED_TITLE_THRESHOLD) + int(regular_timing)
		if score >= 2:
			evidence[author] = {
				"score": score,
				"records": len(records),
				"signals": signals,
			}
	return evidence


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	fieldnames = list(rows[0]) if rows else []
	with path.open("w", newline="", encoding="utf-8") as handle:
		writer = csv.DictWriter(handle, fieldnames=fieldnames)
		if fieldnames:
			writer.writeheader()
			writer.writerows(rows)


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--output-dir", type=Path, default=Path("filtered data"))
	parser.add_argument("files", nargs="*", type=Path, default=list(DEFAULT_FILES))
	args = parser.parse_args()
	paths = args.files or list(DEFAULT_FILES)
	files, by_author = load_rows(paths)
	evidence = bot_evidence(by_author)
	bot_authors = set(evidence)

	for path, rows in files.items():
		filtered = [row for row in rows if (row.get(AUTHOR_COLUMN) or row.get(ISSUE_PR_AUTHOR_COLUMN) or "").strip() not in bot_authors]
		write_csv(args.output_dir / path.name, filtered)

	report_path = args.output_dir / "bot-report.csv"
	report_rows = [
		{"Author": author, "Score": details["score"], "Records": details["records"], "Evidence": "; ".join(details["signals"])}
		for author, details in sorted(evidence.items(), key=lambda item: (-item[1]["score"], item[0].lower()))
	]
	write_csv(report_path, report_rows)

	print(f"Identified {len(bot_authors)} likely bot authors.")
	for author, details in sorted(evidence.items(), key=lambda item: (-item[1]["score"], item[0].lower())):
		print(f"- {author} ({details['score']}/4): {'; '.join(details['signals'])}")
	print(f"Filtered files written to: {args.output_dir}")


if __name__ == "__main__":
	main()