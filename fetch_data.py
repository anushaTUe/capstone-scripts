import os
import time

import requests

TOKEN = os.getenv("GITHUB_TOKEN")
PAGE_SIZE = 25
MAX_RETRIES = 8

headers = {
    "Authorization": f"Bearer {TOKEN}" if TOKEN else "",
    "Accept": "application/vnd.github+json",
}


def safe_author(author):
    if not author:
        return "Unknown"
    return f'{author.get("login", "Unknown")} ({author.get("name") or "Unknown"})'


def get_commit_contributors(commit_nodes):
    contributors = set()
    for commit in commit_nodes:
        for author in commit.get("commit", {}).get("authors", {}).get("nodes", []):
            name = author.get("name") or "Unknown"
            user = author.get("user") or {}
            username = user.get("login") or "Unknown"
            contributors.add(f"{username} ({name})")
    return ", ".join(sorted(contributors))


def get_comment_contributors(comment_nodes):
    contributors = set()
    for comment in comment_nodes:
        author = comment.get("author")
        if author:
            username = author.get("login") or "Unknown"
            name = author.get("name") or "Unknown"
            contributors.add(f"{username} ({name})")
    return ", ".join(sorted(contributors))


def github_search(item_type, states):
    url = "https://api.github.com/graphql"
    all_items = []
    cursor = None
    session = requests.Session()

    if item_type == "pullRequests":
        fields = """
            title
            author { login ... on User { name } }
            createdAt
            closedAt
            merged
            additions
            deletions
            changedFiles
            commits(first: 10) {
                nodes {
                    commit {
                        authors(first: 5) {
                            nodes {
                                name
                                user { login }
                            }
                        }
                    }
                }
            }
        """
    else:
        fields = """
            title
            author { login ... on User { name } }
            createdAt
            closedAt
            stateReason
            comments(first: 20) {
                nodes {
                    author {
                        login
                        ... on User { name }
                    }
                }
            }
        """

    query = f"""
    query($cursor: String) {{
        repository(owner: "excalidraw", name: "excalidraw") {{
            {item_type}(first: {PAGE_SIZE}, after: $cursor, states: {states}) {{
                totalCount
                pageInfo {{
                    hasNextPage
                    endCursor
                }}
                nodes {{
                    {fields}
                }}
            }}
        }}
    }}
    """

    while True:
        retry_count = 0
        while True:
            try:
                response = session.post(
                    url,
                    json={"query": query, "variables": {"cursor": cursor}},
                    headers=headers,
                    timeout=(15, 90),
                )
            except requests.RequestException as error:
                retry_count += 1
                if retry_count >= MAX_RETRIES:
                    raise RuntimeError(
                        f"GitHub request failed after {retry_count} attempts: {error}"
                    ) from error
                delay = min(60, 2 ** retry_count)
                print(
                    f"GitHub request failed ({error}). Retrying in {delay} seconds "
                    f"({retry_count}/{MAX_RETRIES})..."
                )
                time.sleep(delay)
                continue

            if response.status_code in (429, 502, 503, 504):
                retry_count += 1
                if retry_count >= MAX_RETRIES:
                    raise RuntimeError(
                        f"GitHub returned HTTP {response.status_code} after "
                        f"{retry_count} attempts: {response.text[:500]}"
                    )
                retry_after = response.headers.get("Retry-After")
                delay = (
                    int(retry_after)
                    if retry_after and retry_after.isdigit()
                    else min(60, 2 ** retry_count)
                )
                print(
                    f"GitHub returned HTTP {response.status_code} "
                    f"({response.reason}). Retrying in {delay} seconds "
                    f"({retry_count}/{MAX_RETRIES})..."
                )
                time.sleep(delay)
                continue

            response.raise_for_status()
            break

        data = response.json()

        if "errors" in data:
            errors = "; ".join(
                error.get("message", str(error)) for error in data["errors"]
            )
            if any("rate limit" in error.lower() for error in errors.split("; ")):
                print("GitHub GraphQL rate limit reached. Retrying in 60 seconds...")
                time.sleep(60)
                continue
            raise RuntimeError(f"GitHub GraphQL error: {errors}")

        result = data["data"]["repository"][item_type]
        all_items.extend(result["nodes"])

        print(f"{item_type}: {len(all_items)}/{result['totalCount']}")

        if not result["pageInfo"]["hasNextPage"]:
            break

        cursor = result["pageInfo"]["endCursor"]
        time.sleep(1)

    return {"items": all_items, "total_count": result["totalCount"]}


def write_prs(file_name, prs, include_closed=False):
    with open(file_name, "w", encoding="utf-8") as output_file:
        for pr in prs:
            contributors = get_commit_contributors(pr.get("commits", {}).get("nodes", []))
            author = safe_author(pr.get("author"))
            created = pr.get("createdAt")
            additions = pr.get("additions")
            deletions = pr.get("deletions")
            files_changed = pr.get("changedFiles")

            if include_closed:
                closed = pr.get("closedAt")
                output_file.write(
                    f"Title: {pr['title']} | Author: {author} | Contributors: {contributors} | "
                    f"Created at: {created} | Closed at: {closed} | "
                    f"Additions: {additions} | Deletions: {deletions} | Files Changed: {files_changed}\n"
                )
            else:
                output_file.write(
                    f"Title: {pr['title']} | Author: {author} | Contributors: {contributors} | "
                    f"Created at: {created} | Additions: {additions} | Deletions: {deletions} | "
                    f"Files Changed: {files_changed}\n"
                )


def write_issues(file_name, issues, closed=False):
    with open(file_name, "w", encoding="utf-8") as output_file:
        for issue in issues:
            contributors = get_comment_contributors(issue.get("comments", {}).get("nodes", []))
            author = safe_author(issue.get("author"))
            created = issue.get("createdAt")

            if closed:
                closed_at = issue.get("closedAt")
                reason = issue.get("stateReason")
                output_file.write(
                    f"Title: {issue['title']} | Author: {author} | Contributors: {contributors} | "
                    f"Created at: {created} | Closed at: {closed_at} | Reason: {reason}\n"
                )
            else:
                output_file.write(
                    f"Title: {issue['title']} | Author: {author} | Contributors: {contributors} | "
                    f"Created at: {created}\n"
                )


def require_token():
    if not TOKEN:
        raise RuntimeError(
            "GITHUB_TOKEN is not set. Set it before running the script, for example: "
            "$env:GITHUB_TOKEN = '<your-token>'"
        )


if __name__ == "__main__":
    require_token()
    pr_open = github_search("pullRequests", "[OPEN]")
    closed_prs = github_search("pullRequests", "[CLOSED]")
    pr_merged_items = [pr for pr in closed_prs["items"] if pr["merged"]]
    pr_closed_items = [pr for pr in closed_prs["items"] if not pr["merged"]]
    pr_merged = {"items": pr_merged_items, "total_count": len(pr_merged_items)}
    pr_closed = {"items": pr_closed_items, "total_count": len(pr_closed_items)}

    issues_open = github_search("issues", "[OPEN]")
    issues_closed = github_search("issues", "[CLOSED]")

    write_prs("openPRs.txt", pr_open["items"])
    write_prs("unmergedPRs.txt", pr_closed["items"], include_closed=True)
    write_prs("mergedPRs.txt", pr_merged["items"], include_closed=True)

    write_issues("openIssues.txt", issues_open["items"])
    write_issues("closedIssues.txt", issues_closed["items"], closed=True)

    print()
    print(
        "PULL REQUESTS:",
        pr_open["total_count"],
        "open,",
        pr_closed["total_count"],
        "unmerged,",
        pr_merged["total_count"],
        "merged.",
        "TOTAL:",
        pr_open["total_count"] + pr_closed["total_count"] + pr_merged["total_count"],
    )
    print(
        "ISSUES:",
        issues_open["total_count"],
        "open,",
        issues_closed["total_count"],
        "closed. TOTAL:",
        issues_open["total_count"] + issues_closed["total_count"],
    )
