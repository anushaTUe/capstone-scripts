#!/usr/bin/env python3
"""Classify GitHub accounts with multiple identity representations.

The script uses filtered CSV exports because they retain both the GitHub login
and the display name. Display-name differences alone do not prove that an
account was shared by multiple people.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_FILES = (
    Path("filtered richer data/commit-log.csv"),
    Path("filtered richer data/closedIssues.csv"),
    Path("filtered richer data/mergedPRs.csv"),
    Path("filtered richer data/openIssues.csv"),
    Path("filtered richer data/openPRs.csv"),
    Path("filtered richer data/unmergedPRs.csv"),
)
FIELD_RE = re.compile(
    r"\s*\|\s*(?=(?:Author|Contributors|Created at|Closed at|Merged at|"
    r"Status|Additions|Deletions|Files Changed|Reason):\s)"
)
IDENTITY_RE = re.compile(r"^\s*(?P<login>[^()]+?)\s*\((?P<name>[^()]*)\)\s*$")
UNKNOWN_VALUES = {"", "unknown", "null", "nan"}
SERVICE_RE = re.compile(
    r"(?:\bbot\b|\[bot\]|\bdependabot\b|\brenovate\b|\bgithub[- ]actions\b|"
    r"\bsemantic[- ]release\b|\bclaude\b|\bexcalidraw bot\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Observation:
    login: str
    name: str
    date: datetime
    source: str
    title: str


def parse_date(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def parse_identity(value: str) -> tuple[str, str] | None:
    value = value.strip()
    match = IDENTITY_RE.match(value)
    if match:
        login = match.group("login").strip()
        name = match.group("name").strip() or "Unknown"
    else:
        login, name = value, "Unknown"
    if login.lower() in UNKNOWN_VALUES:
        return None
    return login, name


def normalise_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.casefold())


def likely_alias(first: str, second: str) -> bool:
    first_normalised = normalise_name(first)
    second_normalised = normalise_name(second)
    if not first_normalised or not second_normalised:
        return True
    if first_normalised in second_normalised or second_normalised in first_normalised:
        return True
    return difflib.SequenceMatcher(None, first_normalised, second_normalised).ratio() >= 0.72


def parse_line(line: str, source: str) -> list[Observation]:
    parts = FIELD_RE.split(line.strip())
    fields: dict[str, str] = {}
    for part in parts:
        key, separator, value = part.partition(":")
        if separator:
            fields[key.strip()] = value.strip()

    date_value = fields.get("Created at")
    if not date_value:
        return []
    date = parse_date(date_value)
    identities = [fields.get("Author", "")]
    identities.extend(fields.get("Contributors", "").split(","))
    observations = []
    for identity in identities:
        parsed = parse_identity(identity)
        if parsed:
            login, name = parsed
            observations.append(
                Observation(login, name, date, source, fields.get("Title", ""))
            )
    return observations


def load_observations(paths: list[Path]) -> list[Observation]:
    observations = []
    for path in paths:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            title_key = "Subject" if "Subject" in fieldnames else "Title"
            date_key = "Date" if "Date" in fieldnames else "Created at"
            author_key = next(
                (column for column in ("Author", "Authors", "Contributors") if column in fieldnames),
                None,
            )
            if not all((title_key, date_key, author_key)):
                raise ValueError(
                    f"{path}: CSV must contain a title, date, and author/contributors column"
                )
            for line_number, row in enumerate(reader, start=2):
                try:
                        date_value = (row.get(date_key) or "").strip()
                        if not date_value:
                            continue
                        date = parse_date(date_value)
                        observations.extend(
                            Observation(login, name, date, str(path), row.get(title_key, ""))
                            for identity in (row.get(author_key) or "").split(",")
                            if (parsed := parse_identity(identity))
                            for login, name in [parsed]
                        )
                except (KeyError, TypeError, ValueError) as error:
                    raise ValueError(f"{path}:{line_number}: {error}") from error
    return observations


def find_candidates(observations: list[Observation]) -> list[dict[str, str | int]]:
    by_login: dict[str, list[Observation]] = defaultdict(list)
    for observation in observations:
        by_login[observation.login].append(observation)

    candidates = []
    for login, account_observations in by_login.items():
        name_counts = defaultdict(int)
        for item in account_observations:
            if (
                item.name.lower() not in UNKNOWN_VALUES
                and item.name.casefold() != login.casefold()
            ):
                name_counts[item.name] += 1
        names = sorted(name_counts)
        if len(names) < 2:
            continue

        concurrent_pairs = set()
        for index, first in enumerate(account_observations):
            for second in account_observations[index + 1 :]:
                if (
                    first.name != second.name
                    and first.name in names
                    and second.name in names
                    and abs((first.date - second.date).days) <= 30
                ):
                    concurrent_pairs.add(tuple(sorted((first.name, second.name))))

        service_account = bool(
            SERVICE_RE.search(login)
            or any(SERVICE_RE.search(name) for name in names)
        )
        alias_pairs = {
            tuple(sorted((first, second)))
            for index, first in enumerate(names)
            for second in names[index + 1 :]
            if likely_alias(first, second)
        }
        distinct_names = [
            name
            for name in names
            if all(tuple(sorted((name, other))) not in alias_pairs for other in names if other != name)
        ]
        repeated_distinct_names = sum(name_counts[name] >= 2 for name in distinct_names)
        if service_account:
            classification = "automation/service_account"
        elif (
            len(distinct_names) >= 2
            and repeated_distinct_names >= 2
            and concurrent_pairs
        ):
            classification = "possible_shared_account"
        else:
            classification = "likely_alias_variation"
        organizational_assessment = (
            "possible_organizational_account"
            if (
                not service_account
                and len(distinct_names) >= 2
                and repeated_distinct_names >= 2
                and concurrent_pairs
            )
            else "insufficient_evidence"
        )

        signals = ["the login is associated with multiple display names"]
        if alias_pairs:
            signals.append(f"{len(alias_pairs)} display-name pair(s) look like aliases")
        if concurrent_pairs:
            signals.append(
                    "different display names occur in the same activity period"
            )
        if classification == "possible_shared_account":
            signals.append(
                    "at least two distinct names recur and overlap in the same activity period"
            )
        if service_account:
            signals.append("the login or display name contains a service-account marker")
        candidates.append(
            {
                    "Account": login,
                    "Profile": f"https://github.com/{login}",
                    "Classification": classification,
                    "Organizational assessment": organizational_assessment,
                    "Display names": "; ".join(names),
                    "Name count": len(names),
                    "Observations": len(account_observations),
                    "Concurrent name pairs": len(concurrent_pairs),
                "First seen": min(item.date for item in account_observations).isoformat(),
                "Last seen": max(item.date for item in account_observations).isoformat(),
                "Signals": "; ".join(signals),
            }
        )
    return sorted(
        candidates,
        key=lambda row: (-int(row["Concurrent name pairs"]), -int(row["Name count"]), str(row["Account"]).lower()),
    )


def write_report(path: Path, rows: list[dict[str, str | int]]) -> None:
    fieldnames = [
        "Account",
        "Profile",
        "Classification",
        "Organizational assessment",
        "Display names",
        "Name count",
        "Observations",
        "Concurrent name pairs",
        "First seen",
        "Last seen",
        "Signals",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("filtered richer data/identity-variation-report.csv"),
        help="CSV report path (default: filtered richer data/identity-variation-report.csv)",
    )
    parser.add_argument("files", nargs="*", type=Path, default=list(DEFAULT_FILES))
    args = parser.parse_args()
    paths = args.files or list(DEFAULT_FILES)

    rows = find_candidates(load_observations(paths))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_report(args.output, rows)
    print(f"Found {len(rows)} candidate account(s).")
    print(f"Report written to: {args.output}")
    for row in rows:
        print(
            f"- {row['Account']}: {row['Classification']} "
            f"({row['Concurrent name pairs']} concurrent name pair(s))"
        )


if __name__ == "__main__":
    main()
