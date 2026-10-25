import csv
from datetime import datetime, timedelta, timezone
from statistics import median, quantiles
import matplotlib.pyplot as plt

# Put this file in the same folder as your CSV files.
START = datetime(2025, 10, 25, tzinfo=timezone.utc)
END = datetime(2026, 10, 25, tzinfo=timezone.utc)  # Not included
HALF = datetime(2026, 4, 25, tzinfo=timezone.utc)
SIX_MONTHS = timedelta(days=183)


def load(filename):
    with open(filename, encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def get_date(text):
    if not text or not text.strip():
        return None
    return datetime.fromisoformat(text.strip().replace("Z", "+00:00"))


def pct(part, total):
    return round(100 * part / total, 1) if total else 0


# Read the five activity files and the filtered (human) commit log.
issues_open = load("openIssues.csv")
issues_closed = load("closedIssues.csv")
prs_open = load("openPRs.csv")
prs_merged = load("mergedPRs.csv")
prs_unmerged = load("unmergedPRs.csv")
commits = load("commit-log.csv")

issues = issues_open + issues_closed
prs = prs_open + prs_merged + prs_unmerged

for row in issues + prs:
    row["created"] = get_date(row.get("Created at"))
    row["closed"] = get_date(row.get("Closed at"))

for row in commits:
    row["date"] = get_date(row["Date"])

commits = [row for row in commits if row["date"] and row["date"] < END]
recent_commits = [row for row in commits if START <= row["date"] < END]
recent_issues = [row for row in issues if row["created"] and START <= row["created"] < END]
recent_prs = [row for row in prs if row["created"] and START <= row["created"] < END]
issues_closed_year = [row for row in issues_closed if row["closed"] and START <= row["closed"] < END]
merged_year = [row for row in prs_merged if row["closed"] and START <= row["closed"] < END]
unmerged_year = [row for row in prs_unmerged if row["closed"] and START <= row["closed"] < END]
prs_closed_year = merged_year + unmerged_year

# Categorise the people who authored COMMITS.
authors = {}
for row in commits:
    author = row["Author"]
    if author not in authors:
        authors[author] = []
    authors[author].append(row["date"])

active = key = newcomers = dormant = occasional = once = last_year = 0
key_names = []
for author, dates in authors.items():
    dates.sort()
    months = set()
    for day in dates:
        if START <= day < END:
            months.add((day.year, day.month))

    is_active = dates[-1] >= END - timedelta(days=30)
    is_key = len(months) >= 6
    is_new = dates[0] >= END - SIX_MONTHS
    active += is_active
    key += is_key
    if is_key:
        key_names.append(author)
    newcomers += is_new
    dormant += dates[-1] < END - SIX_MONTHS
    occasional += is_active and not is_key and not is_new
    once += len(dates) == 1
    last_year += len(months) > 0

bots = {}
for row in load("bot-report.csv"):
    account = row["Author"].split(" (")[0]
    bots[account] = row["Score"]

print("\n3.2 CONTRIBUTORS (commit authors only)")
print("All human commit authors:", len(authors))
print("Authors who committed last year:", last_year)
print("Active in last 30 days:", active)
print("Key (at least 6 active months):", key, key_names)
print("New (first commit in last 183 days):", newcomers)
print("Dormant (no commit in last 183 days):", dormant)
print("Occasional (active, not new or key):", occasional)
print("Authors with exactly one commit:", once)
gaps = long_gaps = 0
for dates in authors.values():
    for index in range(1, len(dates)):
        gaps += 1
        if dates[index] - dates[index - 1] > timedelta(days=180):
            long_gaps += 1
print("Gaps longer than 180 days:", long_gaps, "/", gaps, "=", pct(long_gaps, gaps), "%")
print("Bots in bot-report.csv:", len(bots), bots)
print("Shared human accounts: none confirmed by the report (requires manual checking)")

# Count the work done during the last year.
added = deleted = files_changed = 0
for row in recent_commits:
    added += int(row["Insertions"])
    deleted += int(row["Deletions"])
    files_changed += int(row["FilesChanged"])

issues_closed_cohort = 0
for row in recent_issues:
    if row["closed"] and row["closed"] < END:
        issues_closed_cohort += 1

prs_closed_cohort = 0
for row in recent_prs:
    if row["closed"] and row["closed"] < END:
        prs_closed_cohort += 1

print("\n3.3 PROJECT ACTIVITY (last 12 months)")
print("Commit frequency:", len(recent_commits), "per year")
print("Commit recency:", round((END - max(r["date"] for r in commits)).total_seconds() / 86400, 2), "days")
print("Code churn:", added + deleted, "lines (", added, "added,", deleted, "deleted )")
print("Files changed across commits:", files_changed)
print("New PRs:", len(recent_prs))
print("PRs closed during year:", len(prs_closed_year))
print("PRs merged / closed during year:", len(merged_year), "/", len(prs_closed_year))
print("PR merge rate:", pct(len(merged_year), len(prs_closed_year)), "%")
print("PR closure rate (created this year):", prs_closed_cohort, "/", len(recent_prs), "=", pct(prs_closed_cohort, len(recent_prs)), "%")
print("New issues:", len(recent_issues))
print("Issues closed during year:", len(issues_closed_year))
print("Issue closure rate (created this year):", issues_closed_cohort, "/", len(recent_issues), "=", pct(issues_closed_cohort, len(recent_issues)), "%")

# Calculate five metrics for each month and draw one graph for each.
months = []
monthly_commits = []
monthly_recency = []
monthly_churn = []
monthly_prs = []
monthly_merge_rate = []
monthly_issues = []
monthly_issue_closure_rate = []

print("\nMONTH        COMMITS  RECENCY (days)  CHURN (lines)  NEW PRs  PR MERGE RATE  NEW ISSUES  ISSUE CLOSURE RATE")
for year, month in [(2025, 10), (2025, 11), (2025, 12)] + [(2026, m) for m in range(1, 11)]:
    month_start = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        month_end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        month_end = datetime(year, month + 1, 1, tzinfo=timezone.utc)

    # Restrict October 2025 and October 2026 to the actual observation period.
    month_start = max(month_start, START)
    month_end = min(month_end, END)
    month_commits = [r for r in recent_commits if month_start <= r["date"] < month_end]
    month_prs = [r for r in recent_prs if month_start <= r["created"] < month_end]
    month_issues = [r for r in recent_issues if month_start <= r["created"] < month_end]
    issues_resolved = sum(1 for r in month_issues if r["closed"] and r["closed"] < END)
    issue_closure_rate = pct(issues_resolved, len(month_issues))
    merged = [r for r in merged_year if month_start <= r["closed"] < month_end]
    unmerged = [r for r in unmerged_year if month_start <= r["closed"] < month_end]

    # Recency means days since the latest commit, measured at this month's cutoff.
    latest = max(r["date"] for r in commits if r["date"] < month_end)
    recency = round((month_end - latest).total_seconds() / 86400, 2)
    churn = sum(int(r["Insertions"]) + int(r["Deletions"]) for r in month_commits)
    merge_rate = pct(len(merged), len(merged) + len(unmerged))
    label = f"{year}-{month:02d}"

    months.append(label)
    monthly_commits.append(len(month_commits))
    monthly_recency.append(recency)
    monthly_churn.append(churn)
    monthly_prs.append(len(month_prs))
    monthly_merge_rate.append(merge_rate)
    monthly_issues.append(len(month_issues))
    monthly_issue_closure_rate.append(issue_closure_rate)
    print(f"{label:12} {len(month_commits):7} {recency:15.2f} {churn:14} {len(month_prs):8} {merge_rate:12.1f}% {len(month_issues):11} {issue_closure_rate:18.1f}%")

# Seven separate charts: each one is saved as a PNG and displayed on screen.
graphs = [
    ("Monthly Commit Frequency", monthly_commits, "Commits", "monthly_commit_frequency.png"),
    ("Monthly Commit Recency", monthly_recency, "Days since last commit", "monthly_commit_recency.png"),
    ("Monthly Code Churn", monthly_churn, "Lines added + deleted", "monthly_code_churn.png"),
    ("Monthly PR Creation Frequency", monthly_prs, "New pull requests", "monthly_pr_frequency.png"),
    ("Monthly PR Merge Rate", monthly_merge_rate, "Merge rate (%)", "monthly_pr_merge_rate.png"),
    ("Monthly Issue Creation Frequency", monthly_issues, "New issues", "monthly_issue_frequency.png"),
    ("Monthly Issue Closure Rate", monthly_issue_closure_rate, "Closure rate (%)", "monthly_issue_closure_rate.png"),
]

for title, values, ylabel, filename in graphs:
    plt.figure(figsize=(11, 5))
    plt.bar(months, values)
    plt.title(title)
    plt.xlabel("Month")
    plt.ylabel(ylabel)
    plt.xticks(rotation=45)
    plt.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(filename, dpi=180)
    print("Saved:", filename)

print("Note: October 2025 and October 2026 are partial months.")
print("Monthly issue closure rate = issues created that month and closed before 25 Oct 2026 / issues created that month.")
# Resolution times and backlog age.
print("\n3.4 PROCESS METRICS")
for name, closed_rows, open_rows in [
    ("Issues", issues_closed_year, issues_open),
    ("PRs", prs_closed_year, prs_open)
]:
    times = []
    for row in closed_rows:
        times.append((row["closed"] - row["created"]).total_seconds() / 86400)
    print(name, "resolution median:", round(median(times), 2), "days")
    print(name, "resolution 90th percentile:", round(quantiles(times, n=10, method="inclusive")[8], 2), "days")

    ages = []
    for row in open_rows:
        ages.append((END - row["created"]).total_seconds() / 86400)
    old = sum(1 for age in ages if age > 365)
    print(name, "backlog older than 1 year:", old, "/", len(ages), "=", pct(old, len(ages)), "%")
    print(name, "median age of open items:", round(median(ages), 1), "days")

print("Issue close-open ratio:", round(len(issues_closed_year) / len(recent_issues), 2))
print("PR close-open ratio:", round(len(prs_closed_year) / len(recent_prs), 2))
print("Unanswered rate: cannot be calculated reliably from incomplete Contributors fields")

# Newcomer retention: another commit within 183 days AFTER the first commit.
eligible = retained = 0
for dates in authors.values():
    if dates[0] <= END - SIX_MONTHS:
        eligible += 1
        for day in dates[1:]:
            if day <= dates[0] + SIX_MONTHS:
                retained += 1
                break
print("Newcomer retention:", retained, "/", eligible, "=", pct(retained, eligible), "%")

# Turnover: commits in the first six months, but none in the next six.
earlier = set()
later = set()
for author, dates in authors.items():
    for day in dates:
        if START <= day < HALF:
            earlier.add(author)
        if HALF <= day < END:
            later.add(author)
left = len(earlier - later)
print("Contributor turnover:", left, "/", len(earlier), "=", pct(left, len(earlier)), "%")

# Concentration: minimum number of authors accounting for half of the commits.
for name, rows in [("Full history", commits), ("Last year", recent_commits)]:
    counts = {}
    for row in rows:
        author = row["Author"]
        counts[author] = counts.get(author, 0) + 1
    total = 0
    people = 0
    for number in sorted(counts.values(), reverse=True):
        total += number
        people += 1
        if total >= len(rows) / 2:
            break
    largest = max(counts.values())
    print(name, "contributors for 50% of commits:", people)
    print(name, "largest author's share:", largest, "/", len(rows), "=", pct(largest, len(rows)), "%")
