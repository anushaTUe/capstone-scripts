import requests

TOKEN = "ADD YOUT OWN GITHUB TOKEN"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json"
}


def github_search(query):
    url = "https://api.github.com/search/issues"
    all_items = []
    page = 1

    while page <= 10:
        params = {
            "q": query,
            "per_page": 100,
            "page": page
        }

    

    response = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=30
    )

    response.raise_for_status()
    data = response.json()
    all_items.extend(data["items"])
    page += 1
    data["items"] = all_items

    return data


# Number of pull requests open and closed
prso = github_search(
    "repo:excalidraw/excalidraw is:pr is:open"
)

prsc = github_search(
    "repo:excalidraw/excalidraw is:pr is:closed"
)

# Number of issues open and closed 
issueso = github_search(
    "repo:excalidraw/excalidraw is:issue is:open"
)

issuesc = github_search(
    "repo:excalidraw/excalidraw is:issue is:closed"
)


# Create files and fetch data from PRs & Issues
prsoFile = open("openPRs.txt", "w")
for pr in prso["items"]:
    prsoFile_titles = pr["title"]
    prsoFile_authors = pr["user"]["login"]
    prsoFile_created = pr["created_at"]
    
    # request additions and deletions
    prso_url = pr["pull_request"]["url"]
    prso_details = requests.get(prso_url, headers=headers).json()
    
    prsoFile_additions = prso_details["additions"]
    prsoFile_deletions = prso_details["deletions"]
    prsoFile_filesChanged = prso_details["changed_files"]

    prsoFile.write(f"Title: {prsoFile_titles} | Authors: {prsoFile_authors} | Created at: {prsoFile_created} | Additions: {prsoFile_additions} | Deletions: {prsoFile_deletions} | Files Changed: {prsoFile_filesChanged}\n")


prscFile = open("closedPRs.txt", "w")
for pr in prsc["items"]:
    prscFile_titles = pr["title"]
    prscFile_authors = pr["user"]["login"]
    prscFile_created = pr["created_at"]
    prscFile_closed = pr["closed_at"]
    
    # request additions and deletions
    prsc_url = pr["pull_request"]["url"]
    prsc_details = requests.get(prsc_url, headers=headers).json()
    
    prscFile_additions = prsc_details["additions"]
    prscFile_deletions = prsc_details["deletions"]
    prscFile_filesChanged = prsc_details["changed_files"]
    prscFile.write(f"Title: {prscFile_titles} | Authors: {prscFile_authors} | Created at: {prscFile_created} | Closed at: {prscFile_closed} | Additions: {prscFile_additions} | Deletions: {prscFile_deletions} | Files Changed: {prscFile_filesChanged}\n")


issuesoFile = open("openIssues.txt", "w")
for issues in issueso["items"]:
    issuesoFile_titles = issues["title"]
    issuesoFile_authors = issues["user"]["login"]
    issuesoFile_created = issues["created_at"]
    issuesoFile.write(f"Title: {issuesoFile_titles} | Authors: {issuesoFile_authors} | Created at: {issuesoFile_created}\n")


issuescFile = open("closedIssues.txt", "w")
for issues in issuesc["items"]:
    issuescFile_titles = issues["title"]
    issuescFile_authors = issues["user"]["login"]
    issuescFile_created = issues["created_at"]
    issuescFile_closed = issues["closed_at"]
    issuescFile.write(f"Title: {issuescFile_titles} | Authors: {issuescFile_authors} | Created at: {issuescFile_created} | Closed at: {issuescFile_closed}\n")




# Print result stuff..
print()
print("COMMITS:", 210)
print("PULL REQUESTS:", prso["total_count"], "open,", prsc["total_count"], "closed. TOTAL:", prso["total_count"] + prsc["total_count"],)
print("ISSUES:", issueso["total_count"], "open,", issuesc["total_count"], "closed. TOTAL:", issueso["total_count"] + issuesc["total_count"])
