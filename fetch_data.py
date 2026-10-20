
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
        fields = "title author { login } createdAt closedAt additions deletions changedFiles"
    else:
        fields = "title author { login } createdAt closedAt"

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
prsc = github_search("pullRequests", "[CLOSED, MERGED]")

# Number of issues open and closed
issueso = github_search("issues", "[OPEN]")
issuesc = github_search("issues", "[CLOSED]")


# Create files and fetch data from PRs & Issues
prsoFile = open("openPRs.txt", "w", encoding="utf-8")
for pr in prso["items"]:
    prsoFile_titles = pr["title"]
    prsoFile_authors = pr["author"]["login"] if pr["author"] else "Unknown"
    prsoFile_created = pr["createdAt"]
    prsoFile_additions = pr["additions"]
    prsoFile_deletions = pr["deletions"]
    prsoFile_filesChanged = pr["changedFiles"]

    prsoFile.write(f"Title: {prsoFile_titles} | Authors: {prsoFile_authors} | Created at: {prsoFile_created} | Additions: {prsoFile_additions} | Deletions: {prsoFile_deletions} | Files Changed: {prsoFile_filesChanged}\n")


prscFile = open("closedPRs.txt", "w", encoding="utf-8")
for pr in prsc["items"]:
    prscFile_titles = pr["title"]
    prscFile_authors = pr["author"]["login"] if pr["author"] else "Unknown"
    prscFile_created = pr["createdAt"]
    prscFile_closed = pr["closedAt"]
    prscFile_additions = pr["additions"]
    prscFile_deletions = pr["deletions"]
    prscFile_filesChanged = pr["changedFiles"]

    prscFile.write(f"Title: {prscFile_titles} | Authors: {prscFile_authors} | Created at: {prscFile_created} | Closed at: {prscFile_closed} | Additions: {prscFile_additions} | Deletions: {prscFile_deletions} | Files Changed: {prscFile_filesChanged}\n")


issuesoFile = open("openIssues.txt", "w", encoding="utf-8")
for issues in issueso["items"]:
    issuesoFile_titles = issues["title"]
    issuesoFile_authors = issues["author"]["login"] if issues["author"] else "Unknown"
    issuesoFile_created = issues["createdAt"]

    issuesoFile.write(f"Title: {issuesoFile_titles} | Authors: {issuesoFile_authors} | Created at: {issuesoFile_created}\n")


issuescFile = open("closedIssues.txt", "w", encoding="utf-8")
for issues in issuesc["items"]:
    issuescFile_titles = issues["title"]
    issuescFile_authors = issues["author"]["login"] if issues["author"] else "Unknown"
    issuescFile_created = issues["createdAt"]
    issuescFile_closed = issues["closedAt"]

    issuescFile.write(f"Title: {issuescFile_titles} | Authors: {issuescFile_authors} | Created at: {issuescFile_created} | Closed at: {issuescFile_closed}\n")


prsoFile.close()
prscFile.close()
issuesoFile.close()
issuescFile.close()


# Print result stuff..
print()
print("PULL REQUESTS:", prso["total_count"], "open,", prsc["total_count"], "closed. TOTAL:", prso["total_count"] + prsc["total_count"])
print("ISSUES:", issueso["total_count"], "open,", issuesc["total_count"], "closed. TOTAL:", issueso["total_count"] + issuesc["total_count"])
