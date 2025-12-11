# github_fetcher.py
import requests
import os
from dotenv import load_dotenv

load_dotenv()

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
