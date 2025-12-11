# github_fetcher.py
import requests
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

load_dotenv()

def iso(dt):
    return dt.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def get_week_ranges():
    now = datetime.now(timezone.utc)

    # Start of this week (Monday)
    start_of_week = now - timedelta(days=now.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)

    # Start of last week
    start_of_last_week = start_of_week - timedelta(days=7)

    return {
        "this_week_since": iso(start_of_week),
        "this_week_until": iso(now),
        "last_week_since": iso(start_of_last_week),
        "last_week_until": iso(start_of_week)
    }

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

def list_files(owner: str, repo: str, branch: str = "main"):
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    tree = r.json().get("tree", [])
    return [item["path"] for item in tree if item["type"] == "blob"]

def fetch_raw(owner: str, repo: str, path: str, branch: str = "main"):
    raw = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    r = requests.get(raw, headers=headers)
    r.raise_for_status()
    return r.text

def compute_loc(owner, repo, branch="main"):
    files = list_files(owner, repo, branch)
    total = 0

    for path in files:
        try:
            text = fetch_raw(owner, repo, path, branch)
            total += len(text.splitlines())
        except:
            pass

    return total


def fetch_repo_metadata(owner: str, repo_name: str):
    url = f"https://api.github.com/repos/{owner}/{repo_name}"
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    r = requests.get(url, headers=headers)
    r.raise_for_status()

    return r.json()

def fetch_contributors(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/contributors?per_page=100"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return len(r.json())


def fetch_weekly_loc_changes(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/stats/code_frequency"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    r = requests.get(url, headers=headers)
    r.raise_for_status()
    data = r.json()

    if not data:
        return None

    last = data[-1]          # This week
    prev = data[-2] if len(data) > 1 else [0,0,0]

    this_add, this_del = last[1], abs(last[2])
    prev_add, prev_del = prev[1], abs(prev[2])

    def pct_change(now, before):
        if before == 0:
            return None
        return round((now - before) / before * 100, 2)

    return {
        "this_week": {
            "additions": this_add,
            "deletions": this_del
        },
        "last_week": {
            "additions": prev_add,
            "deletions": prev_del
        },
        "pct_change_additions": pct_change(this_add, prev_add),
        "pct_change_deletions": pct_change(this_del, prev_del)
    }

def fetch_commits(owner, repo, since, until):
    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    params = {"since": since, "until": until, "per_page": 100}

    r = requests.get(url, headers=headers, params=params)
    r.raise_for_status()

    return r.json()

def fetch_commits_this_and_last_week(owner, repo):
    ranges = get_week_ranges()

    commits_this_week = fetch_commits(
        owner, repo,
        since=ranges["this_week_since"],
        until=ranges["this_week_until"]
    )

    commits_last_week = fetch_commits(
        owner, repo,
        since=ranges["last_week_since"],
        until=ranges["last_week_until"]
    )

    return {
        "this_week_count": len(commits_this_week),
        "last_week_count": len(commits_last_week),
        "this_week_commits": commits_this_week,
        "last_week_commits": commits_last_week
    }


def get_repo_stats(owner, repo, branch="main"):
    stats = {}

    stats["total_loc"] = compute_loc(owner, repo, branch)
    stats["contributors"] = fetch_contributors(owner, repo)
    stats["commits_this_week"] = fetch_commits_this_and_last_week(owner, repo)
    stats["weekly_loc_changes"] = fetch_weekly_loc_changes(owner, repo)

    return stats
