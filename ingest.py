# ingest.py
from github_fetcher import list_files, fetch_raw
from chunker import chunk_text_by_tokens
from embedder import embed_texts
from neo4j_client import (
    driver,
    create_file_node,
    create_dep_relation,
)
from uuid import uuid4
import re
from typing import List, Dict

# Regex for simple Python and JS imports
PY_IMPORT_RE = re.compile(r'^\s*(?:from\s+([\w\.]+)\s+import|import\s+([\w\.]+))', re.MULTILINE)
JS_IMPORT_RE = re.compile(
    r"""^\s*(?:import\s+(?:[\w\{\}\*\s,]+)\s+from\s+['"](.+)['"]|const\s+\w+\s*=\s*require\(['"](.+)['"]\))""",
    re.MULTILINE
)


def detect_imports(file_path: str, text: str) -> List[str]:
    imports = set()
    if file_path.endswith(".py"):
        for m in PY_IMPORT_RE.finditer(text):
            module = m.group(1) or m.group(2)
            if module:
                imports.add(module)
    else:
        for m in JS_IMPORT_RE.finditer(text):
            module = m.group(1) or m.group(2)
            if module:
                imports.add(module)
    return list(imports)


def insert_repo(owner: str, repo: str, branch: str = "main", user_id: str = None) -> str:
    repo_id = str(uuid4())
    with driver.session() as session:
        session.run(
            """
            CREATE (r:Repo {id: $id, owner: $owner, repo: $repo, branch: $branch, user_id: $user_id})
            """,
            id=repo_id, owner=owner, repo=repo, branch=branch, user_id=user_id
        )
    return repo_id


def insert_chunks(repo_id: str, rows):
    with driver.session() as session:
        for row in rows:
            session.run("""
                MATCH (r:Repo {id: $repo_id})
                CREATE (c:Chunk {
                    file_path: $file_path,
                    chunk_index: $chunk_index,
                    content: $content,
                    embedding: $embedding
                })
                CREATE (r)-[:HAS_CHUNK]->(c)
            """,
            repo_id=repo_id,
            file_path=row["file_path"],
            chunk_index=row["chunk_index"],
            content=row["content"],
            embedding=list(row["embedding"])  # store as list
            )


def resolve_import_to_file(current_file: str, import_str: str, all_files: list) -> str:
    """
    Try to resolve an import string to an actual file path in the repo.
    """
    # Handle relative imports (Python)
    if import_str.startswith("."):
        current_dir = "/".join(current_file.split("/")[:-1])
        relative_parts = import_str.replace(".", "/")
        potential_path = f"{current_dir}/{relative_parts}.py"
        if potential_path in all_files:
            return potential_path
    
    # Handle relative imports (JS/TS)
    if import_str.startswith("./") or import_str.startswith("../"):
        current_dir = "/".join(current_file.split("/")[:-1])
        
        # Normalize the path
        if import_str.startswith("./"):
            potential_base = f"{current_dir}/{import_str[2:]}"
        else:
            # Handle ../
            parts = current_dir.split("/")
            up_count = import_str.count("../")
            remaining = import_str.replace("../", "", up_count)
            base_dir = "/".join(parts[:-up_count]) if up_count < len(parts) else ""
            potential_base = f"{base_dir}/{remaining}" if base_dir else remaining
        
        # Try different extensions
        for ext in [".js", ".ts", ".jsx", ".tsx", ".py"]:
            potential_path = potential_base + ext
            if potential_path in all_files:
                return potential_path
            
            # Also try with /index
            potential_index = f"{potential_base}/index{ext}"
            if potential_index in all_files:
                return potential_index
    
    # Handle Python module imports (convert module path to file path)
    if not ("/" in import_str or import_str.startswith(".")):
        # Try to find a matching file
        potential_path = import_str.replace(".", "/") + ".py"
        if potential_path in all_files:
            return potential_path
    
    return None


# At the top of ingest.py
SUPPORTED_EXTENSIONS = [
    # Code
    ".py", ".js", ".ts", ".jsx", ".tsx", 
    # Web
    ".html", ".css", ".scss", ".sass", ".less",
    # Config
    ".json", ".yaml", ".yml", ".toml", ".ini",
    # Docs
    ".md", ".rst", ".txt",
    # Other
    ".sql", ".sh", ".bash"
]

BINARY_EXTENSIONS = [
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".pdf", ".zip", ".tar", ".gz",
    ".woff", ".woff2", ".ttf", ".eot"
]

def should_process_file(path: str) -> bool:
    """Determine if a file should be ingested"""
    # Skip binary files
    if any(path.endswith(ext) for ext in BINARY_EXTENSIONS):
        return False
    
    # Skip common directories to ignore
    ignore_patterns = [
        "node_modules/", ".git/", "dist/", "build/", 
        "__pycache__/", ".venv/", "venv/", ".next/",
        "coverage/", ".cache/"
    ]
    if any(pattern in path for pattern in ignore_patterns):
        return False
    
    # Process if extension is supported
    return any(path.endswith(ext) for ext in SUPPORTED_EXTENSIONS)


def ingest_repo(owner: str, repo: str, branch: str = "main", user_id: str = None) -> str:
    repo_id = insert_repo(owner, repo, branch, user_id)
    files = list_files(owner, repo, branch)
    
    print(f"Found {len(files)} total files in repo")

    # First pass: create all file nodes
    code_files = []
    for path in files:
        if not should_process_file(path):
            continue
        code_files.append(path)
        create_file_node(repo_id, path)
    
    print(f"Processing {len(code_files)} code files")

    # Second pass: process content and create dependencies
    for i, path in enumerate(code_files):
        print(f"Processing {i+1}/{len(code_files)}: {path}")
        
        try:
            text = fetch_raw(owner, repo, path, branch)
        except Exception as e:
            print(f"❌ Fetch error {path}: {e}")
            continue

        # Create chunks
        chunks = chunk_text_by_tokens(text, max_tokens=400, overlap=50)
        if not chunks:
            print(f"⚠️  No chunks created for {path}")
            continue

        print(f"✓ Created {len(chunks)} chunks for {path}")

        embeddings = embed_texts(chunks)
        rows = [
            {"file_path": path, "chunk_index": i, "content": chunk, "embedding": emb}
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
        ]
        insert_chunks(repo_id, rows)

        # Detect imports & create dependency relations
        imports = detect_imports(path, text)
        if imports:
            print(f"  Found {len(imports)} imports: {imports[:3]}...")
            for module in imports:
                resolved_path = resolve_import_to_file(path, module, code_files)
                if resolved_path:
                    create_dep_relation(repo_id, path, resolved_path)
                    print(f"  ✓ Created dependency: {path} -> {resolved_path}")

    print(f"✅ Ingestion complete for {repo_id}")
    return repo_id