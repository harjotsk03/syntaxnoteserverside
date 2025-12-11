# supabase_client.py
import os
from uuid import UUID
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def convert_uuids_to_strings(obj):
    """Recursively convert UUIDs to strings in nested structures"""
    if isinstance(obj, UUID):
        return str(obj)
    elif isinstance(obj, dict):
        return {k: convert_uuids_to_strings(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_uuids_to_strings(i) for i in obj]
    else:
        return obj


def insert_repo(owner, repo, branch="main", user_id=None):
    # insert returns a SyncQueryRequestBuilder; you call .execute() to get the result
    res = supabase.table("repos").insert({
        "owner": owner,
        "repo": repo,
        "branch": branch,
        "user_id": user_id
    }).execute()  # no .select()

    # Check for errors
    if hasattr(res, 'error') and res.error:
        raise Exception(res.error.message)

    # convert UUID to string before returning
    repo_id = res.data[0]["id"]
    if isinstance(repo_id, UUID):
        repo_id = str(repo_id)

    return repo_id


def insert_chunks(rows):
    """Insert multiple chunk rows into Supabase."""
    rows = convert_uuids_to_strings(rows)
    res = supabase.table("repo_chunks").insert(rows).execute()

    # Debug
    print("res.data:", res.data)
    print("res.error:", getattr(res, "error", None))

    if getattr(res, "error", None):
        raise Exception(res.error.message)

    res.data = convert_uuids_to_strings(res.data)
    return res
