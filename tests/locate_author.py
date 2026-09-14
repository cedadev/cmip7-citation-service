
import requests

def get_first_commit_author(owner, repo, filepath, branch="main", token=None):
    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    params = {
        "path": filepath,
        "sha": branch,
        "per_page": 1,
        "page": 1
    }

    # First request: get pagination info
    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()

    # Extract "last" page number from Link header
    link_header = resp.headers.get("Link", "")
    last_page = 1

    if 'rel="last"' in link_header:
        parts = link_header.split(",")
        for part in parts:
            if 'rel="last"' in part:
                # extract page=NN
                last_page = int(part.split("page=")[-1].split(">")[0])
                break

    # Fetch the last page (oldest commit)
    params["page"] = last_page
    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()

    commits = resp.json()
    if not commits:
        return None

    commit = commits[0]

    # Prefer GitHub username if available
    author = commit.get("author")
    if author:
        return author["login"]

    # Fallback: raw commit metadata (if user not linked)
    return commit["commit"]["author"]["name"]


def get_user_profile(username, token=None):
    url = f"https://api.github.com/users/{username}"

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    resp = requests.get(url, headers=headers)
    resp.raise_for_status()

    data = resp.json()

    profile = {}
    name = data.get("name")
    if name:
        profile['first_name'] = name.split(' ')[0]
        profile['last_name'] = name.split(' ')[-1]
        if len(name.split(' ')) > 2:
            profile['middle_names'] = name.split(' ')[1:-1]
        if data.get('email'):
            profile['email'] = data.get('email')

    return profile

source_id = 'CanESM5-1'

# Example usage
owner = "WCRP-CMIP"
repo = "Essential-Model-Documentation"
filepath = f"model/{source_id}.json"

username = get_first_commit_author(owner, repo, filepath, branch='src-data')
profile = get_user_profile(username)
print('Citation Profile: ',profile)
