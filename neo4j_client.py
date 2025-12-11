# neo4j_client.py
import os
from uuid import uuid4
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USER")
PASS = os.getenv("NEO4J_PASS")

driver = GraphDatabase.driver(URI, auth=(USER, PASS))

def create_user(email: str, hashed_pw: str) -> str:
    user_id = str(uuid4())
    with driver.session() as session:
        session.run("""
            MERGE (u:User {email: $email})
            SET u.password = $password, u.user_id = $user_id
        """, email=email, password=hashed_pw, user_id=user_id)
    return user_id

def get_user_by_email(email: str):
    with driver.session() as session:
        result = session.run("""
            MATCH (u:User {email: $email})
            RETURN u.user_id AS id, u.password AS password
        """, email=email)
        record = result.single()
        if record:
            return {"user_id": record["id"], "password": record["password"]}
        return None

def create_file_node(repo_id: str, file_path: str):
    with driver.session() as session:
        session.run("""
            MATCH (r:Repo {id: $repo_id})
            MERGE (f:File {repo_id: $repo_id, path: $path})
            MERGE (r)-[:HAS_FILE]->(f)
        """, repo_id=repo_id, path=file_path)


def create_dep_relation(repo_id: str, src_path: str, dst_path: str):
    with driver.session() as session:
        session.run("""
            MERGE (a:File {repo_id:$repo_id, path:$src})
            MERGE (b:File {repo_id:$repo_id, path:$dst})
            MERGE (a)-[:DEPENDS_ON]->(b)
        """, repo_id=repo_id, src=src_path, dst=dst_path)



def get_neighbors(repo_id: str, path: str, depth: int = 1):
    with driver.session() as session:
        result = session.run("""
            MATCH (f:File {repo_id:$repo_id, path:$path})-[:DEPENDS_ON*1..$depth]-(n)
            RETURN DISTINCT n.path AS path
        """, repo_id=repo_id, path=path, depth=depth)
        return [r["path"] for r in result]

def run_query(query: str, params: dict = None):
    with driver.session() as session:
        return list(session.run(query, params or {}))
    
def list_users():
    with driver.session() as session:
        result = session.run("MATCH (u:User) RETURN u.user_id AS id, u.email AS email")
        return [{"user_id": r["id"], "email": r["email"]} for r in result]


def insert_repo(owner, repo, branch="main", user_id=None):
    """Insert a repo node into Neo4j and link to the owning user."""
    repo_id = str(uuid4())
    query = """
        MATCH (u:User {user_id: $user_id})
        CREATE (r:Repo {
            id: $id,
            owner: $owner,
            repo: $repo,
            branch: $branch,
            user_id: $user_id
        })
        CREATE (u)-[:OWNS]->(r)
        RETURN r.id AS id
    """
    with driver.session() as session:
        result = session.run(query, id=repo_id, owner=owner, repo=repo, branch=branch, user_id=user_id)
        return result.single()["id"]



def insert_chunks(repo_id: str, rows):
    with driver.session() as session:
        for row in rows:
            session.run("""
                MATCH (r:Repo {id: $repo_id})
                MATCH (f:File {repo_id: $repo_id, path: $file_path})
                CREATE (c:Chunk {
                    id: randomUUID(),
                    chunk_index: $chunk_index,
                    content: $content,
                    embedding: $embedding
                })
                CREATE (r)-[:HAS_CHUNK]->(c)
                CREATE (f)-[:HAS_CHUNK]->(c)
            """, 
            repo_id=repo_id,
            file_path=row["file_path"],
            chunk_index=row["chunk_index"],
            content=row["content"],
            embedding=list(row["embedding"]))
            
def get_user_repos(user_id: str):
    """
    Get all repositories owned by a specific user using user_id property on Repo nodes
    """
    with driver.session() as session:
        result = session.run("""
            MATCH (r:Repo)
            WHERE r.user_id = $user_id
            RETURN r.id AS id, r.owner AS owner, r.repo AS repo, r.branch AS branch
            ORDER BY r.id DESC
        """, user_id=user_id)

        repos = []
        for record in result:
            repos.append({
                "id": record["id"],
                "owner": record["owner"],
                "repo": record["repo"],
                "branch": record["branch"]
            })

        return repos


def get_user_by_email_or_id(identifier: str):
    """
    Get user by either email or user_id
    """
    with driver.session() as session:
        result = session.run("""
            MATCH (u:User)
            WHERE u.email = $identifier OR u.user_id = $identifier
            RETURN u.user_id AS user_id, u.email AS email, u.password AS password
        """, identifier=identifier)
        
        record = result.single()
        if record:
            return {
                "user_id": record["user_id"],
                "email": record["email"],
                "password": record["password"]
            }
        return None