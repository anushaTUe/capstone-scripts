import csv
import sys
from collections import Counter
from datetime import datetime


def make_bar_graph(csv_file="commit-log.csv", output_file="commits-past-year.png"):
    import matplotlib.pyplot as plt

    dates = []
    with open(csv_file, newline="", encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            dates.append(datetime.fromisoformat(row["Date"].replace("Z", "+00:00")))

    latest_month = max(dates).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    months = []
    for months_ago in range(11, -1, -1):
        month_number = latest_month.month - months_ago
        year = latest_month.year + (month_number - 1) // 12
        month = (month_number - 1) % 12 + 1
        months.append(f"{year:04d}-{month:02d}")

    counts = Counter(date.strftime("%Y-%m") for date in dates)
    values = [counts[month] for month in months]

    plt.bar(months, values)
    plt.xlabel("Month")
    plt.ylabel("Commits")
    plt.title("Commits in the past year")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(output_file)
    plt.close()


def main():
    csv_file = sys.argv[1] if len(sys.argv) > 1 else "commit-log.csv"
    commits_per_month = Counter()

    with open(csv_file, newline="", encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            date = datetime.fromisoformat(row["Date"].replace("Z", "+00:00"))
            commits_per_month[date.strftime("%Y-%m")] += 1

    for month in sorted(commits_per_month):
        print(f"{month}: {commits_per_month[month]} commits")

    make_bar_graph(csv_file)


if __name__ == "__main__":
    main()
