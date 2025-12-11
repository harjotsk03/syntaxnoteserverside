# app.py
import os
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional
from models import IngestRequest, QueryRequest, RegisterRequest, LoginRequest, TokenResponse
from ingest import ingest_repo
from query_engine import answer_question
from auth import hash_password, verify_password, create_access_token, decode_access_token
from neo4j_client import create_user, get_user_by_email, list_users, get_user_repos, get_user_by_email_or_id

app = FastAPI()
security = HTTPBearer()

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # allow your frontend
    allow_credentials=True,
    allow_methods=["*"],  # allow POST, GET, OPTIONS, etc.
    allow_headers=["*"],  # allow headers like Authorization
)

# Response model ensures repo_id is a string
class IngestResponse(BaseModel):
    repo_id: str = Field(..., description="The inserted repo ID")

class RepoInfo(BaseModel):
    id: str
    owner: str
    repo: str
    branch: str
    created_at: Optional[str] = None

# Dependency to extract user_id from JWT
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Extract and validate JWT token, return user_id
    """
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
        return {
            "total_files": len(files),
            "files": files
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# NEW ROUTE: Get current user's repositories
@app.get("/my-repos")
def get_my_repos(current_user_id: str = Depends(get_current_user)):
    """
    Get all repositories owned by the authenticated user
    Requires: Bearer token in Authorization header
    """
    try:
        repos = get_user_repos(current_user_id)
        return {
            "user_id": current_user_id,
            "total_repos": len(repos),
            "repos": repos
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# BONUS: Get current user info
@app.get("/me")
def get_current_user_info(current_user_id: str = Depends(get_current_user)):
    """
    Get current authenticated user's information
    Requires: Bearer token in Authorization header
    """
    user = get_user_by_email_or_id(current_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "user_id": user["user_id"],
        "email": user["email"]
    }