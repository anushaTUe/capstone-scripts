import requests

TOKEN = "ADD YOUR GITHUB TOKEN"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json"
}


def github_search(query):
    url = "https://api.github.com/search/issues"

    params = {
        "q": query,
        "per_page": 100
    }

    response = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=30
    )

    print("Status:", response.status_code)

    response.raise_for_status()

    return response.json()


# Number of pull requests open and closed
prso = github_search(
    "repo:excalidraw/excalidraw is:pr is:open created:2026-01-01..2026-09-25"
)
prsc = github_search(
    "repo:excalidraw/excalidraw is:pr is:closed created:2026-01-01..2026-09-25"
)

# Number of issues open and closed 
issueso = github_search(
    "repo:excalidraw/excalidraw is:issue is:open created:2026-01-01..2026-09-25"
)
issuesc = github_search(
    "repo:excalidraw/excalidraw is:issue is:closed created:2026-01-01..2026-09-25"
)

# Print result stuff..
print()
print("COMMITS:", 210)
print("PULL REQUESTS:", prso["total_count"], "open,", prsc["total_count"], "closed. TOTAL:", prso["total_count"] + prsc["total_count"],)
print("ISSUES:", issueso["total_count"], "open,", issuesc["total_count"], "closed. TOTAL:", issueso["total_count"] + issuesc["total_count"])
