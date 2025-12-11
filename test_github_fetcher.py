# test_github_fetcher.py
from github_fetcher import list_files, fetch_raw

OWNER = "harjotsk03"
REPO = "anchorfunds"

def test_list_files():
    print("→ Fetching file list...")
    files = list_files(OWNER, REPO)
    print(f"Found {len(files)} files.")
    print("Sample:", files[:10])

def test_fetch_raw():
    print("\n→ Fetching README content...")
    content = fetch_raw(OWNER, REPO, "README.md")  # <-- FIXED
    print("README content sample:\n", content[:300])

if __name__ == "__main__":
    test_list_files()
    print("\n--------------------\n")
    test_fetch_raw()
