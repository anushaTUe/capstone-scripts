#!/usr/bin/env python3
"""Analyse repository commit history for a project-health report.

The input is the CSV produced by get-commits.py (Hash, Author, Date, Subject).
The analysis deliberately distinguishes observable evidence from claims that
cannot be established from a commit log alone, such as a person's identity or
whether an account is automated.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


BOT_NAME_RE = re.compile(r"(?:\[bot\]|bot\b|dependabot|renovate|github-actions|semantic-release|release-bot)", re.I)
TYPE_RE = re.compile(r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]+)\))?!?:", re.I)
BOT_TEMPLATE_RE = re.compile(r"^chore\([^)]*\)(?:!|):", re.I)
REPEATED_SUBJECT_THRESHOLD = 3


@dataclass(frozen=True)
class Commit:
	hash: str
	author: str
	date: datetime
	subject: str


def parse_date(value: str) -> datetime:
	value = value.strip().replace("Z", "+00:00")
	parsed = datetime.fromisoformat(value)
	if parsed.tzinfo is None:
		parsed = parsed.replace(tzinfo=timezone.utc)
	return parsed


def load_commits(path: Path) -> list[Commit]:
	commits: list[Commit] = []
	with path.open(newline="", encoding="utf-8-sig") as handle:
		reader = csv.DictReader(handle)
		required = {"Hash", "Author", "Date", "Subject"}
		missing = required - set(reader.fieldnames or [])
		if missing:
			raise ValueError(f"Missing CSV columns: {', '.join(sorted(missing))}")
		for line_number, row in enumerate(reader, start=2):
			try:
				commits.append(Commit(row["Hash"].strip(), row["Author"].strip(), parse_date(row["Date"]), row["Subject"].strip()))
			except (AttributeError, ValueError) as error:
				raise ValueError(f"Invalid row {line_number}: {error}") from error
	return sorted(commits, key=lambda commit: commit.date)


def classify_contributors(commits: list[Commit], newcomer_days: int, dormant_days: int) -> dict[str, dict]:
	if not commits:
		return {}
	latest = max(commit.date for commit in commits)
	by_author: dict[str, list[Commit]] = defaultdict(list)
	for commit in commits:
		by_author[commit.author].append(commit)
	result = {}
	for author, author_commits in sorted(by_author.items(), key=lambda item: (-len(item[1]), item[0].lower())):
		first = min(commit.date for commit in author_commits)
		last = max(commit.date for commit in author_commits)
		active_months = {commit.date.strftime("%Y-%m") for commit in author_commits}
		recent_months = {(latest - timedelta(days=30 * index)).strftime("%Y-%m") for index in range(12)}
		monthly_recent = sum(month in active_months for month in recent_months)
		days_since_last = (latest - last).days
		labels = []
		if monthly_recent >= 6:
			labels.append("frequent/key")
		if (latest - first).days <= newcomer_days:
			labels.append("newcomer")
		if days_since_last >= dormant_days:
			labels.append("dormant")
		if not labels:
			labels.append("occasional/active")
		result[author] = {
			"commits": len(author_commits),
			"first_commit": first.date().isoformat(),
			"last_commit": last.date().isoformat(),
			"days_since_last": days_since_last,
			"active_months": len(active_months),
			"recent_active_months": monthly_recent,
			"categories": labels,
		}
	return result


def parse_aliases(values: Iterable[str]) -> dict[str, str]:
	aliases = {}
	for value in values:
		if "=" not in value:
			raise ValueError(f"Alias must use ACCOUNT=PERSON format: {value}")
		account, person = value.split("=", 1)
		aliases[account.strip()] = person.strip()
	return aliases


def bot_evidence(commits: list[Commit]) -> dict[str, dict]:
	by_author: dict[str, list[Commit]] = defaultdict(list)
	for commit in commits:
		by_author[commit.author].append(commit)
	evidence = {}
	for author, author_commits in by_author.items():
		name_signal = bool(BOT_NAME_RE.search(author))
		subjects = [commit.subject for commit in author_commits]
		conventional = sum(bool(TYPE_RE.match(subject)) for subject in subjects) / len(subjects)
		bot_template = sum(bool(BOT_TEMPLATE_RE.match(subject)) for subject in subjects) / len(subjects)
		repeated_subject_count = max(Counter(subjects).values(), default=0)
		ordered = sorted(author_commits, key=lambda commit: commit.date)
		intervals = [(b.date - a.date).total_seconds() for a, b in zip(ordered, ordered[1:])]
		regular_timing = len(intervals) >= 2 and (statistics.pstdev(intervals) / statistics.mean(intervals) < 0.05 if statistics.mean(intervals) else False)
		signals = []
		if name_signal:
			signals.append("account name contains a bot marker")
		if bot_template >= 0.9:
			signals.append(f"{bot_template:.0%} of subjects use the recurring chore(...) automation template")
		if repeated_subject_count >= REPEATED_SUBJECT_THRESHOLD:
			signals.append(f"the same subject appears {repeated_subject_count} times")
		if regular_timing:
			signals.append("commit intervals are unusually regular")
		if signals:
			evidence[author] = {"bot_signals": signals, "bot_score": int(name_signal) + int(bot_template >= 0.9) + int(repeated_subject_count >= REPEATED_SUBJECT_THRESHOLD) + int(regular_timing)}
	return evidence


def subject_metrics(commits: list[Commit]) -> dict:
	types = Counter()
	scopes = Counter()
	for commit in commits:
		match = TYPE_RE.match(commit.subject)
		if match:
			types[match.group("type").lower()] += 1
			if match.group("scope"):
				scopes[match.group("scope").lower()] += 1
	return {
		"commit_count": len(commits),
		"authors": len({commit.author for commit in commits}),
		"conventional_subjects": sum(types.values()),
		"subject_types": dict(types),
		"top_scopes": dict(scopes.most_common(15)),
		"commit_size": "Unavailable: CSV has no files changed or line counts.",
		"pull_requests": "Unavailable: a commit log does not contain opened, merged, rejected, or response-time events.",
	}


def sample(commits: list[Commit], size: int, seed: int) -> dict:
	"""Return reproducible random, stratified, and targeted sample references."""
	import random

	rng = random.Random(seed)
	ordered = sorted(commits, key=lambda commit: commit.date)
	random_sample = rng.sample(ordered, min(size, len(ordered)))
	by_author: dict[str, list[Commit]] = defaultdict(list)
	for commit in ordered:
		by_author[commit.author].append(commit)
	strata = [rng.choice(by_author[author]) for author in sorted(by_author)]
	targeted = sorted(ordered, key=lambda commit: (len(commit.subject), commit.date), reverse=True)[:size]
	return {"random": random_sample, "stratified_one_per_author": strata, "targeted_long_subjects": targeted}


def commit_link(commit: Commit, repo_url: str) -> str:
	return f"{repo_url.rstrip('/')}/commit/{commit.hash}"


def markdown_report(commits: list[Commit], args: argparse.Namespace) -> str:
	if not commits:
		return "# Repository health analysis\n\nNo commits were found."
	latest = max(commit.date for commit in commits)
	earliest = min(commit.date for commit in commits)
	categories = classify_contributors(commits, args.newcomer_days, args.dormant_days)
	bots = bot_evidence(commits)
	metrics = subject_metrics(commits)
	aliases = parse_aliases(args.alias)
	samples = sample(commits, args.sample_size, args.seed)
	lines = [
		"# Repository health analysis",
		"",
		f"**Data window:** {earliest.date()} to {latest.date()} ({metrics['commit_count']} commits, {metrics['authors']} author strings).",
		"",
		"## Scope and limitations",
		"This script uses observable commit metadata only. It cannot establish a person's real identity, whether an account is human, who wrote the code, deleted work, private communication, or why a change was made. PR/review and issue metrics require an API export in addition to this CSV.",
		"",
		"## Contributor involvement",
		f"Thresholds are configurable: newcomer means first commit within {args.newcomer_days} days of the latest observed commit; dormant means no commit for at least {args.dormant_days} days; frequent/key means activity in at least 6 of the latest 12 calendar months. These thresholds are pragmatic report categories, not proof of role.",
		"",
		"| Contributor | Commits | First | Last | Recent active months | Category |",
		"|---|---:|---|---|---:|---|",
	]
	for author, details in categories.items():
		lines.append(f"| {author} | {details['commits']} | {details['first_commit']} | {details['last_commit']} | {details['recent_active_months']}/12 | {', '.join(details['categories'])} |")
	lines += [
		"",
		"## Filtering accounts",
		"### Bots",
		f"The script applies at least two independent measures: (1) identity-string evidence, such as `[bot]`, `dependabot`, or `renovate` in the author; and (2) activity/message evidence, including recurring `chore(...)` automation subjects, the same subject appearing at least {REPEATED_SUBJECT_THRESHOLD} times, and unusually regular timing. Generic `type(scope): description` formatting is treated as a normal project practice, not bot evidence. A high score is a filtering candidate, not confirmation. Inspect and cite the linked profile before excluding it.",
		"",
	]
	for author, details in sorted(bots.items(), key=lambda item: (-item[1]["bot_score"], item[0].lower())):
		example = next(commit for commit in commits if commit.author == author)
		lines.append(f"- **{author}** (score {details['bot_score']}/4): {'; '.join(details['bot_signals'])}. Example: [{example.subject}]({commit_link(example, args.repo_url)}). Profile: https://github.com/{author}")
	if not bots:
		lines.append("- No account crossed the evidence threshold in this commit export; manually inspect service accounts before claiming there are no bots.")
	lines += [
		"",
		"### Multiple accounts and borderline cases",
		"Account merging is never inferred from a display name alone. Use at least two measures: explicit evidence supplied with `--alias ACCOUNT=PERSON`, and corroboration from matching email/author identity, linked profiles, commit signing, or consistent scopes and time patterns when those fields are available. The CSV has no email field, so aliases supplied here must be justified with external profile links in the report.",
	]
	for account, person in aliases.items():
		lines.append(f"- Treat `{account}` as an account of **{person}** only as a documented hypothesis; add profile/source links and explain the evidence.")
	lines += [
		"- Borderline case to discuss: an account whose commits frequently use `chore(...)` but have no bot marker. It may be a human maintainer performing maintenance work. Do not filter it without checking the profile and surrounding activity; report both signals and uncertainty.",
		"",
		"## Activity and practice metrics",
		f"- Recency: latest observed commit is {latest.date()}; this indicates activity, but a stable project may intentionally have bursts.",
		f"- Frequency: {metrics['commit_count']} commits across {metrics['authors']} author strings; interpret alongside the {earliest.date()} to {latest.date()} window.",
		"- Dormancy: use the table's days since last commit and the configured threshold; it can misclassify contributors whose role is non-coding.",
		f"- Commit subjects: {metrics['conventional_subjects']} ({metrics['conventional_subjects'] / metrics['commit_count']:.0%}) match a conventional/template-like format. Types: {metrics['subject_types'] or 'none detected'}. This is a communication signal, not a quality measure.",
		f"- Scope awareness: common subject scopes are {metrics['top_scopes'] or 'not available'}; this approximates activity areas but does not prove package ownership.",
		f"- {metrics['commit_size']}",
		f"- {metrics['pull_requests']}",
		"",
		"## Sampling approach",
		f"The script emits a reproducible random sample (seed {args.seed}) for an unbiased overview, a stratified sample with one commit per author for comparing involvement, and a targeted sample of the longest subjects for qualitative follow-up. Use random sampling for prevalence claims, stratification when contributor representation matters, and targeted sampling for unusual or high-context changes. Read each selected commit and quote its subject with the generated link; do not generalise a targeted sample to the whole repository.",
		"",
	]
	for sample_name, selected in samples.items():
		lines.append(f"### {sample_name.replace('_', ' ').title()}")
		for commit in selected:
			lines.append(f"- [{commit.subject}]({commit_link(commit, args.repo_url)}) - {commit.author}, {commit.date.date()}")
		lines.append("")
	lines += [
		"## Qualitative questions and improvement suggestions",
		"Use the linked examples above to inspect onboarding clues, review/coordination context, documentation changes, and whether work is concentrated in a few people. The commit CSV cannot observe review response time, rejected PRs, issue labels, or newcomer conversations, so export those events before making strong claims.",
		"",
		"| Potential issue to test | Artifact/change | Metric expected to improve |",
		"|---|---|---|",
		"| Newcomers appear but do not persist | contribution guide, good-first-issue labels, issue templates, newcomer check-in | newcomer-to-second-contribution rate; active contributors after 6 months |",
		"| Work is concentrated in a small core | CODEOWNERS, maintainer rotation, documented role ownership | contributor concentration; number of active roles/authors |",
		"| Coordination is hard to observe | PR template requiring context, decision, tests, and screenshots where relevant | review turnaround; reopened/rejected PR rate; qualitative completeness |",
		"| Automated and human activity are mixed | bot labels, author mapping, release automation documentation | human contributor counts; false-positive filtering decisions |",
		"| Coding activity hides documentation/community gaps | contribution guide, issue labels, docs ownership, community health files | docs/community contributions and issue response time |",
		"",
		"## JSON export",
		"Run with `--json-out analysis.json` to preserve machine-readable evidence for the report.",
	]
	return "\n".join(lines)


def main() -> None:
	reconfigure = getattr(sys.stdout, "reconfigure", None)
	if callable(reconfigure):
		reconfigure(encoding="utf-8")
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("csv", nargs="?", type=Path, default=Path("commit-log.csv"))
	parser.add_argument("--repo-url", default="https://github.com/excalidraw/excalidraw", help="Repository URL used for evidence links")
	parser.add_argument("--newcomer-days", type=int, default=183)
	parser.add_argument("--dormant-days", type=int, default=183)
	parser.add_argument("--sample-size", type=int, default=10)
	parser.add_argument("--seed", type=int, default=42)
	parser.add_argument("--alias", action="append", default=[], metavar="ACCOUNT=PERSON", help="Document a possible multi-account identity; repeat this option")
	parser.add_argument("--json-out", type=Path, help="Write summary metrics and contributor evidence as JSON")
	args = parser.parse_args()
	commits = load_commits(args.csv)
	print(markdown_report(commits, args))
	if args.json_out:
		args.json_out.write_text(json.dumps({
			"source": str(args.csv),
			"repo_url": args.repo_url,
			"metrics": subject_metrics(commits),
			"contributors": classify_contributors(commits, args.newcomer_days, args.dormant_days),
			"bot_evidence": bot_evidence(commits),
			"aliases": parse_aliases(args.alias),
		}, indent=2), encoding="utf-8")


if __name__ == "__main__":
	main()
