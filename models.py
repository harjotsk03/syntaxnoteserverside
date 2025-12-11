# models.py
from pydantic import BaseModel, Field, constr
from typing import List, Optional
from uuid import UUID

class RegisterRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class IngestRequest(BaseModel):
    owner: str
    repo: str
    branch: Optional[str] = "main"
    user_id: Optional[str] = None

class FileChunk(BaseModel):
    repo_id: UUID
    file_path: str
    chunk_index: int
    content: str
    embedding: List[float]

class QueryRequest(BaseModel):
    repo_id: UUID
    question: str
    top_k: int = Field(default=5, ge=1, le=25)
