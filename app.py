import os
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional
from cachetools import TTLCache
from models import IngestRequest, QueryRequest, RegisterRequest, LoginRequest, TokenResponse
from ingest import ingest_repo
from query_engine import answer_question
from auth import hash_password, verify_password, create_access_token, decode_access_token
from neo4j_client import create_user, get_user_by_email, list_users, get_user_repos, get_user_by_email_or_id, get_repo_metadata
from github_fetcher import fetch_repo_metadata, get_repo_stats

app = FastAPI()
security = HTTPBearer()

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory cache: 5 min TTL, max 100 items
repo_cache = TTLCache(maxsize=100, ttl=300)

class IngestResponse(BaseModel):
    repo_id: str = Field(..., description="The inserted repo ID")

class RepoInfo(BaseModel):
    id: str
    owner: str
    repo: str
    branch: str
    created_at: Optional[str] = None

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: missing user_id")
        return user_id
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

@app.post("/ingest", response_model=IngestResponse)
def api_ingest(req: IngestRequest):
    try:
        repo_id = ingest_repo(req.owner, req.repo, req.branch, req.user_id)
        return IngestResponse(repo_id=str(repo_id))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/query")
def api_query(req: QueryRequest):
    try:
        answer = answer_question(str(req.repo_id), req.question, req.top_k)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest):
    existing = get_user_by_email(req.email)
    if existing:
        raise HTTPException(400, "Email already registered")
    hashed_pw = hash_password(req.password)
    user_id = create_user(req.email, hashed_pw)
    token = create_access_token({"sub": user_id})
    return TokenResponse(access_token=token)

@app.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    user = get_user_by_email(req.email)
    if not user or not verify_password(req.password, user["password"]):
        raise HTTPException(401, "Invalid email or password")
    token = create_access_token({"sub": user["user_id"]})
    return TokenResponse(access_token=token)

@app.get("/users")
def get_users():
    users = list_users()
    return {"users": users}

@app.get("/debug/list-files")
def debug_list_files(owner: str, repo: str, branch: str = "main"):
    from github_fetcher import list_files
    try:
        files = list_files(owner, repo, branch)
        return {"total_files": len(files), "files": files}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/my-repos")
def get_my_repos(current_user_id: str = Depends(get_current_user)):
    try:
        repos = get_user_repos(current_user_id)
        return {
            "user_id": current_user_id,
            "total_repos": len(repos),
            "repos": repos
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/me")
def get_current_user_info(current_user_id: str = Depends(get_current_user)):
    user = get_user_by_email_or_id(current_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "user_id": user["user_id"],
        "email": user["email"]
    }

@app.get("/repo-metadata/{repo_id}")
def api_repo_metadata(
    repo_id: str,
    current_user: str = Depends(get_current_user)
):
    # Check cache
    if repo_id in repo_cache:
        print(f"Cache HIT for {repo_id}")
        return repo_cache[repo_id]
    
    print(f"Cache MISS for {repo_id}")
    
    # Fetch from database
    repoNode = get_repo_metadata(repo_id)
    if not repoNode:
        raise HTTPException(404, "Repo not found")

    owner = repoNode["owner"]
    repo = repoNode["repo_name"]

    repoStats = get_repo_stats(owner, repo)
    repoMetadata = fetch_repo_metadata(owner, repo)

    result = {
        "repoNode": repoNode,
        "repoStats": repoStats,
        "repoMetadata": repoMetadata
    }
    
    # Store in cache
    repo_cache[repo_id] = result
    
    return result