import requests
import time

TOKEN = "GITHUB_TOKEN"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json"
}


def github_search(item_type, states):
    url = "https://api.github.com/graphql"
    all_items = []
    cursor = None

    if item_type == "pullRequests":
        fields = """
            title author { login ... on User { name } }
            createdAt closedAt additions deletions changedFiles
            commits(first: 20) {
                nodes {
                    commit {
                        authors(first: 10) {
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
        fields = fields = """
            title author { login ... on User { name } }
            createdAt closedAt stateReason
            comments(first: 20) {
                nodes {
                    author {
                        login
                        ... on User { name }
                    }
                }
            }
        """

    query = """
    query($cursor: String) {
        repository(owner: "excalidraw", name: "excalidraw") {
            ITEM(first: 100, after: $cursor, states: STATES) {
                totalCount
                pageInfo {
                    hasNextPage
                    endCursor
                }
                nodes {
                    FIELDS
                }
            }
        }
    }
    """

    query = query.replace("ITEM", item_type)
    query = query.replace("STATES", states)
    query = query.replace("FIELDS", fields)

    while True:
        response = requests.post(
            url,
            json={"query": query, "variables": {"cursor": cursor}},
            headers=headers,
            timeout=30
        )

        if response.status_code in (502, 503, 504):
            print("GitHub server error. Retrying in 10 seconds...")
            time.sleep(10)
            continue

        response.raise_for_status()
        data = response.json()

        if "errors" in data:
            raise RuntimeError(data["errors"])

        result = data["data"]["repository"][item_type]
        all_items.extend(result["nodes"])

        print(f"{item_type}: {len(all_items)}/{result['totalCount']}")

        if not result["pageInfo"]["hasNextPage"]:
            break

        cursor = result["pageInfo"]["endCursor"]
        time.sleep(1)

    return {"items": all_items, "total_count": result["totalCount"]}


# Number of pull requests open and closed
prso = github_search("pullRequests", "[OPEN]")
prsum = github_search("pullRequests", "[CLOSED]")
prsm = github_search("pullRequests", "[MERGED]")

# Number of issues open and closed
issueso = github_search("issues", "[OPEN]")
issuesc = github_search("issues", "[CLOSED]")


# Create files and fetch data from PRs & Issues
prsoFile = open("openPRs.txt", "w", encoding="utf-8")
for pr in prso["items"]:
    prsoFile_titles = pr["title"]
    prsoFile_authors = f'{pr["author"]["login"]} ({pr["author"].get("name") or "Unknown"})' if pr["author"] else "Unknown"

    contributors = set()

    for commit in pr["commits"]["nodes"]:
        for author in commit["commit"]["authors"]["nodes"]:
            name = author["name"]
            username = author["user"]["login"] if author["user"] else "Unknown"
            contributors.add(f"{username} ({name})")

    prsoFile_contributors = ", ".join(sorted(contributors))

    prsoFile_created = pr["createdAt"]
    prsoFile_additions = pr["additions"]
    prsoFile_deletions = pr["deletions"]
    prsoFile_filesChanged = pr["changedFiles"]

    prsoFile.write(f"Title: {prsoFile_titles} | Author: {prsoFile_authors} | Contributors: {prsoFile_contributors} | Created at: {prsoFile_created} | Additions: {prsoFile_additions} | Deletions: {prsoFile_deletions} | Files Changed: {prsoFile_filesChanged}\n")


prsumFile = open("unmergedPRs.txt", "w", encoding="utf-8")
for pr in prsum["items"]:
    prsumFile_titles = pr["title"]
    prumFile_authors = f'{pr["author"]["login"]} ({pr["author"].get("name") or "Unknown"})' if pr["author"] else "Unknown"

    contributors = set()

    for commit in pr["commits"]["nodes"]:
        for author in commit["commit"]["authors"]["nodes"]:
            name = author["name"]
            username = author["user"]["login"] if author["user"] else "Unknown"
            contributors.add(f"{username} ({name})")

    prsumFile_contributors = ", ".join(sorted(contributors))

    prsumFile_created = pr["createdAt"]
    prsumFile_closed = pr["closedAt"]
    prsumFile_additions = pr["additions"]
    prsumFile_deletions = pr["deletions"]
    prsumFile_filesChanged = pr["changedFiles"]

    prsumFile.write(f"Title: {prsumFile_titles} | Author: {prsumFile_authors} | Contributors: {prsumFile_contributors} | Created at: {prsumFile_created} | Closed at: {prsumFile_closed} | Additions: {prsumFile_additions} | Deletions: {prsumFile_deletions} | Files Changed: {prsumFile_filesChanged}\n")

prsmFile = open("mergedPRs.txt", "w", encoding="utf-8")
for pr in prsm["items"]:
    prsmFile_titles = pr["title"]
    prsmFile_authors = f'{pr["author"]["login"]} ({pr["author"].get("name") or "Unknown"})' if pr["author"] else "Unknown"

    contributors = set()

    for commit in pr["commits"]["nodes"]:
        for author in commit["commit"]["authors"]["nodes"]:
            name = author["name"]
            username = author["user"]["login"] if author["user"] else "Unknown"
            contributors.add(f"{username} ({name})")

    prsmFile_contributors = ", ".join(sorted(contributors))

    prsmFile_created = pr["createdAt"]
    prsmFile_closed = pr["closedAt"]
    prsmFile_additions = pr["additions"]
    prsmFile_deletions = pr["deletions"]
    prsmFile_filesChanged = pr["changedFiles"]

    prsmFile.write(f"Title: {prscFile_titles} | Author: {prscFile_authors} | Contributors: {prsmFile_contributors} | Created at: {prscFile_created} | Closed at: {prscFile_closed} | Additions: {prscFile_additions} | Deletions: {prscFile_deletions} | Files Changed: {prscFile_filesChanged}\n")


issuesoFile = open("openIssues.txt", "w", encoding="utf-8")
for issues in issueso["items"]:
    issuesoFile_titles = issues["title"]
    issuesoFile_authors = f'{issues["author"]["login"]} ({issues["author"].get("name") or "Unknown"})' if issues["author"] else "Unknown"

    contributors = set()

    for comment in issues["comments"]["nodes"]:
        author = comment["author"]

        if author:
            username = author["login"]
            name = author.get("name") or "Unknown"
            contributors.add(f"{username} ({name})")

    issuesoFile_contributors = ", ".join(sorted(contributors))
    
    issuesoFile_created = issues["createdAt"]

    issuesoFile.write(f"Title: {issuesoFile_titles} | Author: {issuesoFile_authors} | Contributors: {issuesoFile_contributors} | Created at: {issuesoFile_created}\n")


issuescFile = open("closedIssues.txt", "w", encoding="utf-8")
for issues in issuesc["items"]:
    issuescFile_titles = issues["title"]
    issuescFile_authors = f'{issues["author"]["login"]} ({issues["author"].get("name") or "Unknown"})' if issues["author"] else "Unknown"

    contributors = set()

    for comment in issues["comments"]["nodes"]:
        author = comment["author"]

        if author:
            username = author["login"]
            name = author.get("name") or "Unknown"
            contributors.add(f"{username} ({name})")

    issuescFile_contributors = ", ".join(sorted(contributors))

    issuescFile_created = issues["createdAt"]
    issuescFile_closed = issues["closedAt"]
    issuescFile_reason = issues["stateReason"]

    issuescFile.write(f"Title: {issuescFile_titles} | Author: {issuescFile_authors} | Contributors: {issuescFile_contributors} | Created at: {issuescFile_created} | Closed at: {issuescFile_closed} | Reason: {issuescFile_reason}\n")


prsoFile.close()
prsumFile.close()
prsmFile.close()
issuesoFile.close()
issuescFile.close()


# Print result stuff..
print()
print("PULL REQUESTS:", prso["total_count"], "open,", prsum["total_count"], "unmerged,", prsm["total_count"], "merged.", "TOTAL:", prso["total_count"] + prsum["total_count"] + prsm["total_count"])
print("ISSUES:", issueso["total_count"], "open,", issuesc["total_count"], "closed. TOTAL:", issueso["total_count"] + issuesc["total_count"])
